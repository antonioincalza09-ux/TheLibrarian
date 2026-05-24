from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.config import RuntimeConfig
from src.executor import execute_plan
from src.jsonio import read_plan
from src.planner import build_plan
from src.providers import ProviderContext, get_provider
from src.scanner import scan_directory
from src.security import SafetyError, resolve_root


def create_server(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> ThreadingHTTPServer:
    resolved_root = resolve_root(root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, status: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._html(200, _page())
                    return
                if parsed.path == "/api/inventory":
                    self._json(200, scan_directory(resolved_root).to_dict())
                    return
                if parsed.path == "/api/plan":
                    inventory = scan_directory(resolved_root)
                    provider = get_provider(config.provider)
                    context = ProviderContext(
                        model=config.model,
                        endpoint=config.endpoint,
                        privacy_mode=config.privacy_mode,
                    )
                    self._json(200, build_plan(inventory, provider=provider, context=context).to_dict())
                    return
                self._json(404, {"error": "Not found"})
            except (SafetyError, ValueError, OSError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if parsed.path != "/api/apply":
                    self._json(404, {"error": "Not found"})
                    return
                if query.get("confirm", ["false"])[0].lower() != "true":
                    self._json(403, {"error": "Apply requires confirm=true and a saved plan path."})
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(content_length).decode("utf-8") or "{}")
                plan_path = payload.get("plan")
                if not isinstance(plan_path, str):
                    self._json(400, {"error": "Request body must include plan path."})
                    return
                plan = read_plan(plan_path)
                execution = execute_plan(resolved_root, plan, dry_run=False)
                self._json(200, execution.to_dict())
            except (SafetyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def serve(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> None:
    resolved_root = resolve_root(root)
    server = create_server(resolved_root, host=host, port=port, config=config)
    print(f"TheLibrarian web app: http://{host}:{port}")
    print(f"Root: {resolved_root}")
    server.serve_forever()


def _page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TheLibrarian</title>
  <style>
    :root { color-scheme: light; font-family: Georgia, 'Times New Roman', serif; }
    body { margin: 0; background: #f4f1ea; color: #20201d; }
    header { padding: 24px 32px; border-bottom: 1px solid #d7d0c2; background: #fffaf0; }
    h1 { margin: 0; font-size: 30px; letter-spacing: 0; }
    main { padding: 24px 32px; max-width: 1180px; margin: 0 auto; }
    nav { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
    button { border: 1px solid #4a5d4f; background: #eef3eb; color: #1c2b20; padding: 9px 12px; cursor: pointer; }
    button.active { background: #4a5d4f; color: white; }
    pre { background: #1f2421; color: #f7f4ea; padding: 16px; overflow: auto; min-height: 420px; }
    .status { margin-bottom: 14px; font-family: Verdana, sans-serif; font-size: 14px; }
  </style>
</head>
<body>
  <header><h1>TheLibrarian</h1></header>
  <main>
    <nav>
      <button data-view="inventory" class="active">Inventory</button>
      <button data-view="plan">Plan</button>
      <button data-view="review">Review</button>
      <button data-view="warnings">Warnings</button>
      <button data-view="manifest">Manifest</button>
    </nav>
    <div class="status" id="status">Loading inventory</div>
    <pre id="output"></pre>
  </main>
  <script>
    const output = document.querySelector('#output');
    const status = document.querySelector('#status');
    let inventory = null;
    let plan = null;
    async function load() {
      inventory = await (await fetch('/api/inventory')).json();
      plan = await (await fetch('/api/plan')).json();
      render('inventory');
    }
    function render(view) {
      document.querySelectorAll('button').forEach(button => button.classList.toggle('active', button.dataset.view === view));
      if (view === 'inventory') output.textContent = JSON.stringify(inventory, null, 2);
      if (view === 'plan') output.textContent = JSON.stringify(plan, null, 2);
      if (view === 'review') output.textContent = JSON.stringify(plan.entries.filter(entry => entry.category === 'Review'), null, 2);
      if (view === 'warnings') output.textContent = JSON.stringify({ scan: inventory.warnings, plan: plan.warnings }, null, 2);
      if (view === 'manifest') output.textContent = 'Apply uses saved plan JSON only. Use CLI apply or POST /api/apply?confirm=true with {"plan":"path"}.'; 
      status.textContent = `${inventory.summary.total_files} files scanned, ${plan.entries.length} plan entries`;
    }
    document.querySelectorAll('button').forEach(button => button.addEventListener('click', () => render(button.dataset.view)));
    load().catch(error => { status.textContent = error.message; output.textContent = String(error.stack || error); });
  </script>
</body>
</html>"""
