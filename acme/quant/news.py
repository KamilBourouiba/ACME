"""News headline ingestion for market symbols."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from functools import partial
from xml.etree import ElementTree

import httpx

logger = logging.getLogger("acme.quant.news")

_YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_rss(xml_text: str, symbol: str, limit: int = 5) -> list[dict]:
    items: list[dict] = []
    try:
        root = ElementTree.fromstring(xml_text)
        for item in root.findall(".//item")[:limit]:
            title = _strip_html(item.findtext("title") or "")
            link = item.findtext("link") or ""
            pub = item.findtext("pubDate") or ""
            desc = _strip_html(item.findtext("description") or "")[:500]
            if not title:
                continue
            items.append(
                {
                    "symbol": symbol.upper(),
                    "title": title,
                    "link": link,
                    "published": pub,
                    "summary": desc,
                    "source_id": link or f"yahoo-rss:{symbol}:{hash(title) & 0xFFFF}",
                    "timestamp": datetime.now(timezone.utc),
                }
            )
    except Exception as exc:
        logger.warning("RSS parse failed for %s: %s", symbol, exc)
    return items


async def _fetch_symbol_news(symbol: str, limit: int = 5) -> list[dict]:
    url = _YAHOO_RSS.format(symbol=symbol.upper())
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ACME-Quant/1.0"})
            if resp.status_code >= 400:
                return []
            return _parse_rss(resp.text, symbol, limit)
    except Exception as exc:
        logger.warning("News fetch failed for %s: %s", symbol, exc)
        return []


async def fetch_news(symbols: list[str], limit_per_symbol: int = 3) -> list[dict]:
    tasks = [_fetch_symbol_news(sym, limit_per_symbol) for sym in symbols[:8]]
    batches = await asyncio.gather(*tasks, return_exceptions=True)
    headlines: list[dict] = []
    for batch in batches:
        if isinstance(batch, list):
            headlines.extend(batch)
    return headlines


def format_news_experience(headline: dict) -> str:
    sym = headline.get("symbol", "")
    title = headline.get("title", "")
    summary = headline.get("summary", "")
    text = f"[{sym}] {title}"
    if summary and summary != title:
        text += f" — {summary[:300]}"
    return text
