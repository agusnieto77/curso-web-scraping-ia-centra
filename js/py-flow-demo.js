'use strict';
/* Diapositiva 2 · Tres bibliotecas, un flujo: consola de Python por fases. */
PY.console({
  selector: '.pyflow',
  phases: [
    {
      lines: [
        ['cmd', 'import requests'],
        ['cmd', 'r = requests.get(url, timeout=10)'],
        ['cmd', 'r.status_code'],
        ['out', '200']
      ],
      note: 'Transporte: timeout siempre, y el estado se comprueba antes de leer el cuerpo.'
    },
    {
      lines: [
        ['cmd', 'from bs4 import BeautifulSoup'],
        ['cmd', 'soup = BeautifulSoup(r.text, "html.parser")'],
        ['cmd', 'arts = soup.select("article")'],
        ['out', '12']
      ],
      note: 'Interpretación: BeautifulSoup no descarga nada; lee el HTML que ya tienes.'
    },
    {
      lines: [
        ['cmd', 'import pandas as pd'],
        ['cmd', 'df = pd.DataFrame(rows)'],
        ['cmd', 'df.shape'],
        ['out', '(12, 3)'],
        ['cmd', 'df.to_csv("noticias.csv", index=False)']
      ],
      note: 'Estructura: las mismas claves en cada fila y un único punto de exportación.'
    }
  ]
});
