# Lost at Night — Promoción y comunidad

Notas de trabajo. Actualizado: 2026-10-03.

## Lo que sabemos de la comunidad (datos del panel, 2026-10-03)

- 136 cuentas verificadas, ~12 activas al mes, ~90 contribuciones/día en las
  mejores semanas. Las cuentas sin verificar (5204 bots, abr–jul 2026) se
  borraron el 2026-10-03.
- La actividad grande viene **en bloques**: una sesión de aula/taller anónima
  hizo 118 contribuciones en una mañana (3 oct), otra 57 (30 sep). Una sesión
  rinde lo que una semana de voluntarios sueltos.
- La gente abandona cuando la foto no tiene punto de partida (nivel C: 5,9
  saltos por tarea hecha, 47 % sin tocar) y se queda cuando lo tiene (nivel A:
  0,9 saltos, 15 % sin tocar). Promocionar sin arreglar esto es llenar un cubo
  agujereado: a los nuevos, fotos de nivel A y B.
- El correo de novedades (3 oct, 136 destinatarios, ES+EN) trajo visitas, no
  una ola de contribuciones. Efecto a medir en 1–2 semanas (evento en /stats/).

## Prioridades (esfuerzo → resultado)

1. **Grupos antes que individuos.** Kit para profesores y clubes de una página:
   qué es, crear el equipo en 2 min, enlace de invitación, sesión tipo de 60
   min con reto regional, diploma al final. Destinatarios: agrupaciones
   astronómicas, profesores de geografía/física de secundaria, programas de
   ciencia ciudadana escolar que Ibercivis ya conoce.
2. **Que cada foto se pueda compartir.** Página por foto localizada (imagen,
   lugar, "localizada por N personas") con OpenGraph para que en redes salga la
   foto. Igual para diplomas y puesto en el ranking. La promoción la hacen los
   voluntarios.
3. **Redes donde ya está el público**: r/darksky (post hecho, 3 oct),
   r/astrophotography (una foto y su historia), Mastodon/Bluesky (comunidad
   astronómica muy activa), grupos de Facebook de astronomía amateur locales.
   Siempre una foto concreta, no el proyecto en abstracto.
4. **Momentos**: International Dark Sky Week (abril), Noche Europea de los
   Investigadores (final de septiembre), Earth Hour, noticias de LEDs/cielos.
   Un reto con fecha de fin por evento.
5. **Volver**: resumen mensual corto por correo (mapa, ranking del mes, reto en
   marcha, foto destacada). `send_bulk_email` + evento automático.
6. **Prensa y aliados**: nota con los números del catálogo (8,2 M fotos, 4,4 M
   nocturnas, 1,8 k localizadas); canales del proyecto europeo; equipo del
   Gateway to Astronaut Photography de la NASA (difundió Cities at Night).

**Medir**: cada acción, una línea en los eventos de `/stats/`.

## Colegios: 10 sesiones (Zaragoza)

Diseño acordado el 2026-10-05. Sustituye a la versión del 3 de octubre en lo
que se contradigan.

### Formato de la sesión (55 min; con clase de 50, intro 7 y trabajo 23)

| Bloque | Min | Qué pasa |
|---|---|---|
| Contaminación lumínica | 10 | Zaragoza desde la ISS en 2011 (ISS026, 200 mm, nivel A, "Zaragoza at night") y en 2021-22 (ISS065/ISS066, 400 mm, nivel B). Por qué importa, cómo se reconoce una ciudad de noche. |
| La app en el proyector | 5 | Una foto de Zaragoza de 2022 resuelta entre todos ("eso es el Ebro, eso es la Expo"). Nadie toca aún su cuenta. |
| Registro + equipo + reto | 10 | **Decisión (5 oct): los alumnos se registran en el aula**, en su móvil, con un QR en el proyector. Objetivo: < 10 min con 25-30 alumnos. |
| Trabajo por parejas | 25 | Portátil por pareja. Cuenta de uno los primeros 12 min, del otro los siguientes: los dos puntúan. 150-200 contribuciones por clase. |
| Cierre | 5 | Página del equipo del cole (mapa de lo localizado hoy), ranking entre colegios. Encargo: tres fotos más en casa esta semana. |

### Palancas para que el registro quepa en 10 minutos

1. **Entrar con Google.** Si el centro usa Google Workspace, 20 s y sin
   verificar correo. Hoy a medias: credenciales en `.env` pero no en la clave
   `APP` que lee allauth 65, sin `SocialApp` en BD, 0 cuentas Google. Probar
   antes del primer piloto. Preguntar al profesor qué cuenta tienen los alumnos.
2. **Verificación por código** (`ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED`,
   disponible en allauth 65): seis dígitos en la misma página, sin salir al
   correo a buscar el enlace.
3. **Móvil para registrarse, portátil para trabajar.**
4. **Un solo enlace/QR** que une a equipo y reto y termina en la primera
   tarea, no en la portada. Hoy son tres pasos.
5. **Quien no lo consiga trabaja anónimo** en el mismo batch (sirve a la
   ciencia, no suma al equipo) y se registra en casa.

Cronometrar el bloque de registro en los dos pilotos de octubre. Si pasa de
10 min con Google y código, el cuello es la wifi del centro.

### Fotos y estructura

- **Un solo batch "Colegios 2026"**: primero las 70 nocturnas de nivel A/B de
  Aragón del catálogo (6 ya cargadas), detrás las de España (2178 A/B
  nocturnas, 211 cargadas). Diez clases gastan 1500-2000 contribuciones; no se
  agota. El batch regional por colegio se descarta: Aragón no da para 10.
- Reto "Colegios 2026" con región España y fecha de cierre; ranking de equipos
  = clasificación entre centros. Un equipo por colegio, creado por el profesor.
- Alumnado de 14 o más (3º ESO en adelante): consienten por sí mismos. Edad
  mínima 14 en privacidad y términos.

### Requisitos y estimación

- Portátil o tableta por pareja (en móvil la herramienta va mal), proyector,
  wifi probada con el flujo completo una vez. 15 min con el profesor la semana
  anterior: crea el equipo, recibe el enlace, confirma dispositivos y cuentas.
- Estimación 10 colegios: 1500-2000 contribuciones, 150-250 registros, 15-30
  que siguen en casa → doblar la comunidad activa. 2 pilotos en octubre, 8 en
  noviembre-diciembre.

### Pendiente de producto (en orden)

1. Entrar con Google funcionando y probado.
2. Verificación por código.
3. Enlace de invitación que une a equipo y reto y termina en la tarea.
4. Batch "Colegios 2026" (Aragón + España, A/B) y reto.
5. Diploma de equipo con el nombre del colegio.
6. Edad mínima 14 en privacidad y términos.
7. Kit del profesor y materiales (ver inventario).

### Inventario de materiales (acordado 2026-10-05)

Archivos generados el 2026-10-05 en `promocion/` (sin commitear):
`Institutos_Zaragoza_2026.docx` (este diseño en Word, con el aviso de ≥ 14 años)
y `Contacto_institutos_Zaragoza_2026.xlsx` (hojas Resumen · Institutos ·
Sesiones; 26 IES públicos de Zaragoza como candidatos de partida, sin datos
de contacto: comprobar en el buscador de centros de educa.aragon.es).

Una sola vez:
- **Guion de puesta en marcha** (checklist única): producto 1-7, cuentas de
  prueba, batch y reto creados, calendario de los 10 colegios, plantillas.
- **Presentación** (8-10 diapositivas, imágenes en local, sin depender de red).
- **Kit del profesor** (1 página): qué es, qué necesita, qué hace la semana
  antes, qué pasa con los datos de sus alumnos.
- **Plantillas de correo**: primer contacto (dirección / profesor de física,
  geografía, tecnología), confirmación, recordatorio, resultados.
- **Nota informativa para familias** (opcional; ≥ 14 no la exige, los centros
  la suelen pedir).
- **Chuleta del alumno** (1 página): cómo reconocer una ciudad de noche, qué
  es un punto de control, saltar sin miedo.
- **Tabla de seguimiento de colegios**: contactado · confirmado · fecha ·
  hecho · resultados.
- **Hoja de datos por sesión**: colegio, fecha, alumnos, registros, minutos
  de registro, contribuciones, incidencias. Alimenta la memoria final.

Por sesión (**guion con checkboxes**: antes / durante / después):
- Antes: llamada con el profesor, equipo creado, QR generado, prueba en la
  wifi del centro, mochila (portátil, HDMI, hotspot, QR impreso, hoja de datos).
- Durante: los 5 bloques con sus tiempos y el cronómetro del registro.
- Después: evento en `/stats/`, correo al profesor con mapa y números,
  diploma de equipo, hoja de datos rellena, seguimiento a 1 semana y 1 mes.

Al final del programa: **memoria** con los datos de las 10 sesiones, para
repetir en otra ciudad y para pedir apoyo al ayuntamiento o a la DGA.

## Reddit

### r/darksky — post publicado 2026-10-03

Texto en inglés, tono "lo hacemos entre todos", sin imagen (el sub no las
permite en texto; enlace al mapa `lostatnight.org/#map-section` en su lugar).
Clave del mensaje: no "localizar" sino **georreferenciar** (puntos de control
→ la foto proyectada sobre el mapa, medible, comparable entre años). Anotar
el hilo como evento en /stats/.

### Comentario recibido y respuesta

Un lector apuntó a subreddits de puzles y a "bibliotecarias catalogando
estrellas en los 50". Se refiere a las **Harvard Computers** (Annie Jump
Cannon, Williamina Fleming, Henrietta Leavitt; 1880–1920; Cannon clasificó
~350.000 espectros a ojo): el paralelismo con reconocimiento de patrones
humano a escala es exacto. Respuesta publicada recogiendo la referencia e
invitando a jugadores de GeoGuessr.

### r/geoguessr: descartado (normas leídas el 2026-10-04)

Regla 6 "No r/whereisthis posts" (fotos preguntando dónde es, salvo capturas
del juego) y regla 7 "No self-promotion". Un reto con foto de la ISS incumple
las dos. r/geochallenges tampoco: es para enlaces de partidas de GeoGuessr.
Queda el Discord de GeoGuessr (canal de vídeos/comunidad) como vía indirecta.

### Siguiente: r/whereisthis (pregunta de verdad, no quiz)

Normas leídas el 2026-10-04: solo lugares desconocidos (regla 3, nada de
retos); contexto completo, de dónde sale la foto (enlace) y por qué se quiere
el lugar (reglas 1-2); al resolverse, responder "Solved!" al primer acierto y
poner el flair Solved (regla 6, si no, riesgo de ban); esperar una semana antes
de repetir. El proyecto se menciona como motivo y en el comentario de cierre.

La comunidad GeoGuessr (cientos de miles de miembros) es el perfil ideal:
reconocen lugares por detalles mínimos. En r/whereisthis el post debe ser una
pregunta real, así que se usa una foto de **nivel C** (solo nadir, ciudad
desconocida para nosotros), nunca una de nivel A/B con respuesta conocida.
Candidata elegida: ISS057-E-95922 (nadir 43.4 N 13.1 E, 85 mm, 2018-11-13,
gran ciudad en el centro, sin catalogar). Reserva: ISS047-E-14025 (costa
libia, 50 mm). El enlace al proyecto va en un comentario, al cerrar el hilo.
También r/puzzles. Otros subs afines: r/CitizenScience, r/astrophotography,
r/Astronomy, r/spaceporn, r/ISS.

## Textos reutilizables

- Post r/darksky (EN): ver historial del 2026-10-03; versión final sin
  imagen, verbo "georeference", cierre "come and pin it to the map with us".
- Correo de novedades (EN/ES): `emails/email_2026_10_news.html` y `_es.html`.
