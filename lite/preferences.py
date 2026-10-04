"""Versioned per-user preferences; no account credentials or game writes."""
import json,os,tempfile
from pathlib import Path

def path():
    base=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming'))) if os.name=='nt' else Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    return base/'gamebridge-lite'/'preferences.json'

def validate(value):
    if not isinstance(value,dict) or value.get('schema')!=1:raise ValueError('Unsupported GameBridge preferences version')
    for key in ('root','player_name','source','steam_id'):
        item=value.get(key)
        if item is not None and (not isinstance(item,str) or len(item)>4096 or '\0' in item):raise ValueError('Invalid preferences field: '+key)
    name=value.get('player_name')
    if name and (len(name)>128 or any(ord(c)<32 or ord(c)==127 for c in name)):raise ValueError('Invalid saved player name')
    return {key:value.get(key) for key in ('schema','root','player_name','source','steam_id')}

def load():
    p=path()
    if not p.exists():return {}
    if p.is_symlink() or p.stat().st_size>32768:raise ValueError('Invalid preferences file')
    return validate(json.loads(p.read_text(encoding='utf-8')))

def save(value):
    data=json.dumps(validate(value),ensure_ascii=False,indent=2).encode();p=path();p.parent.mkdir(parents=True,exist_ok=True)
    if p.is_symlink():raise ValueError('Linked preferences file refused')
    fd,tmp=tempfile.mkstemp(prefix='.preferences-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as stream:os.chmod(tmp,0o600);stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
