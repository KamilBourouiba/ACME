# Nexus Advisory — Site Architecture

```
static/          # Frontend (GitHub Pages + nginx)
  index.html
  css/           # Design tokens, layout, components
  js/            # API client, UI components, app bootstrap
api/             # FastAPI backend (VM)
  config.py      # Settings from env
  db.py          # Postgres pool + migrations
  models.py      # Pydantic schemas
  routes/        # HTTP handlers (health, leads, services)
server.py        # ASGI entrypoint
tests/           # Smoke tests
docker-compose.yml
nginx.conf       # TLS termination + /api proxy
```

**Data flow:** Browser → nginx → static assets | `/api/*` → FastAPI → Postgres (private VNet).

**Deploy targets:** GitHub Pages (static/) + secure squad VM (full stack).
