"""Build belief reasoning trail — pipeline layout from episodes, beliefs, trades."""

from __future__ import annotations

from typing import Any

from acme.quant.schemas import BeliefOut, TraceOut, TradeOut

# Pipeline columns (x centers in viewBox 0..800)
_COL = {"market": 100, "extract": 280, "belief": 480, "trade": 680}
_ROW_START = 70
_ROW_GAP = 52


def _kind_for_status(status: str) -> str:
    if status in ("belief", "promoted"):
        return "bel"
    if status in ("challenged", "deprecated"):
        return "clash"
    if status == "hypothesis":
        return "hyp"
    return "obs"


def _layout_rows(count: int, col_x: float) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    total_h = (count - 1) * _ROW_GAP
    y0 = max(_ROW_START, 180 - total_h / 2)
    return [(col_x, y0 + i * _ROW_GAP) for i in range(count)]


def build_trace(
    *,
    episodes: list[dict[str, Any]],
    beliefs: list[BeliefOut],
    trades: list[TradeOut],
    existing_nodes: list[dict] | None = None,
    existing_edges: list[dict] | None = None,
    existing_steps: list[dict] | None = None,
) -> TraceOut:
    """Rebuild graph from current data; preserve step timeline history."""
    _ = existing_nodes, existing_edges  # layout is always fresh
    nodes: list[dict] = []
    edges: list[dict] = []
    steps: list[dict] = list(existing_steps or [])

    ep_slice = episodes[:10]
    bel_slice = beliefs[:8]
    tr_slice = trades[:8]

    # --- Market observations (left column) ---
    ep_positions = _layout_rows(len(ep_slice), _COL["market"])
    for i, (ep, (x, y)) in enumerate(zip(ep_slice, ep_positions)):
        text = (ep.get("text") or "")[:72]
        nodes.append(
            {
                "id": f"ep{i}",
                "kind": "obs",
                "column": "market",
                "label": text,
                "short": text[:28] + ("…" if len(text) > 28 else ""),
                "x": x,
                "y": y,
                "meta": ep.get("time", ""),
            }
        )
        if i > 0:
            edges.append({"from": f"ep{i - 1}", "to": f"ep{i}", "flow": "time"})

    # --- Beliefs (center-right) ---
    bel_positions = _layout_rows(len(bel_slice), _COL["belief"])
    for j, (b, (x, y)) in enumerate(zip(bel_slice, bel_positions)):
        kind = _kind_for_status(b.status)
        nodes.append(
            {
                "id": f"bel{j}",
                "kind": kind,
                "column": "belief",
                "label": b.label[:80],
                "short": b.label[:32] + ("…" if len(b.label) > 32 else ""),
                "x": x,
                "y": y,
                "crs": round(b.crs, 2),
                "meta": b.status,
            }
        )
        if ep_slice:
            edges.append({"from": "ep0", "to": f"bel{j}", "flow": "supports"})
        if j > 0:
            edges.append({"from": f"bel{j - 1}", "to": f"bel{j}", "flow": "refine"})

    # --- Trades (right column) ---
    tr_positions = _layout_rows(len(tr_slice), _COL["trade"])
    for k, (t, (x, y)) in enumerate(zip(tr_slice, tr_positions)):
        side = t.side.lower()
        kind = "trade-buy" if side == "buy" else "trade-sell"
        label = f"{t.side.upper()} {t.symbol} @ ${t.price:.2f}"
        nodes.append(
            {
                "id": f"tr{k}",
                "kind": kind,
                "column": "trade",
                "label": label,
                "short": f"{t.symbol} {side.upper()}",
                "x": x,
                "y": y,
                "crs": round(t.crs_at_trade, 2) if t.crs_at_trade else None,
                "meta": (t.belief_label or "momentum")[:24],
            }
        )
        linked = False
        if t.belief_graph_id:
            for j, b in enumerate(bel_slice):
                if b.graph_id == t.belief_graph_id:
                    edges.append({"from": f"bel{j}", "to": f"tr{k}", "flow": "drives"})
                    linked = True
                    break
        if not linked and bel_slice:
            edges.append({"from": f"bel{min(k, len(bel_slice) - 1)}", "to": f"tr{k}", "flow": "drives"})

    # --- Bootstrap timeline if empty ---
    if not steps:
        steps = _bootstrap_steps(episodes, beliefs, trades)

    return TraceOut(nodes=nodes, edges=edges, steps=steps)


def _bootstrap_steps(
    episodes: list[dict],
    beliefs: list[BeliefOut],
    trades: list[TradeOut],
) -> list[dict]:
    ep_slice = [{"t": ep.get("time", ""), "text": ep.get("text", "")} for ep in episodes[:6]]
    crs_vals = [b.crs for b in beliefs] or [0.42]
    active_obs = [f"ep{i}" for i in range(min(3, len(episodes)))]
    active_bel = [f"bel{i}" for i in range(min(2, len(beliefs)))]
    active_tr = [f"tr{i}" for i in range(min(1, len(trades)))]

    steps: list[dict] = [
        {
            "title": "Market ingest",
            "phase": "market",
            "crs": round(crs_vals[0] * 0.7, 2),
            "summary": f"{len(episodes)} observation(s) from live quotes",
            "episodes": ep_slice[:2],
            "activeNodes": active_obs[:1],
            "activeEdges": [],
            "inspector": None,
        },
        {
            "title": "Belief formation",
            "phase": "belief",
            "crs": round(max(crs_vals), 2),
            "summary": f"{len(beliefs)} belief(s) in memory graph",
            "episodes": ep_slice,
            "activeNodes": active_obs + active_bel,
            "activeEdges": [["ep0", active_bel[0]]] if active_obs and active_bel else [],
            "inspector": _belief_inspector(beliefs[0]) if beliefs else None,
        },
    ]
    if trades:
        t0 = trades[0]
        steps.append(
            {
                "title": "Paper execution",
                "phase": "trade",
                "crs": round(t0.crs_at_trade or crs_vals[0], 2),
                "summary": f"{t0.side.upper()} {t0.symbol} · ${t0.notional:,.0f}",
                "episodes": [
                    {
                        "t": t0.created_at.strftime("%H:%M"),
                        "text": f"<strong>{t0.side.upper()} {t0.symbol}</strong> @ ${t0.price:.2f}",
                    },
                    {"t": "", "text": (t0.reasoning or "")[:180]},
                ],
                "activeNodes": active_obs + active_bel + active_tr,
                "activeEdges": [[active_bel[0], active_tr[0]]] if active_bel and active_tr else [],
                "inspector": _trade_inspector(t0),
            }
        )
    return steps


def _belief_inspector(b: BeliefOut) -> dict:
    return {
        "id": b.graph_id,
        "type": "Belief",
        "title": b.label[:80],
        "desc": "CRS-scored belief linked to market evidence in the cognitive graph.",
        "stats": {
            "CRS": f"{b.crs:.2f}",
            "status": b.status,
            "evidence": str(b.supporting_evidence),
            "predictions": f"{b.prediction_successes}/{b.prediction_successes + b.prediction_failures}",
        },
    }


def _trade_inspector(t: TradeOut) -> dict:
    return {
        "id": str(t.id),
        "type": "Trade",
        "title": f"{t.side.upper()} {t.symbol}",
        "desc": (t.reasoning or "Paper fill on demo account.")[:300],
        "stats": {
            "price": f"${t.price:.2f}",
            "notional": f"${t.notional:,.0f}",
            "fee": f"${getattr(t, 'fee', 0) or 0:.2f}",
            "leverage": f"{getattr(t, 'leverage', 1) or 1:.0f}x",
            "belief": (t.belief_label or "—")[:40],
        },
    }


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
    phase: str = "cycle",
    summary: str = "",
    max_steps: int = 24,
) -> list[dict]:
    prev_eps = steps[-1]["episodes"] if steps else []
    new_eps = list(prev_eps[-5:]) + [{"t": time_str, "text": episode_text}]
    step = {
        "title": title,
        "phase": phase,
        "crs": round(crs, 2),
        "summary": summary or episode_text[:100],
        "episodes": new_eps,
        "activeNodes": active_nodes,
        "activeEdges": active_edges or [],
        "inspector": inspector,
    }
    return (steps + [step])[-max_steps:]
