# REST: descubrir antes de operar

## 1. URL → raíz REST

No pedir al estudiante `/wp-json`, IDs ni nombres de plugins. Conservar la URL y su subdirectorio: `https://sitio.example/blog/` no equivale a la raíz del dominio. Un multisite puede tener una API por subsitio; no recorrer la red completa.

1. Si la URL ya es un índice REST, validarlo directamente.
2. Consultar la página aportada (HEAD si ofrece cabeceras, GET si hace falta HTML). Buscar `Link: <...>; rel="https://api.w.org/"` o `<link rel="https://api.w.org/" href="...">`. Resolver URLs relativas respecto a la respuesta. No extraer una ruta de cualquier texto que mencione `wp-json`.
3. Sin anuncio utilizable, probar `<base>/wp-json/` y `<base>/?rest_route=/`. Si se aportó una página interior, usar primero su anuncio; solo probar padres plausibles con presupuesto acotado, no enumerar directorios.
4. Aceptar un objeto JSON con `namespaces`/`routes` coherentes. `200`, extensión o `Content-Type` por sí solos no prueban WordPress. Un JSON de error con `code`, `message`, `data.status` no es el índice.
5. Registrar raíz efectiva, rutas pertinentes y `authentication`; no copiar el índice entero al chat. Un origen distinto anunciado por el sitio requiere revisar su relación y autorización antes de visitarlo; nunca trasladar credenciales. Redirecciones públicas no autorizan acceso a redes internas.

**Fallback no es evasión:** la forma `rest_route` resuelve enlaces permanentes simples o reescrituras ausentes, no un permiso para sortear un 403. Si hay bloqueo explícito, detener esa vía. Si no se localiza índice pero una ruta anunciada funciona, informar descubrimiento parcial y usar solo esa evidencia.

### Construir rutas sin romper los enlaces simples

| Índice descubierto | Colección |
|---|---|
| `https://sitio.example/blog/wp-json/` | `https://sitio.example/blog/wp-json/wp/v2/posts` |
| `https://sitio.example/blog/?rest_route=/` | `https://sitio.example/blog/?rest_route=/wp/v2/posts&per_page=5` |

Usar un constructor de URL y parámetros, no concatenar `?` sobre otra query ni reemplazar el subdirectorio. El `rest_route` completo es un parámetro; filtros son parámetros separados.

## 2. Capacidades disponibles ≠ permisos concedidos

- `namespaces`: core y extensiones. No asumir WooCommerce, WPML, ACF, Yoast o rutas de un plugin por el aspecto visual del sitio.
- `routes`: rutas y métodos anunciados; examinar solo los del recurso pedido.
- `OPTIONS` del endpoint: argumentos, campos, tipos, enums y esquema cuando estén disponibles. Si OPTIONS está bloqueado, usar argumentos del índice y documentación oficial; no adivinar campos de escritura.
- `GET /wp/v2/types`: mapear tipo a `rest_namespace` y `rest_base`; no usar su slug como ruta por defecto.
- `GET /wp/v2/taxonomies`: mapear taxonomías necesarias. No listar usuarios para descubrir un login.
- `authentication`: mecanismos anunciados, no prueba de que la cuenta tenga autorización. Un mapa vacío no demuestra que toda autenticación sea imposible.

Los permisos efectivos dependen del usuario, objeto, autoría, estado y plugins. Un `Allow: POST` o una ruta `DELETE` no es autorización. Consultar [autenticación](autenticacion.md) ante necesidad real.

## 3. Recursos habituales

Rutas relativas a la raíz, **solo tras comprobar disponibilidad**:

| Petición natural | Recurso / filtro |
|---|---|
| Últimas noticias | `wp/v2/posts`, `orderby=date&order=desc` |
| Páginas del sitio | `wp/v2/pages` |
| Catálogos, imágenes, audio, video | `wp/v2/media` con `mime_type` (acepta varios valores); el CLI de la skill usa alias (`--mime pdf,jpg`) |
| Exportar datos estructurados | Colección (`posts`, `categories`, ruta de plugin) vía `export` del CLI: JSON/NDJSON verificado con manifiesto |
| Buscar texto | `search` del recurso; no confundir búsqueda con coincidencia exacta |
| Productos/tipo propio | Namespace/base de `types`; APIs de comercio pueden tener autenticación distinta |
| Categorías/etiquetas | Ruta de la taxonomía descubierta |
| Borradores/privados | Colección con estado y `context=edit` si permitido; autenticar |

Para archivos usar `source_url`, no reconstruir desde `guid.rendered`. Los archivos enlazados en páginas pueden no estar registrados en media: cero resultados no demuestra ausencia de archivos. HTML público es una alternativa explícitamente parcial, no una biblioteca equivalente.

## 4. Consultas eficientes

- Muestra inicial: `per_page=5`; tope core habitual 100, respetar esquema si difiere.
- `_fields=id,title,link` para listados; añadir solo lo necesario. Para archivos: `source_url,mime_type,media_details.filesize,date,slug`.
- `search`, `slug`, `include`, `after`, `before`, `orderby` según intención y esquema.
- Leer `X-WP-Total` y `X-WP-TotalPages`; detener al alcanzar el máximo pedido. Si faltan cabeceras, usar páginas acotadas y señalar total desconocido.
- Deduplicar por sitio + ID. Paginación sobre un sitio cambiante no es una captura atómica; registrar fecha y límites, no prometer exhaustividad.
- Reutilizar raíz y mapa de rutas dentro de la sesión. No consultar todos los endpoints ni todos los esquemas por adelantado.

## 5. Diagnóstico

| Evidencia | Interpretación y recuperación |
|---|---|
| 404/HTML en `/wp-json/` | Probar anuncio y `rest_route`, no declarar API ausente |
| 401 JSON WP | Credencial ausente/inválida o requisito de autenticación; revisar operación |
| 403 JSON WP | Permiso insuficiente u otra política; no asumir contraseña errónea |
| 403 HTML / desafío | WAF/restricción probable; no evadir ni insistir |
| 400 `rest_invalid_param` | Corregir según esquema, no repetir igual |
| 400 página inválida | Revisar paginación y total; no convertir todo el resultado en vacío |
| 429 | Respetar `Retry-After`, pausar; máximo dos reintentos de lectura |
| Timeout/502/503/504 | Reintentar lectura hasta dos veces con espera 1 y 2 s, salvo Retry-After mayor; si exige espera prolongada informar y detener |
| TLS/DNS/conexión | Informar causa observada; no declarar que WordPress no existe |

## 6. Herramientas y ejemplo público

Los CLI incluidos resuelven descubrimiento, descarga de medios **públicos de cualquier formato** y **exportación JSON** de colecciones; no envían Application Passwords aunque existan variables de entorno. REST general lo ejecuta el agente con HTTP seguro o un script breve ajustado a la tarea, siguiendo las otras referencias.

Desde la raíz del repositorio:

```sh
python wp-api/assets/wp_api.py discover --site https://symaga.com
python wp-api/assets/wp_api.py media --site https://symaga.com --search "Silos granja Distribucion pienso" --mime pdf --max 3
python wp-api/assets/wp_api.py export --site https://symaga.com --recurso posts --max 5 --out datos
```

No fijar cantidades actuales a partir de evidencia histórica. Para la ejecución actual consultar el informe de validación.

## Fuentes oficiales

- [Descubrimiento WordPress](https://developer.wordpress.org/rest-api/using-the-rest-api/discovery/)
- [Esquema y OPTIONS](https://developer.wordpress.org/rest-api/extending-the-rest-api/schema/)
- [Tipos](https://developer.wordpress.org/rest-api/reference/post-types/)
- [Paginación](https://developer.wordpress.org/rest-api/using-the-rest-api/pagination/)
- [Medios](https://developer.wordpress.org/rest-api/reference/media/)
