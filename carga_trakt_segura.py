"""Carga incremental controlada de títulos verificados en TMDB a listas Trakt."""
import json, os, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path

API='https://api.trakt.tv'
NAMES={'Netflix':'Netflix España','HBO Max':'HBO Max España','Disney+':'Disney+ España','Prime Video':'Prime Video España'}
MODE=os.getenv('MODO_CARGA','simular')
BATCH=int(os.getenv('MAX_POR_LISTA','25'))
if MODE not in ('simular','escribir') or not 1<=BATCH<=100:
    raise SystemExit('Modo o límite no válido')
creds=json.loads(os.environ['TRAKT_CREDENTIALS_JSON'])
client=creds['client_id']; access=creds['token']['access_token']
report=json.loads(Path('verificacion_disponibilidad.json').read_text(encoding='utf-8'))

def request(path, method='GET', payload=None):
    headers={'Accept':'application/json','Content-Type':'application/json','trakt-api-version':'2','trakt-api-key':client,'Authorization':'Bearer '+access,'User-Agent':'trakt-streaming-originals-safe-sync/1.0'}
    data=json.dumps(payload).encode() if payload is not None else None
    for attempt in range(6):
        req=urllib.request.Request(API+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=45) as r:
                raw=r.read(); return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code==401: raise SystemExit('Trakt 401: renovar autorización antes de escribir')
            if e.code not in (429,500,502,503,504) or attempt==5: raise SystemExit(f'Error Trakt HTTP {e.code} en {method} {path.split("?")[0]}')
            wait=e.headers.get('Retry-After','')
            try: delay=min(90,max(1,int(wait)))
            except ValueError: delay=min(60,2**attempt+2)
            time.sleep(delay)
        except urllib.error.URLError:
            if attempt==5: raise SystemExit('Error de conexión con Trakt')
            time.sleep(min(30,2**attempt+1))

def paged(path):
    out=[]
    for page in range(1,101):
        sep='&' if '?' in path else '?'
        chunk=request(f'{path}{sep}limit=100&page={page}')
        if not isinstance(chunk,list): raise SystemExit('Respuesta inesperada de Trakt')
        out.extend(chunk)
        if len(chunk)<100: return out
    raise SystemExit('Demasiadas páginas, abortando por seguridad')

settings=request('/users/settings')
slug=urllib.parse.quote(settings['user']['ids']['slug'],safe='')
lists=paged(f'/users/{slug}/lists')
results={}
for platform, list_name in NAMES.items():
    found=[x for x in lists if x.get('name','').casefold()==list_name.casefold()]
    if len(found)!=1: raise SystemExit(f'Lista no encontrada o duplicada: {list_name}')
    lst=found[0]
    list_id=urllib.parse.quote(str(lst.get('ids',{}).get('trakt') or lst.get('ids',{}).get('slug') or ''),safe='')
    if not list_id: raise SystemExit('Lista sin identificador')
    entries=paged(f'/users/{slug}/lists/{list_id}/items')
    existing=set()
    for x in entries:
        typ=x.get('type'); obj=x.get(typ,{}) if typ in ('movie','show') else {}
        tid=obj.get('ids',{}).get('tmdb')
        if tid is not None: existing.add(('tv' if typ=='show' else 'movie',int(tid)))
    source=report['plataformas'][platform]
    if source.get('errores',0) or source.get('no_confirmados',0)<0: raise SystemExit(f'Informe con errores para {platform}')
    candidates=[]; seen=set()
    for item in source['coincidencias']:
        media, idstr=item['tmdb'].split(':',1)
        if media not in ('tv','movie') or not idstr.isdigit() or not item.get('proveedores_coincidentes'): raise SystemExit('Entrada de informe inválida')
        key=(media,int(idstr))
        if key not in existing and key not in seen: candidates.append(key);seen.add(key)
    batch=candidates[:BATCH]
    print(f'{list_name}: {len(source["coincidencias"])} verificados, {len(existing)} IDs TMDB ya en lista, {len(candidates)} pendientes, lote {len(batch)}')
    results[platform]={'pendientes':len(candidates),'lote':len(batch),'modo':MODE}
    if MODE=='escribir' and batch:
        payload={'movies':[{'ids':{'tmdb':tid}} for media,tid in batch if media=='movie'], 'shows':[{'ids':{'tmdb':tid}} for media,tid in batch if media=='tv']}
        response=request(f'/users/{slug}/lists/{list_id}/items','POST',payload)
        added=response.get('added',{}); not_found=response.get('not_found',{})
        print(f'  Respuesta Trakt: añadidas películas={added.get("movies",0)}, series={added.get("shows",0)}, no encontradas películas={len(not_found.get("movies",[]))}, series={len(not_found.get("shows",[]))}')
        results[platform]['respuesta']=response
Path('informe_carga_trakt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('FIN: '+('SIMULACIÓN, sin cambios en Trakt' if MODE=='simular' else 'LOTE DE ESCRITURA FINALIZADO. Revisar informe.'))
