"""Read-only content snapshots and immutable three-way sync planning.

This module does not copy, delete, convert, certify compatibility or advance a
baseline. A future apply layer must independently prove quiescence, ownership,
backup durability and publication, then revalidate this plan immediately before
writing. A caller-provided compatibility reference is provenance, not a new
compatibility certificate produced by the planner.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path,PurePosixPath
from hashlib import sha256
import json,os,stat,unicodedata

MAX_FILES=4096
MAX_BYTES=256*1024*1024

def fingerprint(value):return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class Identity:
    game: str
    distribution: str
    account: str
    runtime: str
    representation: str
    endpoint: str

@dataclass(frozen=True)
class File:
    path: str
    sha256: str
    bytes: int

@dataclass(frozen=True)
class Snapshot:
    identity: Identity
    state: str
    initialized: bool
    files: tuple[File,...]=()
    reason: str=''
    @property
    def fingerprint(self):return fingerprint(asdict(self))

@dataclass(frozen=True)
class Baseline:
    local: Identity
    remote: Identity
    files: tuple[File,...]
    generation: str

@dataclass(frozen=True)
class Action:
    direction: str
    path: str
    source_sha256: str
    destination_sha256: str|None

@dataclass(frozen=True)
class Plan:
    local_fingerprint: str
    remote_fingerprint: str
    baseline_fingerprint: str|None
    compatibility_reference: str|None
    state: str
    actions: tuple[Action,...]
    protected: tuple[str,...]
    @property
    def id(self):return fingerprint(asdict(self))
    def validate_fresh(self,local,remote,baseline):
        if local.fingerprint!=self.local_fingerprint or remote.fingerprint!=self.remote_fingerprint or (fingerprint(asdict(baseline)) if baseline else None)!=self.baseline_fingerprint:
            raise ValueError('PLAN_STALE: Review again; endpoint content or baseline changed')


def safe_relative(path):
    parts=PurePosixPath(path).parts
    if not path or PurePosixPath(path).is_absolute() or any(part in ('..','.') for part in parts) or '\\' in path:return False
    for part in parts:
        if part.endswith((' ','.')) or any(ord(c)<32 or c in ':*?"<>|' for c in part):return False
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:return False
    return '/'.join(parts)==path


def _unlinked_directory_chain(path:Path):
    """Reject observable links/junctions in every directory component.

    This is read-only discovery hardening, not a lock or an atomic filesystem
    snapshot. Any future apply still requires independent quiescence and
    platform-specific race-safe write handling.
    """
    for directory in (*reversed(path.parents),path):
        info=directory.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(directory,'is_junction',lambda:False)():
            raise ValueError('Linked directory ancestry requires an explicit real-root mapping: '+str(directory))
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('Directory changed during discovery: '+str(directory))


def snapshot(root:Path,identity:Identity,*,initialized=False,max_files=MAX_FILES,max_bytes=MAX_BYTES):
    """Never interpret a missing/inaccessible path as an empty initialized save."""
    root=Path(root).absolute();files=[];total=0;seen=set()
    try:
        if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise ValueError('Linked endpoint root requires an explicit real-root mapping')
        if not root.exists():return Snapshot(identity,'missing',False,reason='Endpoint does not exist; initialization is unproven')
        if not root.is_dir():raise ValueError('Endpoint is not a directory')
        _unlinked_directory_chain(root)
        def walk_error(error):raise error
        for folder,dirs,names in os.walk(root,followlinks=False,onerror=walk_error):
            _unlinked_directory_chain(Path(folder))
            dirs.sort();names.sort()
            for name in dirs+names:
                path=Path(folder)/name;rel=path.relative_to(root).as_posix()
                if not safe_relative(rel):raise ValueError('Path is not safely portable between supported filesystems: '+rel)
                key=unicodedata.normalize('NFC',rel).casefold()
                if key in seen:raise ValueError('Case or Unicode path collision: '+rel)
                seen.add(key)
                info=path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(path,'is_junction',lambda:False)():raise ValueError('Linked save paths are protected: '+rel)
                if name in dirs:
                    if not stat.S_ISDIR(info.st_mode):raise ValueError('Directory changed during discovery')
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Nonregular or hardlinked save is protected: '+rel)
                total+=info.st_size
                if len(files)>=max_files or total>max_bytes:raise ValueError('Endpoint exceeds bounded snapshot limits')
                _unlinked_directory_chain(path.parent)
                descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));digest=sha256();read=0
                with os.fdopen(descriptor,'rb') as stream:
                    opened=os.fstat(stream.fileno())
                    if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):raise ValueError('File changed while opening')
                    while chunk:=stream.read(256*1024):
                        read+=len(chunk)
                        if read>info.st_size or read>max_bytes:raise ValueError('File grew during snapshot')
                        digest.update(chunk)
                    after=os.fstat(stream.fileno())
                _unlinked_directory_chain(path.parent)
                final=path.lstat()
                if read!=info.st_size or any(getattr(info,k)!=getattr(other,k) for other in (after,final) for k in ('st_dev','st_ino','st_size','st_mtime_ns')):raise ValueError('File changed during snapshot')
                files.append(File(rel,digest.hexdigest(),read))
        return Snapshot(identity,'present',bool(initialized),tuple(sorted(files,key=lambda item:item.path)))
    except (OSError,ValueError) as error:return Snapshot(identity,'unavailable',False,reason=str(error))


def _index(files):
    result={};portable=set()
    for entry in files:
        if not safe_relative(entry.path) or entry.path in result:raise ValueError('Invalid or duplicate snapshot path')
        key=unicodedata.normalize('NFC',entry.path).casefold()
        if key in portable:raise ValueError('Snapshot path collision')
        portable.add(key)
        if len(entry.sha256)!=64 or any(c not in '0123456789abcdef' for c in entry.sha256) or entry.bytes<0:raise ValueError('Invalid content fingerprint')
        result[entry.path]=entry
    return result


def plan(local:Snapshot,remote:Snapshot,baseline:Baseline|None,*,compatibility_reference:str|None=None):
    problems=[];actions=[]
    identities=(local.identity,remote.identity)
    if any(not isinstance(value,str) or not value for identity in identities for value in asdict(identity).values()):problems.append('Incomplete endpoint identity')
    if local.identity.endpoint==remote.identity.endpoint:problems.append('Endpoints must be distinct')
    for field in ('game','distribution','account','representation'):
        if getattr(local.identity,field)!=getattr(remote.identity,field):problems.append('Unsupported cross-'+field+' pairing')
    if not isinstance(compatibility_reference,str) or not compatibility_reference.strip() or len(compatibility_reference)>500:problems.append('A separately verified compatibility reference is required')
    if any(s.state!='present' or not s.initialized for s in (local,remote)):problems.append('Missing, unavailable or uninitialized endpoint; absence is not empty data')
    if baseline and (baseline.local!=local.identity or baseline.remote!=remote.identity or not baseline.generation):problems.append('Baseline belongs to a different endpoint context')
    if problems:return Plan(local.fingerprint,remote.fingerprint,fingerprint(asdict(baseline)) if baseline else None,compatibility_reference,'protected',(),tuple(problems))
    try:left,right=_index(local.files),_index(remote.files);before=_index(baseline.files) if baseline else {}
    except ValueError as error:return Plan(local.fingerprint,remote.fingerprint,fingerprint(asdict(baseline)) if baseline else None,compatibility_reference,'protected',(),(str(error),))
    if baseline is None:
        state='baseline-required' if left==right else 'first-run-choice-required'
        return Plan(local.fingerprint,remote.fingerprint,None,compatibility_reference,state,(),('No baseline; never choose a winner by timestamps',))
    for path in sorted(set(left)|set(right)|set(before)):
        l,r,b=left.get(path),right.get(path),before.get(path)
        if b is not None and (l is None or r is None):problems.append('Deletion or missing file is protected: '+path);continue
        if l==r:continue
        if l==b and r is not None:actions.append(Action('import',path,r.sha256,l.sha256 if l else None))
        elif r==b and l is not None:actions.append(Action('export',path,l.sha256,r.sha256 if r else None))
        else:problems.append('Divergent content; preserve both versions: '+path)
    # A conflicted plan exposes no executable partial subset.
    return Plan(local.fingerprint,remote.fingerprint,fingerprint(asdict(baseline)),compatibility_reference,'conflict' if problems else 'content-ready' if actions else 'unchanged',() if problems else tuple(actions),tuple(problems))
