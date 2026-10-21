"""Simulación sin escrituras de candidatos TMDB hacia listas Trakt.
No confirma disponibilidad real. No envía solicitudes POST/PUT/DELETE.
"""
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

BASE = 'https://api.trakt.tv'
NAMES = {'Netflix':'Netflix España', 'HBO Max':'HBO Max España', 'Disney+':'Disney+ España', 'Prime Video':'Prime Video España'}

def get(path, client, token):
    req = urllib.request.Request(BASE + path, headers={
        'Accept':'application/json', 'trakt-api-version':'2',
        'trakt-api-key':client, 'Authorization':'Bearer '+token,
        'User-Agent':'trakt-streaming-originals-dry-run/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Error HTTP {e.code} en consulta de Trakt. No se ha modificado ninguna lista.') from None

def main():
    raw = os.environ.get('TRAKT_CREDENTIALS_JSON','')
    if not raw: raise SystemExit('Falta TRAKT_CREDENTIALS_JSON')
    try:
        creds = json.loads(raw)
        client, token = creds['client_id'], creds['token']['access_token']
    except (ValueError, KeyError, TypeError):
        raise SystemExit('Formato inválido de TRAKT_CREDENTIALS_JSON') from None
    report_path = Path('novedades.json')
    if not report_path.exists(): raise SystemExit('Falta novedades.json; ejecuta primero monitor.py')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    slug = get('/users/settings', client, token)['user']['ids']['slug']
    all_lists=[]
    for page in range(1, 11):
        batch=get('/users/'+urllib.parse.quote(slug,safe='')+f'/lists?limit=100&page={page}',client,token)
        if not isinstance(batch,list): raise SystemExit('Respuesta inesperada al consultar listas')
        all_lists.extend(batch)
        if len(batch)<100: break
    output={'date':report.get('date'), 'mode':'DRY_RUN', 'warning':'Nuevas detecciones en muestra TMDB, NO incorporaciones confirmadas.', 'platforms':{}}
    for platform, name in NAMES.items():
        matches=[x for x in all_lists if x.get('name','').casefold()==name.casefold()]
        if len(matches)!=1: raise SystemExit(f'Lista ausente o duplicada: {name}')
        ident=matches[0].get('ids',{}).get('trakt')
        if not ident: raise SystemExit(f'Sin ID de lista: {name}')
        existing=set()
        for page in range(1, 101):
            items=get(f'/users/{urllib.parse.quote(slug,safe="")}/lists/{ident}/items?limit=100&page={page}',client,token)
            if not isinstance(items,list): raise SystemExit(f'Respuesta inesperada en {name}')
            for entry in items:
                typ=entry.get('type')
                if typ in ('movie','show'):
                    tmdb=entry.get(typ,{}).get('ids',{}).get('tmdb')
                    if tmdb is not None: existing.add(('tv' if typ=='show' else 'movie')+':'+str(tmdb))
            if len(items)<100: break
        data=report.get('platforms',{}).get(platform)
        if data is None: raise SystemExit(f'No hay datos del monitor para {platform}')
        candidates=data.get('recent_observed',[])
        pending=[]
        for item in candidates:
            typ=item.get('media_type')
            tmdb=item.get('tmdb_id')
            if typ not in ('tv','movie') or not isinstance(tmdb,int): continue
            if typ+':'+str(tmdb) not in existing:
                pending.append({'title':item.get('title',''), 'type':typ,'tmdb_id':tmdb, 'first_detected':item.get('first_detected')})
        output['platforms'][platform]={'list_name':name,'existing_items_with_tmdb_id':len(existing),'candidate_count':len(candidates),'would_add_unverified':pending}
        print(f'{name}: {len(existing)} títulos identificados en lista; {len(candidates)} candidatos; {len(pending)} pendientes NO confirmados')
    Path('simulacion_trakt.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SIMULACIÓN FINALIZADA. NO se ha modificado Trakt.')

if __name__=='__main__': main()
