# Fase 2: monitor de novedades (sin escribir en Trakt)

Esta versión detecta cambios en una **muestra** de títulos que TMDB marca como disponibles por suscripción en España. Consulta hasta 10 páginas por tipo y plataforma, ordenadas por popularidad; **no es un inventario completo**. Una alta detectada puede deberse a cambios en TMDB o en el ranking, no necesariamente a una incorporación real al servicio.

## Instalación en el repositorio existente
1. Sube `monitor.py` a la raíz, junto a `config.json`.
2. En GitHub usa **Add file → Create new file** y crea `.github/workflows/monitor.yml`; pega el contenido del archivo homónimo de este ZIP y guarda.
3. Conserva el secreto `TMDB_API_TOKEN` (token largo de lectura TMDB).
4. Abre **Actions → Monitor novedades de plataformas → Run workflow**.
5. Descarga `novedades-plataformas` desde **Artifacts** al terminar.
6. La primera ejecución solo crea `estado_catalogo.json` como línea base: NO considera novedades todos los títulos existentes. Las ejecuciones posteriores detectan cambios en la muestra.

## Importante
- No toca listas de Trakt. La integración OAuth y la sincronización aún están pendientes.
- Los 90 días son desde la **primera detección por este monitor**, no desde el estreno real ni desde la incorporación oficial a Netflix/HBO/Disney/Prime.
- Para fechas de incorporación fiables se necesita una fuente que publique historial de disponibilidad en España.
- Se necesitan permisos `contents: write` y que GitHub Actions tenga permiso para escribir en el repositorio (Settings → Actions → General → Workflow permissions). Si falla el guardado, revisa ese permiso.
- El archivo de estado se guarda mediante commits automáticos; si tienes protección de rama que lo impida, necesitarás ajustar el flujo.
