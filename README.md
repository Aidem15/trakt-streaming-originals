# Trakt Streaming Originals — fase 1 (vista previa)

Este paquete **NO crea ni modifica listas de Trakt todavía**. Ejecuta diariamente en GitHub Actions una búsqueda de candidatos de Netflix, HBO Max, Disney+ y Prime Video disponibles en España usando TMDB.

## Instalación

1. En GitHub, abre tu repositorio privado `trakt-streaming-originals`.
2. Sube `config.json`, `preview.py`, este `README.md` y `.github/workflows/preview.yml` conservando exactamente las rutas. En la interfaz web de GitHub, si no puedes subir carpetas ocultas fácilmente, usa **Add file > Create new file** y escribe `.github/workflows/preview.yml` como nombre, pegando el contenido del archivo del ZIP.
3. Consigue tu **API Read Access Token** de TMDB en https://www.themoviedb.org/settings/api . No lo compartas en chats ni lo subas al repositorio.
4. En **Settings > Secrets and variables > Actions > New repository secret**, crea `TMDB_API_TOKEN` con ese token de TMDB (NO el de Trakt).
5. En **Actions > Vista previa de estrenos > Run workflow**, ejecuta una prueba.
6. Al terminar, descarga el artefacto `candidatos-streaming` y revisa `preview.json`.

## Qué hace y qué no

- Busca candidatos con disponibilidad de suscripción (`flatrate`) en España y fecha de estreno de los últimos 180 días.
- Para series, filtra además por redes asociadas a la plataforma. Esos IDs son orientativos y pueden cambiar.
- **No garantiza originales exclusivos**: que una película esté en Netflix no implica que sea un original de Netflix. Las temporadas nuevas de series antiguas tampoco se identifican correctamente con `first_air_date`.
- **No modifica Trakt**. El secreto `TRAKT_CLIENT_ID` que ya has creado se conserva para la siguiente fase.
- Las consultas de disponibilidad TMDB utilizan datos de JustWatch: atribución a JustWatch requerida al publicar o mostrar esos datos.
- El programador de GitHub Actions puede retrasarse; no se garantiza la ejecución a la hora exacta.

## Siguiente fase

Tras revisar los candidatos, añadiremos verificación de originales, autorización OAuth PKCE, gestión segura de refresh tokens de un solo uso y sincronización con las listas de Trakt, respetando límites de cuenta y API. No compartas tokens de acceso ni de actualización.

Fuentes técnicas: https://developer.trakt.tv/docs/authentication-oauth ; https://developer.trakt.tv/docs/pkce ; https://developer.themoviedb.org/reference/discover-tv
