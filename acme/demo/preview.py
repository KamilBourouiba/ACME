"""Assemble staging preview HTML from demo artifacts."""

from acme.demo.agents import APP_JS, INDEX_HTML, STYLES_CSS


def build_staging_preview(artifacts: dict[str, str]) -> str:
    """Inline CSS/JS so the preview iframe works without extra requests."""
    html = artifacts.get("index.html") or INDEX_HTML
    css = artifacts.get("styles.css") or STYLES_CSS
    js = artifacts.get("app.js") or APP_JS

    if '<link rel="stylesheet" href="styles.css">' in html:
        html = html.replace(
            '<link rel="stylesheet" href="styles.css">',
            f"<style>\n{css}\n</style>",
        )
    if '<script src="app.js"></script>' in html:
        html = html.replace(
            '<script src="app.js"></script>',
            f"<script>\n{js}\n</script>",
        )
    return html
