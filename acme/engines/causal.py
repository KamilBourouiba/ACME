"""Causal intervention validation — correlates → causes only after verified outcome."""

from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord
from acme.engines.belief import BeliefEngine
from acme.engines.prediction import PredictionEngine
from acme.graph.neo4j_client import Neo4jClient
from acme.schemas import CausalRelationType, CausalValidateRequest, CausalValidateResponse, PredictionValidate


class CausalEngine:
    def __init__(
        self,
        session: AsyncSession,
        graph: Neo4jClient,
    ) -> None:
        self.session = session
        self.graph = graph
        self.beliefs = BeliefEngine(session)
        self.predictions = PredictionEngine(session)

    async def validate_intervention(self, data: CausalValidateRequest) -> CausalValidateResponse:
        success = data.success
        causal_upgraded = False

        if data.prediction_id:
            await self.predictions.validate(
                PredictionValidate(
                    prediction_id=data.prediction_id,
                    actual_outcome=data.actual_outcome,
                    success=success,
                )
            )

        if data.belief_graph_id:
            belief = await self.beliefs._get_by_graph_id(data.belief_graph_id)
            if belief:
                if success:
                    belief.supporting_evidence += 1
                    belief.confidence = min(1.0, belief.confidence + 0.1)
                    causal_upgraded = await self._upgrade_causal_type(belief)
                else:
                    belief.contradicting_evidence += 1
                    belief.confidence = max(0.0, belief.confidence - 0.15)
                await self.beliefs._apply_lifecycle(belief)
                belief.crs = BeliefEngine.compute_crs(belief)
                await self.session.flush()

        await self.session.commit()
        return CausalValidateResponse(
            success=success,
            causal_upgraded=causal_upgraded,
            belief_graph_id=data.belief_graph_id,
            message="Causal link confirmed via intervention" if success and causal_upgraded else "Intervention recorded",
        )

    async def _upgrade_causal_type(self, belief: BeliefRecord) -> bool:
        if "correlates" in belief.label.lower() or "observed_with" in belief.label.lower():
            belief.label = belief.label.replace("correlates", "causes").replace("observed_with", "causes")
            return True
        parts = belief.label.split(" -[")
        if len(parts) == 2:
            source_target = parts[0]
            rest = parts[1]
            if CausalRelationType.CORRELATES.value in rest or CausalRelationType.OBSERVED_WITH.value in rest:
                belief.label = (
                    f"{source_target} -[{CausalRelationType.CAUSES.value}]-> "
                    + rest.split("]->", 1)[-1]
                )
                return True
        return False
