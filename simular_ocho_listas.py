"""Comprueba las ocho listas nuevas y el informe TMDB. SOLO LECTURA."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://api.trakt.tv'
PLATFORMS = ['Netflix', 'HBO Max', 'Disney+', 'Prime Video']


def get(path, client, token):
    req = urllib.request.Request(API + path, headers={
        'Accept': 'application/json', 'trakt-api-version': '2',
        'trakt-api-key': client, 'Authorization': 'Bearer ' + token,
        'User-Agent': 'trakt-streaming-originals-8lists-readonly/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f'Error Trakt HTTP {exc.code} consultando {path.split("?")[0]}') from None


def paged(path, client, token):
    result = []
    for page in range(1, 101):
        sep = '&' if '?' in path else '?'
        chunk = get(f'{path}{sep}limit=100&page={page}', client, token)
        if not isinstance(chunk, list):
            raise SystemExit('Respuesta inesperada de Trakt')
        result.extend(chunk)
        if len(chunk) < 100:
            return result
    raise SystemExit('Demasiadas páginas en Trakt')


def main():
    raw = os.getenv('TRAKT_CREDENTIALS_JSON', '').strip()
    if not raw:
        raise SystemExit('Falta TRAKT_CREDENTIALS_JSON')
    creds = json.loads(raw)
    client, token = creds['client_id'], creds['token']['access_token']
    report = json.loads(Path('verificacion_disponibilidad.json').read_text(encoding='utf-8'))
    settings = get('/users/settings', client, token)
    slug = urllib.parse.quote(settings['user']['ids']['slug'], safe='')
    lists = paged(f'/users/{slug}/lists', client, token)
    result = {'modo': 'solo_lectura', 'plataformas': {}}
    for platform in PLATFORMS:
        old_name = platform + ' España'
        new_names = {'movie': old_name + ' - Películas', 'tv': old_name + ' - Series'}
        matched = {}
        for name in [old_name, *new_names.values()]:
            found = [x for x in lists if x.get('name', '').casefold() == name.casefold()]
            if len(found) != 1:
                raise SystemExit(f'Lista ausente o duplicada: {name}')
            matched[name] = found[0]
        counts = {'movie': 0, 'tv': 0}
        source = report['plataformas'][platform]
        if source.get('errores') or not isinstance(source.get('coincidencias'), list):
            raise SystemExit(f'Informe inválido para {platform}')
        for entry in source['coincidencias']:
            media, sep, itemid = entry.get('tmdb', '').partition(':')
            if not sep or media not in counts or not itemid.isdigit() or not entry.get('proveedores_coincidentes'):
                raise SystemExit(f'Identificador inválido para {platform}')
            counts[media] += 1
        def items_for(name):
            obj = matched[name]
            lid = obj.get('ids', {}).get('trakt') or obj.get('ids', {}).get('slug')
            if not lid:
                raise SystemExit(f'Lista sin ID: {name}')
            lid = urllib.parse.quote(str(lid), safe='')
            return paged(f'/users/{slug}/lists/{lid}/items', client, token)
        old_items = items_for(old_name)
        new_movie = items_for(new_names['movie'])
        new_show = items_for(new_names['tv'])
        old_movie = sum(x.get('type') == 'movie' for x in old_items)
        old_show = sum(x.get('type') == 'show' for x in old_items)
        print(f'{platform}: informe {counts["movie"]} películas, {counts["tv"]} series; lista antigua {old_movie} películas y {old_show} series; nuevas {len(new_movie)} películas y {len(new_show)} series')
        result['plataformas'][platform] = {
            'verificados_peliculas': counts['movie'], 'verificados_series': counts['tv'],
            'antigua_peliculas': old_movie, 'antigua_series': old_show,
            'nueva_peliculas_items': len(new_movie), 'nueva_series_items': len(new_show),
        }
    Path('informe_ocho_listas.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FIN: SOLO LECTURA. No se han modificado listas de Trakt.')


if __name__ == '__main__':
    main()
