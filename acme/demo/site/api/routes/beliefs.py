from fastapi import APIRouter

from api.belief_data import EDGES, NODES, TRACE_STEPS
from api.models import TraceOut

router = APIRouter()


@router.get("/trace", response_model=TraceOut)
async def investigation_trace() -> TraceOut:
    return TraceOut(nodes=NODES, edges=EDGES, steps=TRACE_STEPS)
