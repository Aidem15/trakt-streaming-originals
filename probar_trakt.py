"""Prueba de solo lectura de Trakt desde GitHub Actions."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://api.trakt.tv'
EXPECTED = ['Netflix España', 'HBO Max España', 'Disney+ España', 'Prime Video España']


def get_json(path, client_id, access_token):
    req = urllib.request.Request(BASE + path, headers={
        'Accept': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': client_id,
        'Authorization': 'Bearer ' + access_token,
        'User-Agent': 'trakt-streaming-originals-readonly/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f'Error HTTP {exc.code} al consultar {path.split("?")[0]}')
        if exc.code == 401:
            print('El token ha caducado o no es válido. No se ha intentado renovarlo.')
        raise SystemExit(1) from None


def main():
    raw = os.environ.get('TRAKT_CREDENTIALS_JSON', '').strip()
    if not raw:
        raise SystemExit('Falta el secreto TRAKT_CREDENTIALS_JSON.')
    try:
        creds = json.loads(raw)
        client_id = creds['client_id']
        token = creds['token']['access_token']
    except (ValueError, KeyError, TypeError):
        raise SystemExit('El secreto TRAKT_CREDENTIALS_JSON no tiene el formato esperado.') from None
    print('Paso 1: consultar cuenta de Trakt...')
    settings = get_json('/users/settings', client_id, token)
    slug = settings['user']['ids']['slug']
    print('Cuenta: acceso correcto.')
    print('Paso 2: consultar listas...')
    lists = get_json('/users/' + urllib.parse.quote(slug, safe='') + '/lists?limit=100&page=1', client_id, token)
    for name in EXPECTED:
        matches = [item for item in lists if item.get('name', '').casefold() == name.casefold()]
        print(f'{name}: ' + ('encontrada' if len(matches) == 1 else 'NO encontrada o duplicada'))
    print('Paso 3: consultar informe del monitor...')
    path = Path('novedades.json')
    if not path.exists():
        print('No existe novedades.json en este checkout. Se omite el informe; no es un fallo de Trakt.')
    else:
        report = json.loads(path.read_text(encoding='utf-8'))
        for platform, data in report.get('platforms', {}).items():
            print(f'{platform}: {data.get("new_since_previous_scan", "?")} nuevas detecciones')
    print('Prueba terminada. No se ha modificado ninguna lista.')


if __name__ == '__main__':
    main()
