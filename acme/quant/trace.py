"""Build belief reasoning trail from episodes, beliefs, and trades."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from acme.quant.schemas import BeliefOut, TraceOut, TradeOut


def _kind_for_status(status: str, knowledge_type: str) -> str:
    if status in ("belief", "promoted"):
        return "bel"
    if status in ("challenged", "deprecated"):
        return "clash"
    if knowledge_type == "hypothesis" or status == "hypothesis":
        return "hyp"
    return "obs"


def build_trace(
    *,
    episodes: list[dict[str, Any]],
    beliefs: list[BeliefOut],
    trades: list[TradeOut],
    existing_nodes: list[dict] | None = None,
    existing_edges: list[dict] | None = None,
    existing_steps: list[dict] | None = None,
) -> TraceOut:
    nodes: list[dict] = list(existing_nodes or [])
    edges: list[dict] = list(existing_edges or [])
    steps: list[dict] = list(existing_steps or [])

    node_ids = {n["id"] for n in nodes}
    edge_keys = {(e["from"], e["to"]) for e in edges}

    def add_node(nid: str, kind: str, label: str, x: float, y: float) -> None:
        if nid not in node_ids:
            nodes.append({"id": nid, "kind": kind, "label": label[:80], "x": x, "y": y})
            node_ids.add(nid)

    def add_edge(src: str, dst: str) -> None:
        key = (src, dst)
        if key not in edge_keys:
            edges.append({"from": src, "to": dst})
            edge_keys.add(key)

    # Map episodes to observation nodes
    for i, ep in enumerate(episodes[:12]):
        eid = f"ep{i}"
        add_node(eid, "obs", ep.get("text", "")[:60], 80, 120 + i * 55)
        if i > 0:
            add_edge(f"ep{i - 1}", eid)

    # Map beliefs
    for j, b in enumerate(beliefs[:8]):
        bid = f"bel{j}"
        kind = _kind_for_status(b.status, "belief")
        add_node(bid, kind, b.label, 320 + j * 30, 180 + j * 45)
        if episodes:
            add_edge("ep0", bid)
        if j > 0:
            add_edge(f"bel{j - 1}", bid)

    # Map trades
    for k, t in enumerate(trades[:6]):
        tid = f"tr{k}"
        side_label = f"{t.side.upper()} {t.symbol} @ ${t.price:.2f}"
        add_node(tid, "bel" if t.side == "buy" else "hyp", side_label, 520, 200 + k * 50)
        if t.belief_graph_id and beliefs:
            for j, b in enumerate(beliefs):
                if b.graph_id == t.belief_graph_id:
                    add_edge(f"bel{j}", tid)
                    break
        elif beliefs:
            add_edge(f"bel{min(k, len(beliefs) - 1)}", tid)

    # Build steps from pipeline stages
    if not steps:
        ep_slice = [
            {"t": ep.get("time", ""), "text": ep.get("text", "")}
            for ep in episodes[:6]
        ]
        active_obs = [f"ep{i}" for i in range(min(3, len(episodes)))]
        active_bel = [f"bel{i}" for i in range(min(2, len(beliefs)))]
        active_tr = [f"tr{i}" for i in range(min(1, len(trades)))]

        crs_vals = [b.crs for b in beliefs] or [0.42]
        steps = [
            {
                "title": "Market ingest",
                "crs": round(crs_vals[0] * 0.7, 2),
                "episodes": ep_slice[:2],
                "activeNodes": active_obs[:1],
                "activeEdges": [],
                "inspector": None,
            },
            {
                "title": "Knowledge extract",
                "crs": round(crs_vals[0] * 0.85, 2),
                "episodes": ep_slice[:4],
                "activeNodes": active_obs,
                "activeEdges": [["ep0", "ep1"]] if len(active_obs) > 1 else [],
                "inspector": None,
            },
            {
                "title": "Belief formation",
                "crs": round(max(crs_vals), 2) if crs_vals else 0.5,
                "episodes": ep_slice,
                "activeNodes": active_obs + active_bel,
                "activeEdges": [[active_obs[0], active_bel[0]]] if active_obs and active_bel else [],
                "inspector": (
                    {
                        "id": active_bel[0],
                        "type": "Belief",
                        "title": beliefs[0].label[:80] if beliefs else "Forming thesis",
                        "desc": "CRS-scored market belief from accumulated evidence.",
                        "stats": {
                            "crs": f"{beliefs[0].crs:.2f}" if beliefs else "—",
                            "sources": str(beliefs[0].supporting_evidence) if beliefs else "0",
                            "status": beliefs[0].status if beliefs else "hypothesis",
                        },
                    }
                    if beliefs
                    else None
                ),
            },
        ]
        if trades:
            t0 = trades[0]
            steps.append(
                {
                    "title": "Paper trade",
                    "crs": round(t0.crs_at_trade or crs_vals[0], 2),
                    "episodes": [
                        {
                            "t": t0.created_at.strftime("%H:%M"),
                            "text": f"<strong>{t0.side.upper()} {t0.quantity:.0f} {t0.symbol}</strong> @ ${t0.price:.2f}",
                        },
                        {"t": "", "text": t0.reasoning[:200] if t0.reasoning else ""},
                    ],
                    "activeNodes": active_obs + active_bel + active_tr,
                    "activeEdges": [[active_bel[0], active_tr[0]]] if active_bel and active_tr else [],
                    "inspector": {
                        "id": active_tr[0],
                        "type": "Trade",
                        "title": f"{t0.side.upper()} {t0.symbol}",
                        "desc": t0.reasoning[:300] or "Executed on demo account.",
                        "stats": {
                            "price": f"${t0.price:.2f}",
                            "notional": f"${t0.notional:,.0f}",
                            "belief": (t0.belief_label or "—")[:40],
                        },
                    },
                }
            )

    return TraceOut(nodes=nodes, edges=edges, steps=steps)


def append_cycle_step(
    steps: list[dict],
    *,
    title: str,
    crs: float,
    episode_text: str,
    time_str: str,
    active_nodes: list[str],
    active_edges: list[list[str]] | None = None,
    inspector: dict | None = None,
    max_steps: int = 20,
) -> list[dict]:
    prev_eps = steps[-1]["episodes"] if steps else []
    new_eps = list(prev_eps[-4:]) + [{"t": time_str, "text": episode_text}]
    step = {
        "title": title,
        "crs": round(crs, 2),
        "episodes": new_eps,
        "activeNodes": active_nodes,
        "activeEdges": active_edges or [],
        "inspector": inspector,
    }
    steps = steps + [step]
    return steps[-max_steps:]
