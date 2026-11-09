'use strict';
/* Diapositivas 5 y 6 · Escenas SVG: recorrido con límite y script reutilizable. */

PY.scene({
  selector: '.pypage',
  gap: 900,
  hot: [{ at: 3, selector: '[data-at="2"] .box' }],
  notes: [
    'La primera URL se visita y se guarda en la lista de vistas.',
    'Se sigue el enlace «Siguiente» y se resuelve con urljoin().',
    'El recorrido continúa mientras el enlace exista.',
    'Condición a: sin enlace «Siguiente» el recorrido termina.',
    'Condición b: si la URL ya estaba visitada, se detiene el bucle.',
    'Condición c: MAX_PAGINAS garantiza que el proceso termina siempre.',
    '3 páginas visitadas y 36 registros: el bucle acaba por una condición explícita, nunca por agotamiento.'
  ]
});

PY.scene({
  selector: '.pyscript',
  gap: 900,
  hot: [{ at: 5, selector: '[data-at="5"] .box' }],
  notes: [
    'La configuración vive fuera del código: fuente, límite, pausa y salida.',
    'descargar(url, timeout) devuelve la respuesta o deja el error en el log.',
    'parsear(html) devuelve registros; no vuelve a tocar la red.',
    'validar(filas) descarta lo que no cumple el esquema y lo anota.',
    'guardar(df) escribe el CSV en un único punto del script.',
    'Dos salidas: los datos válidos y el registro de lo que falló.',
    'El mismo script, con otro archivo de configuración, recorre otra fuente.'
  ]
});
