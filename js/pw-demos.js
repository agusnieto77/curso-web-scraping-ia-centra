'use strict';
/* Clase 05 · Animaciones sobre el motor compartido (py-engine.js).
   Las salidas de consola y las cifras de quotes.toscrape.com se midieron con Playwright 1.x y Chromium. */

/* Diapositiva 2 · Quién decide el próximo clic. */
PY.pane({
  selector: '.pwmode',
  gap: 850,
  steps: [
    {
      notes: [
        'Los pasos se escriben y se revisan antes de ejecutar.',
        'Playwright repite exactamente las mismas acciones en cada corrida.',
        'No hay modelo durante la ejecución: no hay costo por tokens.'
      ],
      verdict: ['✓', 'Repetible y auditable: la opción por defecto para una tarea conocida.', 'same']
    },
    {
      notes: [
        'El modelo elige cada acción, pero una persona supervisa.',
        'Opera el navegador mediante herramientas MCP o CLI y deja un registro.',
        'El resultado esperable no son los datos: es un script que se puede revisar.'
      ],
      verdict: ['✓', 'Explorar con IA, ejecutar con código: el agente investiga y deja un script.', 'same']
    },
    {
      notes: [
        'El modelo decide en cada ejecución: el recorrido puede variar.',
        'Cada corrida consume tokens y depende del proveedor del modelo.',
        'Bhardwaj, Diwan y Wang (2026): 35 sitios, cinco niveles de seguridad, menos de 5 ajustes al prompt.'
      ],
      verdict: ['!', 'Útil si la interfaz cambia; en sitios estáticos, el script asistido suele ser más simple y rápido.', 'diff']
    }
  ]
});

/* Diapositiva 3 · Playwright: navegador, localizadores y esperas. */
PY.console({
  selector: '.pwflow',
  phases: [
    {
      lines: [
        ['cmd', 'requests.get(URL).text.count(\'class="quote"\')'],
        ['out', '0'],
        ['cmd', 'page = p.chromium.launch(headless=True).new_page()'],
        ['cmd', 'page.goto(URL).status'],
        ['out', '200']
      ],
      note: 'Con requests, /js/ llega sin citas: las escribe JavaScript. El navegador las ejecuta.'
    },
    {
      lines: [
        ['cmd', 'page.locator("div.quote").count()'],
        ['out', '10'],
        ['cmd', 'page.locator("span.text").first.inner_text()'],
        ['out', '\'“The world as we have created it is a process…”\'']
      ],
      note: 'CSS para la estructura del documento: cada cita es un div.quote con su span.text.'
    },
    {
      lines: [
        ['cmd', 'page.get_by_role("link", name="Next").click()'],
        ['cmd', 'page.wait_for_url("**/js/page/2/")'],
        ['cmd', 'expect(page.locator("div.quote")).to_have_count(10)'],
        ['dim', '# pasa: la página 2 ya tiene sus 10 citas']
      ],
      note: 'El control se localiza por rol y nombre accesible; se espera una condición, no segundos.'
    }
  ]
});

/* Diapositiva 4 · Scroll infinito con final explícito. */
PY.scene({
  selector: '.pwscroll',
  gap: 800,
  hot: [{ at: 6, selector: '[data-at="6"] .box' }],
  itemSteps: [0, 1, 6],
  notes: [
    'Ciclo 1: se leen las citas visibles y se guardan sus textos como identificadores.',
    'Se desplaza hasta la última cita y se espera a que cambie la cantidad.',
    'Llegan 20: los lotes no tienen tamaño fijo.',
    'Llegan 30 de una vez: contar lotes no sirve para saber cuánto falta.',
    'Se compara contra lo ya visto, no contra la posición en la lista.',
    'Ciclo 6: 100 citas acumuladas.',
    'Ciclo 7: ninguna cita nueva. Es la condición de salida.',
    'Fin explícito: sin novedades o MAX_CICLOS, lo que ocurra primero.',
    '100 citas, 0 duplicadas. Medido sobre quotes.toscrape.com/scroll.'
  ]
});

/* Diapositiva 5 · Qué recibe el modelo. */
PY.pane({
  selector: '.pwview',
  gap: 850,
  steps: [
    {
      notes: [
        'page.content() devuelve el DOM ya renderizado.',
        'Incluye scripts, clases y atributos que el modelo no necesita.',
        'Es la mejor entrada para un parser, no para una conversación.'
      ],
      verdict: ['!', 'Preciso pero ruidoso: conviene al script, no al contexto del modelo.', 'diff']
    },
    {
      notes: [
        'aria_snapshot() resume la página como árbol de accesibilidad.',
        'Cada elemento aparece con su rol y su nombre.',
        'El enlace conserva su destino.',
        'Playwright MCP añade una referencia [ref=e…] para actuar sobre él.'
      ],
      verdict: ['✓', 'En esta página el snapshot es 4,8 veces más corto y nombra los controles por su rol.', 'same']
    },
    {
      notes: [
        'Una captura de 1280 × 720 en PNG.',
        'Requiere un modelo multimodal que interprete la imagen.',
        'Huang y Joung (2026) combinan imagen, herramientas y un procedimiento de cinco etapas.'
      ],
      verdict: ['!', 'La imagen ve lo que el árbol no expone, a cambio de un modelo multimodal y más tokens.', 'diff']
    }
  ]
});

/* Diapositiva 6 · Las cuatro capas de un agente de navegador. */
PY.scene({
  selector: '.pwstack',
  gap: 900,
  itemSteps: [0, 2, 3],
  notes: [
    'El modelo decide la próxima acción. Por sí solo no abre páginas.',
    'El arnés sostiene la conversación, expone herramientas y ejecuta sus llamadas.',
    'El driver traduce «hacer clic en Next» en órdenes para el navegador.',
    'El motor ejecuta JavaScript y mantiene el DOM. Cada frontera entre capas suma latencia; lo que llega al modelo, tokens.'
  ]
});

/* Diapositiva 7 · Del navegador común a los navegadores para agentes. */
PY.pane({
  selector: '.pwtools',
  gap: 850,
  steps: [
    {
      notes: [
        'Chrome, Edge, Firefox o Safari: ventana, pestañas, extensiones y perfil con logins.',
        'Ese perfil da alcance y riesgo: solo cuentas propias o autorizadas, sin sortear CAPTCHA.',
        'Automatizarlo es un añadido (CDP) y renderiza aunque nadie mire: pesado a escala.'
      ],
      verdict: ['!', 'Sirve para explorar con tu sesión; no para recolectar a escala.', 'diff']
    },
    {
      notes: [
        'Chromium es el proyecto open source; el navegador de cada día añade sincronización y servicios.',
        'Playwright lo lanza headless con perfil limpio: sin tus logins, la sesión se lleva aparte.',
        'Playwright es biblioteca, no navegador: maneja Chromium, Firefox y WebKit con script, MCP o CLI.'
      ],
      verdict: ['✓', 'El motor que usan casi todas las demás herramientas.', 'same']
    },
    {
      notes: [
        'OpenCode Browse trabaja sobre tu Chrome, Edge o Brave y te devuelve la pestaña para login o 2FA.',
        'ego lite modifica Chromium: Spaces en paralelo, Snapshot de 200–400 tokens y varias acciones por llamada.',
        'Lightpanda reemplaza el motor (Zig, sin render): ~9×/16× según su proveedor; sin ventana ni perfil personal.'
      ],
      verdict: ['!', 'Elegir por sesión, motor y control; medir con el sitio propio antes de cambiar.', 'diff']
    }
  ]
});

/* Diapositiva 8 · Criterios con evidencia. */
PY.pane({
  selector: '.pwdecide',
  gap: 850,
  steps: [
    {
      notes: [
        'Primero, el panel Network: ¿el dato ya llega como JSON o HTML?',
        'Con navegador se ejecuta todo el JavaScript, pero cuesta recursos a escala.',
        'Kositsyna y Lloret-Gazo (2026): extracción sin navegador con reglas adaptativas.'
      ],
      verdict: ['✓', 'Si el dato llega por HTTP, el navegador es un costo adicional.', 'same']
    },
    {
      notes: [
        'BaRA recorre el sitio en anchura: primero todos los enlaces de un nivel.',
        'Comprueba que cada enlace exista antes de seguirlo.',
        'Reintenta con su historial y trabaja con un presupuesto fijo de interacciones.'
      ],
      verdict: ['✓', 'Un agente que recorre un sitio debe demostrar que cada enlace existe (Lee et al., 2026).', 'same']
    },
    {
      notes: [
        'WCXB: siete tipos de página, 13 sistemas de extracción.',
        'En artículos, los mejores sistemas convergen.',
        'En listados, foros y productos el desempeño se dispersa.'
      ],
      verdict: ['!', 'Que funcione con noticias no prueba que funcione con listados (Foley, 2026).', 'diff']
    }
  ]
});
