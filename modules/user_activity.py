import json
import time
from pathlib import Path

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / 'config' / 'user_activity.json'

def _load():
    if not FILE.exists(): return {}
    try: return json.loads(FILE.read_text(encoding='utf8'))
    except Exception: return {}

def _save(data):
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')

def record(chat_id, user_id, message):
    data=_load(); g=data.setdefault(normalize_group_id(chat_id), {}); u=g.setdefault(str(user_id), {'gifs':0,'videos':0,'first':time.time(),'last':time.time()})
    now=time.time(); u['last']=now; u.setdefault('first',now)
    doc=getattr(message,'document',None) or getattr(getattr(message,'media',None),'document',None)
    mime=(getattr(doc,'mime_type',None) or '').lower()
    if bool(getattr(message,'gif',False)) or bool(getattr(message,'animation',None)) or mime=='image/gif': u['gifs']+=1
    elif mime.startswith('video/'): u['videos']+=1
    _save(data)

def get(chat_id,user_id):
    return _load().get(normalize_group_id(chat_id),{}).get(str(user_id), {'gifs':0,'videos':0,'first':0,'last':0})
