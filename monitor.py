"""Monitor de candidatos nuevos en muestras ampliadas de TMDB.

No afirma fechas reales de alta en plataformas y NO escribe en Trakt.
La primera ejecución de esta versión crea una línea base nueva.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = json.loads(Path('config.json').read_text(encoding='utf-8'))
TOKEN = os.environ.get('TMDB_API_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit('Falta TMDB_API_TOKEN')
TODAY = dt.datetime.now(dt.timezone.utc).date()
STATE_PATH = Path('estado_catalogo.json')
OLD = json.loads(STATE_PATH.read_text(encoding='utf-8')) if STATE_PATH.exists() else {}
VERSION = 3
# 25 páginas de 20 resultados por tipo = hasta 1000 títulos por plataforma.
PAGES_PER_TYPE = 25


def api(path, params):
    url = 'https://api.themoviedb.org/3' + path + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Accept': 'application/json',
        'User-Agent': 'TraktStreamingMonitor/3.0',
    })
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
            retry_after = error.headers.get('Retry-After', '')
            wait = int(retry_after) if retry_after.isdigit() else min(2 ** attempt + 1, 30)
            time.sleep(wait)
        except (TimeoutError, urllib.error.URLError):
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt + 1, 30))
    raise RuntimeError('No se pudo consultar TMDB')


def collect(provider_ids):
    results = {}
    for media in ('movie', 'tv'):
        # Orden estable por fecha de estreno, no por popularidad.
        date_key = 'primary_release_date' if media == 'movie' else 'first_air_date'
        for page in range(1, PAGES_PER_TYPE + 1):
            params = {
                'watch_region': CONFIG.get('region', 'ES'),
                'with_watch_providers': '|'.join(map(str, provider_ids)),
                'with_watch_monetization_types': 'flatrate',
                'sort_by': date_key + '.desc',
                'language': CONFIG.get('language', 'es-ES'),
                'include_adult': 'false',
                'page': page,
            }
            data = api('/discover/' + media, params)
            for item in data.get('results', []):
                key = media + ':' + str(item['id'])
                results[key] = {
                    'media_type': media,
                    'tmdb_id': item['id'],
                    'title': item.get('title') or item.get('name') or '',
                    'release_date': item.get('release_date') or item.get('first_air_date') or '',
                }
            if page >= data.get('total_pages', 1):
                break
    return results


# Construir TODO en memoria: si falla una plataforma no se sobrescribe el estado.
previous_platforms = OLD.get('platforms', {}) if OLD.get('monitor_version') == VERSION else {}
new_state = {'monitor_version': VERSION, 'last_scan': TODAY.isoformat(), 'platforms': {}}
report = {
    'date': TODAY.isoformat(),
    'disclaimer': ('Altas detectadas en una muestra TMDB, NO altas oficiales de plataformas. '
                   'Los cambios en el muestreo pueden producir falsos positivos. '
                   'Las fechas de estreno NO son fechas de incorporación. No modifica Trakt.'),
    'platforms': {},
}
for platform, settings in CONFIG['platforms'].items():
    current = collect(settings['provider_ids'])
    previous = previous_platforms.get(platform)
    known = set(previous.get('known', [])) if previous else set()
    first_seen = dict(previous.get('first_seen', {})) if previous else {}
    if previous is None:
        # Evita falsos positivos al ampliar la muestra desde la versión anterior.
        additions = []
        for key in current:
            first_seen.setdefault(key, TODAY.isoformat())
    else:
        additions = [key for key in current if key not in known]
        for key in additions:
            first_seen.setdefault(key, TODAY.isoformat())
    cutoff = TODAY - dt.timedelta(days=90)
    recent = [dict(current[key], first_detected=first_seen[key]) for key in current
              if key in first_seen and key not in known and previous is not None
              and dt.date.fromisoformat(first_seen[key]) >= cutoff]
    recent.sort(key=lambda item: (item['first_detected'], item['release_date']), reverse=True)
    report['platforms'][platform] = {
        'sampled': len(current),
        'new_since_previous_scan': len(additions),
        'baseline_created': previous is None,
        'recent_observed': recent[:200],
    }
    # Conservamos títulos conocidos que salieron de la ventana de 25 páginas:
    # así no reaparecen como novedades cuando cambie la clasificación.
    all_known = known | set(current)
    new_state['platforms'][platform] = {
        'known': sorted(all_known),
        'first_seen': {k: v for k, v in first_seen.items() if k in all_known},
    }
    print(f'{platform}: {len(current)} muestreados, {len(additions)} nuevas detecciones, '
          f'linea_base={previous is None}')

Path('novedades.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
STATE_PATH.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding='utf-8')
print('Monitor v3 completado. No se ha modificado Trakt.')
