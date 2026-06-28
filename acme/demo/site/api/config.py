import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_TITLE = "Lumen API"
API_VERSION = "1.0.0"

FEATURES = [
    {"icon": "⚡", "title": "Signal ingestion", "desc": "Unify CRM, product, and billing events into one revenue graph."},
    {"icon": "🎯", "title": "Forecast AI", "desc": "ML models trained on your pipeline history — not generic benchmarks."},
    {"icon": "🔔", "title": "Churn radar", "desc": "Early warnings when accounts show expansion or contraction patterns."},
    {"icon": "📊", "title": "Board packs", "desc": "One-click exports for QBRs with narrative + chart auto-generation."},
    {"icon": "🔗", "title": "RevOps sync", "desc": "Bi-directional Salesforce & HubSpot with field-level mapping."},
    {"icon": "🛡️", "title": "Enterprise SSO", "desc": "SAML, SCIM, and audit logs for regulated industries."},
]

PRICING = {
    "monthly": [
        {"name": "Starter", "price": 49, "features": ["5 seats", "CRM sync", "Weekly forecasts"]},
        {"name": "Pro", "price": 149, "featured": True, "features": ["25 seats", "Churn radar", "Board packs"]},
        {"name": "Enterprise", "price": None, "features": ["Unlimited seats", "SSO / SCIM", "Custom models"]},
    ],
    "annual": [
        {"name": "Starter", "price": 39, "features": ["5 seats", "CRM sync", "Weekly forecasts"]},
        {"name": "Pro", "price": 119, "featured": True, "features": ["25 seats", "Churn radar", "Board packs"]},
        {"name": "Enterprise", "price": None, "features": ["Unlimited seats", "SSO / SCIM", "Custom models"]},
    ],
}

METRICS = {"waitlist_count": 2140, "forecast_accuracy": 94, "customers_beta": 47}
