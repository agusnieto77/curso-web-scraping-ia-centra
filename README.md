# Web Scraping Asistido por IA: recolección inteligente de datos

## Presentación

El presente curso está orientado a quienes necesitan recolectar datos que no se encuentran disponibles mediante APIs públicas o repositorios ya estructurados. A lo largo de los encuentros se abordará el diseño y la implementación de flujos de recolección de información mediante scraping asistido por inteligencia artificial, combinando herramientas de R, Python y Playwright para extraer datos desde prensa digital, redes sociales y archivos en línea.

El curso propone una aproximación eminentemente práctica, centrada en la construcción de agentes y rutinas de scraping capaces de adaptarse a entornos web heterogéneos, incluyendo páginas estáticas, dinámicas y sitios con múltiples niveles de navegación. Junto con ello, se trabajará sobre criterios para documentar procesos de captura, organizar datos recolectados y evaluar la calidad, trazabilidad y reproducibilidad de los resultados obtenidos.

Asimismo, se prestará especial atención a las dimensiones éticas y legales del scraping web, considerando que la recolección automatizada de datos exige evaluar restricciones de acceso, términos de uso, privacidad, derechos sobre contenidos y buenas prácticas de investigación responsable. Durante el curso se compartirán materiales, scripts, ejemplos de trabajo y referencias de apoyo para que cada estudiante pueda adaptar los procedimientos aprendidos a sus propios proyectos de investigación académica o profesional.

## Objetivos

### Objetivo general

Aproximar a quienes cursan a los fundamentos conceptuales, metodológicos y técnicos del web scraping asistido por inteligencia artificial, brindando herramientas para diseñar y ejecutar procesos de recolección inteligente de datos desde sitios web, prensa digital, redes sociales y archivos en línea, con criterios de sistematicidad, trazabilidad y adecuación ética y legal.

### Objetivos de aprendizaje específicos

- Identificar distintos tipos de entornos web y evaluar la estrategia de extracción más adecuada según la estructura de la fuente, la naturaleza de los datos y los obstáculos técnicos presentes.
- Conocer y utilizar herramientas de scraping en R y Python para extraer, limpiar y estructurar información proveniente de páginas estáticas y dinámicas.
- Incorporar el uso de Playwright y asistentes basados en IA para automatizar tareas complejas de navegación, inspección y captura de datos.
- Diseñar flujos de trabajo reproducibles para la recolección de datos desde medios digitales, redes sociales y archivos documentales en línea.
- Organizar y documentar los datos obtenidos en formatos tabulares adecuados para su análisis posterior.
- Reconocer los principales problemas éticos y legales asociados al scraping web y desarrollar criterios para una práctica responsable de la recolección automatizada de datos.

## Programa

| Sesión | Contenidos | Duración |
| --- | --- | --- |
| 1. Introducción al scraping asistido por IA | Presentación general del curso. ¿Qué es el web scraping y cuándo conviene utilizarlo con asistencia de la IA generativa? Datos accesibles, datos no estructurados y límites de las APIs. Introducción a los agentes de scraping con IA. Panorama de herramientas: R, Python, Playwright y modelos de apoyo para extracción y parsing. | 2 horas cronológicas |
| 2. Estructura de la web y estrategias de extracción | HTML, CSS, selectores, XPath y carga dinámica de contenidos. Inspección de páginas con herramientas del navegador asistida por IA. Diferencias entre páginas estáticas y dinámicas. Criterios para decidir entre scraping simple, automatización del navegador o extracción asistida por IA. | 2 horas cronológicas |
| 3. Scraping con R para páginas estáticas y semiestructuradas | Introducción a flujos de trabajo en R con IA. Uso de paquetes orientados a scraping y parsing. Extracción de nodos, tablas, textos y metadatos. Limpieza inicial y transformación de datos semiestructurados en estructuras tabulares. | 2 horas cronológicas |
| 4. Scraping con Python y automatización de procesos | Introducción a Python con IA para scraping. Requests, BeautifulSoup, pandas y estrategias de paginación. Desarrollo de scripts reutilizables para captura seriada de información. Registro de errores, validación de resultados y almacenamiento de datos. | 2 horas cronológicas |
| 5. Navegación automatizada con Playwright | Automatización asistida por IA para la navegación en sitios dinámicos. Renderizado de JavaScript, interacción con botones, formularios, scroll, login y esperas. Extracción de contenidos en contextos más complejos. Introducción a patrones de scraping resiliente. | 2 horas cronológicas |
| 6. Recolección de datos en prensa digital, redes sociales y archivos en línea | Estrategias diferenciales para medios de prensa, plataformas sociales y repositorios documentales. Captura de textos, enlaces, imágenes, metadatos y series documentales. Problemas frecuentes: bloqueos, cambios de estructura, duplicados y normalización de resultados con IA. | 2 horas cronológicas |
| 7. Agentes de scraping con IA y flujos híbridos | Integración de modelos de IA para asistir la detección de patrones, la generación de selectores, la clasificación de páginas y la extracción contextual de información. Diseño de pipelines híbridos entre scraping tradicional y agentes inteligentes. Evaluación de costos, ventajas y límites. | 2 horas cronológicas |
| 8. Ética, legalidad y documentación del proceso | Términos de uso, robots.txt, privacidad, consentimiento, derechos sobre contenidos, trazabilidad metodológica y documentación reproducible. Buenas prácticas para investigación responsable. Cierre del curso y discusión de casos aplicados a proyectos de quienes cursan. | 2 horas cronológicas |

## Profesor/profesores (Orcid y breve reseña)

Agustín Nieto, [https://orcid.org/0000-0003-4467-873X](https://orcid.org/0000-0003-4467-873X)

Profesor y doctor en historia por la Universidad Nacional de Mar del Plata. Se desempeña como docente en el Departamento de Sociología de la Facultad de Humanidades del UNMdP. En los últimos cinco años ha impartido cursos sobre el uso de R en las ciencias sociales y las humanidades en carreras de grado y posgrado. Sus temas de interés se articulan en torno al análisis computacional de la conflictividad social pasada y presente. En el ámbito de la investigación se ha vinculado con proyectos de alto nivel académico y profesional desarrollados por prestigiosas instituciones internacionales y del sistema de investigación científica en Argentina (AUIP, CONICET). Actualmente es investigador independiente del CONICET con lugar de trabajo en el Instituto de Humanidades y Ciencias Sociales. Es autor y desarrollador de “ACEP” y “TweetScraperR”. ACEP: se trata de un paquete de funciones en lenguaje R útiles para la detección y el análisis de eventos de protesta en corpus de textos periodísticos. Sus funciones son aplicables a cualquier corpus de textos (https://agusnieto77.github.io/ACEP/). TweetScraperR: se trata de un paquete de funciones en lenguaje R útiles para extraer datos de X/Twitter, incluidos tweets, usuarixs y metadatos asociados. (https://github.com/agusnieto77/TweetScraperR).

## Modalidad

On line con clases en directo. Sesiones grabadas y material disponible en el campus.

## Fechas

12, 15, 19, 22, 26, 29 de octubre y 2, 5 de noviembre de 2026.

## Nº de horas

16 horas

## Horario

16:30h-18:30h

## Organizan

Fundación centra y Asociación Andaluza de Sociología

## Necesidades (alumnos)

- Para participar en el curso, cada estudiante debe disponer de un ordenador con permisos para instalar programas y acceso estable a internet. Es recomendable tener instalados previamente R, RStudio, Python y Visual Studio Code (o algún entorno equivalente), además de un navegador actualizado y Playwright configurado desde las primeras sesiones.
- Se trabajará principalmente con software libre y bibliotecas de código abierto, sin necesidad de licencias privativas. Si se utilizan servicios externos o modelos restringidos, se facilitarán alternativas gratuitas. Se espera que quienes cursan tengan conocimientos básicos o intermedios de programación orientada al análisis de datos y experiencia mínima en R o Python, además de familiaridad con estructuras de archivos y navegación web.
