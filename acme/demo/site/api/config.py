import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_TITLE = "Erebor Intelligence API"
API_VERSION = "1.0.0"

OSS_SOURCES = [
    {
        "id": "github",
        "label": "GitHub",
        "endpoint": "https://api.github.com",
        "license": "MIT Terms",
        "description": "Repository metadata, stars, languages — public REST API.",
    },
    {
        "id": "openalex",
        "label": "OpenAlex",
        "endpoint": "https://api.openalex.org",
        "license": "CC0",
        "description": "Scholarly works graph — papers, citations, institutions.",
    },
    {
        "id": "nominatim",
        "label": "OpenStreetMap Nominatim",
        "endpoint": "https://nominatim.openstreetmap.org",
        "license": "ODbL",
        "description": "Geocoding and place intelligence from OSM.",
    },
    {
        "id": "restcountries",
        "label": "REST Countries",
        "endpoint": "https://restcountries.com/v3.1",
        "license": "MPL-2.0",
        "description": "Country metadata for geopolitical context nodes.",
    },
]

SEED_GRAPH = {
    "nodes": [
        {
            "id": "gh:postgres/postgres",
            "kind": "repo",
            "label": "postgres/postgres",
            "source": "GitHub",
            "description": "Advanced open-source relational database.",
            "lat": 37.77,
            "lng": -122.42,
            "score": 98,
            "url": "https://github.com/postgres/postgres",
        },
        {
            "id": "gh:apache/kafka",
            "kind": "repo",
            "label": "apache/kafka",
            "source": "GitHub",
            "description": "Distributed event streaming platform.",
            "lat": 51.51,
            "lng": -0.12,
            "score": 96,
            "url": "https://github.com/apache/kafka",
        },
        {
            "id": "oa:W2741809807",
            "kind": "paper",
            "label": "Attention Is All You Need",
            "source": "OpenAlex",
            "description": "Transformer architecture — foundational ML paper.",
            "lat": 52.52,
            "lng": 13.40,
            "score": 99,
            "url": "https://openalex.org/W2741809807",
        },
        {
            "id": "geo:berlin",
            "kind": "place",
            "label": "Berlin, Germany",
            "source": "Nominatim",
            "description": "EU open-source hub — clusters around Mapbox, Wikimedia.",
            "lat": 52.52,
            "lng": 13.405,
            "score": 72,
        },
        {
            "id": "gh:grafana/grafana",
            "kind": "repo",
            "label": "grafana/grafana",
            "source": "GitHub",
            "description": "Observability dashboards — AGPL observability stack.",
            "lat": 59.33,
            "lng": 18.06,
            "score": 94,
            "url": "https://github.com/grafana/grafana",
        },
    ],
    "edges": [
        {"from": "gh:postgres/postgres", "to": "gh:apache/kafka"},
        {"from": "gh:apache/kafka", "to": "oa:W2741809807"},
        {"from": "oa:W2741809807", "to": "geo:berlin"},
        {"from": "geo:berlin", "to": "gh:grafana/grafana"},
    ],
}
