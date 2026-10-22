# Etica, legalidad y limites

La API REST de WordPress es matizada: **poder** leer no equivale a **poder** redistribuir. Este documento fija el criterio del curso.

## 1. Que dice la ley (marco general)

- El contenido (textos, fotografias, planos, catalogos) esta protegido por derecho de autor desde su creacion, con o sin aviso. Un PDF publico sigue teniendo dueno.
- La base de datos del sitio puede tener proteccion adicional (proteccion *sui generis* de bases de datos en la Union Europea).
- El rastreo automatizado puede quedar alcanzado por los terminos de uso del sitio aunque no exista `robots.txt`.
- Uso con fines de investigacion, docencia o cita puede ampararse en excepciones (cita, ilustracion con fines didacticos, mineria de textos en ciertos marcos), pero **citar y analizar no es lo mismo que republicar**.

Nada de esto es asesoramiento legal: es el criterio conservador que aplicar en la cursada.

## 2. `robots.txt` no es un permiso

`robots.txt` es un mecanismo de exclusion voluntaria: dice donde un rastreador *deberia* no entrar. Un `Disallow:` vacio significa "no me excluyo", no "puedes hacer lo que quieras". El archivo relevante de esta skill:

```
User-agent: *
Disallow:
```

Eso habilita el rastreo general (es el default de Yoast SEO), y se cumple. No autoriza redistribuir el catalogo.

Reglas de trabajo:

1. Leer `robots.txt` y respetar las rutas excluidas.
2. No suplantar rastreadores exceptuados (Googlebot, bingbot): cambiar el `User-Agent` para pasar un `Disallow` es evasion.
3. Identificarse: `User-Agent` con nombre del curso/proyecto y un contacto.
4. Chequear los Terminos de Uso y, si el material es central para el trabajo, la pagina de condiciones/legales del sitio antes de automatizar volumen.

5. Leer robots del origen de cada recurso: un CDN u otro host puede tener reglas diferentes. Evaluar la ruta real con su subdirectorio, no solo `/wp-content/uploads`.
6. Ante fallo de red/5xx en robots, no asumir permiso para rastreo masivo. Un 404 puede indicar ausencia del archivo, no autorización legal. Los parsers simplificados de los CLI no son validadores completos de todas las variantes de robots; ante reglas complejas o duda, interpretar con una herramienta adecuada y aplicar el criterio conservador.
7. Administrar contenido propio mediante API autenticada no es lo mismo que rastrear terceros: requiere autorización del titular, permisos de WordPress y confirmación de cambios, aunque robots permita rastreo público.

## 3. Limites operativos que aplica la skill

| Limite | Valor por defecto | Por que |
|---|---|---|
| `per_page` | 5 en la muestra inicial; máximo core habitual 100, sujeto al esquema | Separar tamaño de consulta del límite del servidor |
| Pausa entre peticiones | 1 s | No degradar el servicio |
| Maximo por corrida | 1-3 en clase | Muestra, no espejo del sitio |
| Freno de volumen | 5 archivos (descarga) o solicitudes estimadas (exportación); por encima exige `--confirmo-bajar N` (exit 3) | Obliga a mirar el costo antes del lote |
| Alcance | Busqueda o URL puntual | Evitar "bajar toda la biblioteca" |
| Credenciales | Ninguna para contenido publico | Sin datos propios expuestos |
| Reutilizacion | Por `sha256` | No redescargar lo ya obtenido |

## 4. Derechos: que documentar antes de publicar un dataset

- Fuente (dominio), fecha y hora de captura.
- `id` y `source_url` de cada material, con `sha256`.
- Licencia o condicion observada (pie de pagina, pagina legal, metadatos).
- Base de uso: cita, analisis, ilustracion didactica, etc.
- Si el material es protegido y el trabajo lo va a **redistribuir**, pedir permiso: el contacto suele figurar en el sitio.

Ejemplo del material del curso: el PDF del catálogo proviene del sitio corporativo de un fabricante (catálogo comercial de silos). Es útil para *practicar* la descarga y el análisis, pero no es material de publicación abierta: se cita como fuente y se redistribuye solo si hay autorización.

## 5. Datos personales

La biblioteca de medios de un WordPress corporativo puede contener fotos de personas, organigramas o fichas. Si aparecen datos personales:

- Minimizar: no recolectar lo que no hace falta.
- No reidentificar ni cruzar con otras fuentes.
- Anonimizar antes de publicar (rostros, nombres, contactos).
- Aplicar el marco de proteccion de datos vigente (ej. RGPD en la UE, Ley 25.326 en Argentina).

## 6. Cuatro frases para el aula

1. **Publico no es libre.** Ver el PDF no habilita republicarlo.
2. **Rapido no es cortes.** Bajar 5.000 archivos en cinco minutos es abuso aunque funcione.
3. **Trazable no es legal.** Un buen manifiesto muestra *que* hiciste; no lo justifica.
4. **Preguntar es barato.** Un correo al sitio resuelve lo que una discusion legal no.
