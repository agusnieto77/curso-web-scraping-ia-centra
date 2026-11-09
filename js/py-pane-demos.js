'use strict';
/* Diapositivas 3, 4 y 8 · Paneles por pasos: estado de la respuesta, registros y validación. */

PY.pane({
  selector: '.pycheck',
  gap: 850,
  steps: [
    {
      notes: [
        'La petición sale con timeout explícito.',
        'raise_for_status() no encuentra error: la respuesta es 200.',
        'El cuerpo llega completo: 18 402 bytes.'
      ],
      verdict: ['✓', 'La red responde: el estado no es el problema.', 'same']
    },
    {
      notes: [
        'El estado sigue siendo correcto: 200 OK.',
        'El tipo de respuesta es el esperado: text/html.',
        'Pero no hay ni un article: la respuesta no contiene datos.'
      ],
      verdict: ['!', '200 con 0 artículos: la respuesta no contiene lo que se esperaba.', 'diff']
    },
    {
      notes: [
        'El cuerpo pide un CAPTCHA: el acceso está restringido.',
        'Un 403 o un CAPTCHA no se esquivan: el proceso se detiene.',
        'El intento queda en el log; no se inventa ningún registro.'
      ],
      verdict: ['✗', 'Acceso restringido: detener, pedir autorización y registrar el motivo.', 'diff']
    }
  ]
});

PY.pane({
  selector: '.pyrecord',
  gap: 850,
  steps: [
    {
      notes: [
        'El conjunto de contenedores es el punto de partida.',
        'El primer article.',
        'El segundo article.',
        'El tercero: 12 contenedores en total.'
      ],
      verdict: ['✓', 'Los contenedores son las unidades: un article, un registro.', 'same']
    },
    {
      notes: [
        'Cada campo se busca dentro de su propio article.',
        'El título del artículo B.',
        'El enlace del artículo B.',
        'B no tiene fecha: select_one() devuelve None.'
      ],
      verdict: ['!', 'Un campo ausente es None: no es un error ni un valor inventado.', 'diff']
    },
    {
      notes: [
        'zip() une por posición: si una lista es más corta, el dato se desplaza.',
        'Primera fila: A con su fecha.',
        'Segunda fila: B recibe la fecha de C. Error silencioso.',
        'Tercera fila: C se queda sin fecha.',
        'La alternativa: un diccionario por article.',
        'B conserva None y el resto no se mueve.'
      ],
      verdict: ['✓', 'Un registro por article: lo que falta queda como None, nunca como el dato de otro.', 'same']
    }
  ]
});

PY.pane({
  selector: '.pyvalid',
  gap: 850,
  steps: [
    {
      notes: [
        'Primero el esquema: las columnas esperadas.',
        'Ninguna URL duplicada: la clave es la URL.',
        'Una fecha no se pudo interpretar y queda marcada.'
      ],
      verdict: ['!', 'Consistencia con una excepción: revisar la fecha señalada.', 'diff']
    },
    {
      notes: [
        'La cobertura se compara con lo previsto.',
        '5 páginas previstas, 4 visitadas.',
        '1 página falló y está en el log de errores.'
      ],
      verdict: ['!', 'Cobertura incompleta: 4 de 5 páginas. El CSV no está completo.', 'diff']
    },
    {
      notes: [
        'El archivo final, con su trazabilidad.',
        'Columna «capturado» con la fuente y la fecha de ejecución.'
      ],
      verdict: ['✓', 'El CSV es un resultado; la validación es la prueba de calidad.', 'same']
    }
  ]
});
