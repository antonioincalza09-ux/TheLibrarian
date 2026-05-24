# Local Web App

The local web app is a browser-based preview surface for the standalone application.

```bash
thelibrarian serve C:\target --host 127.0.0.1 --port 8765
```

The server exposes:

- `/`: browser UI.
- `/api/inventory`: inventory JSON.
- `/api/plan`: plan JSON.
- `/api/apply?confirm=true`: applies a saved plan path from JSON body.

The v1 UI shows Inventory, Plan, Review, Warnings, and Manifest guidance. It does not auto-apply generated plans. Apply requires a saved plan path and explicit confirmation.

The target root is supplied when the server starts. The UI does not browse arbitrary filesystem locations.
