# Plan de revisión sistemática de traducciones

## Estado actual

8 idiomas en `locale/<lang>/LC_MESSAGES/django.po`: `de, es, fr, it, ja, pt, ru, zh_Hans`.

| Idioma | msgids | vacíos | fuzzy |
|--------|-------:|-------:|------:|
| de     |    837 |   ~423 |     6 |
| es     |    841 |   ~416 |     6 |
| fr     |    837 |   ~423 |     6 |
| it     |    837 |   ~423 |     6 |
| ja     |    837 |   ~425 |     5 |
| pt     |    837 |   ~423 |     6 |
| ru     |    837 |   ~425 |     5 |
| zh_Hans|    837 |   ~426 |     5 |

**Problemas detectados hasta ahora (en `es`, ya corregidos):**
- `"Create an account"` → `"Eliminar cuenta"` ❌ (debería ser "Crear una cuenta") — **replicado en los 8 idiomas** como "Delete account" en cada lengua
- `"Sign out"` → `"Iniciar sesión"` ❌ (opuestos intercambiados) — verificar en otros idiomas
- `"Delete"` (formset Django) → `"Eliminar cuenta"` ❌
- Validadores de contraseña de Django usaban "Su" formal en vez de tuteo

**Hipótesis:** alguien hizo find/replace masivo. Habrá más casos.

**Restricción:** sin revisor humano nativo. Para idiomas con baja confianza (ja, ru, zh_Hans) hay que ser conservador.

---

## Pasada 1 — Errores activos (URGENTE)

> Una traducción **incorrecta** es peor que una vacía: la vacía cae al inglés, la incorrecta engaña al usuario.

### 1.1 Detectar msgstr duplicados sospechosos (firma del find/replace)

Para cada `.po`, listar msgstr no vacíos que aparezcan en ≥2 msgids distintos. Filtrar las legítimas (p.ej. "Delete" y "Delete account" pueden compartir traducción en algunos idiomas; "Email"/"E-mail"; etc.).

Comando base (a refinar):
```bash
for lang in de es fr it ja pt ru zh_Hans; do
  echo "=== $lang ==="
  awk '/^msgstr "/ && !/^msgstr ""$/{print}' locale/$lang/LC_MESSAGES/django.po \
    | sort | uniq -c | sort -rn | awk '$1>1'
done
```

Para cada duplicado sospechoso, mirar los msgids asociados y decidir si es legítimo o un error.

### 1.2 Detectar pares semánticos invertidos

Lista de pares opuestos a verificar manualmente que NO estén intercambiados:
- Sign in / Sign out · Log in / Log out
- Create / Delete · Add / Remove
- Save / Cancel · Accept / Reject · Confirm / Cancel
- Enable / Disable · Show / Hide · Open / Close
- Yes / No · On / Off

Para cada par y cada idioma: extraer ambos msgstr y comprobar a ojo que no coincidan ni estén invertidos.

### 1.3 Aplicar correcciones

Como los msgids son los mismos en todos los idiomas, una vez identificada la lista de "msgids con traducción rota", aplicar correcciones por idioma. Para cada uno:
- de, fr, it, pt, es: traducción directa con confianza razonable
- ja, ru, zh_Hans: traducir, pero **dejar `#, fuzzy`** si la correción no es trivial (mejor caer al inglés que dejar algo inventado)

**Salida esperada de la pasada:** 0 traducciones activamente erróneas en los 8 `.po`.

---

## Pasada 2 — Rellenar vacíos por prioridad (user-facing primero)

No tocar las ~420 cadenas vacías de cada idioma de golpe. Por **superficie de exposición al usuario**:

### Prioridad A — autenticación y onboarding
Archivos fuente:
- `templates/account/login.html`
- `templates/account/signup.html`
- `templates/account/logout.html`
- `templates/account/password_reset.html`

Es el primer contacto. Errores aquí pierden usuarios.

### Prioridad B — UI principal
- `frontend/templates/index.html`
- `frontend/templates/_topbar.html`, `_footer.html`, `_cookie_banner.html`
- `frontend/templates/challenge_detail.html`, `_challenge_card.html`
- `frontend/templates/gettask.html`
- `frontend/templates/manual.html`, `contact.html`
- `frontend/templates/legal/*`
- Strings en `frontend/static/js/*.js` (botones, modales, mensajes inline)

### Prioridad C — perfil de usuario
- `user_profile/templates/user.html`
- `user_profile/templates/edit_profile.html`
- `user_profile/templates/delete_account.html`

### Prioridad D — admin / backend / edge cases
- `georeferencing/admin.py`, `georeferencing/models.py` (admin Django)
- Strings de `venv/...` (Django built-in formsets, auth, etc.) — la mayoría ya tiene traducción en el `.po` bundled de Django y no necesitan override
- Mensajes de error / excepciones poco frecuentes

**Procedimiento por prioridad:**
1. Filtrar cadenas vacías cuyo `#:` apunte a archivos de la prioridad actual.
2. Traducir en bloque por idioma.
3. Compilar `.mo` y verificar que no haya errores de sintaxis.
4. Revisión visual: abrir las páginas afectadas en el navegador con `?lang=xx` (o cambiando el idioma del usuario) para confirmar que se ven bien.

---

## Pasada 3 — Fuzzy + revisión final

- Cada idioma tiene 5–6 entradas `#, fuzzy`. Django las ignora hasta que se quita el flag.
- Para cada `fuzzy`: leer la traducción propuesta, corregir si hace falta, quitar el flag.
- Verificación final: `msgfmt --statistics` por idioma para confirmar 0 fuzzy y conteo de traducidas.

---

## Salvaguardas (sin revisor humano)

1. **Git como red de seguridad.** Commit por pasada (Pasada 1, Pasada 2-A, 2-B, 2-C, 3) para poder revertir granularmente.
2. **Compilar `.mo` tras cada cambio significativo.** `msgfmt -c` con `--check` falla ante problemas de placeholders (`%s`, `%(name)s`) entre msgid y msgstr.
3. **Conservadurismo en ja/ru/zh_Hans:** preferir dejar `#, fuzzy` (cae al inglés) antes que colocar una traducción dudosa que pase desapercibida.
4. **Cross-check con Django bundled:** para strings de Django (auth, admin, formsets), comparar con `venv/lib/python3.12/site-packages/django/contrib/<app>/locale/<lang>/LC_MESSAGES/django.po` cuando exista, para no contradecir convenciones del propio framework.
5. **Coherencia de tuteo:** el proyecto tutea (`tú`) en es. En de usar `du`, en fr `tu`, en it `tu`, en pt `tu/você` (decidir uno y mantener), en ru `ты`. Mantener consistencia dentro de cada idioma.
6. **Placeholders intactos:** `%(name)s`, `{var}`, `<a href="...">` deben aparecer idénticos en msgid y msgstr.

---

## Orden de ejecución propuesto

1. Pasada 1.1 (detección duplicados) → reporte → tú confirmas qué corregir → aplicar → commit
2. Pasada 1.2 (pares invertidos) → reporte → confirmar → aplicar → commit
3. Pasada 2-A (auth, los 8 idiomas) → compilar → commit
4. Pasada 2-B (UI principal) → compilar → revisión visual del index/challenge → commit
5. Pasada 2-C (perfil) → commit
6. Pasada 2-D (admin/edge) → commit (opcional, baja prioridad)
7. Pasada 3 (fuzzy) → commit final

Cada paso es independiente: puedes parar en cualquier punto y el estado es coherente.

---

## Estimación de esfuerzo

- Pasada 1: rápido (~30 min). Pocos errores pero alta prioridad.
- Pasada 2-A: media (~1h). Pocos archivos, alto impacto.
- Pasada 2-B: la más larga (~2-3h). Mucho texto en UI principal.
- Pasada 2-C: media (~45 min).
- Pasada 2-D: opcional, aplazable.
- Pasada 3: rápido (~15 min).
