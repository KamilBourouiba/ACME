"""Neo4j semantic graph memory — tenant-scoped entities and relations."""

import json
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from acme.config import settings
from acme.schemas import GraphEntity, GraphRelation, KnowledgeType


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await self._init_constraints()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @property
    def driver(self) -> AsyncDriver:
        if not self._driver:
            raise RuntimeError("Neo4j client not connected")
        return self._driver

    async def ping(self) -> bool:
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def _init_constraints(self) -> None:
        queries = [
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX entity_tenant IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id)",
            "CREATE INDEX knowledge_type IF NOT EXISTS FOR (e:Entity) ON (e.knowledge_type)",
            """
            CREATE CONSTRAINT entity_tenant_name IF NOT EXISTS
            FOR (e:Entity) REQUIRE (e.tenant_id, e.name) IS UNIQUE
            """,
            "MATCH (e:Entity) WHERE e.tenant_id IS NULL SET e.tenant_id = 'default'",
        ]
        async with self.driver.session() as session:
            for query in queries:
                try:
                    await session.run(query)
                except Exception:
                    if "entity_tenant_name" not in query and "entity_name" not in query:
                        raise

    async def upsert_entity(
        self,
        entity: GraphEntity,
        *,
        tenant_id: str = "default",
        benchmark_tag: str | None = None,
    ) -> str:
        query = """
        MERGE (e:Entity {name: $name, tenant_id: $tenant_id})
        ON CREATE SET e.created_at = datetime()
        SET e.entity_type = $entity_type,
            e.knowledge_type = $knowledge_type,
            e.properties = $properties,
            e.benchmark_tag = $benchmark_tag,
            e.updated_at = datetime()
        RETURN e.name AS name
        """
        async with self.driver.session() as session:
            result = await session.run(
                query,
                name=entity.name,
                tenant_id=tenant_id,
                entity_type=entity.entity_type,
                knowledge_type=entity.knowledge_type.value,
                properties=json.dumps(entity.properties or {}),
                benchmark_tag=benchmark_tag,
            )
            record = await result.single()
            return record["name"]

    async def upsert_relation(
        self,
        relation: GraphRelation,
        *,
        tenant_id: str = "default",
        benchmark_tag: str | None = None,
    ) -> dict[str, Any]:
        rel_type = self._sanitize_rel_type(relation.relation_type)
        query = f"""
        MERGE (a:Entity {{name: $source, tenant_id: $tenant_id}})
        MERGE (b:Entity {{name: $target, tenant_id: $tenant_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        ON CREATE SET r.created_at = datetime(),
                      r.supporting_evidence = 0,
                      r.contradicting_evidence = 0,
                      r.tenant_id = $tenant_id
        SET r.confidence = $confidence,
            r.knowledge_type = $knowledge_type,
            r.causal_type = $causal_type,
            r.properties = $properties,
            r.benchmark_tag = $benchmark_tag,
            r.tenant_id = $tenant_id,
            r.updated_at = datetime()
        RETURN a.name AS source, type(r) AS relation_type, b.name AS target, id(r) AS rel_id
        """
        async with self.driver.session() as session:
            result = await session.run(
                query,
                source=relation.source,
                target=relation.target,
                tenant_id=tenant_id,
                confidence=relation.confidence,
                knowledge_type=relation.knowledge_type.value,
                causal_type=relation.causal_type.value,
                properties=json.dumps(relation.properties or {}),
                benchmark_tag=benchmark_tag,
            )
            record = await result.single()
            return dict(record) if record else {}

    async def apply_extraction(
        self,
        entities: list[GraphEntity],
        relations: list[GraphRelation],
        *,
        tenant_id: str = "default",
        benchmark_tag: str | None = None,
    ) -> tuple[list[str], list[tuple[GraphRelation, str]]]:
        entity_refs: list[str] = []
        relation_refs: list[tuple[GraphRelation, str]] = []
        for entity in entities:
            name = await self.upsert_entity(
                entity, tenant_id=tenant_id, benchmark_tag=benchmark_tag
            )
            entity_refs.append(f"entity:{name}")
        for relation in relations:
            result = await self.upsert_relation(
                relation, tenant_id=tenant_id, benchmark_tag=benchmark_tag
            )
            if result:
                graph_id = f"relation:{result['rel_id']}"
                relation_refs.append((relation, graph_id))
        return entity_refs, relation_refs

    async def search_entities(
        self,
        terms: list[str],
        limit: int = 20,
        *,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        if not terms:
            return []
        query = """
        MATCH (e:Entity {tenant_id: $tenant_id})
        WHERE ANY(term IN $terms WHERE toLower(e.name) CONTAINS toLower(term))
        OPTIONAL MATCH (e)-[r]->(related:Entity {tenant_id: $tenant_id})
        RETURN e.name AS name,
               e.entity_type AS entity_type,
               e.knowledge_type AS knowledge_type,
               collect(DISTINCT {
                   type: type(r),
                   target: related.name,
                   confidence: r.confidence,
                   knowledge_type: r.knowledge_type
               }) AS outgoing
        LIMIT $limit
        """
        async with self.driver.session() as session:
            result = await session.run(query, terms=terms, limit=limit, tenant_id=tenant_id)
            records = await result.data()
            return records

    async def get_neighborhood(
        self,
        entity_name: str,
        depth: int = 2,
        *,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        depth = max(1, min(depth, 3))
        query = f"""
        MATCH path = (e:Entity {{name: $name, tenant_id: $tenant_id}})-[*1..{depth}]-(connected:Entity {{tenant_id: $tenant_id}})
        UNWIND relationships(path) AS r
        RETURN DISTINCT
            startNode(r).name AS source,
            type(r) AS relation_type,
            endNode(r).name AS target,
            r.confidence AS confidence,
            r.knowledge_type AS knowledge_type
        LIMIT 100
        """
        async with self.driver.session() as session:
            result = await session.run(query, name=entity_name, tenant_id=tenant_id)
            return await result.data()

    async def adjust_relation_confidence(self, rel_id: int, delta: float) -> None:
        query = """
        MATCH ()-[r]->()
        WHERE id(r) = $rel_id
        SET r.confidence = CASE
            WHEN r.confidence + $delta > 1.0 THEN 1.0
            WHEN r.confidence + $delta < 0.0 THEN 0.0
            ELSE r.confidence + $delta
        END,
        r.updated_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(query, rel_id=rel_id, delta=delta)

    async def increment_evidence(self, rel_id: int, supporting: bool) -> None:
        field = "supporting_evidence" if supporting else "contradicting_evidence"
        query = f"""
        MATCH ()-[r]->()
        WHERE id(r) = $rel_id
        SET r.{field} = coalesce(r.{field}, 0) + 1,
            r.updated_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(query, rel_id=rel_id)

    async def delete_benchmark_graph(
        self,
        benchmark_tag: str,
        *,
        tenant_id: str = "default",
    ) -> dict[str, int]:
        """Remove entities and relations tagged during MemoryBench runs for one tenant."""
        entity_query = """
        MATCH (e:Entity {benchmark_tag: $tag, tenant_id: $tenant_id})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        rel_query = """
        MATCH ()-[r {benchmark_tag: $tag, tenant_id: $tenant_id}]->()
        DELETE r
        RETURN count(r) AS deleted
        """
        async with self.driver.session() as session:
            entity_result = await session.run(
                entity_query, tag=benchmark_tag, tenant_id=tenant_id
            )
            entity_record = await entity_result.single()
            rel_result = await session.run(rel_query, tag=benchmark_tag, tenant_id=tenant_id)
            rel_record = await rel_result.single()
            return {
                "entities_deleted": entity_record["deleted"] if entity_record else 0,
                "relations_deleted": rel_record["deleted"] if rel_record else 0,
            }

    async def prune_orphan_entities(self, *, tenant_id: str | None = None) -> int:
        if tenant_id:
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            WHERE NOT (e)--()
            DELETE e
            RETURN count(e) AS deleted
            """
            params = {"tenant_id": tenant_id}
        else:
            query = """
            MATCH (e:Entity)
            WHERE NOT (e)--()
            DELETE e
            RETURN count(e) AS deleted
            """
            params = {}
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record["deleted"] if record else 0

    @staticmethod
    def _sanitize_rel_type(relation_type: str) -> str:
        cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in relation_type.upper())
        return cleaned or "RELATED_TO"


neo4j_client = Neo4jClient()
