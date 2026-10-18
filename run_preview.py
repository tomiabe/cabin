"""Serve the included production build without installing Node dependencies."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser


ROOT = Path(__file__).resolve().parent / "dist"
if not (ROOT / "index.html").is_file():
    raise SystemExit("The dist/ build is missing. Run npm install, then npm run build.")

handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Lime Cabin is ready at {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
