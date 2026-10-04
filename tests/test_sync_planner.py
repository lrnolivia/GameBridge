import sys,unittest,tempfile,os
from pathlib import Path
from dataclasses import replace
from hashlib import sha256
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gamebridge.sync import *

def file(path,value):return File(path,sha256(value.encode()).hexdigest(),len(value))
class SyncPlannerTests(unittest.TestCase):
    def setUp(self):
        self.left=Identity('game-1','steam','account-1','windows','test-format','windows-endpoint')
        self.right=replace(self.left,runtime='proton',endpoint='proton-endpoint')
        self.old=file('slot.sav','old');self.new=file('slot.sav','new')
        self.base=Baseline(self.left,self.right,(self.old,),'generation-1')
    def snapshots(self,l=None,r=None):return Snapshot(self.left,'present',True,tuple(l if l is not None else [self.old])),Snapshot(self.right,'present',True,tuple(r if r is not None else [self.old]))
    def plan(self,l=None,r=None,base=True):
        left,right=self.snapshots(l,r);return plan(left,right,self.base if base else None,compatibility_reference='synthetic-fixture-only')
    def test_unchanged_and_identical_convergence(self):
        self.assertEqual(self.plan().state,'unchanged');self.assertEqual(self.plan([self.new],[self.new]).state,'unchanged')
    def test_one_sided_changes_have_explicit_direction_and_preimage(self):
        p=self.plan([self.new]);self.assertEqual(p.actions,(Action('export','slot.sav',self.new.sha256,self.old.sha256),))
        self.assertEqual(self.plan(r=[self.new]).actions[0].direction,'import')
    def test_additions_can_flow_but_deletions_never_do(self):
        added=file('new-slot.sav','new');self.assertEqual(self.plan([self.old,added]).actions[0].destination_sha256,None)
        self.assertEqual(self.plan([]).state,'conflict');self.assertEqual(self.plan([],[]).state,'conflict')
    def test_conflict_does_not_expose_partial_apply(self):
        p=self.plan([file('slot.sav','mine'),file('new.sav','addition')],[file('slot.sav','theirs')]);self.assertEqual(p.state,'conflict');self.assertEqual(p.actions,())
    def test_first_run_is_never_an_automatic_winner(self):
        self.assertEqual(self.plan(base=False).state,'baseline-required');self.assertEqual(self.plan([self.new],base=False).state,'first-run-choice-required');self.assertEqual(self.plan([],base=False).state,'first-run-choice-required')
    def test_missing_and_uninitialized_are_protected(self):
        left,right=self.snapshots()
        for state in ('missing','unavailable','present'):
            p=plan(replace(left,state=state,initialized=False),right,self.base,compatibility_reference='fixture');self.assertEqual(p.state,'protected')
    def test_identity_and_certificate_required(self):
        left,right=self.snapshots();self.assertEqual(plan(left,right,self.base).state,'protected')
        for field in ('game','distribution','account','representation'):
            p=plan(left,replace(right,identity=replace(right.identity,**{field:'different'})),self.base,compatibility_reference='fixture');self.assertEqual(p.state,'protected')
    def test_plan_stale_uses_content_and_baseline_not_timestamps(self):
        left,right=self.snapshots([self.new]);p=plan(left,right,self.base,compatibility_reference='fixture');p.validate_fresh(left,right,self.base)
        with self.assertRaisesRegex(ValueError,'PLAN_STALE'):p.validate_fresh(replace(left,files=(self.old,)),right,self.base)
        with self.assertRaisesRegex(ValueError,'PLAN_STALE'):p.validate_fresh(left,right,replace(self.base,generation='generation-2'))
        self.assertEqual(p.id,plan(left,right,self.base,compatibility_reference='fixture').id)
    def test_snapshot_is_read_only_and_missing_is_distinct_from_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.assertEqual(snapshot(root/'missing',self.left).state,'missing');self.assertFalse(snapshot(root,self.left).initialized)
            (root/'slot.sav').write_bytes(b'save');before=(root/'slot.sav').stat().st_mtime_ns
            snap=snapshot(root,self.left,initialized=True);self.assertEqual(snap.files[0].sha256,sha256(b'save').hexdigest());self.assertEqual((root/'slot.sav').stat().st_mtime_ns,before)
            self.assertEqual(snapshot(root,self.left,max_bytes=1).state,'unavailable')
    def test_portable_names_and_duplicate_paths_are_protected(self):
        for path in ('../save','/save','a\\b','NUL.sav','save:stream','a/../b','a//b','trail.'):self.assertFalse(safe_relative(path),path)
        p=self.plan([file('Slot.sav','x'),file('slot.sav','y')]);self.assertEqual(p.state,'protected')
    def test_links_are_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);outside=root/'outside';outside.write_text('do not read');endpoint=root/'endpoint';endpoint.mkdir();(endpoint/'link').symlink_to(outside)
            self.assertEqual(snapshot(endpoint,self.left,initialized=True).state,'unavailable')

    def test_ancestor_link_is_rejected_before_any_save_file_open(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);real=root/'real';endpoint=real/'saves'
            endpoint.mkdir(parents=True);(endpoint/'slot.sav').write_text('outside alias')
            alias=root/'alias'
            try:alias.symlink_to(real,target_is_directory=True)
            except OSError as error:self.skipTest('Directory symlink unavailable: '+str(error))
            original_open=os.open
            with patch('gamebridge.sync.os.open',wraps=original_open) as opened:
                result=snapshot(alias/'saves',self.left,initialized=True)
                self.assertEqual(result.state,'unavailable')
                self.assertFalse(opened.called,'Aliased endpoint must be rejected before reading save bytes')

    def test_directory_changed_to_link_during_walk_is_protected(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'endpoint';root.mkdir();nested=root/'nested';nested.mkdir()
            outside=base/'outside';outside.mkdir();(outside/'slot.sav').write_text('outside save')
            probe=base/'probe'
            try:probe.symlink_to(outside,target_is_directory=True);probe.unlink()
            except OSError as error:self.skipTest('Directory symlink unavailable: '+str(error))
            def changed_walk(*args,**kwargs):
                yield str(root),['nested'],[]
                nested.rmdir();nested.symlink_to(outside,target_is_directory=True)
                yield str(nested),[],['slot.sav']
            original_open=os.open
            with patch('gamebridge.sync.os.walk',side_effect=changed_walk),patch('gamebridge.sync.os.open',wraps=original_open) as opened:
                result=snapshot(root,self.left,initialized=True)
                self.assertEqual(result.state,'unavailable')
                self.assertFalse(opened.called,'Changed directory must be rejected before following it')

if __name__=='__main__':unittest.main()
