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

## Colegios: 10 sesiones

- Formato **60 min**: 10 intro (dos fotos en proyector, por qué importa, cómo
  se reconoce una ciudad de noche) · 40 trabajo por parejas · 10 cierre (mapa
  de la clase + ranking entre colegios).
- Requisitos: portátil/tableta por pareja, navegador, wifi. 15 min de
  preparación con el profesor la semana anterior.
- **Menores**: ≥ 14 pueden registrarse (mejor antes, en casa, con el enlace del
  equipo del colegio); < 14 sin cuenta, con **código de sesión** que atribuye el
  trabajo al equipo del colegio sin datos personales. Añadir edad mínima (14)
  a privacidad y términos. El código de sesión también evita los 10–15 min de
  verificación de correo en clase.
- Cada colegio, un batch regional de niveles A y B (desde el catálogo), 150–200
  fotos; los primeros 5 minutos deciden si la clase engancha.
- Reto "Colegios 2026" con fecha de cierre; ranking de equipos = clasificación
  entre centros. Diploma de equipo con nombre del colegio.
- Estimación 10 colegios: 1000–1200 contribuciones (~900 fotos georreferenciadas
  por primera vez, la mitad de lo hecho hasta hoy), 80–120 registros si ≥ 14,
  10–25 que siguen en casa (5–10 % de retención típica) → doblar la comunidad
  activa. Plan: 2 pilotos en octubre, 8 entre noviembre y diciembre.
- Pendiente de producto (en orden): código de sesión → batch regional por
  colegio → diploma de equipo → frase de edad en legal.

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

### Siguiente: r/geoguessr y r/whereisthis

La comunidad GeoGuessr (cientos de miles de miembros) es el perfil ideal:
reconocen lugares por detalles mínimos. Mejor un **reto** que una presentación:
"¿Dónde es esto? Pista: tomada desde la ISS a 400 km", con una foto difícil
(nivel C, cámara oblicua) y, en los comentarios, el enlace para georreferenciarla
de verdad. También r/puzzles. Otros subs afines: r/CitizenScience,
r/astrophotography, r/Astronomy, r/spaceporn, r/ISS.

## Textos reutilizables

- Post r/darksky (EN): ver historial del 2026-10-03; versión final sin
  imagen, verbo "georeference", cierre "come and pin it to the map with us".
- Correo de novedades (EN/ES): `emails/email_2026_10_news.html` y `_es.html`.
