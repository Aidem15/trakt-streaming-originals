"""Verificación independiente de disponibilidad ES. SOLO LECTURA."""
import json, os, time, urllib.request, urllib.error
from pathlib import Path

TOKEN = os.environ.get('TMDB_API_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit('Falta TMDB_API_TOKEN en GitHub Secrets')
config = json.loads(Path('config.json').read_text(encoding='utf-8'))
state = json.loads(Path('estado_catalogo.json').read_text(encoding='utf-8'))
limit = int(os.environ.get('VERIFICAR_POR_PLATAFORMA', '40'))
if not 1 <= limit <= 1000:
    raise SystemExit('VERIFICAR_POR_PLATAFORMA debe estar entre 1 y 1000')

def get(url):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer '+TOKEN, 'Accept':'application/json'})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt == 4:
                raise
            time.sleep(min(20,2**attempt+1))

out = {'nota':'Verificación de proveedores flatrate en España según TMDB/JustWatch. No es garantía de disponibilidad en tiempo real. No modifica Trakt.', 'limite_por_plataforma':limit, 'plataformas':{}}
cache = {}
for name, settings in config['platforms'].items():
    ids = set(map(int, settings['provider_ids']))
    known = state.get('platforms',{}).get(name,{}).get('known',[])
    selected = sorted(set(known))[:limit]
    matches, nonmatches, errors = [], [], []
    for key in selected:
        try:
            media, item_id = key.split(':',1)
            if media not in ('movie','tv') or not item_id.isdigit():
                raise ValueError('Identificador no válido')
            if key not in cache:
                cache[key] = get(f'https://api.themoviedb.org/3/{media}/{item_id}/watch/providers')
            es = cache[key].get('results',{}).get('ES',{})
            providers = es.get('flatrate',[])
            found = sorted(ids & {int(p['provider_id']) for p in providers})
            entry = {'tmdb':key, 'proveedores_coincidentes':found}
            (matches if found else nonmatches).append(entry)
        except (ValueError, KeyError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            errors.append({'tmdb':key,'error':type(e).__name__})
    out['plataformas'][name] = {'revisados':len(selected),'confirmados_en_tmdb':len(matches),'no_confirmados':len(nonmatches),'errores':len(errors),'coincidencias':matches,'sin_coincidencia':nonmatches,'fallos':errors}
    print(f'{name}: {len(selected)} revisados, {len(matches)} con proveedor ES flatrate, {len(nonmatches)} sin coincidencia, {len(errors)} errores')
Path('verificacion_disponibilidad.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('FIN: Solo lectura. Ninguna lista de Trakt modificada.')
