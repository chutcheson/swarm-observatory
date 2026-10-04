"""SQLite state and content-addressed helpers."""
import contextlib,hashlib,json,os,sqlite3,tempfile
from datetime import datetime,timezone
from pathlib import Path

def now():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256((value if isinstance(value,str) else canonical(value)).encode()).hexdigest()
def atomic_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def connect(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(path,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=30000')
 c.executescript('''
 CREATE TABLE IF NOT EXISTS sources(uid TEXT PRIMARY KEY,dataset TEXT,logical_id TEXT,kind TEXT,text TEXT,content_hash TEXT,metadata TEXT,created_at TEXT);
 CREATE INDEX IF NOT EXISTS source_logical ON sources(dataset,logical_id);
 CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,dataset TEXT,kind TEXT,title TEXT,metadata TEXT);
 CREATE TABLE IF NOT EXISTS packets(id TEXT PRIMARY KEY,entity_id TEXT,dataset TEXT,content_hash TEXT,payload TEXT,coverage TEXT,created_at TEXT);
 CREATE INDEX IF NOT EXISTS packet_entity ON packets(entity_id);
 CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,stage TEXT,packet_id TEXT,queue TEXT,status TEXT,config_hash TEXT,attempt_count INTEGER DEFAULT 0,max_attempts INTEGER DEFAULT 3,lease_token TEXT,lease_until REAL,error TEXT,created_at TEXT,updated_at TEXT,available_at REAL DEFAULT 0);
 CREATE INDEX IF NOT EXISTS runnable ON jobs(status,queue,available_at,created_at);
 CREATE TABLE IF NOT EXISTS dependencies(job_id TEXT,depends_on TEXT,PRIMARY KEY(job_id,depends_on));
 CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,job_id TEXT,worker TEXT,lease_token TEXT,started_at TEXT,finished_at TEXT,status TEXT,output TEXT,usage TEXT,error TEXT);
 CREATE TABLE IF NOT EXISTS results(job_id TEXT PRIMARY KEY,content_hash TEXT,payload TEXT,created_at TEXT);
 CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,job_id TEXT,kind TEXT,status TEXT,payload TEXT,created_at TEXT);
 CREATE TABLE IF NOT EXISTS invalidations(id TEXT PRIMARY KEY,job_id TEXT,reason TEXT,created_at TEXT);
 CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
 ''')
 return c
@contextlib.contextmanager
def transaction(c):
 c.execute('BEGIN IMMEDIATE')
 try:yield;c.execute('COMMIT')
 except BaseException:c.execute('ROLLBACK');raise

def setting(c,key,default=None):
 r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone();return json.loads(r[0]) if r else default

def set_setting(c,key,value):c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,canonical(value)))
