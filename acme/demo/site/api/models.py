from pydantic import BaseModel


class TraceOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    steps: list[dict]
