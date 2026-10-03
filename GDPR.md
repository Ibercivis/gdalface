# GDPR — Plan de cumplimiento

Plan accionable para que **Lost at Night** cumpla con el RGPD (UE 2016/679) y la LOPDGDD (LO 3/2018). No es un consejo jurídico — recomendado revisar el resultado con un abogado/DPO antes de publicar.

---

## 0. Resumen ejecutivo

Lo que hay que entregar antes de poder afirmar que cumplimos:

1. **Modelo de datos**: nuevos campos en `UserProfile` que registren consentimientos con marca temporal (GDPR, newsletter, cookies analíticas).
2. **Signup** con checkbox obligatorio de privacidad + opcional de newsletter.
3. **Editar perfil**: toggle para suscripción al newsletter, link de baja directo, descarga de datos, borrado de cuenta (ya existe).
4. **Páginas legales**: política de privacidad, política de cookies, aviso legal, términos de uso.
5. **Banner de cookies** (analíticas/funcionales separadas de las imprescindibles).
6. **Endpoint de exportación** de datos personales en formato máquina-legible.
7. **Endpoint de baja** del newsletter por token (link en cada correo).
8. **Registro de actividades de tratamiento** (Art. 30) en este documento.
9. **Procedimiento de brechas** (Art. 33-34): comunicación a la AEPD < 72h.

---

## 1. Estado actual del código (lo que ya tenemos)

| Pieza | Dónde | Estado |
|---|---|---|
| Borrado de cuenta | `user_profile/views.py` `delete_account` | ✅ Implementado |
| Login/signup vía allauth + email obligatorio | `gdalface/settings.py:ACCOUNT_EMAIL_REQUIRED=True` | ✅ Funciona |
| `UserProfile` con datos personales (país, profile_pic, visibilidad ranking) | `user_profile/models.py` | ✅ Existe — falta consentimiento explícito |
| Verificación de email obligatoria | `ACCOUNT_EMAIL_VERIFICATION = 'mandatory'` | ✅ |
| Reverse-geocode en cliente vía Nominatim | `frontend/static/js/main.js` | ⚠️ Procesador externo no documentado |
| Política de privacidad / términos | — | ❌ No existe |
| Banner de cookies | — | ❌ No existe |
| Newsletter | — | ❌ No existe |
| Exportación de datos personales | — | ❌ No existe |
| Registro temporal de consentimientos | — | ❌ No existe |
| Logs de acceso anonimizados | — | ⚠️ Verificar nginx logs |

---

## 2. Cambios en el modelo

Añadir a `user_profile/models.py` (`UserProfile`):

```python
# Consentimientos GDPR
privacy_accepted_at      = models.DateTimeField(null=True, blank=True)
privacy_policy_version   = models.CharField(max_length=20, blank=True)  # ej. "2026-05-02"

newsletter_subscribed    = models.BooleanField(default=False)
newsletter_subscribed_at = models.DateTimeField(null=True, blank=True)
newsletter_unsubscribed_at = models.DateTimeField(null=True, blank=True)
newsletter_token         = models.CharField(max_length=48, blank=True, db_index=True)  # para link de baja

cookies_analytics_consent     = models.BooleanField(default=False)
cookies_consent_at            = models.DateTimeField(null=True, blank=True)
```

**¿Por qué `privacy_accepted_at` en lugar de un boolean?** El RGPD exige poder demostrar **cuándo** se obtuvo el consentimiento (Art. 7.1). El timestamp + versión de política bastan como prueba. Si la política cambia → invalidamos los consentimientos antiguos y pedimos re-aceptación.

**Migración** (georeferencing/user_profile):
```bash
python manage.py makemigrations user_profile
python manage.py migrate
```

Backfill: para usuarios existentes, marcar `privacy_accepted_at = NULL` y forzarles aceptar la nueva política la próxima vez que entren (middleware o flag).

---

## 3. Signup — checkboxes obligatorio + opcional

Editar `templates/account/signup.html`:

```html
<label class="ds-check ds-check--required">
  <input type="checkbox" name="privacy_accepted" required>
  <span class="ds-check__box">…</span>
  <span class="ds-check__label">
    {% blocktrans %}I have read and accept the
    <a href="/privacy/" target="_blank">privacy policy</a>
    and the <a href="/terms/" target="_blank">terms of use</a>.{% endblocktrans %}
  </span>
</label>

<label class="ds-check">
  <input type="checkbox" name="newsletter_subscribed">
  <span class="ds-check__box">…</span>
  <span class="ds-check__label">
    {% trans "Send me updates about Lost at Night and citizen-science campaigns (optional)." %}
  </span>
</label>
```

Hook con allauth: usar **`ACCOUNT_FORMS`** o un signal `user_signed_up` para guardar los timestamps. Patrón recomendado:

```python
# user_profile/forms.py
from allauth.account.forms import SignupForm
from django.utils import timezone

class CustomSignupForm(SignupForm):
    privacy_accepted = forms.BooleanField(required=True)
    newsletter_subscribed = forms.BooleanField(required=False)

    def save(self, request):
        user = super().save(request)
        profile = user.userprofile
        now = timezone.now()
        profile.privacy_accepted_at = now
        profile.privacy_policy_version = settings.PRIVACY_POLICY_VERSION
        if self.cleaned_data.get('newsletter_subscribed'):
            profile.newsletter_subscribed = True
            profile.newsletter_subscribed_at = now
            profile.newsletter_token = secrets.token_urlsafe(32)
        profile.save()
        return user
```

```python
# settings.py
ACCOUNT_FORMS = {'signup': 'user_profile.forms.CustomSignupForm'}
PRIVACY_POLICY_VERSION = '2026-05-02'
```

---

## 4. Editar perfil — toggle newsletter + baja

En `user_profile/templates/user.html` (modal de edit-profile), añadir:

```html
<div class="ds-field">
  <label class="ds-toggle">
    <input type="checkbox" name="newsletter_subscribed"
           {% if profile.newsletter_subscribed %}checked{% endif %}>
    <span class="ds-toggle__track"><span class="ds-toggle__thumb"></span></span>
    <span class="ds-toggle__label">{% trans "Receive newsletters and project updates" %}</span>
  </label>
  {% if profile.newsletter_subscribed_at %}
    <span class="helptext">
      {% blocktrans with d=profile.newsletter_subscribed_at|date:"Y-m-d" %}
        Subscribed on {{ d }}.
      {% endblocktrans %}
    </span>
  {% endif %}
</div>
```

`UserProfileForm` (en `user_profile/forms.py`) debe incluir `newsletter_subscribed` y la view `edit_profile` debe escribir `newsletter_subscribed_at` / `newsletter_unsubscribed_at` en función del cambio.

**Botón "unsubscribe rápido"** dentro del email del newsletter:
```
GET /newsletter/unsubscribe/<token>/
```
View que pone `newsletter_subscribed=False`, `newsletter_unsubscribed_at=now`, regenera el token (para que el link expire) y muestra confirmación.

---

## 5. Páginas legales (mínimo)

Crear:

- **`/privacy/`** — política de privacidad (`templates/legal/privacy.html`).
- **`/terms/`** — términos de uso.
- **`/cookies/`** — política de cookies con tabla de cada cookie.
- **`/legal/`** — aviso legal (titular, NIF/CIF, contacto).

Contenidos mínimos de la política de privacidad (Arts. 13-14):

1. **Responsable del tratamiento** — Nombre legal de Ibercivis / IAA-CSIC, dirección postal, email de contacto del DPO.
2. **Finalidad del tratamiento** — geolocalización colaborativa de imágenes ISS para investigación de contaminación lumínica; gestión de cuenta; envío de newsletter (si optaste).
3. **Base legal** — consentimiento (Art. 6.1.a) para newsletter; ejecución de contrato/términos para cuenta (6.1.b); interés legítimo para datos pseudonimizados de telemetría (6.1.f).
4. **Categorías de datos** — email, username, password (hashed), país (opcional), foto de perfil (opcional), control points realizados, IP en logs (limitado).
5. **Plazos de conservación** — datos de cuenta hasta borrado solicitado; logs de acceso 30 días; control points y geo-attempts indefinidos (datos científicos pseudonimizados).
6. **Destinatarios / encargados** — Nominatim (OpenStreetMap Foundation, UK), proveedor de email transaccional/marketing (a definir — Brevo / Mailjet / SendGrid?), hosting (a definir).
7. **Transferencias internacionales** — solo si usas servicios fuera del EEE; documentar SCC.
8. **Derechos** — acceso, rectificación, supresión, oposición, portabilidad, limitación, retirada del consentimiento, reclamación ante la AEPD.
9. **Decisiones automatizadas** — ninguna.
10. **Cómo ejercer los derechos** — email a `privacy@lostatnight.org` o desde el panel de usuario.

---

## 6. Banner de cookies

Tres categorías (no usar "aceptar todas" como único botón):

- **Imprescindibles** (siempre activas): `sessionid`, `csrftoken`, `messages`. No requieren consentimiento.
- **Funcionales**: idioma, preferencias de tema. Consentimiento implícito si interactúas.
- **Analíticas** (si usas Plausible/Matomo/GA): solo si el usuario marca el checkbox.

Implementación recomendada: librería ligera tipo **klaro** o **CookieYes**, o un componente propio de ~40 líneas. Persistir consentimiento en `UserProfile.cookies_analytics_consent` para usuarios autenticados, y en `localStorage` para anónimos.

Tabla de cookies a documentar en `/cookies/`:

| Cookie | Origen | Tipo | Plazo | Finalidad |
|---|---|---|---|---|
| `sessionid` | propia | Imprescindible | Sesión | Mantener sesión |
| `csrftoken` | propia | Imprescindible | 1 año | Protección CSRF |
| `django_language` | propia | Funcional | 1 año | Idioma elegido |
| (analítica si la añades) | Plausible | Analítica | — | Métricas agregadas |

---

## 7. Derechos del usuario (Arts. 15-22)

| Derecho | Cómo lo cubrimos | Ruta |
|---|---|---|
| **Acceso (Art. 15)** | Endpoint `GET /user-profile/data-export/` que devuelve un ZIP/JSON con todos los datos del usuario | A implementar |
| **Rectificación (Art. 16)** | Modal de edit-profile actual | ✅ |
| **Supresión / olvido (Art. 17)** | `delete_account` view actual | ✅ — verificar que borra **todo** (geo-attempts, control points, log entries) |
| **Limitación (Art. 18)** | Toggle "pausar cuenta" — suspende sin borrar | A implementar (baja prioridad) |
| **Portabilidad (Art. 20)** | Mismo endpoint que acceso, formato JSON | A implementar |
| **Oposición (Art. 21)** | Toggle newsletter + opción de excluirse del ranking público (ya existe `visible`) | ✅ parcialmente |
| **Retirada del consentimiento** | Newsletter unsubscribe + delete account | ✅ |

**Sobre `delete_account` actual** — auditar: ¿borra `GeoAttempt`, `ControlPoint`, `ChallengeParticipant`, `GeoAttemptsByUserByDay`? El RGPD permite **anonimizar** en lugar de borrar si los datos científicos pseudonimizados son necesarios para investigación (Art. 89), pero hay que **separar** la identidad del registro: reemplazar `user` con `null` o un usuario "deleted" en lugar de hacer `CASCADE`. Decisión de diseño a tomar.

---

## 8. Newsletter — flujo completo

Pasos para enviar emails legalmente:

1. **Doble opt-in**: tras marcar el checkbox en signup, enviar email de confirmación con link único. Solo activar tras click. (Reduce spam y bots, y demuestra consentimiento real.)
2. **Footer en cada email**: nombre del responsable, dirección postal, link de baja en 1 click.
3. **Datos del envío**: registrar `(user_id, sent_at, campaign_id)` en una tabla `NewsletterDelivery` para auditoría.
4. **Proveedor**: elegir uno con DPA firmado en el EEE (Brevo en Francia, Mailjet en Francia, MailerSend en EU). Documentar en política de privacidad.
5. **Frecuencia esperada** declarada al usuario (p.ej. "1-2 emails al mes").
6. **Categorías**: separar transaccional (verificación email, password reset — base legal contrato) de marketing (newsletter — base legal consentimiento). Solo el marketing requiere opt-in.

---

## 9. Datos sensibles a vigilar

- **Coordenadas geográficas** que el usuario marca: técnicamente no son datos personales (son del fenómeno luminoso, no del usuario), salvo que el usuario revele su ubicación en una imagen propia. Lost at Night solo procesa imágenes de la ISS, así que **no aplica**.
- **Logs de IP en nginx**: limitar retención a 30 días. Considerar configurar nginx para anonimizar el último octeto: `log_format anonymized '$remote_addr_anon ...'`. Bug menor.
- **Foto de perfil**: el usuario puede subir una imagen suya → dato personal sensible si es identificable. Permitir borrarla (ya está). Documentar dónde se almacena (filesystem local en `/media/profile_pics/`) y plazo (hasta borrado).
- **Visited places** del usuario (vista `Statistics`): es perfilado. Asegurar que solo el propio usuario lo ve, **no** otros. Confirmar que la ruta `/user-profile/<id>/` exige autenticación y `request.user.id == id`.

---

## 10. Sub-procesadores externos identificados

| Procesador | Finalidad | Datos | Ubicación | DPA |
|---|---|---|---|---|
| **OpenStreetMap Nominatim** | Reverse-geocode de coordenadas en el mapa de tareas | Lat/Lon de la imagen ISS (no del usuario) + IP del navegador | UK | ⚠️ Verificar uso público; considerar mover el reverse-geocode al backend para no exponer la IP del usuario |
| **Let's Encrypt** | Certificados HTTPS | — | US | Política pública aceptada |
| **Hosting (a definir)** | Almacenamiento del servidor | Todos | EU recomendado | DPA del proveedor |
| **Email transaccional (a definir)** | Verificación email + reset password | email | EU | DPA |
| **Newsletter (a definir)** | Envío de newsletters | email + nombre | EU | DPA |

**Acción**: documentar todos en `/privacy/` y firmar DPAs.

---

## 11. Registro de actividades de tratamiento (Art. 30)

Tabla a mantener en este documento o en `docs/processing-records.md`:

```
Actividad: gestión de cuentas de usuario
Responsable: Ibercivis
Finalidad: identificación, autenticación, derechos del usuario
Categorías de interesados: ciudadanos voluntarios mayores de 16 años
Categorías de datos: email, username, password (hashed), país (opc.), foto (opc.)
Destinatarios: ninguno (datos no compartidos)
Transferencias internacionales: ninguna
Plazo: hasta solicitud de borrado por el usuario
Medidas técnicas: HTTPS, hashing PBKDF2/argon2, CSRF, sesiones firmadas
```

(Repetir para: newsletter, control points / contribución científica, logs, cookies analíticas.)

---

## 12. Procedimiento de brechas (Arts. 33-34)

Documento corto en `docs/breach-response.md`:

1. **Detección**: sentry / logs / aviso de usuario.
2. **Contención**: revoke sesiones, rotar tokens, parchar.
3. **Evaluación de riesgo**: ¿afecta a derechos y libertades? ¿qué categorías de datos?
4. **Notificación a la AEPD < 72h** si hay riesgo: formulario en sede.aepd.gob.es.
5. **Notificación a usuarios** si el riesgo es alto.
6. **Post-mortem** documentado.

Designar un responsable de seguridad (puede coincidir con el DPO si lo hay).

---

## 13. Edad mínima

`ACCOUNT_EMAIL_REQUIRED=True` no comprueba edad. En España la edad mínima de consentimiento digital es **14 años** (LOPDGDD Art. 7), en el RGPD por defecto **16** salvo modificación nacional. Añadir:

- Checkbox separado en signup: "Confirmo que tengo al menos 14 años (o cuento con autorización paterna/tutor)".
- Si el público objetivo incluye menores → preparar mecanismo de verificación de tutor.

---

## 14. Roadmap priorizado

### P0 — Bloqueante para producción legal
1. **Política de privacidad y de cookies publicadas** en `/privacy/` y `/cookies/`.
2. **Migración con campos de consentimiento** + checkbox en signup.
3. **Banner de cookies** funcional.
4. **Aviso legal** con datos del responsable.
5. **Verificar `delete_account`** borra/anonimiza todas las relaciones.

### P1 — Necesario antes de mandar el primer newsletter
6. Implementar campos newsletter (`newsletter_subscribed`, `_at`, `token`).
7. Endpoint `/newsletter/unsubscribe/<token>/`.
8. Toggle en edit-profile.
9. Doble opt-in tras signup.
10. Elegir proveedor de email + firmar DPA.

### P2 — Mejora de cumplimiento
11. Endpoint de exportación de datos (`/user-profile/data-export/`).
12. Mover reverse-geocode al backend (privacidad de IP).
13. Anonimizar IPs en nginx logs (último octeto).
14. Toggle "pausar cuenta" (Art. 18).
15. Procedimiento de brechas escrito.
16. Comprobación de edad mínima.

### P3 — Operacional
17. DPO designado (si aplica — empresa pequeña no obligada salvo categoría especial de datos).
18. Auditoría anual.
19. Formación interna del equipo.

---

## 15. Mapeo a archivos del repo

Cuando se implemente:

- `user_profile/models.py` → nuevos campos.
- `user_profile/migrations/0XXX_gdpr_fields.py` → migración.
- `user_profile/forms.py` → `CustomSignupForm`, ampliar `UserProfileForm`.
- `user_profile/views.py` → `data_export`, `newsletter_unsubscribe`, ampliar `delete_account`, ampliar `edit_profile`.
- `user_profile/urls.py` → rutas nuevas.
- `templates/account/signup.html` → checkboxes.
- `user_profile/templates/user.html` → toggle newsletter en modal.
- `frontend/templates/legal/privacy.html`, `terms.html`, `cookies.html`, `legal.html` → páginas nuevas.
- `frontend/templates/_cookie_banner.html` → componente.
- `frontend/templates/_footer.html` → links a páginas legales.
- `gdalface/settings.py` → `ACCOUNT_FORMS`, `PRIVACY_POLICY_VERSION`, configuración de email transaccional.

---

## 16. Métrica de "hecho"

Podemos afirmar que cumplimos cuando:

- ☐ Las 4 páginas legales están publicadas y enlazadas en el footer.
- ☐ Signup tiene checkbox obligatorio de privacidad y opcional de newsletter, ambos guardan timestamp.
- ☐ Banner de cookies categorizado (no "aceptar todas").
- ☐ `delete_account` borra/anonimiza todas las tablas relacionadas.
- ☐ Hay un endpoint de exportación de datos.
- ☐ Newsletter tiene doble opt-in y baja en 1 click.
- ☐ Procesadores externos firmados con DPA y listados en política.
- ☐ Procedimiento de brechas escrito y comunicado al equipo.
- ☐ Auditoría inicial firmada por un DPO o asesor legal.
