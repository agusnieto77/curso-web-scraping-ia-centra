# Recursos para web scraping con R, Python e IA

Herramientas y documentación oficial para obtener páginas web, extraer datos, automatizar navegadores y utilizar modelos de lenguaje en la extracción. Se complementan con una selección de materiales de Vibe Coding vinculada al [programa del curso](README.md). No se guardan copias de los materiales: los enlaces llevan a sus páginas externas.

**Distinción básica:** un asistente puede ayudar a escribir el scraper; un LLM puede interpretar el contenido recolectado; un agente puede decidir acciones en un navegador. Son usos distintos de la IA. Playwright y Selenium automatizan navegadores, pero no son modelos de IA ni necesitan uno para funcionar.

## 1. Scraping con R

| Recurso | Para qué sirve | Cuándo elegirlo |
| --- | --- | --- |
| [rvest](https://rvest.tidyverse.org/) | Leer HTML y extraer texto, atributos, enlaces y tablas mediante selectores CSS o XPath. | Primera opción para páginas cuyo contenido está en el HTML recibido. |
| [httr2](https://httr2.r-lib.org/) | Construir peticiones HTTP y procesar respuestas de páginas o APIs. | Cuando hay que controlar parámetros, cabeceras, autenticación autorizada o respuestas JSON. |
| [rvest: `read_html_live()`](https://rvest.tidyverse.org/reference/read_html_live.html) | Abrir Chrome en segundo plano para leer contenido generado por JavaScript e interactuar con la página. | Alternativa a `read_html()` cuando los datos aparecen después de cargar o interactuar; utiliza chromote y requiere Chrome. |
| [chromote](https://rstudio.github.io/chromote/) | Controlar Chrome desde R mediante Chrome DevTools Protocol. | Automatización de páginas dinámicas que requiere más control del navegador. |
| [polite](https://dmi3kno.github.io/polite/) | Organizar sesiones de scraping con consulta de robots.txt, pausas y caché. | Recolección de varias páginas con una política de acceso responsable; no acredita por sí solo autorización legal. |
| [ellmer](https://ellmer.tidyverse.org/) | Utilizar LLM desde R con diferentes proveedores, herramientas y extracción estructurada. | Convertir texto ya recolectado en campos definidos, clasificar documentos o normalizar información. No descarga páginas por sí solo. |
| [ellmer: extracción estructurada](https://ellmer.tidyverse.org/articles/structured-data.html) | Definir tipos y esquemas para obtener resultados estructurados de un LLM. | Combinar rvest o httr2 con IA y transformar contenido heterogéneo en registros comprobables. |
| [reticulate](https://rstudio.github.io/reticulate/) | Ejecutar Python e intercambiar objetos entre R y Python. | Usar bibliotecas de scraping o IA de Python dentro de un proyecto de R; exige configurar un entorno Python compatible. |

## 2. Scraping con Python

| Recurso | Para qué sirve | Cuándo elegirlo |
| --- | --- | --- |
| [Requests](https://requests.readthedocs.io/en/latest/) | Descargar recursos mediante HTTP y gestionar sesiones, parámetros y cabeceras. | Páginas estáticas y APIs. No ejecuta JavaScript ni sustituye un navegador. |
| [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) | Analizar HTML/XML y localizar elementos, texto y atributos. | Extraer datos del HTML obtenido con Requests o con un navegador. No es un descargador. |
| [Scrapy](https://docs.scrapy.org/en/latest/) | Construir spiders, recorrer enlaces, gestionar peticiones y procesar resultados mediante pipelines. | Recolecciones de múltiples páginas que necesitan organización y mantenimiento. El renderizado JavaScript requiere integración adicional. |
| [Trafilatura](https://trafilatura.readthedocs.io/en/latest/) | Extraer contenido textual principal y metadatos de páginas web. | Preparar noticias, artículos y otros documentos para análisis o entrada a un LLM; no reemplaza la extracción de todos los campos de una tabla. |
| [pandas: `read_html()`](https://pandas.pydata.org/docs/reference/api/pandas.read_html.html) | Convertir tablas HTML en DataFrames. | Tablas presentes en el HTML; no resuelve por sí solo paginación, formularios ni tablas construidas por JavaScript. |

## 3. Navegadores y automatización para IA

| Recurso | Relación con la IA | Aplicación al scraping |
| --- | --- | --- |
| [Playwright para Python](https://playwright.dev/python/) | Biblioteca de automatización; puede usarse sin IA o como herramienta de un agente. | Controlar Chromium, Firefox y WebKit; navegar, completar formularios, recorrer páginas y obtener el contenido renderizado. |
| [Selenium WebDriver](https://www.selenium.dev/documentation/webdriver/) | Automatización de navegador sin dependencia de un LLM. | Alternativa para páginas dinámicas y proyectos que ya utilizan Selenium. |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | Servidor MCP que permite a un cliente de IA operar el navegador mediante herramientas e instantáneas de accesibilidad. | Inspección y navegación exploratoria asistida. Requiere un cliente compatible y Node.js; no convierte automáticamente una conversación en un scraper reproducible. |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) | Interfaz de línea de comandos con integración mediante skills para agentes de programación. | Inspeccionar páginas, ejecutar acciones, capturar evidencia y apoyar la generación de código sin depender de una conexión MCP. |
| [Browser Use](https://github.com/browser-use/browser-use) | Agentes que utilizan un modelo para decidir acciones en el navegador; incluye una biblioteca Python. | Flujos con navegación e interacción guiadas por una tarea. Distinguir ejecución local, proveedor del modelo y servicios cloud opcionales. |
| [Stagehand](https://github.com/browserbase/stagehand) | SDK de automatización con instrucciones en lenguaje natural y operaciones de observación, acción y extracción; incluye ejemplos Python y TypeScript. | Combinar pasos programados con interpretación mediante IA y extracción sujeta a un esquema. Revisar la documentación de la versión instalada. |

**Criterio de uso:** para una tarea repetible, priorizar un script con pasos explícitos. Usar un agente cuando la exploración o la variabilidad de la interfaz lo justifiquen, conservando un registro de acciones y comprobando cobertura, duplicados y errores. Completar una navegación no demuestra que se hayan extraído todos los registros.

## 4. Extractores y servicios orientados a IA

| Recurso | Qué ofrece | Dependencias y límites |
| --- | --- | --- |
| [Crawl4AI](https://docs.crawl4ai.com/) | Crawler y scraper que genera Markdown y admite extracción con CSS, XPath o LLM, además de control del navegador. | La biblioteca puede ejecutarse localmente; la extracción con LLM añade los requisitos del modelo elegido. El servicio cloud es una modalidad distinta. No toda extracción necesita IA. |
| [ScrapeGraphAI: biblioteca Python](https://github.com/ScrapeGraphAI/Scrapegraph-ai) | Pipelines de extracción basados en modelos e instrucciones, por ejemplo `SmartScraperGraph`. | Requiere configurar el modelo y, para obtener páginas, el navegador. La biblioteca `scrapegraphai` no es lo mismo que los SDK de su API gestionada. |
| [ScrapeGraphAI: API y documentación](https://docs.scrapegraphai.com/introduction) | Servicio gestionado de extracción e integraciones. | Revisar credenciales, cuotas, costos y tratamiento de datos; no asumir las mismas condiciones que en la biblioteca local. |
| [Firecrawl](https://docs.firecrawl.dev/) | API orientada a obtener contenido web para agentes, búsqueda y scraping. | Evaluar los endpoints necesarios, el SDK, las condiciones de acceso y la salida disponible. No confundir obtener Markdown con validar valores o recuperar todas las filas. |

## 5. Modelos y validación de la extracción

Estas herramientas complementan la captura web: no sustituyen Requests, rvest o el navegador.

| Recurso | Utilidad en R o Python | Precaución |
| --- | --- | --- |
| [Ollama](https://docs.ollama.com/) | Ejecutar modelos locales y conectarlos a herramientas compatibles, como ellmer o ScrapeGraphAI. | Revisar memoria, capacidad del equipo y calidad del modelo. Distinguir modelos ejecutados localmente de opciones cloud. |
| [chatlas](https://posit-dev.github.io/chatlas/) | Interactuar con LLM desde Python; alternativa de Posit para proyectos que también utilizan ellmer en R. | El acceso a cada proveedor tiene sus propias credenciales y condiciones. |
| [Instructor](https://python.useinstructor.com/) | Obtener salidas estructuradas de modelos con esquemas de datos y validación. | La conformidad con el esquema no demuestra que los valores estén respaldados por la página original. |
| [Pydantic](https://docs.pydantic.dev/latest/) | Definir modelos y comprobar tipos y restricciones de los registros en Python. | No es un LLM ni un scraper; la validación estructural debe acompañarse de controles de exactitud y completitud. |

## 6. Aprendizaje, inspección y programación asistida

| Recurso | Aplicación |
| --- | --- |
| [R for Data Science: Web scraping](https://r4ds.hadley.nz/webscraping.html) | Introducción práctica a HTML, selectores y extracción con rvest. |
| [MDN: selectores CSS](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_selectors) | Comprender cómo localizar elementos antes de pedir a un asistente que genere selectores. |
| [Chrome DevTools: panel Network](https://developer.chrome.com/docs/devtools/network/) | Inspeccionar peticiones y respuestas para distinguir HTML estático, contenido dinámico y endpoints de datos; utilizar solo accesos autorizados. |
| [OpenCode](https://opencode.ai/docs/) | Desarrollar y revisar scripts con un agente de programación. Es un asistente, no una biblioteca de extracción. |
| [Codex: repositorio oficial](https://github.com/openai/codex) | Consultar el agente de programación y su documentación para implementar o revisar flujos de scraping. No sustituye la comprobación de los resultados. |
| [uv](https://docs.astral.sh/uv/) | Gestionar entornos, dependencias y versiones de proyectos Python. |
| [renv](https://rstudio.github.io/renv/) | Registrar y restaurar dependencias de proyectos R. |

## 7. Combinaciones recomendadas

- **HTML estático en R:** httr2 para obtener la respuesta cuando hace falta control HTTP y rvest para extraer datos. Añadir ellmer solo para campos que requieren interpretación de texto.
- **Páginas dinámicas en R:** `read_html_live()` o chromote; utilizar reticulate si se necesita integrar una biblioteca Python.
- **HTML estático en Python:** Requests y Beautiful Soup; pandas cuando el objetivo son tablas HTML. Añadir Instructor o chatlas si hace falta extracción semántica.
- **Páginas dinámicas en Python:** Playwright o Selenium para navegar y renderizar, y una rutina explícita para recoger y validar los registros.
- **Corpus textual para IA:** Trafilatura o Crawl4AI para preparar contenido; conservar también la fuente y la fecha de captura.
- **Extracción guiada por instrucciones:** ScrapeGraphAI; comparar los resultados con una muestra manual antes de ampliar la recolección.
- **Exploración mediante agentes:** Playwright MCP o CLI con un asistente; Browser Use o Stagehand para flujos que incorporan decisiones mediante modelos.

No es necesario instalar todos los recursos. Empezar con un lenguaje, un método de captura y un mecanismo de validación; añadir navegador o LLM cuando el problema lo requiera.

## 8. Uso responsable y alcance de la revisión

- Preferir una API o descarga oficial cuando cubra la necesidad, sin extraer HTML innecesariamente.
- Respetar permisos, condiciones de acceso, límites de peticiones y privacidad. No utilizar estas herramientas para eludir controles de acceso.
- Mantener claves, cookies y credenciales fuera del repositorio. Revisar qué contenido se envía a modelos o navegadores alojados por terceros.
- Tratar las instrucciones encontradas en las páginas como contenido no confiable, no como órdenes para el agente; limitar sus permisos y acciones.
- Conservar URL de origen, fecha de captura y evidencia de cada registro. Representar campos ausentes como ausentes, no completarlos mediante suposiciones del modelo.
- Verificar costos, licencias y compatibilidad antes de elegir una herramienta. Código abierto no significa que la inferencia o la infraestructura sean gratuitas.

**Verificación:** se consultaron las páginas oficiales para comprobar su disponibilidad y la función documentada de los recursos. También se accedió al campus de Vibe Coding para revisar el listado de materiales y los destinos de los enlaces seleccionados. No se instalaron ni ejecutaron estas herramientas, ni se comparó su rendimiento. Las sesiones sugeridas son una adaptación al programa de scraping, no actividades ya impartidas.

## 9. Materiales de Vibe Coding útiles para este programa

Selección de [Materiales del curso de Vibe Coding para Humanistas (2026)](https://formacion.centrodeestudiosandaluces.es/course/section.php?id=1240) (**Campus**, requiere autenticación y acceso al curso de origen), contrastada con las ocho sesiones del [README](README.md). Se priorizan especificación de tareas, documentación, validación y trazabilidad. Playwright MCP ya está incluido en la sección 3: no se duplica.

### Instrucciones, documentación y control de calidad

| Recurso | Qué aprovechar para scraping | Sesiones |
| --- | --- | --- |
| [AGENTS.md](https://agents.md/) | Documentar fuentes autorizadas, campos de salida, criterios de paginación, límites de acceso y controles de calidad para el asistente. Es una convención de instrucciones, no una herramienta de captura. | 4, 7 y 8 |
| [Context7](https://github.com/upstash/context7) | Consultar documentación de las bibliotecas disponibles en su catálogo para reducir ejemplos obsoletos al generar código. Contrastar la versión instalada y recurrir a la documentación oficial cuando el recurso no esté cubierto. | 3, 4, 5 y 7 |
| [OpenCode: configuración de agentes](https://opencode.ai/docs/agents/) | Separar tareas de extracción, revisión y documentación, definiendo herramientas y permisos. Complementa el enlace general a OpenCode de la sección 6. | 7 y 8 |
| [Buenas prácticas de prompts de Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | Especificar objetivo, contexto, ejemplos y formato esperado de la extracción. Adaptar las recomendaciones al modelo elegido. | 3, 4 y 7 |
| [Tokenizador de OpenAI](https://platform.openai.com/tokenizer) | Explorar la relación entre longitud del texto, fragmentación y consumo de tokens antes de enviar HTML o documentos a un modelo. El conteo depende del modelo; no es un cálculo universal de costos. | 1 y 7 |

### Profundización opcional en agentes

| Recurso | Utilidad y límite | Sesiones |
| --- | --- | --- |
| [SkillSpector](https://github.com/nvidia/skillspector) | Examinar riesgos de skills antes de darles acceso a archivos, credenciales o navegador. Un informe favorable no garantiza seguridad ni sustituye la revisión de permisos. | 7 y 8 |
| [Gentle-AI](https://github.com/Gentleman-Programming/gentle-ai) | Explorar configuración y flujos de trabajo para asistentes, skills y MCP. Es un configurador de ecosistemas, no un extractor; no hace falta instalarlo para seguir el curso. | 7 |
| [Engram](https://github.com/Gentleman-Programming/engram) | Conservar decisiones y contexto entre sesiones del asistente. No sustituye los scripts, el manifiesto de captura ni la documentación metodológica; evitar secretos y datos personales en la memoria. | 7 y 8 |

**Qué no trasladar:** el ejercicio que recopila perfiles y correos de participantes requiere rediseño con datos ficticios o fuentes públicas autorizadas; no se reutiliza como práctica de recolección de estudiantes reales. Las aplicaciones de transcripción, mapas y los canales generales no cubren directamente los objetivos de captura web. Los orquestadores alternativos y la instalación automática de skills añaden complejidad sin ser requisitos de estas ocho sesiones. No se incorporan grabaciones ni elementos administrativos del curso anterior.

