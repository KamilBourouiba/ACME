"""Assemble staging preview HTML from demo artifacts."""

from __future__ import annotations


def _pick(artifacts: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in artifacts:
            return artifacts[key]
    return ""


def build_staging_preview(artifacts: dict[str, str]) -> str:
    """Inline CSS/JS so the preview iframe works without extra requests."""
    html = _pick(artifacts, "static/index.html", "index.html")
    if not html:
        return "<!DOCTYPE html><html><body><p>No index yet.</p></body></html>"

    css_files = [
        "static/css/tokens.css",
        "static/css/base.css",
        "static/css/hero.css",
        "static/css/features.css",
        "static/css/pricing.css",
        "static/css/dashboard-mock.css",
        "static/css/animations.css",
    ]
    css = "\n".join(_pick(artifacts, f) for f in css_files if _pick(artifacts, f))

    js_files = [
        "static/js/api.js",
        "static/js/hero.js",
        "static/js/features.js",
        "static/js/pricing.js",
        "static/js/app.js",
    ]
    js = "\n".join(_pick(artifacts, f) for f in js_files if _pick(artifacts, f))

    for link in css_files:
        tag = f'<link rel="stylesheet" href="{link.removeprefix("static/")}">'
        html = html.replace(tag, "")
    html = html.replace('<link rel="stylesheet" href="css/tokens.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/base.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/hero.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/features.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/pricing.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/dashboard-mock.css">', "")
    html = html.replace('<link rel="stylesheet" href="css/animations.css">', "")

    if css and "</head>" in html:
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)

    html = html.replace('<script type="module" src="js/app.js"></script>', "")
    if js:
        html = html.replace("</body>", f"<script type=\"module\">\n{js}\n</script>\n</body>", 1)

    return html
