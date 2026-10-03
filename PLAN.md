# Lost at Night — Plan de reorganización

Resultado de la revisión del 2026-10-03 (participación, estadísticas, equipos).
Complementa `BUGS.md`, que recoge fallos puntuales; esto es el plan de trabajo.

Leyenda de estado:
- ✅ Hecho
- 🔧 En curso
- ⏳ Pendiente

Última actualización: 2026-10-03 (tarde).

---

## Diagnóstico en una página

**Dos sistemas de participación sin jerarquía.** Batches y retos aparecen al mismo
nivel en portada, barra y pie. El batch es un concepto de administración (una
consulta a la API de la NASA, nombre interno tipo `ISS046`, sin descripción). El
reto es el concepto para personas (nombre, objetivo, fechas, comunidad). Hoy
chocan: un usuario inscrito en un reto que pulsa un batch incompatible recibe un
409 con el texto "en este batch". La pantalla de trabajo nunca dice en qué batch
estás.

Datos (últimos 60 días): 80 % de las contribuciones entran por el batch
"Easy ones"; 165 de 349 son anónimas; de 12 contribuyentes activos en el mes,
solo 2 han estado alguna vez en un reto; 7 retos creados, todos finalizados,
0 abiertos.

**Estadísticas dispersas con definiciones distintas.** 12 superficies muestran
contadores. "Tareas" se calcula de tres formas (GeoAttempt DONE, campo
`geoattempts_done` del perfil, suma de `GeoAttemptsByUserByDay`). "Usuarios" son
emails verificados en portada, todos los perfiles en el ranking personal, y solo
los que tienen CP en el diploma. Hay cinco cálculos distintos de "rango global".
La raíz: los contadores desnormalizados del perfil se actualizan en una sola
rama del endpoint de envío, que es público y no es idempotente.

**Equipos invisibles.** Backend funcional y con tests, pero la única entrada es
una tarjeta dentro del área personal (requiere login). Sin enlace en navegación,
sin listado, `/teams/` sin slug da 404, puntuación que suma el historial previo
de cada miembro, cadenas sin traducir. El directorio `teams/` no está en git.

**Decisión de diseño propuesta:** una sola puerta de entrada. "Participa" sirve
la cola general; el reto es la única capa de elección visible. El batch deja de
exponerse al público. Si hace falta ofrecer conjuntos de imágenes concretos, se
hace con retos permanentes (sin fecha de fin efectiva), que el modelo ya admite.

---

## Incidente 2026-10-03 — Puntos de control no guardados ✅

Detectado al arrancar la Fase 1. Desde el commit `68cd7eb` (2026-05-02) el
cliente enviaba `control_points` y el serializador solo aceptaba
`controlPoints`: cada envío DONE persistía una lista vacía. Los contadores del
perfil subían (se calculaban desde la petición), así que portada y rankings
mostraban puntos que no existían. 1552 contribuciones afectadas.

- ✅ Causa corregida en `GeoAttemptIndividualView.patch`: la clave del cliente
  se mapea al campo del modelo antes de validar; `cp_added` se calcula desde
  lo que se guarda.
- ✅ Recuperación desde la salida estándar de gunicorn (`print(request.data)`
  en `/var/log/lostatnight-gunicorn.out.log`): 1550 de 1552 restauradas. Las 2
  restantes (ids 5099 y 20080) se enviaron realmente con cero puntos. Copia
  previa de la tabla en
  `/home/ubuntu/gdalface-backups/geoattempt_before_cp_recovery_20261003.sql.gz`.
  Script en el scratchpad de la sesión (`recover_cp.py`); el log mezcla la
  salida de los 4 workers sin salto de línea, así que hay que extraer los
  payloads por patrón, no por línea.
- ✅ Un DONE sin puntos de control devuelve ahora 400.
- ✅ Test de regresión en `georeferencing/tests.py`.
- ⏳ Quitar el `print(request.data)` solo cuando exista un log estructurado de
  envíos; hoy es la única copia de seguridad del dato.

## Fase 1 — Integridad de datos 🔧 (queda 1.3)

Sin esto, cualquier estadística que mostremos es discutible. No admite debate y
va primero.

### 1.1 Endpoint de envío (`georeferencing/views.py`, `GeoAttemptIndividualView.patch`)
- ✅ Guardia de idempotencia: si el GeoAttempt ya está `DONE`, no volver a sumar
  `geoattempts_done`, `controlPointsDone`, `time_spent`, `cached_cp_count` ni
  `GeoAttemptsByUserByDay`.
- ✅ Comprobación de propiedad: un usuario autenticado solo puede cerrar tareas
  cuyo `assignedUser` sea él; anónimos solo tareas sin `assignedUser`.
- ✅ Contar CP desde lo que se guarda, no desde el cuerpo crudo de la petición.
- ✅ Comprobar bbox al acreditar CP a un reto (hoy solo se comprueba el batch;
  el filtro de asignación sí usa bbox → incoherencia).
- ✅ El liberador de tareas abandonadas (`tasks.update_assigned`) debe limpiar
  `assignedUser` y `assignedDateTime` al devolver a `PENDING`.

### 1.2 Comando de reconciliación (`georeferencing/management/commands/reconcile_counters.py`)
- ✅ Recalcular desde `GeoAttempt` DONE: `UserProfile.geoattempts_done`,
  `controlPointsDone` (= Σ len(controlPoints)), `time_spent`
  (= Σ finished − assigned). Reglas en `georeferencing/reconcile.py`.
- ✅ Reconstruir `GeoAttemptsByUserByDay` desde `finishedDateTime`.
- ⚠️ Recalcular `ChallengeParticipant.cached_cp_count` con una regla única
  (ventana del reto ∩ ventana de inscripción ∩ batch ∩ bbox). Hecho y la
  acción de admin `recompute_totals` usa la misma función, PERO no se aplica
  por defecto (`--challenges`): la reinscripción reutiliza la fila original
  sin guardar historial, así que un usuario que salió y volvió (caso real:
  Germany → Europe 27 min → Germany) no se puede reconstruir. El valor vivo
  sigue siendo el de referencia para retos.
- ✅ Historial de inscripción `ChallengeEnrollmentPeriod` (participant,
  joined_at, left_at, backfilled), escrito por unirse / salir / salida
  automática al cambiar de reto. La regla de reconciliación suma sobre esos
  periodos. Migración 0057 rellenó 76 periodos desde los datos antiguos
  (marcados `backfilled`) y cerró 2 inscripciones heredadas abiertas.
- ⏳ Los 17 participantes con deriva en retos ya finalizados se quedan como
  están: su historial real no se puede reconstruir y hay diplomas emitidos.
  Para retos nuevos (periodos no `backfilled`) `--challenges` es exacto; pasar
  a aplicarlo por defecto cuando el primer reto nuevo termine sin discrepancias.
- ✅ Dry-run por defecto, `--apply` para escribir. Ejecutado en producción el
  2026-10-03: 20 perfiles y 22 filas diarias corregidas (siempre a la baja, 1-3
  tareas: dobles envíos). Deriva restante 0. Anotado como evento en `/stats/`.
  Copia previa en `gdalface-backups/profiles_byday_participants_before_reconcile_20261003.sql.gz`.
- ✅ Programado semanal (lunes 03:00 UTC) en modo dry-run: anota la deriva como
  evento en `/stats/`. Aplicar sigue siendo manual hasta que exista el
  historial de inscripción.

### 1.3 Borrado de cuenta (`user_profile/views.py`, `delete_account`)
- ⏳ Decidir qué pasa con las contribuciones: hoy quedan como anónimas
  (`assignedUser=None`) y desaparecen de equipos, países y retos pero no de la
  portada. Propuesta: mantenerlas como anónimas en todos los sitios y que los
  totales de equipo/país se calculen desde `GeoAttempt`, no desde el perfil.
- ✅ `GeoAttempt.assignedUser` es `on_delete=DO_NOTHING`; cambiado a `SET_NULL`.

### 1.4 Tareas de infraestructura detectadas por el panel
- ✅ 103 tareas `ASSIGNED` con más de 6 h: falsa alarma. El job corre cada hora
  y la foto se tomó justo antes de la ejecución. El panel usa ahora 7 h.
  Además, "saltar" o enviar sobre una tarea ya liberada devuelve 409.
- ✅ Snapshot público parado desde 2026-09-28. **Causa encontrada**: los tests
  de países y equipos llamaban a `cache.clear()`, que en RedisCache es un
  `FLUSHDB` de la base 3 completa, donde también vive el registro de
  rq-scheduler. Cada pasada de tests borraba los trabajos programados. Todos
  los TestCase usan ahora LocMemCache y `schedule_tasks` no se ejecuta bajo el
  test runner. Red de seguridad además: el job horario regenera el snapshot si
  tiene más de 24 h. Si vuelve a pasar: `manage.py migrate` re-registra los
  trabajos.
- ✅ El tutorial nunca emitía `completed`: driver.js ya ha vaciado `state` cuando
  llama a `onDestroyed`, así que `activeIndex` era `undefined` y todo acababa
  como `dismissed` en el paso 1. `tutorial.js` recuerda ahora el último paso
  resaltado. Verificar en `/stats/` que empiezan a llegar completados.

**Criterio de salida:** `reconcile_counters` (dry-run) devuelve cero diferencias
dos semanas seguidas. Estado 2026-10-03: 0 en perfiles y diario; retos
pendientes del historial de inscripción.

---

## Fase 2 — Una definición por métrica 🔧

Estado 2026-10-03: módulo `georeferencing/metrics.py` creado y consumido por
portada, área personal, estadísticas de la ficha de tarea, overlay, diplomas y
JSON público. Decisión tomada: los perfiles ocultos **cuentan siempre y no se
nombran nunca** (antes países los excluía). Equipos aplican el filtro de
verificados. Pendiente: `/ranking/` como consumidor de referencia (Fase 2.5) y
los tests de igualdad entre superficies.

### 2.1 Módulo único (`georeferencing/stats.py`)
- ✅ Funciones puras y documentadas (`georeferencing/metrics.py`), usadas por
  portada, área personal, rankings, diplomas y `/.well-known/stats.json`:
  - `contributions(user=None, since=None)` → GeoAttempt DONE.
  - `control_points(...)`, `time_spent(...)`.
  - `participants()` → usuarios con email verificado (la única definición de
    "usuarios").
  - `active_users(days)` → distinct en `GeoAttemptsByUserByDay`.
  - `global_rank(user, metric)` → verificados, `>` estricto + 1, empates
    comparten puesto.
- ✅ Agregados globales cacheados 5 min en Redis.

### 2.2 Sustituir cálculos locales
- ✅ `frontend/views.index` (bucle Python sobre `controlPoints`, duración).
- ✅ `user_profile/views.user_view`: eliminado el contexto muerto
  (`unified_ranking`, `avg_*`, los tres `order_by` que cargan todos los
  perfiles) y usar el módulo.
- ✅ `georeferencing/views.PendingGeoAttemptView` (`user_stats`): sin el
  "competidor anónimo"; rangos sobre la población verificada.
- ✅ Overlay de resultado: `rank.global` con la misma regla que `/api/v1/ranking/`.
- ✅ Diplomas: `total_contributors` y rango con la misma regla.
- ✅ Rankings de países y equipos: misma población (verificados; ocultos
  cuentan sin nombrarse).

### 2.3 Privacidad
- ✅ `/api/v1/challenges/<pk>/` top-50: nombre `null` si el perfil es oculto.
- ✅ `MyChallengeView.leader` y `my_gap` anonimizados. `/verify/<code>/` se
  deja: el código lo comparte el propio titular, mostrar su nombre es el fin.

### 2.4 Pequeños fallos de cálculo
- ✅ Calendario (`GeoAttemptsCalendarView`): aritmética de fechas segura.
- ✅ Racha: `metrics.streak` compartida por overlay y área personal.
- ✅ `Batch.get_percentage_remaining` → `get_percentage_done`.

**Criterio de salida:** el mismo número para "tareas", "CP" y "usuarios" en
portada, área personal, ranking, diploma y JSON público, verificado con un test
que los compare.

---

## Fase 2.5 — Visualización de estadísticas 🔧 (2.5.2 y 2.5.3 hechas; portada en Fase 3)

Principio: organizar por la pregunta del visitante, no por el tipo de dato.
Tres preguntas, tres formas distintas; solo la segunda lleva tabs.

### 2.5.1 "¿Cómo va el proyecto?" → portada
- ✅ Una sola sección de plataforma: 4 números, gráfica de fotos localizadas por
  semana y enlace a `/ranking/` (hecho en Fase 3).
- ✅ Duplicidad eliminada: el hero ya no lleva KPIs.
- ✅ Los números salen del módulo único de la Fase 2, cacheados 5 min.

### 2.5.2 "¿Quién está contribuyendo?" → `/ranking/` (público)
- ✅ Página `/ranking/` en `frontend` (`ranking.html`), sin login. El widget
  AJAX salió de `user.html`; allí queda una tarjeta "Eres el #N de M" con
  enlaces a la fila propia.
- ✅ Estructura implementada:
  ```
  totales de plataforma (cabecera)
  [ Personas ] [ Equipos ] [ Países ]        Todo · 30d · 7d
  tabla: # · nombre · CP · tareas · tiempo
  fila fija "tu posición #N" + botón "ir a mi fila" (si logueado)
  ```
- ✅ URL por tab y periodo: `/ranking/`, `/ranking/teams/`, `/ranking/countries/`
  con `?period=all|month|week&ordering=cp|tasks|time` y `?focus=me` para
  aterrizar en la fila propia (la página reescribe la URL al cambiar de estado).
  Pendiente: enlazarla desde el overlay de resultado y los diplomas.
- ✅ Las tres tablas comparten componente y población (verificados; ocultos
  cuentan sin nombre).
- ✅ Periodos 7d/30d ordenables por CP y tiempo: `controlPoints` y `seconds`
  en `GeoAttemptsByUserByDay` (migración 0058), rellenados con
  `reconcile_counters --apply` (434 filas). Países y equipos también dan CP por
  periodo.
- ✅ Móvil: la tabla pierde la columna de tiempo por debajo de 640 px.
- ✅ Barra y pie enlazan "Ranking" → `/ranking/`. El pie enlaza `/contact` en
  vez del formulario roto de portada.

### 2.5.3 "¿Cómo voy yo?" → área personal (`/user-profile/`)
- ✅ Sigue siendo un panel; no es tab del ranking.
- ✅ Las tarjetas de puesto enlazan a `/ranking/?ordering=…&focus=me`.
- ✅ Widget sustituido por la tarjeta "Eres el #N de M por puntos de control".
- ✅ Contexto muerto eliminado (Fase 2).

### 2.5.4 Lo que se queda donde está (contextual)
- ⚠️ Clasificación de un reto en su detalle y miembros en la página del equipo
  siguen con sus propias tablas; unificar con el componente de 2.5.2 queda
  como mejora menor.

### 2.5.5 Perfil público `/u/<username>/` (opcional, recomendado)
- ⏳ Página ligera: números, insignias, equipo, retos. Respeta `visible=False`
  (404 o anonimizado). Da destino a los nombres del ranking y a los diplomas,
  que hoy son un callejón sin salida.

**Criterio de salida:** `/ranking/` accesible sin login, con el mismo número que
portada y área personal para cada métrica; el overlay de resultado enlaza a la
fila del usuario.

---

## Fase 3 — Portada y flujo de participación 🔧

### 3.1 Portada (`frontend/templates/index.html`, `frontend/views.index`)
- ✅ Hero con una sola acción principal: **Participa** → `/gettask`. Secundaria:
  "Ver cómo funciona" (vídeo). Debajo, una línea que dice cuántos retos hay
  abiertos o que todo va a la cola general.
- ✅ Sección de retos siempre visible, con explicación de qué es un reto y un
  bloque vacío cuando no hay ninguno abierto.
- ✅ Sección "Available Batches" y enlaces "Batches" eliminados de portada,
  barra y pie. `/gettask/<batch>` sigue funcionando para enlaces antiguos.
- ✅ Una sola sección de estadísticas: 4 números, gráfica de fotos localizadas
  por semana (12 semanas) y enlace a `/ranking/`. El hero ya no lleva KPIs.
- ✅ Formulario de contacto fuera de la portada; el pie enlaza `/contact`.

### 3.2 Pantalla de trabajo (`gettask.html`, `main.js`, `challenge_banner.js`)
- ✅ "Join one" apunta a `/#challenges-section`.
- ✅ Mensajes 409/404 sin la palabra "batch": "Tu reto no tiene tareas
  pendientes" con Ver reto / Ver retos / Inicio. El bypass "seguir sin reto"
  sigue siendo salir del reto desde su página.
- ⏳ Mostrar el contexto de trabajo en la barra: reto activo o "Cola general"
  (cadena `general_queue` ya disponible en `LAN_I18N`; falta pintarla en
  `challenge_banner.js` cuando no hay reto).
- ✅ `MyChallengeView` devuelve `enrolled: false` si el reto ha terminado
  (banner, chip y filtro dejan de usarlo). Un reto futuro sigue pintándose
  como inscrito, con la pastilla "Empieza en…".
- ⚠️ Cadenas fijas: `challenge_banner.js` y `challenge_card.js` pasan por
  `LAN_I18N`. Pendiente `result_overlay.js`.

### 3.3 Retos
- ✅ Unirse a un reto futuro o pausado sigue permitido (preinscripción), pero
  la tarjeta muestra la pastilla "Inscrito" en vez de "Continuar"; solo un
  reto activo lleva a `/gettask`. Los enlaces ya no llevan el batch en la URL.
- ✅ Aviso previo (`confirm`) al unirse a otro reto estando inscrito.
- ✅ "Región" en tarjeta y detalle cuando hay bbox; "General" pasa a "Todas
  las fotos" y "Batch" a "Conjunto de fotos".
- ✅ `participants_count` cuenta solo inscripciones activas (portada, detalle y
  API). `total_cp` sigue sumando a quien se fue: sus puntos se ganaron dentro.
- ⏳ Decidir el reto permanente por defecto ("Cola general") y crearlo.
  **Pendiente de decisión**: nombre, objetivos y texto. Propuesta: no crearlo
  como reto; "Participa" ya sirve la cola general y la portada lo dice.

### 3.4 Navegación
- ✅ Barra: Inicio · Retos · Equipos · Ranking · Participa · (Control, staff).
  "Equipos" → `/ranking/teams/` hasta que exista el listado de equipos.
- ✅ Menú móvil: botón hamburguesa que despliega la navegación bajo la barra.
- ✅ Pie coherente con la barra.
- ✅ Manual: sección de batches reescrita como "De dónde salen las fotos",
  reglas de retos actualizadas, FAQ del filtro corregida, sección de equipos.

**Criterio de salida:** un visitante nuevo llega a su primera tarea en un clic
desde la portada, y entiende qué es un reto antes de unirse. Medir en `/stats/`:
% de contribuciones dentro de reto, tutorial completado, altas → primera
contribución.

---

## Fase 4 — Equipos ✅ (salvo traducciones a 7 idiomas y tests extra)

### 4.1 Entradas
- ✅ Enlace "Equipos" en barra y pie → `/teams/`.
- ✅ Página `/teams/` con listado (ordenado por PC del equipo), buscador,
  formularios de crear (nombre, descripción, abierto/cerrado) y unirse por
  código, tarjeta "Tu equipo".
- ✅ Invitación por URL: `/teams/join/?code=…` muestra confirmación (con aviso
  si se abandona otro equipo) y el POST une. La página del equipo ofrece el
  enlace con botón de copiar.
- ⚠️ Bloque "Tu equipo" en el overlay de resultado (+PC, tuyos para el equipo,
  total). Falta en el banner de la pantalla de trabajo.

### 4.2 Gestión para el propietario
- ✅ Panel del propietario en la página del equipo: editar nombre, descripción
  y privacidad, nuevo código, expulsar, transferir propiedad, borrar (solo si
  está vacío).
- ✅ Al salir el propietario, hereda el miembro más antiguo.
- ✅ Creación con control abierto/cerrado (por defecto cerrado si no se marca;
  el formulario del área personal crea abiertos).

### 4.3 Puntuación
- ✅ Puntuación por aportación: cada membresía guarda los contadores del perfil
  al entrar (`baseline_*`) y aporta la diferencia; al salir la diferencia se
  guarda (`banked_*`) y se queda en el equipo. Reinscribirse toma una base
  nueva. Periodos 7/30 d: tabla diaria desde la fecha de ingreso.
- ✅ Solo puntúan miembros verificados; los ocultos cuentan sin nombre.
- ✅ "Miembros" = membresías activas en API y página.

### 4.4 Endurecimiento y acabado
- ✅ `next` validado con `url_has_allowed_host_and_scheme` en todas las vistas.
- ✅ `IntegrityError` capturado al crear.
- ✅ `team_detail.html`, `team_list.html` y `team_join_confirm.html` sobre
  `_legal_base.html` con componentes `ds-*`.
- ⚠️ Castellano completo para equipos. Faltan los otros 7 idiomas.
- ✅ `teams/` en git.
- ✅ Tests: puntuación (base, banco, reinscripción, sin verificar), ranking por
  periodo desde la fecha de ingreso, enlace de invitación, `next` validado,
  herramientas del propietario, herencia, ocultos.

**Criterio de salida:** al menos un equipo con 3 miembros creado por usuarios
reales en las dos semanas siguientes al lanzamiento. Anotar el lanzamiento como
evento en `/stats/`.

---

## Fase 5 — Panel de control (segunda pasada) ✅

- ✅ Evolución en vez de datos estáticos. Selector de rango 7 d / 30 d / 1 año /
  4 años con agrupado automático (día / día / semana / mes). Seis gráficas:
  contribuciones (registradas vs anónimas + acumulado), altas (+ acumulado),
  activos (por periodo y rodantes 7/30 d), cola de trabajo (pendientes,
  asignadas, imágenes), cuentas (verificadas, newsletter, registradas) y
  comunidad (altas en retos y equipos, inscritos, equipos). Eventos como
  marcas verticales en todas. Tarjetas con el total del rango y la variación
  respecto al rango anterior.
- ✅ Decisión RRD: no. Dos tipos de métrica. Las de **hecho** (contribuciones,
  altas, actividad, altas en retos/equipos) se recalculan desde sus fechas en
  SQL, así las correcciones de datos corrigen las gráficas. Las de **estado**
  (pendientes, equipos, newsletter…) se fotografían una vez al día en
  `DailyMetric` (`georeferencing/timeseries.py`), escritas por el job de
  medianoche con red de seguridad horaria. Relleno retroactivo desde 2024-10
  de lo reconstruible (hechas y pendientes acumuladas, registrados, imágenes,
  activos 7/30, inscritos en retos y equipos): 5808 filas.
- ✅ Endpoint `/stats/series.json?range=` (staff) cacheado 5 min.
- ✅ Retención por cohortes: semanales en 7 d / 30 d, mensuales en 1 / 4 años.
  Por cohorte: altas, % que contribuyó alguna vez, % en el primer periodo y %
  activo en cada uno de los 4 periodos siguientes (celdas vacías si el periodo
  no ha terminado). **Hallazgo**: las cohortes de mayo a julio de 2026 suman
  3625 altas con 0–3 % de contribución; parece registro automatizado. Revisar
  (captcha en el alta, limpieza de cuentas sin verificar).
- ✅ Eventos automáticos: crear reto (`clone_challenge`), batch completado
  (`_finalize_if_last`), envío de newsletter (`send_bulk_email`).
- ✅ Bloque de equipos en el panel: total, miembros, % de usuarios activos en
  un equipo, top 10.

---

## Añadido 2026-10-03 — Mapa de fotos localizadas ✅

- ✅ Mapa en la portada (`#map-section`, enlace "Mapa" en barra y pie): todas
  las fotos localizadas como puntos (centroide de sus puntos de control), con
  agrupación, fondo Esri Dark Gray + luces nocturnas (VIIRS propias / NASA
  Black Marble, fundidas con `mix-blend-mode: screen`), y popup con miniatura,
  fecha, nº de contribuciones, enlace a la NASA y aviso si aún tiene tareas
  pendientes. Sin datos personales. Se descartó una página `/map/` aparte para
  no mantener dos vistas de lo mismo.
- ✅ Datos en `/map/data.geojson` (`georeferencing/mapdata.py`, caché 10 min),
  `?challenge=<id>` filtra por reto, `?mine=1` marca las propias.
- ✅ Componente `located_map.js` reutilizado en el detalle de reto (recortado a
  su región, con la bbox dibujada) y en el área personal (solo mis fotos;
  sustituye al mapa anterior y sus llamadas a Nominatim por cada popup).
- ✅ "Mapa" en barra y pie.
- ⏳ Segunda vuelta: huella aproximada por foto (envolvente de sus puntos) al
  acercarse; capa de calor para ver dónde faltan manos. Guardar el GeoTIFF al
  enviar si algún día se quiere superponer la foto real (~2 MB/contribución).

## Carga de fotos 2026-10-03 ✅

- ✅ `import_task_list`: una llamada a la API por misión y tabla (160 tablas,
  32 misiones, caché en `media/nasa_cache`), resolución local, contraste con el
  CSV, descargas en paralelo, reejecución segura, IPv4 forzado.
- ✅ Importadas 3573 fotos nuevas (×5 réplicas): ISS047-ISS056 1136 (36 de día
  descartadas), ISS057 2112, ISS046 +8, "Easy ones" +347. Cero fallos de
  descarga, cero sin resolver. 18 GB en `media/original`.
- ✅ `enrich_images`: 2328 fotos antiguas completadas desde la caché (cámara
  2326, nadir 2323, focal 400, centro catalogado 133, centro ML 52).
- ✅ Retos nuevos: Europe / Spain / France 2026-27 (clonados), Poland y Brazil
  2026-27 (solo región). Brazil tiene 24 fotos: pendiente de alimentarlo.
- 🔧 **Catálogo NASA propio** (`NasaPhoto`, migración 0060): una fila por foto
  de cada misión con fichero, nadir, centro catalogado, centro ML, hora, cámara,
  focal, inclinación, rasgos NASA, nubosidad, región, elevación solar (NASA y
  calculada), noche (≤ −6°), nivel de dificultad A/B/C/D y enlace a nuestra
  `Image` con tareas hechas/pendientes. Comandos: `fetch_nasa_cache` (tablas
  por misión), `sync_nasa_catalog` (caché → tabla), `nasa_catalog_report`
  (informe por misión, CSV), `import_from_catalog` (selección por misión /
  noche / focal / nivel / región / sin ráfagas → `Image` + ficheros + tareas).
  En curso: descarga de ISS001-ISS080 y sincronización. Pendiente: bloque en
  el panel de control y clasificación de miniaturas (ciudades / estrellas /
  limbo) con muestra revisada a mano.
- ✅ Limpieza del 2026-10-03 (tarde): `dedupe_images --apply` fusionó 212 filas
  duplicadas de `Image` (196 tareas con trabajo movidas a la fila principal,
  559 pendientes sobrantes borradas, 299 estados corregidos); `park_bursts
  --apply` aparcó 4628 fotos de ráfaga (ISS057 2020, ISS046 1326,
  ISS047-ISS056 911, Easy ones 371), 23.140 tareas pendientes menos. Copias en
  `gdalface-backups/image_geoattempt_before_dedup_20261003.sql.gz`.
  **Hallazgo**: las 2112 de ISS057 eran un time-lapse a 1 foto/s y 9 km entre
  fotogramas; con 85 mm el encuadre es de ~180 km. Regla adoptada: dentro de
  una ráfaga (< 20 s entre fotogramas, misma focal) se conserva un fotograma
  cada medio encuadre (36 mm / focal × 420 km). Aplicada también en
  `import_from_catalog`.
- ✅ Datos de abandono por nivel (imágenes cargadas antes de hoy): nivel A 0,9
  saltos por tarea hecha y 15 % sin tocar; nivel C 5,9 saltos por hecha y 47 %
  sin tocar, con la misma focal. El punto de partida fiable decide; la focal
  apenas. Decisión: cargar A (validación) y B (centro ML, 60.757 nocturnas
  aprovechables sin cargar, 7.334 sin ráfagas); C aparcado hasta que la
  herramienta muestre la zona probable.
- 🔧 **Piloto cargado el 2026-10-03** (aprobado): batch "Validation A", 300
  fotos de nivel A (misiones ≥ ISS030, al azar, una por celda de 1°); batch
  "ISS066", nivel B sin ráfagas (~988); batch "ISS045", nivel B sin ráfagas
  (~1208). Todas nocturnas, focal ≥ 50 mm, 5 réplicas.

  **Revisión: 2026-10-17** (dos semanas), en `/stats/` → "Batch health":
  - ¿Se trabajan? `Done 7d` > 0 y `Untouched` bajando en los tres batches.
  - ¿Se abandonan? `Skips / done` por debajo de 2 en A y B (los de nivel C de
    la mañana están entre 4 y 6). Si B supera 3, el centro ML no está
    ayudando lo suficiente: revisar cómo se presenta en la herramienta.
  - ¿Acierta la gente? `Accuracy` en "Validation A": mediana de km entre el
    centroide de la comunidad y el centro NASA. Referencia esperada: < 30 km.
    Si sale > 100 km, hay un problema de herramienta o de instrucciones, no
    de voluntarios.
  - Comparar con los batches antiguos en la misma tabla (ISS046, ISS057).
  Si los tres criterios se cumplen: siguiente tanda de B (ISS072, ISS047,
  ISS065) con la misma regla, 1000-1500 fotos cada una, y dejar la cola en
  pocas semanas de trabajo.
- ✅ **Motivo de salto** (2026-10-03): al pulsar Saltar se elige en un clic
  "no es de noche / no se ven ciudades / demasiado difícil / problema con la
  imagen / saltar sin más" (`SkipReason`). Se ve por batch en "Batch health".
  `park_by_votes` aparca fotos con ≥ 2 votos de no-noche / sin-ciudad /
  imagen-mala y sin trabajo hecho; **en modo informe** hasta la revisión del
  2026-10-17: entonces mirar los votos y, si son coherentes, pasarlo a
  `--apply` y programarlo semanal.
- ⏳ Repartidor: servir A y B primero a quien empieza; C a quien tiene recorrido.
- ⏳ Las 36 fotos de día del zip quedan fuera a propósito.

## Pendiente de infraestructura — IPv6 sin salida (detectado 2026-10-03) ⏳

El servidor tiene dirección y ruta IPv6 (`2001:41d0:306:28b4::/64`, default vía
`2001:41d0:306:28ff:ff:ff:ff:ff`) pero el tráfico IPv6 no llega a destino:
`curl -6 https://eol.jsc.nasa.gov/` falla y `curl -4` responde al instante. Los
servidores de la NASA son dual-stack y Python (`requests`/`urllib3`) prueba la
IPv6 primero y espera el timeout completo en cada conexión antes de caer a IPv4.
Consecuencias observadas: descargas de imágenes a 4/min en vez de 90/min, y los
`API_ERROR` del pipeline de batches (`georeferencing/tasks.py`) y de
`download_image` en los workers de RQ.

- ✅ Parche local: `import_task_list` fuerza IPv4 (`allowed_gai_family`).
- ⏳ **Recomendación**: arreglarlo a nivel de sistema, con una de estas dos:
  1. Dar salida IPv6 real al servidor (revisar con el proveedor la ruta por
     defecto / el firewall).
  2. Preferir IPv4 en la resolución de nombres: en `/etc/gai.conf` añadir
     `precedence ::ffff:0:0/96  100`. Afecta a todos los procesos del host sin
     tocar código. Después, comprobar que `python -c "import requests;
     print(requests.get('https://eol.jsc.nasa.gov/', timeout=10).status_code)"`
     responde en menos de un segundo.
- ⏳ Tras el arreglo, quitar el parche local y aplicar el mismo criterio (o
  ninguno) en `tasks.py`.

## Glosario de estados (para no perder la información)

- **Imagen en cola**: tiene al menos una tarea `PENDING`; puede tocarle a
  cualquiera que pulse Participar (filtrada por su reto si está inscrito).
- **Imagen completada**: sus `replicas` tareas están `DONE` (hoy 5).
- **Imagen aparcada**: `replicas = 0`. Sigue en la base de datos con sus
  ficheros, sin tareas pendientes, nunca se sirve. Motivos: fotograma de
  ráfaga redundante (`park_bursts`), registro NASA inconsistente (nivel X),
  votos de salto "no es de noche / sin ciudad / imagen mala" (`park_by_votes`,
  aún en modo informe). El trabajo hecho o asignado nunca se borra al aparcar.
  Reversible: devolver réplicas y crear tareas. Se ve en "Batch health" →
  columna Parked.
- **Nivel (tier) del catálogo**: A centro catalogado · B centro ML · C solo
  nadir con focal ≥ 50 mm · D solo nadir con gran angular/oblicua · X registro
  catalogado inconsistente (centro a > 2.500 km del nadir) · '' sin coordenadas.
- **Ráfaga**: fotogramas consecutivos de la misma misión y focal con < 20 s
  entre ellos; se conserva uno cada medio encuadre (36 mm / focal × 420 km).
- **Noche**: elevación solar calculada ≤ −6° (campo `sun_elev` en el catálogo;
  el umbral es una decisión, el valor se guarda).

## Pendiente a 2026-10-03 (cierre del día)

Decisiones: IPv6 del servidor · reto permanente (propuesta: no) · aparcar las
702 fotos de nivel C que siguen en cola · revisión del piloto el 2026-10-17.
Tareas: repartidor por nivel (A/B primero a quien empieza) · "Cola general" en
la barra de tarea e i18n del overlay · traducciones a los otros 7 idiomas ·
equipo en el banner de tarea · perfil público opcional · huella y calor en el
mapa · `print(request.data)` solo tras tener un log estructurado de envíos.

## Orden y dependencias

```
Fase 1 (integridad) ──► Fase 2 (definiciones) ──► Fase 2.5 (/ranking/, portada)
                                                        ├─► Fase 3 (flujo, navegación)
                                                        └─► Fase 4 (equipos)
Fase 5 cuando haya datos de 3 y 4.

La Fase 2.5 es donde se materializa "una definición por métrica": la página de
ranking es el consumidor de referencia del módulo de la Fase 2.
```

Los enlaces rotos y el formulario de contacto (3.1, 3.2) son media hora y
pueden hacerse en cualquier momento.

## Hecho en esta revisión ✅

- ✅ Panel de control staff en `/stats/` con personas, contribuciones, cola,
  retos, salud, onboarding y eventos anotables (`StatsEvent`).
- ✅ Métricas de actividad añadidas al JSON público.
- ✅ Bug de portada: `Sum` local hacía sombra al global y "Time invested" salía
  siempre 0.
