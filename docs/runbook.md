# Runbook

## Install for Development

```bash
python -m pip install -e .
```

## Smoke Test

```bash
python -m unittest discover -s tests -v
python -m src.cli providers list
python -m src.cli doctor C:\target
python -m src.cli run C:\target
```

## Safe Apply

```bash
thelibrarian plan C:\target --output C:\target\.thelibrarian\plans\plan.json
thelibrarian apply C:\target --plan C:\target\.thelibrarian\plans\plan.json --confirm
```

## Rollback

Use the manifest printed after apply:

```bash
thelibrarian rollback C:\target --manifest C:\target\.thelibrarian\manifests\rollback-YYYYMMDDTHHMMSSZ.json --confirm
```

Rollback skips any operation whose original destination is now occupied.
