# Lost at Night — Bug Audit

Estado actual del repo. Status legend:
- ✅ Resuelto en esta sesión
- ⚠️ Parcialmente resuelto / mitigado
- ⏳ Pendiente

Última actualización: 2026-05-03.

---

## P0 — Críticos (romper funcionalidad o seguridad)

### 1. ⏳ `visited_places` se serializa con `repr()` en vez de JSON
- **Dónde**: `user_profile/templates/user.html:991` consume `{{ visited_places|safe }}`, populado por `user_profile/views.py:248-263`.
- **Qué falla**: `|safe` aplica `str()` a una lista de dicts, produciendo repr Python (comillas simples, `None` en vez de `null`, `True/False` en mayúsculas). Cualquier nombre con apóstrofe (p.ej. `O'Brien`) rompe el literal JS y el mapa "Visited places" deja de cargar.
- **Fix**: Serializar con `json.dumps(...)` en la view, o usar `{{ visited_places|json_script:"visited-places-data" }}` y `JSON.parse(...)` en JS.

### 2. ✅ `$('.modal-title')` / `$('.modal-body')` sobreescriben el modal de info de tarea
- **Resuelto**: Creado `#alertModal` dedicado en `gettask.html` + helper `showAlert(title, body)` en `main.js`. Reemplazadas las 7 llamadas problemáticas. El branch del georeferencing-modal ahora usa selectores scopeados (`#georeferencingModal .modal-title/body`).

### 3. ⏳ `gettask(pk)` revienta con 500 si el batch no existe
- **Dónde**: `frontend/views.py:217` (`context['batch'] = Batch.objects.get(pk=pk)`).
- **Qué falla**: Visitar `/gettask/99999` lanza `Batch.DoesNotExist` no manejado.
- **Fix**: `get_object_or_404(Batch, pk=pk)`.

### 4. ✅ URL name typo: `getttask` (3 t's)
- **Resuelto**: Renombrado a `gettask_batch` en `frontend/urls.py:15` cuando se añadieron las rutas de páginas legales.

### 5. ⏳ `<dt>` huérfano en el task-info modal cuando no hay ML data
- **Dónde**: Template `frontend/templates/gettask.html:344-345`; JS `frontend/static/js/main.js:138-141`.
- **Qué falla**: Cuando `photo_center_by_machine_learning` es null, el JS oculta solo `<dd id="ti-ml-row">`; el `<dt id="ti-ml-row-dt">` "Photo center (ML)" sigue visible — label colgado sin valor.
- **Fix**: Ocultar ambos juntos: `$('#ti-ml-row, #ti-ml-row-dt').hide()`.

### 16. ⏳ Cheating check incrementa `controlPointsDone` antes de validar
- **Dónde**: `georeferencing/views.py:355-359` y `:403-413`.
- **Qué falla**: En el branch DONE, se incrementan `geoattempts_done`, `time_spent` y `controlPointsDone` ANTES del cheating check (línea 403). Si se detecta cheating, se devuelve 400 pero los counters ya están sumados — quedan inflados sin reversión.
- **Fix**: Mover el cheating check antes de las actualizaciones del UserProfile, o revertir los increments dentro del bloque cheating.

---

## P1 — Regresiones funcionales / privacidad / performance

### 6. ⚠️ i18n roto en strings inyectadas desde JS — parcialmente resuelto
- **Resuelto**:
  - `main.js` alerts (Wrong place / Few CP / Error / Thank you / All done / Challenge filter active) → vía `window.LAN_I18N` poblado por `_topbar.html` + `gettask.html`.
  - `_topbar.html` chip + `challenge_join_modals.js` modales → todos vía `LAN_I18N`.
  - `_legal_base.html` y páginas legales → 100% `{% trans %}`.
- **Pendiente**:
  - `result_overlay.js` (Submitted, Great work, +N CP, totals labels, share text…)
  - `challenge_banner.js` promo state ("active challenge(s) available", "Join one", "Sign in")
  - `challenge_detail.html` y `challenge_card.js` `alert('Could not join/leave/Network error.')`
  - `trylocal.js` (Local georeferencing…, Computing TPS warp, Map not ready, Few control points)
  - `user.html` popup HTML del visited-places ("Looking up location…", "Open ocean", "Unknown")

### 7. ⏳ N+1 en `_challenge_card.html`
- **Dónde**: `frontend/templates/_challenge_card.html:6,32` renderizado dentro de los cuatro `{% for ch in visible_challenges %}` de `index.html`. View en `frontend/views.py:162-166` solo hace `select_related('batch')`.
- **Qué falla**: Por cada tarjeta de challenge: `Sum` agregado sobre participants + `count`. Las cards se renderizan en hasta 4 secciones (active/upcoming/paused/finished). Con N challenges → 8N queries extra por home.
- **Fix**: `annotate(participants_count=Count('participants'), total_cp=Sum('participants__cached_cp_count'))` en la view.

### 8. ⚠️ N+1 en `user_view` (rankings + suma de CP en Python) — parcialmente resuelto
- **Resuelto**: La sección Ranking de `/user-profile/` ahora se carga vía AJAX desde `/api/v1/ranking/` con paginación + columnas indexadas (`controlPointsDone`, `geoattempts_done`, `time_spent` con `db_index=True`). El cómputo del rank usa `count(profiles where metric > mine)` indexado, no full scan.
- **Pendiente**: El código viejo de `user_view` (líneas 130-200) sigue construyendo `top_users` dict en Python aunque ya no se usa en el template — borrarlo. Y los loops de control points en líneas 70-72 / 220-224 (personal stats) siguen sumando en Python; pasar a `annotate(Sum)` cuando se necesite escalar.

### 9. ✅ Privacidad: usuarios `visible=False` filtran sus números en el ranking
- **Resuelto**: El nuevo endpoint `ranking_api` (y su contraparte `ChallengeLeaderboardView`) anonimiza completamente filas con `visible=False` (username, country, profile_pic_url → null). Solo el propio usuario ve sus datos cuando él mismo es invisible. Los counts numéricos quedan visibles solo cuando la fila es visible.

### 10. ⏳ `user_view` redirige anónimos a `/accounts/` (URL inválida)
- **Dónde**: `user_profile/views.py:310` aún hace `return redirect('/accounts/')`.
- **Qué falla**: Allauth sirve `/accounts/login/`, no `/accounts/`. Visitante anónimo a `/user-profile/` cae en una URL inútil.
- **Fix**: `redirect('account_login')` o `redirect(f'{settings.LOGIN_URL}?next=/user-profile/')`.

### 11. ⏳ `GeoAttemptIndividualView.delete` SIN permission_classes
- **Dónde**: `georeferencing/views.py` clase `GeoAttemptIndividualView`.
- **Qué falla**: `DELETE /api/v1/geoattempt-individual/<pk>/` no requiere autenticación ni permisos. Cualquier visitante puede borrar cualquier geo-attempt.
- **Fix**: Añadir `permission_classes = [IsAdminUser]` (o más estricto) a la clase, mínimo al método `delete`.

### 17. ⏳ `update_assigned` job: docstring dice 24 h, código usa 6 h
- **Dónde**: `georeferencing/tasks.py:15-28`.
- **Qué falla**: La docstring dice "more than 24 hours ago" pero `timedelta(hours=6)`. Operación silenciosa sin alarma — pero las tareas asignadas se reciclan 4× más rápido de lo documentado, lo cual puede agresivamente quitar tareas a usuarios que tardan en completarlas.
- **Fix**: Decidir el valor canónico (probablemente 6 h) y actualizar docstring, o relajar a 24 h si se quiere dar más margen.

### 18. ⏳ Inconsistencia camelCase / snake_case en payload de DONE/ASSIGNED
- **Dónde**: `georeferencing/views.py:270, 343` (PATCH `GeoAttemptIndividualView`).
- **Qué falla**: Branch `ASSIGNED` lee `request.data['control_points']` (snake_case), branch `DONE` lee `request.data['controlPoints']` (camelCase). Los respectivos `main.js` líneas 262 y 317 usan cada uno con el nombre correcto, pero la inconsistencia es trampa para futuro mantenimiento.
- **Fix**: Unificar a un solo naming en backend + frontend (preferir snake_case para coherencia con el resto del API).

---

## P2 — Reales pero menos urgentes

### 12. ✅ XSS potencial en `result_overlay.js`
- **Resuelto**: `result_overlay.js` reescrito completamente para el payload rico del backend. Todas las inserciones a `innerHTML` usan ahora el helper `escapeHtml(...)` (imageName, imageCaption, challenge.name, etc.).

### 13. ⏳ Pluralización inglesa vía `+ "s"` en `challenge_banner.js`
- **Dónde**: `frontend/static/js/challenge_banner.js:217-225` (estado promo: `'active challenge' + (n === 1 ? '' : 's')`).
- **Qué falla**: Solo correcto en inglés. Otros idiomas leen raro. Vinculado al pendiente i18n del bug #6.
- **Fix**: Pasar formas singular/plural por `data-attribute` desde el template (`{% blocktrans count counter=n %}`).

### 14. ⏳ Polling cada 60 s al endpoint `/api/v1/challenges/mine/` sin cache
- **Dónde**: `frontend/static/js/challenge_banner.js:8-9, 260`; backend ahora también llamado por el chip del topbar y el banner de bypass — multiplicando la presión.
- **Qué falla**: Cada poll genera ~5 queries (serialización + total_cp + participants.count + leader). Por cada usuario activo, carga sostenida sin caching.
- **Mitigación parcial**: el chip del topbar usa `sessionStorage` cache de 5 min para evitar polls duplicados entre navegaciones. Pero el banner de gettask sigue polling cada 60 s.
- **Fix**: Cachear el challenge serializado por ~60 s (Redis o `cache_page`) en el backend.

### 15. ⏳ Floats con coma decimal dentro de CSS (`|unlocalize` faltante)
- **Dónde**: `frontend/templates/index.html:867, 893` (`conic-gradient(... {{ batch.get_percentage_remaining }}% ...)` y `{{ completion_pct }}%`).
- **Qué falla**: Con locale es/fr/de, `{{ completion_pct }}` se renderiza como `12,3` en vez de `12.3`. Eso rompe el `conic-gradient` igual que en `user.html` (que ya se parcheó).
- **Fix**: Aplicar `|unlocalize` a `completion_pct` y `batch.get_percentage_remaining`.

---

## Bugs descubiertos durante el rediseño

### 19. ⏳ Regla global `button { background-color: var(--accent-color) !important; padding: 0.75rem 1.5rem !important; ... }`
- **Dónde**: `frontend/static/css/main.css:486-500`.
- **Qué falla**: La regla afecta a TODOS los `<button>` del sitio con `!important`, obligando a defenderse con `!important` en cada componente custom (cookie banner, paginator, password toggle, etc.). Cuesta tiempo de debug y arrastra deuda técnica.
- **Mitigación actual**: Cada componente nuevo añade `!important` defensivo (`.ds-pass-toggle`, `.lan-cookie__btn`, `.rk-pager-btn`, etc.).
- **Fix**: Reemplazar la regla global por una clase explícita (`.legacy-cta` o similar) y aplicarla solo donde se necesita ese estilo. Sin esto, cada nuevo botón seguirá pagando el peaje.

### 20. ✅ `Object.assign` sobre objeto literal con getters perdía la live binding
- **Dónde**: Originalmente `frontend/static/js/main.js:64-79`.
- **Qué falla**: `window.LAN = Object.assign(window.LAN || {}, { get iconList() { return iconList; } })` invocaba el getter UNA vez al copiar y guardaba el valor (array vacío inicial). Después de borrar un punto de control, `iconList = iconList.filter(...)` reasignaba la variable closure pero `window.LAN.iconList` seguía apuntando al array viejo. Resultado: el TPS local georreferenciaba con CPs ya borrados.
- **Resuelto**: Reemplazado por `Object.defineProperty(window.LAN, 'iconList', { get: ... })` para conservar el accessor vivo.

### 21. ✅ `{# ... #}` multilínea de Django se renderizaba como texto
- **Resuelto**: 3 ocurrencias migradas a `{% comment %}...{% endcomment %}` (que sí soporta multilínea). La sintaxis `{# #}` es estricta de una sola línea.

### 22. ⚠️ Fuzzy translations heredadas hacían que Django ignorara strings nuevas
- **Dónde**: Todos los `.po` files.
- **Qué falla**: `makemessages` añade `#, fuzzy` a strings nuevas que se parecen a otras antiguas. Django **ignora** `msgstr` con flag fuzzy — el resultado es que la página renderiza el msgid en inglés aunque el `.po` parezca tener traducción.
- **Mitigación actual**: Tras cada `makemessages` se corre `sed -i '/^#, fuzzy$/d'` en los 8 idiomas. Esto se ha automatizado dentro del workflow de los scripts `translate_*.py`.
- **Fix definitivo**: Añadir un Makefile o pre-commit hook que llame al deduplicador automáticamente. Documentarlo en `README.md`.

### 23. ⏳ Image.replicas: cuando se cubren todas las réplicas, los GeoAttempts pending de esa imagen no se invalidan automáticamente
- **Dónde**: Lógica de creación de tareas en `georeferencing/tasks.py` y filtrado en `PendingGeoAttemptView.get`.
- **Qué falla**: Si una imagen tiene `replicas=5` y ya hay 5 `GeoAttempt.status='DONE'`, los pending restantes asociados a esa imagen siguen siendo elegibles. Un usuario puede recibir tareas para una imagen ya cubierta — desperdicio de su tiempo.
- **Fix**: Añadir filtro al pending queryset: `pending.exclude(image_id__in=images_already_completed)`. O al llegar a las réplicas, marcar los pending sobrantes como descartados.

### 24. ⚠️ Skipped tasks pueden volver al mismo usuario (no hay registro per-user)
- **Diseño deliberado** en esta sesión: Opción A acordada (solo se excluyen por usuario las imágenes con DONE propio). Si un usuario salta una imagen, puede reaparecer. Documentar en GDPR.md/UX docs si se decide implementar Opción B (crear `UserSkippedImage` model).

---

## Archivos clave referenciados

- `frontend/static/js/main.js`
- `frontend/static/js/result_overlay.js`
- `frontend/static/js/challenge_banner.js`
- `frontend/static/js/challenge_join_modals.js`
- `frontend/static/js/challenge_card.js`
- `frontend/static/js/trylocal.js`
- `frontend/static/css/main.css`
- `frontend/static/css/design-system.css`
- `frontend/templates/gettask.html`
- `frontend/templates/_topbar.html`
- `frontend/templates/_footer.html`
- `frontend/templates/_cookie_banner.html`
- `frontend/templates/_challenge_card.html`
- `frontend/templates/index.html`
- `frontend/templates/challenge_detail.html`
- `frontend/views.py`
- `frontend/urls.py`
- `user_profile/views.py`
- `user_profile/templates/user.html`
- `georeferencing/views.py`
- `georeferencing/tasks.py`
