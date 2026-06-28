"""Assemble staging preview HTML from demo artifacts."""

from __future__ import annotations

import re


def _pick(artifacts: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in artifacts:
            return artifacts[key]
    return ""


def _strip_esm(code: str) -> str:
    code = re.sub(r"^import\s+.*?;\s*\n", "", code, flags=re.MULTILINE)
    code = re.sub(r"^export\s+", "", code, flags=re.MULTILINE)
    return code


def _bundle_js(artifacts: dict[str, str]) -> str:
    three_import = (
        "import * as THREE from 'three';\n"
        "import { OrbitControls } from 'three/addons/controls/OrbitControls.js';\n"
    )
    files = [
        "static/js/api.js",
        "static/js/panels.js",
        "static/js/timeline.js",
        "static/js/scene.js",
        "static/js/app.js",
    ]
    chunks = [three_import]
    for path in files:
        body = _pick(artifacts, path)
        if body:
            chunks.append(f"// {path}\n{_strip_esm(body)}")
    return "\n".join(chunks)


def build_staging_preview(artifacts: dict[str, str]) -> str:
    """Inline CSS/JS; bundle ES modules so Three.js works in iframe via importmap."""
    html = _pick(artifacts, "static/index.html", "index.html")
    if not html:
        return "<!DOCTYPE html><html><body><p>No index yet.</p></body></html>"

    css_files = [
        "static/css/tokens.css",
        "static/css/base.css",
        "static/css/shell.css",
        "static/css/omnibar.css",
        "static/css/panels.css",
        "static/css/canvas.css",
        "static/css/inspector.css",
        "static/css/timeline.css",
    ]
    css = "\n".join(_pick(artifacts, f) for f in css_files if _pick(artifacts, f))

    for link in css_files:
        short = link.removeprefix("static/")
        html = html.replace(f'<link rel="stylesheet" href="{short}">', "")
        html = html.replace(f'<link rel="stylesheet" href="{link}">', "")

    html = html.replace('<script type="module" src="js/scene.js"></script>', "")
    html = html.replace('<script type="module" src="js/app.js"></script>', "")

    if css and "</head>" in html:
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)

    js = _bundle_js(artifacts)
    if js:
        html = html.replace("</body>", f'<script type="module">\n{js}\n</script>\n</body>', 1)

    return html
