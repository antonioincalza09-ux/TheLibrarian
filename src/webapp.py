from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.config import RuntimeConfig
from src.executor import execute_plan
from src.jobs import JobRunner, JobStore
from src.jsonio import read_plan
from src.planner import build_plan
from src.providers import ProviderContext, get_provider
from src.reporter import write_plan_artifact
from src.scanner import scan_directory
from src.security import SafetyError, resolve_root


class ConfirmationRequired(SafetyError):
    pass


def create_server(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> ThreadingHTTPServer:
    root_lock = threading.RLock()
    root_state = {"path": resolve_root(root)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, status: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self) -> dict[str, object]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length == 0:
                return {}
            payload = json.loads(self.rfile.read(content_length).decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _confirm(self, query: dict[str, list[str]], action: str) -> None:
            if query.get("confirm", ["false"])[0].lower() != "true":
                raise ConfirmationRequired(f"{action} requires confirm=true.")

        def _root(self) -> Path:
            with root_lock:
                return root_state["path"]

        def _set_root(self, root_value: object) -> Path:
            if not isinstance(root_value, str) or not root_value.strip():
                raise SafetyError("Request body must include root path.")
            next_root = resolve_root(root_value)
            with root_lock:
                root_state["path"] = next_root
            return next_root

        def _inventory(self) -> dict[str, object]:
            return scan_directory(self._root()).to_dict()

        def _plan(self) -> dict[str, object]:
            return _build_current_plan(self._root(), config).to_dict()

        def _dashboard(self) -> dict[str, object]:
            resolved_root = self._root()
            inventory = self._inventory()
            plan = self._plan()
            store = JobStore(resolved_root)
            jobs = [job.to_dict() for job in store.list()]
            active_job = jobs[0] if jobs else None
            active_policy = None
            active_events: list[dict[str, object]] = []
            active_manifest = None
            if active_job is not None:
                job_id = str(active_job["job_id"])
                active_events = [event.to_dict() for event in store.read_events(job_id)]
                try:
                    active_policy = store.read_json_artifact(job_id, "policy_decision.json")
                except SafetyError:
                    active_policy = None
                manifest_path = active_job.get("manifest_path")
                if isinstance(manifest_path, str) and manifest_path:
                    try:
                        active_manifest = self._read_root_artifact(manifest_path)
                    except SafetyError:
                        active_manifest = None
            return {
                "root": str(resolved_root),
                "config": {
                    "provider": config.provider,
                    "model": config.model,
                    "endpoint": config.endpoint,
                    "privacy_mode": config.privacy_mode,
                },
                "inventory": inventory,
                "plan": plan,
                "jobs": jobs,
                "active_job": active_job,
                "active_policy": active_policy,
                "active_events": active_events,
                "active_manifest": active_manifest,
            }

        def _read_root_artifact(self, artifact_path: str) -> dict[str, object]:
            resolved_root = self._root()
            path = Path(artifact_path).resolve(strict=False)
            try:
                path.relative_to(resolved_root)
            except ValueError as exc:
                raise SafetyError("Artifact path escapes the assigned root.") from exc
            if not path.exists():
                raise SafetyError(f"Missing artifact: {artifact_path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise SafetyError("Artifact is not a JSON object.")
            return payload

        def _job_id_from_path(self, prefix: str, path: str) -> tuple[str, str]:
            remainder = path.removeprefix(prefix).strip("/")
            parts = remainder.split("/")
            if not parts or not parts[0]:
                raise SafetyError("Missing job id.")
            return parts[0], parts[1] if len(parts) > 1 else ""

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._html(200, _page())
                    return
                if parsed.path == "/api/root":
                    self._json(200, {"root": str(self._root())})
                    return
                if parsed.path == "/api/dashboard":
                    self._json(200, self._dashboard())
                    return
                if parsed.path == "/api/inventory":
                    self._json(200, self._inventory())
                    return
                if parsed.path == "/api/plan":
                    self._json(200, self._plan())
                    return
                if parsed.path == "/api/jobs":
                    self._json(200, {"jobs": [job.to_dict() for job in JobStore(self._root()).list()]})
                    return
                if parsed.path.startswith("/api/jobs/"):
                    job_id, suffix = self._job_id_from_path("/api/jobs/", parsed.path)
                    store = JobStore(self._root())
                    if suffix == "":
                        self._json(200, store.load(job_id).to_dict())
                        return
                    if suffix == "events":
                        self._json(200, {"events": [event.to_dict() for event in store.read_events(job_id)]})
                        return
                    if suffix == "policy":
                        self._json(200, store.read_json_artifact(job_id, "policy_decision.json"))
                        return
                    if suffix == "manifest":
                        job = store.load(job_id)
                        if not job.manifest_path:
                            self._json(404, {"error": "Job has no manifest."})
                            return
                        self._json(200, self._read_root_artifact(job.manifest_path))
                        return
                self._json(404, {"error": "Not found"})
            except ConfirmationRequired as exc:
                self._json(403, {"error": str(exc)})
            except (SafetyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                body = self._body()

                if parsed.path == "/api/root":
                    self._confirm(query, "Root change")
                    next_root = self._set_root(body.get("root"))
                    self._json(200, {"root": str(next_root)})
                    return

                if parsed.path == "/api/plan/save":
                    plan = _build_current_plan(self._root(), config)
                    plan_path = write_plan_artifact(self._root(), plan)
                    self._json(200, {"path": str(plan_path), "plan": plan.to_dict()})
                    return

                if parsed.path == "/api/apply":
                    self._confirm(query, "Apply")
                    plan_path = body.get("plan")
                    if not isinstance(plan_path, str):
                        self._json(400, {"error": "Request body must include plan path."})
                        return
                    plan = read_plan(plan_path)
                    execution = execute_plan(self._root(), plan, dry_run=False)
                    self._json(200, execution.to_dict())
                    return

                if parsed.path == "/api/jobs/create":
                    policy = str(body.get("policy", "dry_run_only"))
                    job = JobRunner(self._root(), config=config).create_job(dry_run=True, policy_name=policy)
                    self._json(200, job.to_dict())
                    return

                if parsed.path == "/api/jobs/run":
                    policy = str(body.get("policy", "dry_run_only"))
                    job = JobRunner(self._root(), config=config).run(dry_run=True, policy_name=policy)
                    self._json(200, job.to_dict())
                    return

                if parsed.path == "/api/jobs/delete-all":
                    self._confirm(query, "Delete all jobs")
                    deleted = JobStore(self._root()).delete_all()
                    self._json(200, {"deleted": deleted})
                    return

                if parsed.path.startswith("/api/jobs/"):
                    job_id, suffix = self._job_id_from_path("/api/jobs/", parsed.path)
                    root_path = self._root()
                    runner = JobRunner(root_path, config=config)
                    if suffix == "approve":
                        self._confirm(query, "Job approval")
                        self._json(200, runner.approve(job_id).to_dict())
                        return
                    if suffix == "apply":
                        self._confirm(query, "Job apply")
                        self._json(200, runner.apply(job_id).to_dict())
                        return
                    if suffix == "rollback":
                        self._confirm(query, "Job rollback")
                        self._json(200, runner.rollback(job_id).to_dict())
                        return
                    if suffix == "delete":
                        self._confirm(query, "Job delete")
                        JobStore(root_path).delete(job_id)
                        self._json(200, {"deleted": 1, "job_id": job_id})
                        return

                self._json(404, {"error": "Not found"})
            except ConfirmationRequired as exc:
                self._json(403, {"error": str(exc)})
            except (SafetyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def _build_current_plan(root: Path, config: RuntimeConfig):
    inventory = scan_directory(root)
    provider = get_provider(config.provider)
    context = ProviderContext(
        model=config.model,
        endpoint=config.endpoint,
        privacy_mode=config.privacy_mode,
    )
    return build_plan(inventory, provider=provider, context=context)


def serve(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> None:
    resolved_root = resolve_root(root)
    server = create_server(resolved_root, host=host, port=port, config=config)
    print(f"TheLibrarian web app: http://{host}:{port}")
    print(f"Root: {resolved_root}")
    server.serve_forever()


def _page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TheLibrarian Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17201c;
      --muted: #63736d;
      --line: #d7ded4;
      --panel: #fbfcf6;
      --panel-strong: #ffffff;
      --field: #f2f6ef;
      --accent: #2f684e;
      --accent-2: #1d5565;
      --warn: #9c6a14;
      --danger: #9b3430;
      --ok: #26704c;
      --shadow: 0 14px 32px rgba(35, 48, 41, 0.12);
      font-family: "Aptos", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        linear-gradient(135deg, rgba(47, 104, 78, 0.12), transparent 34%),
        linear-gradient(315deg, rgba(29, 85, 101, 0.14), transparent 40%),
        #eef3eb;
      color: var(--ink);
    }
    button, select, input {
      font: inherit;
    }
    button {
      min-height: 38px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      color: var(--ink);
      padding: 9px 12px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
    }
    button:hover { border-color: var(--accent); }
    button:disabled { opacity: 0.48; cursor: not-allowed; }
    .button-primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
    }
    .button-blue {
      background: var(--accent-2);
      border-color: var(--accent-2);
      color: #ffffff;
    }
    .button-danger {
      background: #fff4f1;
      border-color: #e0b1a8;
      color: var(--danger);
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
    }
    aside {
      padding: 22px;
      border-right: 1px solid var(--line);
      background: rgba(251, 252, 246, 0.88);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 22px;
    }
    .mark {
      width: 42px;
      height: 42px;
      background: #17201c;
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 800;
      letter-spacing: 0;
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 { font-size: 24px; line-height: 1.1; margin-bottom: 2px; letter-spacing: 0; }
    h2 { font-size: 20px; line-height: 1.25; margin-bottom: 12px; letter-spacing: 0; }
    h3 { font-size: 15px; line-height: 1.25; margin-bottom: 8px; letter-spacing: 0; }
    .subtle { color: var(--muted); font-size: 13px; line-height: 1.45; overflow-wrap: anywhere; }
    .nav {
      display: grid;
      gap: 8px;
      margin: 20px 0;
    }
    .nav button {
      justify-content: flex-start;
      width: 100%;
      background: transparent;
      border-color: transparent;
      padding: 10px;
    }
    .nav button.active {
      background: #e1ece3;
      border-color: #c8d8ca;
      color: #143823;
    }
    .side-panel {
      border: 1px solid var(--line);
      background: #f7faf4;
      padding: 12px;
      margin-top: 14px;
    }
    .side-panel select, .side-panel input {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      padding: 8px;
    }
    main {
      min-width: 0;
      padding: 24px;
    }
    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 18px;
    }
    .title-block {
      min-width: 0;
    }
    .title-block h2 {
      font-size: 30px;
      margin-bottom: 6px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .metric, .panel {
      background: rgba(251, 252, 246, 0.92);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }
    .metric {
      padding: 14px;
      min-height: 92px;
      display: grid;
      align-content: space-between;
    }
    .metric .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .metric .value { font-size: 28px; font-weight: 780; line-height: 1; margin-top: 10px; }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
      gap: 14px;
      align-items: start;
    }
    .panel {
      padding: 16px;
      min-width: 0;
    }
    .panel-header {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .panel-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      background: white;
      max-height: 520px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }
    th, td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #ecf0e8;
      vertical-align: top;
      font-size: 13px;
    }
    th {
      position: sticky;
      top: 0;
      background: #f6f8f1;
      z-index: 1;
      color: #3c4b45;
      font-weight: 700;
    }
    td {
      overflow-wrap: anywhere;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      background: #f7faf4;
      font-size: 12px;
      font-weight: 700;
      color: #33413b;
    }
    .badge.ok { color: var(--ok); border-color: #bad9c9; background: #f0faf3; }
    .badge.warn { color: var(--warn); border-color: #ead5a9; background: #fff9ea; }
    .badge.danger { color: var(--danger); border-color: #e6b9b3; background: #fff4f1; }
    .job-list {
      display: grid;
      gap: 10px;
      max-height: 480px;
      overflow: auto;
      padding-right: 2px;
    }
    .job-card {
      border: 1px solid var(--line);
      background: #ffffff;
      padding: 12px;
      display: grid;
      gap: 8px;
      cursor: pointer;
    }
    .job-card.active {
      border-color: var(--accent);
      box-shadow: inset 4px 0 0 var(--accent);
    }
    .job-card code {
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .details {
      display: grid;
      gap: 10px;
    }
    .kv {
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 10px;
      font-size: 13px;
      align-items: start;
    }
    .kv strong { color: #3c4b45; }
    .kv span { overflow-wrap: anywhere; }
    .status-line {
      min-height: 36px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.82);
      margin-bottom: 14px;
      font-size: 13px;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 99px;
      background: var(--ok);
      flex: 0 0 auto;
    }
    .empty {
      border: 1px dashed #c9d4ca;
      background: #f8fbf6;
      padding: 18px;
      color: var(--muted);
      font-size: 14px;
    }
    pre {
      margin: 0;
      padding: 12px;
      background: #17201c;
      color: #ecf5eb;
      overflow: auto;
      max-height: 420px;
      font-size: 12px;
      line-height: 1.45;
    }
    .view { display: none; }
    .view.active { display: block; }
    @media (max-width: 980px) {
      .shell { grid-template-columns: 1fr; }
      aside { position: static; height: auto; }
      main { padding: 18px; }
      .topbar, .layout { grid-template-columns: 1fr; }
      .toolbar { justify-content: flex-start; }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 560px) {
      aside { padding: 16px; }
      main { padding: 14px; }
      .grid { grid-template-columns: 1fr; }
      .panel { padding: 12px; }
      .title-block h2 { font-size: 24px; }
      button { width: 100%; }
      .panel-header { display: grid; }
      .panel-actions { justify-content: stretch; }
      .kv { grid-template-columns: 1fr; gap: 2px; }
    }
  </style>
</head>
<body>
  <div class="shell" data-app="thelibrarian-dashboard">
    <aside>
      <div class="brand">
        <div class="mark">TL</div>
        <div>
          <h1>TheLibrarian</h1>
          <div class="subtle">Safe directory operations console</div>
        </div>
      </div>
      <div class="subtle" id="rootPath">Loading root</div>
      <nav class="nav" aria-label="Dashboard views">
        <button type="button" class="active" data-view="overview">Overview</button>
        <button type="button" data-view="inventory">Inventory</button>
        <button type="button" data-view="plan">Plan</button>
        <button type="button" data-view="review">Review</button>
        <button type="button" data-view="warnings">Warnings</button>
        <button type="button" data-view="jobs">Jobs</button>
        <button type="button" data-view="policy">Policy</button>
        <button type="button" data-view="events">Events</button>
        <button type="button" data-view="manifest">Manifest</button>
      </nav>
      <div class="side-panel">
        <h3>Target Root</h3>
        <input id="rootInput" type="text" aria-label="Directory to reorganize" placeholder="C:\path\to\directory">
        <button type="button" id="setRootBtn" style="width:100%;margin-top:8px">Set Directory</button>
        <p class="subtle" style="margin:10px 0 0">Changing root switches the dashboard target. Operations remain confined to the selected directory.</p>
      </div>
      <div class="side-panel">
        <h3>Run Policy</h3>
        <select id="policySelect" aria-label="Policy mode">
          <option value="dry_run_only">dry_run_only</option>
          <option value="supervised_autonomy">supervised_autonomy</option>
        </select>
        <p class="subtle" style="margin:10px 0 0">Dry-run remains the default. Apply and rollback always require confirmation.</p>
      </div>
    </aside>
    <main>
      <div class="topbar">
        <div class="title-block">
          <h2>Operations Dashboard</h2>
          <p class="subtle">Scan, plan, review policy decisions, and run controlled job actions from one auditable surface.</p>
        </div>
        <div class="toolbar">
          <button type="button" id="refreshBtn">Refresh</button>
          <button type="button" id="savePlanBtn">Save Plan</button>
          <button type="button" id="createJobBtn">Create Job</button>
          <button type="button" class="button-primary" id="runJobBtn">Run Dry-Run Job</button>
        </div>
      </div>
      <div class="status-line"><span class="dot" id="statusDot"></span><span id="statusText">Loading dashboard</span></div>
      <section class="grid" aria-label="Summary metrics">
        <div class="metric"><span class="label">Files</span><span class="value" id="metricFiles">0</span></div>
        <div class="metric"><span class="label">Planned</span><span class="value" id="metricPlanned">0</span></div>
        <div class="metric"><span class="label">Review</span><span class="value" id="metricReview">0</span></div>
        <div class="metric"><span class="label">Jobs</span><span class="value" id="metricJobs">0</span></div>
      </section>
      <section class="view active" data-view-panel="overview">
        <div class="layout">
          <div class="panel">
            <div class="panel-header">
              <div><h2>Current Plan</h2><p class="subtle">Live deterministic/provider-backed plan preview for this root.</p></div>
              <div class="panel-actions"><button type="button" data-view-jump="plan">Open Plan</button></div>
            </div>
            <div class="table-wrap"><table id="overviewPlanTable"></table></div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div><h2>Active Job</h2><p class="subtle">Latest checkpointed job and safe actions.</p></div>
            </div>
            <div class="details" id="activeJobDetails"></div>
            <div class="panel-actions" style="margin-top:14px">
              <button type="button" id="approveJobBtn">Approve</button>
              <button type="button" class="button-blue" id="applyJobBtn">Apply</button>
              <button type="button" class="button-danger" id="rollbackJobBtn">Rollback</button>
              <button type="button" class="button-danger" id="deleteJobBtn">Delete Job</button>
            </div>
          </div>
        </div>
      </section>
      <section class="view" data-view-panel="inventory">
        <div class="panel">
          <div class="panel-header"><div><h2>Inventory</h2><p class="subtle">Metadata only. File contents are never read for online providers.</p></div></div>
          <div class="table-wrap"><table id="inventoryTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="plan">
        <div class="panel">
          <div class="panel-header"><div><h2>Plan</h2><p class="subtle">Every row includes destination, confidence, reason, and status.</p></div></div>
          <div class="table-wrap"><table id="planTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="jobs">
        <div class="layout">
          <div class="panel">
            <div class="panel-header">
              <div><h2>Job Queue</h2><p class="subtle">Filesystem-backed jobs under .thelibrarian/jobs.</p></div>
              <div class="panel-actions"><button type="button" class="button-danger" id="deleteAllJobsBtn">Delete All Jobs</button></div>
            </div>
            <div class="job-list" id="jobList"></div>
          </div>
          <div class="panel">
            <div class="panel-header"><div><h2>Job Record</h2><p class="subtle">Selected job JSON.</p></div></div>
            <pre id="jobJson">{}</pre>
          </div>
        </div>
      </section>
      <section class="view" data-view-panel="review">
        <div class="panel">
          <div class="panel-header"><div><h2>Review Queue</h2><p class="subtle">Ambiguous, low-confidence, or non-planned entries that should stay human-supervised.</p></div></div>
          <div class="table-wrap"><table id="reviewTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="warnings">
        <div class="panel">
          <div class="panel-header"><div><h2>Warnings</h2><p class="subtle">Scanner, planner, and entry-level safety notes.</p></div></div>
          <div class="table-wrap"><table id="warningsTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="policy">
        <div class="panel">
          <div class="panel-header"><div><h2>Policy Decisions</h2><p class="subtle">Risk-scored decisions for the selected job.</p></div></div>
          <div class="table-wrap"><table id="policyTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="events">
        <div class="panel">
          <div class="panel-header"><div><h2>Events</h2><p class="subtle">Append-only event stream for the selected job.</p></div></div>
          <div class="table-wrap"><table id="eventsTable"></table></div>
        </div>
      </section>
      <section class="view" data-view-panel="manifest">
        <div class="panel">
          <div class="panel-header"><div><h2>Manifest</h2><p class="subtle">Rollback manifest for the selected job, available only after apply.</p></div></div>
          <pre id="manifestJson">{}</pre>
        </div>
      </section>
    </main>
  </div>
  <script>
    const state = { dashboard: null, selectedJobId: null, policy: null, events: [], manifest: null, busy: false };
    const $ = selector => document.querySelector(selector);
    const $$ = selector => Array.from(document.querySelectorAll(selector));

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    }
    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
      return payload;
    }
    function setStatus(message, variant = 'ok') {
      $('#statusText').textContent = message;
      $('#statusDot').style.background = variant === 'danger' ? 'var(--danger)' : variant === 'warn' ? 'var(--warn)' : 'var(--ok)';
    }
    function badge(value) {
      const text = String(value ?? '');
      const lowered = text.toLowerCase();
      const kind = /completed|auto_approved|planned/.test(lowered) ? 'ok' : /failed|blocked|rollback/.test(lowered) ? 'danger' : /approval|review|paused|warning/.test(lowered) ? 'warn' : '';
      return `<span class="badge ${kind}">${escapeHtml(text)}</span>`;
    }
    function table(headers, rows) {
      if (!rows.length) return '<tbody><tr><td class="empty">No data available</td></tr></tbody>';
      const head = `<thead><tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead>`;
      const body = `<tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>`;
      return head + body;
    }
    function activeJob() {
      const jobs = state.dashboard?.jobs || [];
      return jobs.find(job => job.job_id === state.selectedJobId) || jobs[0] || null;
    }
    function setView(view) {
      $$('.nav button').forEach(button => button.classList.toggle('active', button.dataset.view === view));
      $$('[data-view-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.viewPanel === view));
    }
    async function refresh({ keepSelection = true, silent = false } = {}) {
      const previous = keepSelection ? state.selectedJobId : null;
      state.dashboard = await api('/api/dashboard');
      const jobs = state.dashboard.jobs || [];
      state.selectedJobId = jobs.some(job => job.job_id === previous) ? previous : (jobs[0]?.job_id || null);
      await loadJobSideData();
      render();
      if (!silent) setStatus('Dashboard refreshed');
    }
    async function loadJobSideData() {
      state.policy = null;
      state.events = [];
      state.manifest = null;
      if (!state.selectedJobId) return;
      const policyResult = await fetch(`/api/jobs/${state.selectedJobId}/policy`);
      if (policyResult.ok) state.policy = await policyResult.json();
      const eventResult = await fetch(`/api/jobs/${state.selectedJobId}/events`);
      if (eventResult.ok) state.events = (await eventResult.json()).events || [];
      const manifestResult = await fetch(`/api/jobs/${state.selectedJobId}/manifest`);
      if (manifestResult.ok) state.manifest = await manifestResult.json();
    }
    function render() {
      const dashboard = state.dashboard;
      if (!dashboard) return;
      const inventory = dashboard.inventory;
      const plan = dashboard.plan;
      const jobs = dashboard.jobs || [];
      const selected = activeJob();
      $('#rootPath').textContent = dashboard.root;
      if (document.activeElement !== $('#rootInput')) $('#rootInput').value = dashboard.root;
      $('#metricFiles').textContent = inventory.summary.total_files;
      $('#metricPlanned').textContent = plan.entries.filter(entry => entry.status === 'planned').length;
      $('#metricReview').textContent = plan.entries.filter(entry => entry.category === 'Review').length;
      $('#metricJobs').textContent = jobs.length;
      renderPlanTables(plan);
      renderInventory(inventory);
      renderJobs(jobs, selected);
      renderReview(plan);
      renderWarnings(inventory, plan);
      renderPolicy();
      renderEvents();
      renderManifest();
      renderActiveJob(selected);
    }
    function renderPlanTables(plan) {
      const rows = plan.entries.slice(0, 8).map(entry => [
        escapeHtml(entry.source),
        escapeHtml(entry.destination),
        badge(entry.category),
        badge(entry.status),
        escapeHtml(Number(entry.confidence).toFixed(2)),
      ]);
      $('#overviewPlanTable').innerHTML = table(['Source', 'Destination', 'Category', 'Status', 'Confidence'], rows);
      const fullRows = plan.entries.map(entry => [
        escapeHtml(entry.source),
        escapeHtml(entry.destination),
        badge(entry.category),
        badge(entry.status),
        escapeHtml(Number(entry.confidence).toFixed(2)),
        escapeHtml(entry.reason),
      ]);
      $('#planTable').innerHTML = table(['Source', 'Destination', 'Category', 'Status', 'Confidence', 'Reason'], fullRows);
    }
    function renderInventory(inventory) {
      const rows = inventory.files.map(file => [
        escapeHtml(file.relative_path),
        escapeHtml(file.extension || '(none)'),
        escapeHtml(file.size_bytes),
        escapeHtml(file.parent),
        escapeHtml(file.modified_at),
      ]);
      $('#inventoryTable').innerHTML = table(['Path', 'Ext', 'Bytes', 'Parent', 'Modified'], rows);
    }
    function renderJobs(jobs, selected) {
      $('#jobList').innerHTML = jobs.length ? jobs.map(job => `
        <button type="button" class="job-card ${selected?.job_id === job.job_id ? 'active' : ''}" data-job="${escapeHtml(job.job_id)}">
          <div>${badge(job.status)} ${badge(job.phase)}</div>
          <code>${escapeHtml(job.job_id)}</code>
          <div class="subtle">${escapeHtml(job.updated_at)}</div>
        </button>
      `).join('') : '<div class="empty">No jobs yet. Run a dry-run job to create the first checkpoint.</div>';
      $$('[data-job]').forEach(button => button.addEventListener('click', async () => {
        state.selectedJobId = button.dataset.job;
        await loadJobSideData();
        render();
      }));
      $('#jobJson').textContent = selected ? JSON.stringify(selected, null, 2) : '{}';
    }
    function renderReview(plan) {
      const reviewRows = plan.entries
        .filter(entry => entry.category === 'Review' || entry.status !== 'planned' || Number(entry.confidence) < 0.92)
        .map(entry => [
          escapeHtml(entry.source),
          escapeHtml(entry.destination),
          badge(entry.category),
          badge(entry.status),
          escapeHtml(Number(entry.confidence).toFixed(2)),
          escapeHtml(entry.warning || entry.reason),
        ]);
      $('#reviewTable').innerHTML = table(['Source', 'Destination', 'Category', 'Status', 'Confidence', 'Why review'], reviewRows);
    }
    function renderWarnings(inventory, plan) {
      const rows = [
        ...(inventory.warnings || []).map(warning => ['scanner', warning]),
        ...(plan.warnings || []).map(warning => ['planner', warning]),
        ...plan.entries.filter(entry => entry.warning).map(entry => [entry.source, entry.warning]),
      ].map(([source, warning]) => [escapeHtml(source), escapeHtml(warning)]);
      $('#warningsTable').innerHTML = table(['Source', 'Warning'], rows);
    }
    function renderActiveJob(job) {
      if (!job) {
        $('#activeJobDetails').innerHTML = '<div class="empty">No active job selected.</div>';
        $('#approveJobBtn').disabled = true;
        $('#applyJobBtn').disabled = true;
        $('#rollbackJobBtn').disabled = true;
        $('#deleteJobBtn').disabled = true;
        return;
      }
      $('#activeJobDetails').innerHTML = [
        ['Job', job.job_id],
        ['Status', job.status],
        ['Phase', job.phase],
        ['Policy', job.policy_name || '(none)'],
        ['Plan', job.plan_path || '(none)'],
        ['Policy File', job.policy_path || '(none)'],
        ['Manifest', job.manifest_path || '(none)'],
      ].map(([key, value]) => `<div class="kv"><strong>${escapeHtml(key)}</strong><span>${escapeHtml(value)}</span></div>`).join('');
      $('#approveJobBtn').disabled = !job.policy_path;
      $('#applyJobBtn').disabled = !job.policy_path;
      $('#rollbackJobBtn').disabled = !job.manifest_path;
      $('#deleteJobBtn').disabled = false;
    }
    function renderPolicy() {
      const decisions = state.policy?.decisions || [];
      const rows = decisions.map(decision => [
        escapeHtml(decision.source),
        escapeHtml(decision.destination),
        badge(decision.category),
        badge(decision.status),
        escapeHtml(Number(decision.risk_score).toFixed(2)),
        escapeHtml(decision.approved_by_user ? 'yes' : 'no'),
        escapeHtml(decision.reason),
      ]);
      $('#policyTable').innerHTML = table(['Source', 'Destination', 'Category', 'Decision', 'Risk', 'Manual', 'Reason'], rows);
    }
    function renderEvents() {
      const rows = state.events.map(event => [
        escapeHtml(event.timestamp),
        badge(event.status),
        badge(event.phase),
        escapeHtml(event.message),
      ]);
      $('#eventsTable').innerHTML = table(['Time', 'Status', 'Phase', 'Message'], rows);
    }
    function renderManifest() {
      $('#manifestJson').textContent = state.manifest ? JSON.stringify(state.manifest, null, 2) : '{}';
    }
    async function runAction(label, action, { refreshAfter = true } = {}) {
      if (state.busy) return;
      state.busy = true;
      try {
        setStatus(`${label} running`, 'warn');
        await action();
        if (refreshAfter) await refresh({ silent: true });
        setStatus(`${label} completed`);
      } catch (error) {
        setStatus(error.message, 'danger');
      } finally {
        state.busy = false;
      }
    }
    function confirmAction(text) {
      return window.confirm(text);
    }
    $('#refreshBtn').addEventListener('click', () => runAction('Refresh', () => refresh({ silent: true }), { refreshAfter: false }));
    $('#savePlanBtn').addEventListener('click', () => runAction('Save plan', async () => {
      const saved = await api('/api/plan/save', { method: 'POST', body: '{}' });
      setStatus(`Saved plan: ${saved.path}`);
    }, { refreshAfter: false }));
    $('#setRootBtn').addEventListener('click', () => {
      const root = $('#rootInput').value.trim();
      if (!root || !confirmAction('Switch dashboard to this directory? Existing files will not be moved.')) return;
      runAction('Set directory', async () => {
        await api('/api/root?confirm=true', { method: 'POST', body: JSON.stringify({ root }) });
        state.selectedJobId = null;
      });
    });
    $('#createJobBtn').addEventListener('click', () => runAction('Create job', async () => {
      const policy = $('#policySelect').value;
      const job = await api('/api/jobs/create', { method: 'POST', body: JSON.stringify({ policy }) });
      state.selectedJobId = job.job_id;
    }));
    $('#runJobBtn').addEventListener('click', () => runAction('Dry-run job', async () => {
      const policy = $('#policySelect').value;
      const job = await api('/api/jobs/run', { method: 'POST', body: JSON.stringify({ policy }) });
      state.selectedJobId = job.job_id;
    }));
    $('#approveJobBtn').addEventListener('click', () => {
      const job = activeJob();
      if (!job || !confirmAction('Approve all review-required policy decisions for this job?')) return;
      runAction('Approve job', () => api(`/api/jobs/${job.job_id}/approve?confirm=true`, { method: 'POST', body: '{}' }));
    });
    $('#applyJobBtn').addEventListener('click', () => {
      const job = activeJob();
      if (!job || !confirmAction('Apply policy-approved moves for this job? A rollback manifest will be required.')) return;
      runAction('Apply job', () => api(`/api/jobs/${job.job_id}/apply?confirm=true`, { method: 'POST', body: '{}' }));
    });
    $('#rollbackJobBtn').addEventListener('click', () => {
      const job = activeJob();
      if (!job || !confirmAction('Rollback this job using its manifest?')) return;
      runAction('Rollback job', () => api(`/api/jobs/${job.job_id}/rollback?confirm=true`, { method: 'POST', body: '{}' }));
    });
    $('#deleteJobBtn').addEventListener('click', () => {
      const job = activeJob();
      if (!job || !confirmAction('Delete this job record and its job artifacts? User files are not deleted.')) return;
      runAction('Delete job', async () => {
        await api(`/api/jobs/${job.job_id}/delete?confirm=true`, { method: 'POST', body: '{}' });
        state.selectedJobId = null;
      });
    });
    $('#deleteAllJobsBtn').addEventListener('click', () => {
      if (!confirmAction('Delete all job records for this root? User files are not deleted.')) return;
      runAction('Delete all jobs', async () => {
        await api('/api/jobs/delete-all?confirm=true', { method: 'POST', body: '{}' });
        state.selectedJobId = null;
      });
    });
    $$('.nav button').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
    $$('[data-view-jump]').forEach(button => button.addEventListener('click', () => setView(button.dataset.viewJump)));
    refresh({ keepSelection: false }).catch(error => setStatus(error.message, 'danger'));
    window.setInterval(() => {
      if (!state.busy) refresh({ silent: true }).catch(error => setStatus(error.message, 'danger'));
    }, 5000);
  </script>
</body>
</html>"""
