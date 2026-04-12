# Caddy Manager Service

Lightweight REST API for managing Caddy configuration via file-based staging and validation.

## Philosophy

**Caddyfile is the source of truth.** This service:
- Never calls Caddy API
- Works entirely with the Caddyfile on disk
- Uses `caddy validate` for syntax checking
- Provides atomic apply/rollback via staging

## Architecture

```
/etc/caddy/Caddyfile          ← Live config (source of truth)
/var/lib/caddy-manager/
  ├── Caddyfile.staged        ← Pending changes (while staging)
  ├── backups/
  │   ├── Caddyfile.YYYYMMDD_HHMMSS.bak
  │   └── ...
  ├── state.json              ← Last operation times
  ├── history.jsonl           ← Audit log
  └── temp/                   ← Temporary validation files
```

## Workflow

```
1. GET /config/current
   → Read /etc/caddy/Caddyfile

2. POST /config/stage (with new config)
   → Write to Caddyfile.staged
   → Run `caddy validate` on it
   → Return validation result + preview

3. POST /config/apply
   → Validate staged
   → Backup current to backups/
   → Move staged → live
   → systemctl reload caddy

4. POST /config/rollback
   → Restore from latest backup
   → Reload caddy
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/status` | Service + state info |
| `GET` | `/config/current` | Read live Caddyfile |
| `POST` | `/config/validate` | Validate without staging |
| `POST` | `/config/stage` | Stage + validate for review |
| `POST` | `/config/apply` | Apply staged (backup → swap → reload) |
| `POST` | `/config/rollback` | Revert to previous backup |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CADDYFILE_PATH` | `/etc/caddy/Caddyfile` | Path to live Caddyfile |
| `CADDY_MANAGER_DATA` | `/var/lib/caddy-manager` | Data/staging directory |
| `CADDY_RELOAD_CMD` | `systemctl reload caddy` | Reload command |
| `PORT` | `9999` | Listen port |
| `DEBUG` | `false` | Flask debug mode |

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create data directory
sudo mkdir -p /var/lib/caddy-manager
sudo chown caddy:caddy /var/lib/caddy-manager

# Run service
python app.py

# Or systemd service
sudo cp caddy-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now caddy-manager
```

## Note on Validation

Currently assumes Caddyfile content is in JSON format (Caddy API format).
To support native Caddyfile syntax, you'd run:

```bash
caddy adapt --config /path/to/Caddyfile --adapter caddyfile
```

before validation. This is a TODO.

## Request/Response Examples

### Stage a config

```bash
curl -X POST http://localhost:9999/config/stage \
  -H "Content-Type: application/json" \
  -d '{
    "config": "{\"apps\": {\"http\": {...}}}"
  }'
```

Response:
```json
{
  "ok": true,
  "staged_path": "/var/lib/caddy-manager/Caddyfile.staged",
  "preview": "Configuration preview: ...",
  "valid": true,
  "errors": [],
  "warnings": []
}
```

### Apply staged config

```bash
curl -X POST http://localhost:9999/config/apply
```

Response:
```json
{
  "ok": true,
  "message": "Config applied successfully",
  "backup_path": "/var/lib/caddy-manager/backups/Caddyfile.20260413_145530.bak"
}
```

### Rollback

```bash
curl -X POST http://localhost:9999/config/rollback
```

Response:
```json
{
  "ok": true,
  "message": "Rolled back to previous config",
  "restored_from": "/var/lib/caddy-manager/backups/Caddyfile.20260413_145530.bak"
}
```
