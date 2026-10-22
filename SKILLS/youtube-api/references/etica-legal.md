# Ética y legalidad de la recolección en YouTube

Lista de verificación para usar en clase y antes de publicar cualquier dataset. Los puntos 2 y 3 son los que más se incumplen por inercia.

## 1. Distinguir público de disponible para vos

- Un video visible sin cuenta es **público**, no necesariamente **reutilizable**. Lo público describe el acceso; lo reutilizable lo define la licencia.
- La transcripción suele ser una obra protegida: el guion, la traducción automática y el subtítulo son derivados del contenido del autor. Se analizan como fuente de investigación; no se redistribuyen como texto propio.
- Los comentarios son datos personales con nombre de usuario, canal y (a veces) foto de perfil. Que sean públicos no los convierte en datos sin dueño.

## 2. Minimizar y anonimizar antes de publicar

- Publicar el mínimo necesario: si el análisis es de sentimiento o de tema, el identificador del autor no aporta nada.
- Preferir un hash estable del `comment_id` si hace falta resolver el hilo, en lugar del nombre de usuario.
- Cuando el nombre de usuario se necesite, valorar conservarlo solo en el material interno del curso y no en el repositorio público.
- Eliminar avatares y enlaces de canal si el destino del dataset es público.
- No cruzar el dataset con otros datos que identifiquen personas sin necesidad.

## 3. Términos de uso y robots.txt

- Los Terms of Service de YouTube limitan la recolección automatizada y el uso de contenido con fines de aprendizaje automático. Revisar la versión vigente antes de un uso que no sea docente.
- Los `robots.txt` de `youtube.com` y `www.youtube.com` no prohíben explícitamente las rutas usadas en esta skill. Conviene comprobarlo en cada sesión, porque cambia.
- Un `robots.txt` permisivo no autoriza: es una señal técnica, no un permiso legal.

## 4. Límites técnicos de la recolección

- Respetar el ritmo: el CLI inserta una pausa entre peticiones y reintenta solo ante 429, usando `Retry-After`.
- No rotar proxies ni reintentar en bucle ante un bloqueo: `LOGIN_REQUIRED` con motivo `Sign in to confirm you're not a bot` es una respuesta, no un obstáculo a sortear.
- No usar cuentas de usuario ni sesiones ajenas para saltar restricciones de edad o de visibilidad.
- Limitar el volumen a lo que se va a analizar: pedir 200 comentarios de un video con 5 000 es una diferencia operativa que conviene explicitar.

## 5. Atribución y trazabilidad

- Registrar método, fecha de captura y cobertura junto a los datos: `capturado_en_utc`, `comentarios_declarados`, `obtenidos`.
- Citar el video (URL, título, canal, fecha de publicación) como fuente primaria del análisis.
- Distinguir en el informe entre lo observado (salida de la herramienta) y lo inferido.

## 6. Derechos de autor

- Antes de redistribuir una transcripción completa, verificar la licencia del canal: algunos autores publican bajo Creative Commons, otros no. La atribución no sustituye a la licencia.
- El material del curso es para uso docente; reutilizarlo fuera de ese marco requiere revisar la [licencia del repositorio](../../LICENSE).
