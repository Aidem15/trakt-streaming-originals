"""Generate candidates for originals; never changes Trakt lists.

TMDB networks/providers are only indicators, not proof of original status.
"""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://api.themoviedb.org/3'
CONFIG = json.loads(pathlib.Path('config.json').read_text(encoding='utf-8'))
TOKEN = os.getenv('TMDB_API_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit('Missing TMDB_API_TOKEN secret. Nothing was changed.')


def get(endpoint, params):
    url = BASE + endpoint + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json', 'User-Agent': 'StreamingOriginalsPreview/0.1'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503) or attempt == 2:
                raise
            time.sleep(2 ** attempt + 1)
    return {}


def discover(media, providers, networks, start_date, end_date):
    key = 'first_air_date' if media == 'tv' else 'primary_release_date'
    common = {
        'language': CONFIG['language'], 'watch_region': CONFIG['region'],
        'with_watch_monetization_types': 'flatrate',
        'with_watch_providers': '|'.join(map(str, providers)),
        f'{key}.gte': start_date, f'{key}.lte': end_date,
        'sort_by': f'{key}.desc', 'include_adult': 'false'
    }
    if media == 'tv' and networks:
        common['with_networks'] = '|'.join(map(str, networks))
    results = []
    for page in range(1, 4):
        data = get(f'/discover/{media}', dict(common, page=page))
        results.extend(data.get('results', []))
        if page >= data.get('total_pages', 1):
            break
    return results


def main():
    today = dt.date.today()
    start = (today - dt.timedelta(days=180)).isoformat()
    output = {'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'notice': 'Candidates only: provider and network do NOT establish original status; dates for TV are series first-air dates, not new seasons.',
              'platforms': {}}
    for name, settings in CONFIG['platforms'].items():
        items = []
        for media in ('tv', 'movie'):
            # Movies have no reliable original-network filter: treat as unverified.
            for entry in discover(media, settings['provider_ids'], settings['original_network_ids'], start, today.isoformat()):
                items.append({'media_type': media, 'tmdb_id': entry['id'],
                              'title': entry.get('title') or entry.get('name'),
                              'date': entry.get('release_date') or entry.get('first_air_date'),
                              'original_status': 'UNVERIFIED',
                              'reason': 'TMDB provider availability; TV also network-filtered' if media == 'tv' else 'TMDB provider availability only'})
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        output['platforms'][name] = items[:CONFIG['max_candidates_per_platform']]
        print(f'{name}: {len(output["platforms"][name])} candidates (NOT confirmed originals)')
    pathlib.Path('preview.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved preview.json. No Trakt writes performed.')

if __name__ == '__main__':
    main()
