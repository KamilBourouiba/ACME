# Erebor — Open Intelligence Graph

**Erebor** is the product: a Palantir-grade investigation workspace built entirely on open data.

The site *is* the platform — not a marketing landing page. Users search across GitHub, OpenAlex, and OpenStreetMap Nominatim; results populate a Three.js globe graph with entity inspection and investigation trails.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Vanilla ES modules, Three.js r170, CSS grid shell |
| Backend | FastAPI, httpx OSS proxies |
| Data | GitHub REST, OpenAlex, Nominatim (all open APIs) |
| Deploy | Docker Compose + nginx TLS on squad VM |

## OSS API sources

- **GitHub** — repository search + metadata (`api.github.com`)
- **OpenAlex** — scholarly works graph (`api.openalex.org`)
- **Nominatim** — geocoding (`nominatim.openstreetmap.org`)
- **REST Countries** — catalogued for geopolitical context

## File map

```
static/
  index.html          Product shell
  css/                tokens, shell, canvas, panels, inspector, timeline
  js/
    scene.js          Three.js globe + arc graph
    app.js            Bootstrap + search wiring
    api.js            Backend client
    panels.js         Entity list + inspector
    timeline.js       Investigation trail
api/
  oss_clients.py      httpx wrappers for OSS APIs
  routes/intelligence.py  /catalog, /graph, /search, /trail
```

## Run locally

```bash
cd acme/demo/site
pip install -r requirements.txt
uvicorn server:app --reload --port 8080
```

Serve `static/` via any static server or nginx in docker-compose.
