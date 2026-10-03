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
- ⏳ Una sola sección de plataforma: 3-4 números (CP, tareas, participantes,
  activos 30d) y una gráfica de contribuciones por semana. Enlace a `/ranking/`.
- ⏳ Eliminar la duplicidad actual (KPIs del hero + sección de estadísticas).
- ⏳ Los números salen del módulo único de la Fase 2, cacheados 5 min.

### 2.5.2 "¿Quién está contribuyendo?" → `/ranking/` (público)
- ✅ Página `/ranking/` en `frontend` (`ranking.html`), sin login. El widget
  AJAX salió de `user.html`; allí queda una tarjeta "Eres el #N de M" con
  enlaces a la fila propia.
- ⏳ Estructura:
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
- ⏳ Clasificación de un reto en su página de detalle; miembros en la página
  del equipo. Ambas pasan a usar el componente de tabla de 2.5.2.

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

## Fase 5 — Panel de control (segunda pasada) ⏳

- ⏳ Retención por cohortes semanales: altas → primera contribución → activos a
  4 semanas.
- ⏳ Eventos automáticos: crear reto, cargar batch, enviar newsletter.
- ⏳ Bloque de equipos en el panel cuando haya datos (hoy 0 equipos).
- ⏳ Ejecutar `reconcile_counters --dry-run` desde el panel y mostrar la deriva.

---

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
