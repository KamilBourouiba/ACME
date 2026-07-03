from acme.demo.lessons import SQUAD_LESSONS, SQUAD_LESSONS_PROMPT


def test_squad_lessons_cover_static_paths():
    keys = {k for k, _ in SQUAD_LESSONS}
    assert "static-asset-paths" in keys
    assert "pinned-boot-files" in keys
    assert "github-pages-publish" in keys
    assert "ui-audit-workflow" in keys
    assert "/static/" in SQUAD_LESSONS_PROMPT
    assert "css/" in SQUAD_LESSONS_PROMPT
    assert "trace-fallback.json" in SQUAD_LESSONS_PROMPT or "observatory" in SQUAD_LESSONS_PROMPT.lower()
    assert "index.html is PINNED" in SQUAD_LESSONS_PROMPT
