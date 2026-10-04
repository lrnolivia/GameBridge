import sys,json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lite'))
import gamebridge_core as core
import preferences

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'games';self.root.mkdir();self.file=self.root/'game'/'config.ini';self.file.parent.mkdir()
        self.signature=patch.object(core,'is_supported_source_value',lambda value:value=='old');self.signature.start();self.addCleanup(self.signature.stop)
    def change(self,text='UserName=old\nAccountID=123\n',name='Lauren'):
        self.file.write_bytes(text.encode());updated,reasons=core.normalize_text(self.file,text,name)
        return core.Change('game',self.file,text,updated,'utf-8',reasons)
    def test_json_escaping_and_protected_fields(self):
        text='{"UserName":"old","AccountID":"old","note":"UserName: old","nested":{"PlayerName":"old"}}'
        name='Lauren "Lola" \\ ✨';updated,reasons=core.normalize_text(Path('settings.json'),text,name);data=json.loads(updated)
        self.assertEqual(data['UserName'],name);self.assertEqual(data['nested']['PlayerName'],name);self.assertEqual(data['AccountID'],'old');self.assertEqual(data['note'],'UserName: old');self.assertEqual(len(reasons),2)
    def test_xml_escaping(self):
        import xml.etree.ElementTree as ET
        text='<root><UserName>old</UserName><AccountID>123</AccountID></root>'
        updated,_=core.normalize_text(Path('settings.xml'),text,'Lola & <Lauren>');self.assertEqual(ET.fromstring(updated).find('UserName').text,'Lola & <Lauren>');self.assertIn('<AccountID>123</AccountID>',updated)
    def test_unsupported_grammars_and_duplicate_json_protected(self):
        for path,text in [('settings.yaml','UserName: old'),('settings.toml','UserName="old"'),('settings.json','{"UserName":"old","UserName":"old"}')]:self.assertEqual(core.normalize_text(Path(path),text,'Lauren'),(text,[]))
    def test_control_characters_and_lossy_encoding_refused(self):
        for name in ['','Lola\nAccountID=4','x\0y']:
            with self.assertRaises(core.Stop):core.normalize_text(self.file,'UserName=old',name)
        with self.assertRaises(UnicodeEncodeError):core.encode_text('✨','cp1252')
    def test_stale_plan_changes_nothing(self):
        change=self.change();self.file.write_text('new external data')
        with self.assertRaisesRegex(core.Stop,'PLAN_STALE'):core.apply_changes(self.root,[change],'Lauren')
        self.assertEqual(self.file.read_text(),'new external data');self.assertFalse((self.root/'.gamebridge-name.lock').exists())
    def test_atomic_apply_has_verified_unique_backup_and_exact_result(self):
        change=self.change();backup=self.base/'backup'
        with patch.object(core,'default_backup_root',return_value=backup):result=core.apply_changes(self.root,[change],'Lauren')
        self.assertEqual(result[:2],(1,0));self.assertEqual(self.file.read_text(),change.updated_text);self.assertEqual((backup/'game/config.ini').read_text(),change.original_text)
        manifest=json.loads((backup/'manifest.json').read_text());self.assertEqual(manifest['state'],'complete');self.assertEqual(manifest['files'][0]['state'],'verified')
        self.assertNotEqual(core.default_backup_root(),core.default_backup_root())
    def test_mutated_plan_and_link_targets_refused(self):
        change=self.change();change.updated_text+='AccountID=999\n'
        with self.assertRaises(core.Stop):core.apply_changes(self.root,[change],'Lauren')
        change=self.change();other=self.base/'outside';other.write_text(change.original_text);self.file.unlink();self.file.symlink_to(other)
        with self.assertRaises(core.Stop):core.apply_changes(self.root,[change],'Lauren')
        self.assertEqual(other.read_text(),change.original_text)
    def test_exclusive_lock_and_duplicate_plan(self):
        change=self.change();(self.root/'.gamebridge-name.lock').write_text('other')
        with self.assertRaisesRegex(core.Stop,'owns this library'):core.apply_changes(self.root,[change],'Lauren')
        with self.assertRaisesRegex(core.Stop,'duplicate'):core.apply_changes(self.root,[change,change],'Lauren')
    def test_verified_restore_preserves_later_edits(self):
        change=self.change();backup=self.base/'backup'
        with patch.object(core,'default_backup_root',return_value=backup):core.apply_changes(self.root,[change],'Lauren')
        self.file.write_text('new external data')
        with self.assertRaisesRegex(core.Stop,'PLAN_STALE'):core.restore_changes(self.root,backup)
        self.assertEqual(self.file.read_text(),'new external data')
        self.file.write_text(change.updated_text);self.assertEqual(core.restore_changes(self.root,backup),1)
        self.assertEqual(self.file.read_text(),change.original_text);self.assertEqual(core.restore_changes(self.root,backup),0)
    def test_backup_corruption_refuses_restore(self):
        change=self.change();backup=self.base/'backup'
        with patch.object(core,'default_backup_root',return_value=backup):core.apply_changes(self.root,[change],'Lauren')
        (backup/'game/config.ini').write_text('damaged')
        with self.assertRaisesRegex(core.Stop,'checksum'):core.restore_changes(self.root,backup)
        self.assertEqual(self.file.read_text(),change.updated_text)
    def test_representable_encodings_round_trip_exactly(self):
        for kind in ['utf-8','utf-8-sig','utf-16-le-bom','utf-16-be-bom','cp1252']:
            with self.subTest(kind=kind):
                text='UserName=old\r\nAccountID=123\r\n';data=core.encode_text(text,kind);decoded,encoding=core.detect_text(data)
                self.assertEqual(core.encode_text(decoded,encoding),data)
                updated,_=core.normalize_text(self.file,decoded,'Lola');self.assertEqual(core.detect_text(core.encode_text(updated,encoding))[0],'UserName=Lola\r\nAccountID=123\r\n')
    def test_preferences_survive_new_session_and_preserve_manual_name(self):
        with patch.object(preferences,'path',return_value=self.base/'prefs/settings.json'),patch.object(core,'detect_steam_identities',return_value=[]):
            original=core.Session(self.root,'Lola ✨',None,'manual override');core.save_session(original);loaded=core.initial_session(None,None)
            self.assertEqual(loaded.player_name,'Lola ✨');self.assertEqual(loaded.root,self.root);self.assertEqual(loaded.player_name_source,'manual override')
            override=core.initial_session(None,'Different');self.assertEqual(override.player_name,'Different')
    def test_corrupt_preferences_are_preserved(self):
        p=self.base/'settings.json';p.write_text('{broken')
        with patch.object(preferences,'path',return_value=p),patch.object(core,'discover_libraries',return_value=[]),patch.object(core,'detect_steam_username',return_value=None):core.initial_session(None,None)
        self.assertEqual(p.read_text(),'{broken')

if __name__=='__main__':unittest.main()
