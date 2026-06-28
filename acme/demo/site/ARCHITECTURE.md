# Lumen — Revenue Intelligence Platform

```
static/                 Marketing site (GitHub Pages + nginx)
  index.html
  css/                  tokens, hero, features, pricing, dashboard-mock, animations
  js/                   api, hero, pricing, features, app
api/                    FastAPI on secure VM
  config.py             Features, pricing tiers, metrics
  db.py                 Postgres pool
  models.py
  routes/               health, waitlist, features, metrics
server.py
tests/
```

**Stack:** Dark premium UI · animated hero · CSS dashboard mock · interactive pricing · waitlist API → private Postgres.
