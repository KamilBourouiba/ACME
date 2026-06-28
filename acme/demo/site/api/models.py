from pydantic import BaseModel, Field


class CatalogOut(BaseModel):
    sources: list[dict]


class GraphOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class SearchOut(BaseModel):
    query: str
    groups: list[dict]


class TrailIn(BaseModel):
    type: str
    query: str | None = None
    entity_id: str | None = None
    kind: str | None = None


class TrailOut(BaseModel):
    ok: bool
    persisted: bool = False
    id: int | None = None
