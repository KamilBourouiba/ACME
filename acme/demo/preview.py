"""Assemble staging preview HTML from demo artifacts."""

from __future__ import annotations

import re


def _pick(artifacts: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in artifacts:
            return artifacts[key]
    return ""


def build_staging_preview(artifacts: dict[str, str]) -> str:
    """Inline canon shell + trace JS — same bundle as live deploy."""
    from acme.demo.static_assets import publish_artifact_bundle

    bundle = publish_artifact_bundle(artifacts)
    html = _pick(bundle, "static/index.html", "index.html")
    if not html:
        return "<!DOCTYPE html><html><body><p>No index yet.</p></body></html>"

    css = _pick(bundle, "static/css/observatory.css")
    for href in ("css/observatory.css", "static/css/observatory.css"):
        html = html.replace(f'<link rel="stylesheet" href="{href}">', "")

    js_files = ["static/js/api.js", "static/js/app.js"]
    js = "\n".join(f"// {p}\n{_pick(bundle, p)}" for p in js_files if _pick(bundle, p))

    if css and "</head>" in html:
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)

    html = re.sub(r'<script src="js/[^"]+"></script>\s*', "", html)
    if js:
        html = html.replace("</body>", f"<script>\n{js}\n</script>\n</body>", 1)

    return html
