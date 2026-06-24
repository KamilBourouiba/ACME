"""Belief engine — promotion, demotion, CRS, and source-aware confidence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import BeliefRecord
from acme.schemas import (
    BeliefScore,
    BeliefStatus,
    CognitiveProfile,
    GraphRelation,
    KnowledgeType,
)


class BeliefEngine:
    def __init__(self, session: AsyncSession, *, tenant_id: str | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def sync_from_relation(
        self,
        graph_id: str,
        label: str,
        relation: GraphRelation,
        *,
        source_id: str | None = None,
        source_credibility: float = 0.75,
        cognitive_profile: str = "factual",
        tenant_id: str | None = None,
    ) -> BeliefRecord:
        belief = await self._get_by_graph_id(graph_id)
        if belief is None:
            belief = BeliefRecord(
                graph_id=graph_id,
                label=label,
                knowledge_type=relation.knowledge_type.value,
                status=BeliefStatus.HYPOTHESIS.value,
                cognitive_profile=cognitive_profile,
                confidence=relation.confidence * source_credibility,
                tenant_id=tenant_id or self.tenant_id or settings.default_tenant_id,
            )
            self.session.add(belief)
        else:
            belief.confidence = (belief.confidence + relation.confidence * source_credibility) / 2
            belief.label = label

        if source_id and source_id not in (belief.source_ids or []):
            belief.source_ids = list(belief.source_ids or []) + [source_id]
            belief.independent_source_count = len(belief.source_ids)
            belief.time_windows = max(belief.time_windows or 1, len(belief.source_ids))

        belief.supporting_evidence = (belief.supporting_evidence or 0) + 1
        belief.last_reinforced_at = datetime.now(timezone.utc)
        belief.crs = self.compute_crs(belief)
        self._apply_consensus_prediction_boost(belief)
        await self._maybe_promote(belief)
        await self.session.flush()
        return belief

    def _apply_consensus_prediction_boost(self, belief: BeliefRecord) -> None:
        """Multi-source agreement counts as implicit prediction success for CRS."""
        if not settings.belief_consensus_prediction_boost:
            return
        sources = belief.independent_source_count or 0
        supporting = belief.supporting_evidence or 0
        if sources < 2 or supporting < 2:
            return
        pred_total = (belief.prediction_successes or 0) + (belief.prediction_failures or 0)
        if pred_total == 0:
            belief.prediction_successes = 1
            belief.crs = self.compute_crs(belief)

    async def reinforce(
        self,
        graph_id: str,
        supporting: bool,
        *,
        strong_contradiction: bool = False,
        source_id: str | None = None,
    ) -> BeliefRecord | None:
        belief = await self._get_by_graph_id(graph_id)
        if belief is None:
            return None

        if supporting:
            belief.supporting_evidence = (belief.supporting_evidence or 0) + 1
            belief.confidence = min(1.0, (belief.confidence or 0) + 0.05)
            if source_id and source_id not in (belief.source_ids or []):
                belief.source_ids = list(belief.source_ids or []) + [source_id]
                belief.independent_source_count = len(belief.source_ids)
        else:
            belief.contradicting_evidence = (belief.contradicting_evidence or 0) + 1
            penalty = (
                settings.belief_strong_contradiction_penalty
                if strong_contradiction
                else 0.1
            )
            if strong_contradiction:
                belief.strong_contradictions = (belief.strong_contradictions or 0) + 1
            belief.confidence = max(0.0, (belief.confidence or 0) - penalty)

        belief.last_reinforced_at = datetime.now(timezone.utc)
        await self._apply_lifecycle(belief)
        belief.crs = self.compute_crs(belief)
        await self.session.flush()
        return belief

    async def record_contradiction(
        self,
        graph_id: str,
        *,
        strong: bool = False,
        source_id: str | None = None,
    ) -> BeliefRecord | None:
        return await self.reinforce(
            graph_id,
            supporting=False,
            strong_contradiction=strong,
            source_id=source_id,
        )

    async def list_beliefs(
        self,
        min_confidence: float = 0.0,
        exclude_deprecated: bool = True,
    ) -> list[BeliefScore]:
        stmt = select(BeliefRecord).where(BeliefRecord.confidence >= min_confidence)
        if self.tenant_id:
            stmt = stmt.where(BeliefRecord.tenant_id == self.tenant_id)
        if exclude_deprecated:
            stmt = stmt.where(
                BeliefRecord.status.notin_(
                    [BeliefStatus.DEPRECATED.value, BeliefStatus.ARCHIVED.value]
                )
            )
        stmt = stmt.order_by(BeliefRecord.crs.desc())
        result = await self.session.execute(stmt)
        return [self._to_score(b) for b in result.scalars().all()]

    @classmethod
    def compute_crs(cls, belief: BeliefRecord) -> float:
        pred_success = belief.prediction_successes or 0
        pred_fail = belief.prediction_failures or 0
        predictions = pred_success + pred_fail
        pred_rate = pred_success / predictions if predictions > 0 else 0.5
        time_windows = belief.time_windows or 1
        temporal = min(1.0, time_windows / max(1, settings.belief_min_time_windows))
        supporting = belief.supporting_evidence or 0
        contradicting = belief.contradicting_evidence or 0
        total = supporting + contradicting
        contradiction_resistance = supporting / total if total > 0 else 0.5
        source_diversity = min(1.0, (belief.independent_source_count or 0) / max(1, settings.belief_min_independent_sources + 1))

        crs = (
            settings.crs_weight_prediction * pred_rate
            + settings.crs_weight_temporal * temporal
            + settings.crs_weight_contradiction * contradiction_resistance
            + settings.crs_weight_sources * source_diversity
        )
        return round(crs, 4)

    async def _apply_lifecycle(self, belief: BeliefRecord) -> None:
        contradicting = belief.contradicting_evidence or 0
        strong = belief.strong_contradictions or 0

        if contradicting >= settings.belief_archive_contradictions:
            belief.status = BeliefStatus.ARCHIVED.value
            belief.knowledge_type = KnowledgeType.HYPOTHESIS.value
            belief.confidence = min(belief.confidence or 0, 0.1)
            return

        if (
            contradicting >= settings.belief_demote_contradictions
            or (strong >= 1 and contradicting >= 2)
        ):
            belief.status = BeliefStatus.DEPRECATED.value
            belief.knowledge_type = KnowledgeType.HYPOTHESIS.value
            return

        if strong >= 1 or contradicting >= 1:
            if belief.status == BeliefStatus.BELIEF.value:
                belief.status = BeliefStatus.CHALLENGED.value

        await self._maybe_promote(belief)

    async def _maybe_promote(self, belief: BeliefRecord) -> None:
        if belief.status in (BeliefStatus.DEPRECATED.value, BeliefStatus.ARCHIVED.value):
            return

        supporting = belief.supporting_evidence or 0
        contradicting = belief.contradicting_evidence or 0
        total = supporting + contradicting
        if total == 0:
            return

        ratio = supporting / total
        pred_success = belief.prediction_successes or 0
        pred_fail = belief.prediction_failures or 0
        predictions = pred_success + pred_fail
        prediction_rate = pred_success / predictions if predictions > 0 else 0.0

        source_ok = (belief.independent_source_count or 0) >= settings.belief_min_independent_sources or (
            supporting >= settings.belief_min_observations
            and (belief.independent_source_count or 0) >= 1
        )

        if (
            supporting >= settings.belief_min_observations
            and (belief.time_windows or 1) >= settings.belief_min_time_windows
            and ratio >= settings.belief_min_confidence
            and (predictions == 0 or prediction_rate >= settings.belief_min_prediction_rate)
            and source_ok
            and (belief.strong_contradictions or 0) == 0
        ):
            belief.status = BeliefStatus.BELIEF.value
            belief.knowledge_type = KnowledgeType.BELIEF.value
        elif supporting >= 1:
            belief.status = BeliefStatus.HYPOTHESIS.value
            belief.knowledge_type = KnowledgeType.HYPOTHESIS.value

    async def consolidate_lifecycle(self) -> tuple[int, int]:
        """Re-evaluate all beliefs — returns (promoted, demoted) counts."""
        stmt = select(BeliefRecord)
        result = await self.session.execute(stmt)
        promoted = 0
        demoted = 0
        for belief in result.scalars().all():
            before_status = belief.status
            before_type = belief.knowledge_type
            await self._apply_lifecycle(belief)
            belief.crs = self.compute_crs(belief)
            if before_status not in (
                BeliefStatus.DEPRECATED.value,
                BeliefStatus.ARCHIVED.value,
            ) and belief.status in (
                BeliefStatus.DEPRECATED.value,
                BeliefStatus.ARCHIVED.value,
            ):
                demoted += 1
            if before_type != KnowledgeType.BELIEF.value and belief.knowledge_type == KnowledgeType.BELIEF.value:
                promoted += 1
        await self.session.flush()
        return promoted, demoted

    async def _get_by_graph_id(self, graph_id: str) -> BeliefRecord | None:
        stmt = select(BeliefRecord).where(BeliefRecord.graph_id == graph_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    def _to_score(cls, belief: BeliefRecord) -> BeliefScore:
        return BeliefScore(
            entity_or_relation_id=belief.graph_id,
            label=belief.label,
            knowledge_type=KnowledgeType(belief.knowledge_type),
            status=BeliefStatus(belief.status),
            confidence=belief.confidence,
            crs=belief.crs or cls.compute_crs(belief),
            supporting_evidence=belief.supporting_evidence,
            contradicting_evidence=belief.contradicting_evidence,
            strong_contradictions=belief.strong_contradictions,
            independent_sources=belief.independent_source_count or 0,
            prediction_successes=belief.prediction_successes,
            prediction_failures=belief.prediction_failures,
            time_windows=belief.time_windows,
            cognitive_profile=CognitiveProfile(belief.cognitive_profile or "factual"),
        )
