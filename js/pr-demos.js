'use strict';
/* Clase 06 · Animaciones sobre el motor compartido (py-engine.js).
   Las cifras de prensa corresponden a datos/elmundo_andalucia.csv: 207 filas de 4 páginas, 7 sin fecha. */

/* Diapositiva 2 · Tres tipos de fuente, tres unidades. */
PY.pane({
  selector: '.prunit',
  gap: 850,
  steps: [
    {
      notes: [
        'Una noticia es una página web: lo que ves en el navegador.',
        'Ejemplo del curso: la sección Andalucía de elmundo.es dio 207 noticias.',
        'Cada noticia se convierte en una fila con cuatro datos.'
      ],
      verdict: ['✓', 'Prensa: una noticia = una fila de la tabla.', 'same']
    },
    {
      notes: [
        'Una publicación es un mensaje suelto: un tuit, un post, un comentario.',
        'De cada una guardamos quién la escribió, qué dice, cuándo y cuántas reacciones tuvo.',
        'La red decide qué te muestra: lo que recoges es una parte, nunca el total.'
      ],
      verdict: ['!', 'Redes: una publicación = una fila, pero nunca tienes todas.', 'diff']
    },
    {
      notes: [
        'Un documento es un archivo: un PDF, una foto escaneada, una grabación o un video.',
        'Casi siempre viene con una ficha que lo describe, como la etiqueta de un libro.',
        'En una revista académica (OJS), la ficha es la página del artículo y el documento es el PDF.'
      ],
      verdict: ['✓', 'Archivos: un documento = su ficha + el archivo.', 'same']
    }
  ]
});

/* Diapositiva 3 · Prensa: del listado a la tabla. */
PY.console({
  selector: '.prflow',
  phases: [
    {
      lines: [
        ['dim', '# Pedimos la página, como el navegador'],
        ['cmd', 'pagina = s.get(URL_SECCION)'],
        ['cmd', 'pagina.status_code'],
        ['out', '200        # 200 = «todo bien»'],
        ['dim', '# Lo mismo con las páginas 2, 3 y 4']
      ],
      note: 'Descargar es pedirle la página al sitio. El 200 es su forma de responder «aquí la tienes».'
    },
    {
      lines: [
        ['dim', '# Cada noticia está en una «caja»'],
        ['cmd', 'cajas = pagina.select("article")'],
        ['dim', '# De cada caja: título, enlace, antetítulo, fecha'],
        ['cmd', 'tabla.shape'],
        ['out', '(207, 4)   # 207 noticias × 4 datos']
      ],
      note: 'Una caja = una noticia = una fila. Si contáramos enlaces, cada noticia saldría repetida.'
    },
    {
      lines: [
        ['dim', '# ¿Cuántas noticias no traen fecha?'],
        ['cmd', 'tabla["fecha"].isna().sum()'],
        ['out', '7'],
        ['dim', '# Quedan vacías: no se inventa ninguna'],
        ['cmd', 'tabla.to_csv("elmundo_andalucia.csv")']
      ],
      note: 'El CSV es una tabla que se abre con Excel. Las 7 fechas que faltan quedan en blanco.'
    }
  ]
});

/* Diapositiva 4 · Fechas. */
PY.pane({
  selector: '.prdate',
  gap: 850,
  steps: [
    {
      notes: [
        '«Hace 2 horas» depende de cuándo mires: mañana dirá otra cosa.',
        'La página suele guardar la fecha exacta en su código, aunque no se vea.',
        'Si no la guarda, la fila queda sin fecha: nunca se adivina.'
      ],
      verdict: ['✓', 'La fecha se lee de la página, no se calcula ni se supone.', 'same']
    },
    {
      notes: [
        'El 10 de noviembre el diario publica la noticia.',
        'Ese mismo día corrige el título: la fecha que se ve puede ser la de la corrección.',
        'El 12 la guardamos nosotros: esa fecha la anotamos siempre.'
      ],
      verdict: ['!', 'Tres fechas, tres significados: anotar cuál es cuál.', 'diff']
    },
    {
      notes: [
        'Por la mañana el titular dice que cortaron la autovía.',
        'Por la tarde, en el mismo enlace, dice que la reabrieron.',
        'Si guardamos una, anotamos cuál y qué día.'
      ],
      verdict: ['✓', 'Una noticia puede cambiar: guardar también el momento.', 'same']
    }
  ]
});

/* Diapositiva 5 · Redes: lo visible no es el total. */
PY.pane({
  selector: '.prnet',
  gap: 850,
  steps: [
    {
      notes: [
        'Una API es una puerta oficial que la red ofrece para pedir datos, con sus reglas.',
        'Ejemplo: YouTube permite pedir los comentarios de un video por su API.',
        'Sin API, lo que se recoge depende del usuario y de los límites de la red.'
      ],
      verdict: ['✓', 'Si hay puerta oficial, se entra por ahí.', 'same']
    },
    {
      notes: [
        'La red ordena lo que ves según tu perfil, y ese orden no se ve.',
        'Anotar palabras, idioma y fechas: eso es lo que realmente recogiste.',
        'La misma búsqueda, otro día, trae resultados distintos.'
      ],
      verdict: ['!', 'Sin anotar cómo buscaste, nadie puede repetir tu trabajo.', 'diff']
    },
    {
      notes: [
        'Para estudiar un tema suelen bastar el texto y la fecha.',
        'Nombre, foto o ubicación de una persona solo si son imprescindibles.',
        'Al publicar resultados, mostrar el conjunto, no a personas concretas.'
      ],
      verdict: ['✓', 'Que algo sea público no significa que se pueda usar de cualquier forma.', 'same']
    }
  ]
});

/* Diapositiva 6 · Archivos: ficha y documento. */
PY.pane({
  selector: '.prarc',
  gap: 850,
  steps: [
    {
      notes: [
        'La ficha describe el documento, como la etiqueta de un libro.',
        'Trae los datos para citarlo y encontrarlo: título, autor, fecha, número de catálogo.',
        'Pero leer la ficha no es leer el documento.'
      ],
      verdict: ['✓', 'La ficha sirve para citar y encontrar el documento.', 'same']
    },
    {
      notes: [
        'El documento es el archivo: PDF, foto, audio o video.',
        'Su enlace se guarda junto al número de catálogo de su ficha.',
        'Descargar solo si hace falta y el archivo lo permite.'
      ],
      verdict: ['✓', 'Ficha y documento se guardan juntos, nunca sueltos.', 'same']
    },
    {
      notes: [
        'Los documentos tienen un orden: no se mezclan cajas ni carpetas.',
        'Cuando el texto sale de un escaneo, la máquina se equivoca: «Sevilla» puede salir «Sevi11a».',
        'Si faltan hojas, se anota que faltan.'
      ],
      verdict: ['!', 'Fuera de su orden, un documento pierde su contexto.', 'diff']
    }
  ]
});

/* Diapositiva 7 · Que todo diga de dónde salió. */
PY.pane({
  selector: '.prlink',
  gap: 850,
  steps: [
    {
      notes: [
        'Dentro de la página, los enlaces suelen venir recortados.',
        'Hay que guardarlos completos, con https:// y el nombre del sitio.',
        'Si un enlace deja de funcionar, eso también se anota.'
      ],
      verdict: ['✓', 'Un enlace completo funciona fuera de la página.', 'same']
    },
    {
      notes: [
        'El pie de foto explica la imagen: va con ella.',
        'Se anota la dirección de la que se descargó.',
        'Antes de usarla, se mira quién tiene los derechos.'
      ],
      verdict: ['✓', 'La imagen viaja con su pie y sus derechos.', 'same']
    },
    {
      notes: [
        'De qué sitio salió la fila.',
        'Cuál es el enlace exacto.',
        'Qué día la guardamos.'
      ],
      verdict: ['!', 'Sin estos datos, nadie puede comprobar la tabla.', 'diff']
    }
  ]
});

/* Diapositiva 8 · Si algo falla. */
PY.pane({
  selector: '.prblock',
  gap: 850,
  steps: [
    {
      notes: [
        'El sitio niega el acceso o pide demostrar que no eres un robot.',
        'Eso es un «no»: se para y, si hace falta, se pide permiso.',
        'Se anota qué pasó; no se inventa ninguna fila.'
      ],
      verdict: ['✗', 'Un bloqueo no se esquiva: se anota y se para.', 'diff']
    },
    {
      notes: [
        'La página carga bien, pero el programa no encuentra noticias.',
        'Abrir la página a mano: casi siempre cambió el diseño.',
        'Se ajusta el programa; los datos no se tocan.'
      ],
      verdict: ['!', 'Cero noticias suele ser un cambio del sitio, no falta de noticias.', 'diff']
    },
    {
      notes: [
        'Idéntica: mismo enlace y mismo texto. Se queda una.',
        'La misma noticia en otra sección: decidir antes si cuenta dos veces.',
        'Mismo enlace con título corregido: son dos versiones, se guardan ambas.'
      ],
      verdict: ['✓', 'Antes de borrar repetidos, decidir qué cuenta como repetido.', 'same']
    }
  ]
});
