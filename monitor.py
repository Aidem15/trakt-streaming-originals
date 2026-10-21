"""Detecta altas observadas desde TMDB, sin escribir en Trakt."""
import datetime as dt
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import urllib.error

CFG=json.loads(Path('config.json').read_text(encoding='utf-8'))
TOKEN=os.environ.get('TMDB_API_TOKEN','').strip()
if not TOKEN: raise SystemExit('Falta TMDB_API_TOKEN')
TODAY=dt.datetime.now(dt.timezone.utc).date()
STATE=Path('estado_catalogo.json')
PREVIOUS=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'platforms':{}}

def api(path,params):
    url='https://api.themoviedb.org/3'+path+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json'})
    for n in range(4):
        try:
            with urllib.request.urlopen(req,timeout=30) as resp:return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code not in (429,500,502,503) or n==3:raise
            time.sleep(2**n+1)

def collect(provider_ids):
    results={}
    for media in ('movie','tv'):
        for page in range(1,11):
            params={'watch_region':'ES','with_watch_providers':'|'.join(map(str,provider_ids)),
                    'with_watch_monetization_types':'flatrate','sort_by':'popularity.desc',
                    'language':'es-ES','include_adult':'false','page':page}
            data=api('/discover/'+media,params)
            for item in data.get('results',[]):
                key=media+':'+str(item['id'])
                results[key]={'media_type':media,'tmdb_id':item['id'],
                    'title':item.get('title') or item.get('name') or '',
                    'release_date':item.get('release_date') or item.get('first_air_date') or ''}
            if page>=data.get('total_pages',1):break
    return results

updated={'last_scan':TODAY.isoformat(),'platforms':{}}
report={'date':TODAY.isoformat(),'disclaimer':'Fecha de primera detección en la muestra, NO fecha oficial de alta. TMDB no cubre todo el catálogo. No modifica Trakt.', 'platforms':{}}
for platform, settings in CFG['platforms'].items():
    current=collect(settings['provider_ids'])
    prior=PREVIOUS.get('platforms',{}).get(platform)
    first_seen=dict(prior.get('first_seen',{})) if prior else {}
    if prior is None:
        # Primera ejecución: línea base; no considerar estrenos a los existentes.
        for key in current:first_seen[key]=TODAY.isoformat()
        additions=[]
    else:
        additions=[key for key in current if key not in prior.get('known',[])]
        for key in additions:first_seen[key]=TODAY.isoformat()
    cutoff=TODAY-dt.timedelta(days=90)
    recent=[dict(current[key],first_detected=first_seen[key]) for key in current
            if key in first_seen and dt.date.fromisoformat(first_seen[key])>cutoff
            and prior is not None]
    recent.sort(key=lambda item:item['first_detected'],reverse=True)
    report['platforms'][platform]={'sampled':len(current),'new_since_previous_scan':len(additions),
                                   'recent_observed':recent[:200], 'baseline_created':prior is None}
    updated['platforms'][platform]={'known':sorted(current),'first_seen':first_seen}
    print(f'{platform}: {len(current)} muestreados, {len(additions)} nuevas detecciones')
Path('novedades.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
STATE.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8')
print('Monitor completado. Ninguna lista de Trakt modificada.')
