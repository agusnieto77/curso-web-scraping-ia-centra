'use strict';
/* Diapositiva 7 · Errores visibles: el log crece y los resultados válidos se conservan. */
PY.scene({
  selector: '.pyerror',
  gap: 900,
  itemSteps: [1, 2, 3],
  notes: [
    'Cada fallo se escribe con su URL, su etapa y su motivo.',
    'Un timeout no genera una fila: genera una entrada en el log.',
    'Un 429 exige parar o esperar el Retry-After que indica la respuesta.',
    'Una página con otra estructura se registra; no se inventa un registro vacío.',
    'Los resultados válidos se guardan aparte y no se pierden.',
    'El archivo final conserva lo capturado y deja constancia de lo que faltó.'
  ]
});
