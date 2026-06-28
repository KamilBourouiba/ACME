"""Assemble staging preview HTML from demo artifacts."""

from __future__ import annotations


def _pick(artifacts: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in artifacts:
            return artifacts[key]
    return ""


def build_staging_preview(artifacts: dict[str, str]) -> str:
    """Inline CSS/JS modules so the preview iframe works without extra requests."""
    html = _pick(artifacts, "static/index.html", "index.html")
    if not html:
        return "<!DOCTYPE html><html><body><p>No index yet.</p></body></html>"

    css_parts = [
        _pick(artifacts, "static/css/tokens.css", "css/tokens.css"),
        _pick(artifacts, "static/css/layout.css", "css/layout.css"),
        _pick(artifacts, "static/css/components.css", "css/components.css"),
        _pick(artifacts, "styles.css"),
    ]
    css = "\n".join(c for c in css_parts if c)

    js_parts = [
        _pick(artifacts, "static/js/api.js", "js/api.js"),
        _pick(artifacts, "static/js/components.js", "js/components.js"),
        _pick(artifacts, "static/js/app.js", "js/app.js"),
        _pick(artifacts, "app.js"),
    ]
    js = "\n".join(c for c in js_parts if c)

    for link in (
        '<link rel="stylesheet" href="css/tokens.css">',
        '<link rel="stylesheet" href="css/layout.css">',
        '<link rel="stylesheet" href="css/components.css">',
        '<link rel="stylesheet" href="styles.css">',
    ):
        if link in html:
            html = html.replace(link, "", 1)

    if css and "</head>" in html:
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    elif css:
        html = html.replace("<body>", f"<style>\n{css}\n</style>\n<body>", 1)

    for script in (
        '<script type="module" src="js/app.js"></script>',
        '<script src="app.js"></script>',
    ):
        if script in html:
            html = html.replace(script, "", 1)

    if js:
        inline = f"<script type=\"module\">\n{js}\n</script>"
        html = html.replace("</body>", f"{inline}\n</body>", 1)

    return html
