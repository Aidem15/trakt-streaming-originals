"""Simula carga inicial desde TMDB (ES, suscripcion) a cuatro listas Trakt.
Solo GET: nunca modifica listas ni credenciales. Cobertura limitada a 25 paginas por tipo.
"""
import json, os, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

CFG = json.loads(Path('config.json').read_text(encoding='utf-8'))
TMDB = os.environ.get('TMDB_API_TOKEN', '').strip()
RAW = os.environ.get('TRAKT_CREDENTIALS_JSON', '').strip()
if not TMDB or not RAW:
    raise SystemExit('Faltan secretos TMDB_API_TOKEN o TRAKT_CREDENTIALS_JSON')
creds = json.loads(RAW)
CLIENT = creds['client_id']
TOKEN = creds['token']['access_token']
NAMES = {'Netflix':'Netflix España','HBO Max':'HBO Max España','Disney+':'Disney+ España','Prime Video':'Prime Video España'}

def get(url, headers):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=35) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt == 4:
                raise SystemExit(f'Consulta fallida HTTP {e.code}. No se ha modificado Trakt.') from None
            time.sleep(min(2**attempt+1, 20))
        except urllib.error.URLError:
            if attempt == 4: raise SystemExit('Error de red. No se ha modificado Trakt.') from None
            time.sleep(min(2**attempt+1,20))

def trakt(path):
    return get('https://api.trakt.tv'+path, {'trakt-api-version':'2','trakt-api-key':CLIENT,
       'Authorization':'Bearer '+TOKEN,'Accept':'application/json','User-Agent':'trakt-catalog-dry-run/1.0'})

def tmdb(path, params):
    return get('https://api.themoviedb.org/3'+path+'?'+urllib.parse.urlencode(params),
       {'Authorization':'Bearer '+TMDB,'Accept':'application/json','User-Agent':'trakt-catalog-dry-run/1.0'})

def pages_trakt(path):
    out=[]
    for page in range(1,101):
        sep='&' if '?' in path else '?'
        batch=trakt(f'{path}{sep}limit=100&page={page}')
        if not isinstance(batch,list): raise SystemExit('Respuesta inesperada de Trakt')
        out.extend(batch)
        if len(batch)<100: return out
    raise SystemExit('Demasiadas páginas de Trakt; deteniendo por seguridad')

def discover(ids):
    out={}
    for typ in ('movie','tv'):
        datekey='primary_release_date' if typ=='movie' else 'first_air_date'
        for page in range(1,26):
            data=tmdb('/discover/'+typ, {'watch_region':'ES','with_watch_providers':'|'.join(map(str,ids)),
              'with_watch_monetization_types':'flatrate','sort_by':datekey+'.desc',
              'language':'es-ES','include_adult':'false','page':page})
            for x in data.get('results',[]):
                if not isinstance(x.get('id'),int): continue
                key=typ+':'+str(x['id'])
                out[key]={'title':x.get('title') or x.get('name') or '', 'tmdb_id':x['id'],
                  'media_type':typ, 'release_date':x.get('release_date') or x.get('first_air_date') or ''}
            if page>=data.get('total_pages',1):break
    return out

def main():
    slug=trakt('/users/settings')['user']['ids']['slug']
    qslug=urllib.parse.quote(slug,safe='')
    lists=pages_trakt('/users/'+qslug+'/lists')
    report={'mode':'DRY_RUN_NO_WRITES','region':'ES','scope':'TMDB discover: flatrate, 25 pages/movie + 25 pages/tv per platform',
      'warning':'Muestra parcial de TMDB; disponibilidad no garantizada ni fecha de incorporación confirmada. No se escribe en Trakt.',
      'platforms':{}}
    for platform, name in NAMES.items():
        if platform not in CFG['platforms']: raise SystemExit(f'Falta plataforma en config.json: {platform}')
        matches=[x for x in lists if x.get('name','').casefold()==name.casefold()]
        if len(matches)!=1: raise SystemExit(f'Lista no encontrada o duplicada: {name}')
        ident=matches[0].get('ids',{}).get('trakt')
        if ident is None: raise SystemExit(f'Lista sin identificador: {name}')
        items=pages_trakt(f'/users/{qslug}/lists/{ident}/items')
        existing=set()
        for item in items:
            kind=item.get('type')
            if kind in ('movie','show'):
                mid=item.get(kind,{}).get('ids',{}).get('tmdb')
                if mid is not None: existing.add(('tv' if kind=='show' else 'movie')+':'+str(mid))
        sample=discover(CFG['platforms'][platform]['provider_ids'])
        pending=[x for k,x in sample.items() if k not in existing]
        report['platforms'][platform]={'list_name':name,'sampled':len(sample),
          'already_in_list':sum(k in existing for k in sample), 'would_add_unverified_count':len(pending),
          'examples_only':pending[:15]}
        print(f'{name}: {len(sample)} en muestra, {len(existing)} identificados en lista, {len(pending)} posibles altas (NO confirmadas)')
    Path('simulacion_carga_inicial.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SIMULACIÓN COMPLETADA. No se ha modificado ninguna lista de Trakt.')

if __name__=='__main__':main()
