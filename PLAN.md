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

## Fase 1 — Integridad de datos 🔧 (queda 1.3 y el historial de inscripción)

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
- ⏳ Añadir historial de inscripción (`ChallengeEnrollmentPeriod`: participant,
  joined_at, left_at) escrito por join/leave. Con eso la regla es exacta y
  `--challenges` puede pasar a ser el comportamiento por defecto.
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
- ✅ Snapshot público parado desde 2026-09-28: worker y scheduler corren y el
  job encolado a mano funciona. El cron de medianoche no se disparó el 2 ni el
  3 de octubre; causa sin determinar. Red de seguridad añadida: el job horario
  regenera el snapshot si tiene más de 24 h.
- ✅ El tutorial nunca emitía `completed`: driver.js ya ha vaciado `state` cuando
  llama a `onDestroyed`, así que `activeIndex` era `undefined` y todo acababa
  como `dismissed` en el paso 1. `tutorial.js` recuerda ahora el último paso
  resaltado. Verificar en `/stats/` que empiezan a llegar completados.

**Criterio de salida:** `reconcile_counters` (dry-run) devuelve cero diferencias
dos semanas seguidas. Estado 2026-10-03: 0 en perfiles y diario; retos
pendientes del historial de inscripción.

---

## Fase 2 — Una definición por métrica ⏳

### 2.1 Módulo único (`georeferencing/stats.py`)
- ⏳ Funciones puras y documentadas, usadas por portada, área personal,
  rankings, diplomas, `/stats/` y `/.well-known/stats.json`:
  - `contributions(user=None, since=None)` → GeoAttempt DONE.
  - `control_points(...)`, `time_spent(...)`.
  - `participants()` → usuarios con email verificado (la única definición de
    "usuarios").
  - `active_users(days)` → distinct en `GeoAttemptsByUserByDay`.
  - `global_rank(user, metric)` → verificados, `>` estricto + 1, empates
    comparten puesto.
- ⏳ Cachear los agregados globales 5 min en Redis (hoy la portada recorre toda
  la tabla de GeoAttempt en cada visita).

### 2.2 Sustituir cálculos locales
- ⏳ `frontend/views.index` (bucle Python sobre `controlPoints`, duración).
- ⏳ `user_profile/views.user_view`: eliminar el contexto muerto
  (`unified_ranking`, `avg_*`, los tres `order_by` que cargan todos los
  perfiles) y usar el módulo.
- ⏳ `georeferencing/views.PendingGeoAttemptView` (`user_stats`): quitar el
  "competidor anónimo" (`assignedUser=None`) del ranking de tareas.
- ⏳ Overlay de resultado: `rank.global` con la misma regla que `/api/v1/ranking/`.
- ⏳ Diplomas: `total_contributors` y rango con la misma regla.
- ⏳ Rankings de países y equipos: aplicar el mismo filtro de verificados y
  `visible` que el ranking de usuarios.

### 2.3 Privacidad
- ⏳ `/api/v1/challenges/<pk>/` devuelve top-50 con nombres aunque
  `visible=False`. Filtrar o eliminar el campo.
- ⏳ `MyChallengeView.leader`, `my_gap` en detalle de reto y `/verify/<code>/`
  muestran usuarios ocultos. Anonimizar.

### 2.4 Pequeños fallos de cálculo
- ⏳ Calendario (`GeoAttemptsCalendarView`): falla en diciembre
  (`month+1`) y el 29 de febrero.
- ⏳ Racha: unificar la tolerancia a "hoy vacío" entre overlay y área personal.
- ⏳ `Batch.get_percentage_remaining` devuelve % hecho; renombrar.

**Criterio de salida:** el mismo número para "tareas", "CP" y "usuarios" en
portada, área personal, ranking, diploma y JSON público, verificado con un test
que los compare.

---

## Fase 2.5 — Visualización de estadísticas ⏳

Principio: organizar por la pregunta del visitante, no por el tipo de dato.
Tres preguntas, tres formas distintas; solo la segunda lleva tabs.

### 2.5.1 "¿Cómo va el proyecto?" → portada
- ⏳ Una sola sección de plataforma: 3-4 números (CP, tareas, participantes,
  activos 30d) y una gráfica de contribuciones por semana. Enlace a `/ranking/`.
- ⏳ Eliminar la duplicidad actual (KPIs del hero + sección de estadísticas).
- ⏳ Los números salen del módulo único de la Fase 2, cacheados 5 min.

### 2.5.2 "¿Quién está contribuyendo?" → `/ranking/` (público)
- ⏳ Página nueva en `frontend`, sin login. Mover aquí el widget AJAX que hoy
  vive en `user_profile/templates/user.html` (pestañas Usuarios / Países /
  Equipos). Un ranking que exige login no motiva.
- ⏳ Estructura:
  ```
  totales de plataforma (cabecera)
  [ Personas ] [ Equipos ] [ Países ]        Todo · 30d · 7d
  tabla: # · nombre · CP · tareas · tiempo
  fila fija "tu posición #N" + botón "ir a mi fila" (si logueado)
  ```
- ⏳ URL por tab y periodo: `/ranking/`, `/ranking/equipos/`, `/ranking/paises/`,
  con `?periodo=30d|7d`. Enlazables desde overlay de resultado, diploma,
  correos y área personal; `#me` o `?focus=me` lleva a la fila propia.
- ⏳ Las tres tablas usan el mismo componente (columnas, empates, tratamiento de
  perfiles ocultos) y los mismos filtros (verificados, `visible`).
- ⏳ Periodos 7d/30d ordenables por CP y tiempo: añadir `controlPoints` y
  `seconds` a `GeoAttemptsByUserByDay` (hoy solo tareas). Rellenar con el
  comando de reconciliación de la Fase 1. Abre la puerta a retos semanales.
- ⏳ Móvil: tabs como `ds-segmented`; la tabla pierde la columna de tiempo.
- ⏳ Los enlaces "Estadísticas" de barra y pie apuntan aquí, no a un ancla de
  la portada.

### 2.5.3 "¿Cómo voy yo?" → área personal (`/user-profile/`)
- ⏳ Sigue siendo un panel (números, racha, calendario, insignias, retos,
  equipo), no una tabla. No se convierte en tab del ranking.
- ⏳ Cada número personal lleva su puesto al lado y enlaza a su fila en
  `/ranking/…?focus=me`.
- ⏳ El widget de ranking desaparece de aquí, sustituido por una tarjeta
  "Puesto 41 de 136 · ver ranking".
- ⏳ Eliminar el contexto muerto y los tres `order_by` que cargan todos los
  perfiles (ver 2.2).

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

## Fase 3 — Portada y flujo de participación ⏳

### 3.1 Portada (`frontend/templates/index.html`, `frontend/views.index`)
- ⏳ Hero con una sola acción principal: **Participa** → `/gettask`. Secundaria:
  "Ver cómo funciona" (vídeo).
- ⏳ Sección de retos como única capa de elección. Si no hay retos abiertos,
  mostrar un bloque explicativo, no ocultar la sección (hoy el hero enlaza a un
  ancla que no se renderiza).
- ⏳ Eliminar la sección "Available Batches" y los enlaces "Batches" de barra y
  pie. Los batches se gestionan desde admin y se exponen, si hace falta, como
  retos permanentes.
- ⏳ Una sola sección de estadísticas, según 2.5.1 (hoy hay KPIs en el hero y
  otra sección con los mismos números bajo etiquetas distintas).
- ⏳ Quitar el formulario de contacto de la portada (envía a `/`, que responde
  405) y enlazar `/contact` desde el pie.

### 3.2 Pantalla de trabajo (`gettask.html`, `main.js`, `challenge_banner.js`)
- ⏳ Arreglar el enlace "Join one" → `/challenges/` (404). Apuntar a
  `/#challenges-section` o crear la página de listado.
- ⏳ Mensajes de error 409/404 sin la palabra "batch". Si el reto no tiene
  tareas, ofrecer "Seguir sin reto" (hoy el comentario del código promete un
  bypass que no existe).
- ⏳ Mostrar el contexto de trabajo en la barra: reto activo o "Cola general".
- ⏳ `MyChallengeView` debe comprobar estado del reto: una inscripción a un reto
  finalizado o futuro no debe pintarse como activa.
- ⏳ Cadenas en inglés fijo en `challenge_banner.js`, `result_overlay.js`,
  `challenge_card.js`: pasar por i18n.

### 3.3 Retos
- ⏳ No permitir unirse a retos futuros o pausados, o permitirlo pero sin botón
  "Continuar" y con aviso de que el trabajo no cuenta hasta que empiece.
- ⏳ Aviso previo al sustituir una inscripción activa (hoy se entera después).
- ⏳ Mostrar la región (bbox) en tarjeta y detalle cuando exista.
- ⏳ `participants_count` y `total_cp` en tarjetas: decidir si incluyen a quien
  se fue y etiquetarlo.
- ⏳ Decidir el reto permanente por defecto ("Cola general") y crearlo.

### 3.4 Navegación
- ⏳ Barra: Inicio · Retos · Equipos · Participa · Ranking · (Control, staff).
  "Ranking" → `/ranking/` (2.5.2), no a un ancla de portada.
- ⏳ Menú móvil (hoy `.ds-nav` desaparece a ≤768 px sin alternativa).
- ⏳ Pie coherente con la barra.
- ⏳ Manual: eliminar referencias a botones que no existen ("Get a task in this
  batch", salir del reto desde la tarjeta) y añadir sección de equipos.

**Criterio de salida:** un visitante nuevo llega a su primera tarea en un clic
desde la portada, y entiende qué es un reto antes de unirse. Medir en `/stats/`:
% de contribuciones dentro de reto, tutorial completado, altas → primera
contribución.

---

## Fase 4 — Equipos ⏳

### 4.1 Entradas
- ⏳ Enlace "Equipos" en barra y pie.
- ⏳ Página `/teams/` con listado de equipos abiertos, buscador, botón crear.
- ⏳ Invitación por URL: `/teams/join/?code=…` (GET que muestra confirmación y
  POST que une). Hoy unirse es solo POST desde el área personal.
- ⏳ Bloque "Tu equipo" en el overlay de resultado y en el banner de la
  pantalla de trabajo.

### 4.2 Gestión para el propietario
- ⏳ Editar nombre y descripción, abrir/cerrar, rotar código de invitación,
  expulsar miembro, transferir propiedad, borrar equipo. Hoy todo esto solo se
  puede hacer desde admin.
- ⏳ Al salir el propietario, transferir al miembro más antiguo o cerrar el
  equipo.
- ⏳ El formulario de creación no envía `is_open`, así que todos los equipos
  nacen abiertos; añadir el control.

### 4.3 Puntuación
- ⏳ Contar solo contribuciones posteriores a `joined_at` (hoy un miembro trae
  todo su historial y se lo lleva al irse). Requiere calcular desde
  `GeoAttempt`/`GeoAttemptsByUserByDay` con filtro de fecha, no desde el
  perfil.
- ⏳ Aplicar filtros de verificado y `visible` como en el resto de rankings.
- ⏳ Unificar "miembros" (hoy memberships en la API y perfiles en la página).

### 4.4 Endurecimiento y acabado
- ⏳ Validar `next` en `join_team` con `url_has_allowed_host_and_scheme`
  (redirección abierta).
- ⏳ Capturar `IntegrityError` o restricción case-insensitive al crear.
- ⏳ Reescribir `team_detail.html` con componentes `ds-*` (hoy Bootstrap e
  inline styles) y quitar `lang="en"` fijo.
- ⏳ Traducir cadenas de equipos en los 8 `.po` y limpiar los fuzzy erróneos
  ("Create a team" → "Crear una cuenta").
- ⏳ Añadir `teams/` a git.
- ⏳ Tests: periodos 7d/30d, visibilidad, rango en página de equipo, tarjeta
  del perfil.

**Criterio de salida:** al menos un equipo con 3 miembros creado por usuarios
reales en las dos semanas siguientes al lanzamiento. Anotar el lanzamiento como
evento en `/stats/`.

---

## Fase 5 — Panel de control (segunda pasada) ⏳

- ⏳ Retención por cohortes semanales: altas → primera contribución → activos a
  4 semanas.
- ⏳ Eventos automáticos: crear reto, cargar batch, enviar newsletter.
- ⏳ Bloque de equipos cuando haya datos.
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
