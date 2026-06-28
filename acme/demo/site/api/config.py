import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_TITLE = "Nexus Advisory API"
API_VERSION = "1.0.0"

SERVICES = [
    {"title": "Strategy", "desc": "Market entry & portfolio bets"},
    {"title": "Ops", "desc": "Process design & automation"},
    {"title": "Data", "desc": "Analytics roadmaps & governance"},
]
