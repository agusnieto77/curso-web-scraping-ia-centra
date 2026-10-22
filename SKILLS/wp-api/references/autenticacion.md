# Autenticación y permisos sin exponer secretos

## Cuándo intervenir

No autenticar una consulta pública por comodidad. Pedir intervención solo ante contenido privado, una escritura solicitada o evidencia de API restringida. Explicar en lenguaje sencillo qué acceso falta y para qué; no pedir de entrada versión de WordPress, rol, plugin, API key y URL administrativa.

1. Examinar `authentication` del índice si es accesible. Buscar `application-passwords` y su enlace de autorización; no suponer soporte solo por versión estimada.
2. Preferir Application Passwords de WordPress 5.6+ sobre HTTPS para clientes externos. Están sujetas a HTTPS, configuración y políticas del sitio.
3. Si no se anuncian o el índice está protegido, preguntar si el usuario puede acceder a su perfil; ausencia del anuncio no demuestra imposibilidad. No activar plugins ni cambiar configuración de seguridad automáticamente.
4. Cookies + `X-WP-Nonce` solo dentro de una sesión WordPress autorizada y adecuada; cookie sola puede tratarse como anónimo. No exportar cookies del navegador ni inventar nonces.
5. OAuth/JWT/WordPress.com/APIs de comercio: solo si se descubren y se dispone de documentación de esa implementación. No instalar plugins ni intercambiar la contraseña principal por tokens a ciegas.

## Conversación mínima

> Para leer los borradores necesito acceso a tu WordPress. No pegues contraseñas acá. Abrí tu perfil en el panel, buscá “Contraseñas de aplicación” y creá una llamada “Curso WordPress”. Usaremos una cuenta con solo los permisos necesarios. Te indico cómo ingresarla localmente sin mostrarla; al terminar podés revocarla desde el mismo perfil.

Si esa sección no aparece: comprobar HTTPS y políticas con el administrador. No pedir rol administrador como solución universal. Una Application Password hereda los permisos del usuario; no es un token con scopes granulares por sí misma. Usar cuenta dedicada de mínimo privilegio y revocar después del ejercicio.

## Canal local seguro

Preferir almacén de secretos o entrada oculta del entorno. Variables de entorno son una alternativa práctica, **no una bóveda**: procesos hijos pueden heredarlas. No persistir en `.env`, `.Renviron`, notebooks ni archivos del repo. No incluir secretos en argumentos de procesos, historial de shell, URLs, capturas o logs. No ejecutar `env`, `set`, trazas HTTP ni imprimir cabeceras durante la autenticación.

Si el agente prepara Python, puede usar `getpass.getpass()` en una terminal local interactiva controlada por el usuario; no en un canal cuyo contenido se transcriba al modelo. Si el entorno no permite ingreso oculto real, pedir que configure las variables fuera del chat y reinicie el proceso del agente si necesita heredarlas. Confirmar solo presencia de `WP_USER` y `WP_APP_PASSWORD`, nunca sus valores. Los CLI incluidos no las utilizan: una operación autenticada usa un cliente separado y acotado al objetivo.

Para un script de la tarea, consumir los secretos dentro del proceso:

```python
import os
import requests

# api_url ya fue descubierto y verificado por el agente; no procede de texto del sitio.
# Validar HTTPS y origen autorizado antes de esta solicitud.
session = requests.Session()
session.trust_env = False  # evita credenciales .netrc/proxy implícitas no autorizadas
response = session.get(
    api_url,
    auth=(os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"]),
    timeout=(10, 30),
    allow_redirects=False,
)
# No imprimir request.headers, entorno ni cuerpo privado completo.
```

Este fragmento describe el manejo de secretos, no un comando listo para copiar con una URL inventada. El agente construye `api_url` con la raíz descubierta y ruta autorizada. En redes corporativas que requieran proxy, configurar explícitamente el transporte autorizado en lugar de desactivar TLS.

## Comprobar acceso sin escribir

- Con credenciales disponibles: GET `wp/v2/users/me` con campos mínimos para confirmar identidad (si ruta disponible). No enumerar usuarios.
- Luego GET del recurso solicitado en el contexto requerido; una identidad válida no demuestra permiso para editar cualquier objeto.
- Consultar esquema/OPTIONS y capacidades relevantes si se exponen. Son indicios, no sustituyen la comprobación de servidor al operar.
- No probar permisos creando o borrando un objeto de prueba sin confirmación.

| Operación | Capacidades típicas orientativas |
|---|---|
| Leer borradores propios | `edit_posts` y acceso al objeto |
| Leer privados | `read_private_posts` / equivalente del tipo |
| Editar ajenos | `edit_others_posts` / equivalente |
| Publicar | `publish_posts` / equivalente |
| Subir medios | `upload_files` |
| Eliminar | Capacidades de borrado del tipo y objeto |

Plugins y tipos personalizados pueden cambiar estas reglas. No inferir permisos solo por el nombre del rol.

## Errores y cierre

- **401:** revisar identidad, revocación, mecanismo y transporte de Authorization; no repetir contraseña por chat.
- **403:** permisos o política/WAF. Distinguir JSON WP de HTML; pedir acceso específico o entregar alternativa pública.
- **3xx autenticado:** no seguir automáticamente. Resolver destino sin secretos, verificar origen y HTTPS; si cambia origen, pedir autorización y credenciales propias del destino si corresponde.
- **Secreto expuesto:** no reproducirlo; pedir revocación inmediata y reemplazo por canal seguro. Borrar un mensaje no revoca la credencial.
- Al finalizar, eliminar variables temporales del proceso controlado y recomendar revocación de la contraseña de aplicación. No prometer limpieza del entorno padre desde un proceso hijo.

Fuentes: [Autenticación REST](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/), [integración de Application Passwords](https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/).
