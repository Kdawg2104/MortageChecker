"""Which runtime the app is running in.

The same code runs two ways:
- on a normal Python server (`streamlit run app.py`, locally or on Streamlit Community Cloud), and
- inside the visitor's web browser via stlite, which runs Python on Pyodide (WebAssembly).

Pyodide reports its platform as "emscripten", so this one check tells them apart.
"""

import sys

IS_BROWSER = sys.platform == "emscripten"
