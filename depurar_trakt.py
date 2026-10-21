"""Comprueba bajas de proveedores ES en TMDB y retira solo tras 3 días distintos.
Estado persistido en estado_bajas_trakt.json. Primera ejecución: ninguna baja.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://api.trakt.tv'
NAMES = {'Netflix':'Netflix España','HBO Max':'HBO Max España','Disney+':'Disney+ España','Prime Video':'Prime Video España'}
CONFIG = json.loads(Path('config.json').read_text(encoding='utf-8'))
TOKEN = os.environ['TMDB_API_TOKEN']
CREDS = json.loads(os.environ['TRAKT_CREDENTIALS_JSON'])
STATE_FILE = Path('estado_bajas_trakt.json')
STATE = json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {'version':1,'platforms':{}}
if STATE.get('version') != 1: raise SystemExit('Versión de estado de bajas no reconocida')
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()
MODE = os.environ.get('MODO_BAJAS','simular')
if MODE not in ('simular','escribir'): raise SystemExit('MODO_BAJAS inválido')
MAX_REMOVE = 20

def fetch(url, headers, method='GET', payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                raw=response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt == 5: raise
            retry=e.headers.get('Retry-After','')
            time.sleep(min(90,int(retry) if retry.isdigit() else 2**attempt+1))
        except (urllib.error.URLError,TimeoutError):
            if attempt==5: raise
            time.sleep(min(30,2**attempt+1))

def trakt(path,method='GET',payload=None):
    return fetch(API+path,{'Accept':'application/json','Content-Type':'application/json',
        'trakt-api-version':'2','trakt-api-key':CREDS['client_id'],
        'Authorization':'Bearer '+CREDS['token']['access_token']},method,payload)

def paged(path):
    out=[]
    for page in range(1,101):
        sep='&' if '?' in path else '?'
        chunk=trakt(f'{path}{sep}limit=100&page={page}')
        if not isinstance(chunk,list): raise RuntimeError('Paginación inesperada')
        out.extend(chunk)
        if len(chunk)<100: return out
    raise RuntimeError('Demasiadas páginas')

slug=urllib.parse.quote(trakt('/users/settings')['user']['ids']['slug'],safe='')
all_lists=paged(f'/users/{slug}/lists')
report={}
cache={}
for platform,name in NAMES.items():
    matches=[x for x in all_lists if x.get('name','').casefold()==name.casefold()]
    if len(matches)!=1: raise RuntimeError('Lista no encontrada o duplicada: '+name)
    list_id=matches[0]['ids'].get('trakt') or matches[0]['ids'].get('slug')
    list_id=urllib.parse.quote(str(list_id),safe='')
    entries=paged(f'/users/{slug}/lists/{list_id}/items')
    current={}
    for item in entries:
        kind=item.get('type')
        if kind not in ('movie','show'): continue
        tid=item.get(kind,{}).get('ids',{}).get('tmdb')
        if tid is not None: current[('tv' if kind=='show' else 'movie')+':'+str(tid)]=kind
    provider_ids=set(map(int,CONFIG['platforms'][platform]['provider_ids']))
    state=STATE['platforms'].setdefault(platform,{})
    for stale in list(state):
        if stale not in current: del state[stale]
    confirmed=[]; errors=[]; absent=0
    for key,kind in current.items():
        try:
            media,tid=key.split(':')
            if media not in ('tv','movie') or not tid.isdigit(): continue
            if key not in cache:
                cache[key]=fetch(f'https://api.themoviedb.org/3/{media}/{tid}/watch/providers',
                    {'Authorization':'Bearer '+TOKEN,'Accept':'application/json'})
            regions=cache[key].get('results',{})
            # Sin datos de España no hay evidencia suficiente para retirar.
            if 'ES' not in regions:
                state.pop(key,None)
                continue
            es=regions['ES']
            if not isinstance(es,dict): raise ValueError('Respuesta ES inesperada')
            providers=es.get('flatrate',[])
            if not isinstance(providers,list): raise ValueError('flatrate inválido')
            available=bool(provider_ids & {int(p['provider_id']) for p in providers})
            if available:
                state.pop(key,None)
                continue
            absent+=1
            rec=state.get(key,{'days':[]})
            days=rec.get('days',[])
            if TODAY not in days: days.append(TODAY)
            days=sorted(set(days))[-3:]
            state[key]={'days':days}
            if len(days)>=3 and (dt.date.fromisoformat(days[-1])-dt.date.fromisoformat(days[0])).days>=2:
                confirmed.append((key,kind))
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,KeyError,TypeError) as e:
            errors.append({'id':key,'error':type(e).__name__})
            # No contamos una consulta fallida como ausencia.
    # Fallos de verificación: nunca eliminar en esta plataforma.
    removable=confirmed[:MAX_REMOVE] if not errors else []
    deleted=0
    if MODE=='escribir' and removable:
        payload={'movies':[{'ids':{'tmdb':int(k.split(':')[1])}} for k,kind in removable if kind=='movie'],
                 'shows':[{'ids':{'tmdb':int(k.split(':')[1])}} for k,kind in removable if kind=='show']}
        result=trakt(f'/users/{slug}/lists/{list_id}/items','DELETE',payload)
        deleted=int(result.get('deleted',{}).get('movies',0))+int(result.get('deleted',{}).get('shows',0))
        if deleted!=len(removable): raise RuntimeError(f'Bajas parciales en {name}: {deleted}/{len(removable)}. Revisar manualmente.')
        for key,_ in removable: state.pop(key,None)
    report[platform]={'elementos':len(entries),'ausencias_observadas':absent,
        'bajas_confirmadas':len(confirmed),'bajas_elegibles':len(removable),
        'bajas_realizadas':deleted,'errores':errors,'modo':MODE}
    print(f'{name}: {len(entries)} elementos, {absent} sin proveedor, {len(confirmed)} bajas confirmadas, '
          f'{deleted} eliminados, {len(errors)} errores')
    # Guardar estado tras cada plataforma, sin esperar al final de todas.
    STATE_FILE.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')
Path('informe_bajas_trakt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Fin de comprobación de bajas.')
