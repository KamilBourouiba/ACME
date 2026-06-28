from dataclasses import dataclass
from pathlib import Path

_SITE_DIR = Path(__file__).resolve().parent / "site"
SERVER_PY = (_SITE_DIR / "server.py").read_text(encoding="utf-8")


@dataclass(frozen=True)
class DemoAgent:
    id: str
    name: str
    role: str
    tenant_id: str
    color: str
    initials: str
    system_prompt: str
    channels: tuple[str, ...]


DEMO_AGENTS: tuple[DemoAgent, ...] = (
    DemoAgent(
        id="alex",
        name="Alex",
        role="Product Manager",
        tenant_id="demo-nexus-alex",
        color="#611f69",
        initials="A",
        system_prompt="You are Alex, PM for Nexus Advisory's new site. Concise, milestone-focused.",
        channels=("general", "product"),
    ),
    DemoAgent(
        id="priya",
        name="Priya",
        role="UX Designer",
        tenant_id="demo-nexus-priya",
        color="#e01e5a",
        initials="P",
        system_prompt="You are Priya, UX lead. Talk layout, accessibility, and brand tone briefly.",
        channels=("design", "product", "general"),
    ),
    DemoAgent(
        id="marco",
        name="Marco",
        role="Frontend Engineer",
        tenant_id="demo-nexus-marco",
        color="#1264a3",
        initials="M",
        system_prompt="You are Marco, frontend dev. Reference components and CSS in short messages.",
        channels=("engineering", "general"),
    ),
    DemoAgent(
        id="chen",
        name="Chen",
        role="Backend Engineer",
        tenant_id="demo-nexus-chen",
        color="#0b4f6c",
        initials="C",
        system_prompt="You are Chen, backend dev. Mention APIs, forms, and data models briefly.",
        channels=("engineering",),
    ),
    DemoAgent(
        id="nina",
        name="Nina",
        role="DevOps",
        tenant_id="demo-nexus-nina",
        color="#2eb67d",
        initials="N",
        system_prompt="You are Nina, DevOps. Focus on deploy pipelines and GitHub Pages.",
        channels=("deploy", "engineering"),
    ),
    DemoAgent(
        id="jordan",
        name="Jordan",
        role="QA Engineer",
        tenant_id="demo-nexus-jordan",
        color="#ecb22e",
        initials="J",
        system_prompt="You are Jordan, QA. Flag regressions and acceptance criteria tersely.",
        channels=("engineering", "product"),
    ),
    DemoAgent(
        id="sam",
        name="Sam",
        role="Tech Lead",
        tenant_id="demo-nexus-sam",
        color="#1d1c1d",
        initials="S",
        system_prompt="You are Sam, tech lead. Unblock the team and decide trade-offs in 1-2 sentences.",
        channels=("engineering", "general", "deploy"),
    ),
    DemoAgent(
        id="riley",
        name="Riley",
        role="Content Strategist",
        tenant_id="demo-nexus-riley",
        color="#694873",
        initials="R",
        system_prompt="You are Riley, content. Ship headlines and case-study copy briefly.",
        channels=("design", "product"),
    ),
    DemoAgent(
        id="morgan",
        name="Morgan",
        role="Client Success",
        tenant_id="demo-nexus-morgan",
        color="#36c5f0",
        initials="Mo",
        system_prompt="You are Morgan, client success. Relay stakeholder feedback from Nexus Advisory.",
        channels=("product", "general"),
    ),
    DemoAgent(
        id="kai",
        name="Kai",
        role="Engineering Manager",
        tenant_id="demo-nexus-kai",
        color="#4a154b",
        initials="K",
        system_prompt="You are Kai, EM. Track velocity and cross-team dependencies briefly.",
        channels=("general", "engineering", "deploy"),
    ),
)

AGENT_BY_ID = {a.id: a for a in DEMO_AGENTS}

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexus Advisory — Strategy &amp; Digital Transformation</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="hero">
    <nav><strong>Nexus Advisory</strong><a href="#services">Services</a><a href="#contact">Contact</a></nav>
    <h1>Clarity for complex transformations</h1>
    <p>Boutique consulting for SaaS, ops, and go-to-market.</p>
    <button id="cta">Book a discovery call</button>
  </header>
  <section id="services" class="grid"></section>
  <script src="app.js"></script>
</body>
</html>"""

STYLES_CSS = """:root { --brand: #611f69; --accent: #1264a3; }
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; color: #1d1c1d; }
.hero { padding: 4rem 1.5rem; background: linear-gradient(135deg, var(--brand), var(--accent)); color: #fff; }
.hero nav { display: flex; gap: 1.5rem; margin-bottom: 2rem; }
.hero a { color: #fff; text-decoration: none; }
#cta { background: #fff; color: var(--brand); border: 0; padding: 0.75rem 1.25rem; border-radius: 6px; cursor: pointer; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; padding: 2rem; }
.card { border: 1px solid #e8e8e8; border-radius: 8px; padding: 1rem; }"""

APP_JS = """const services = [
  { title: 'Strategy', desc: 'Market entry & portfolio bets' },
  { title: 'Ops', desc: 'Process design & automation' },
  { title: 'Data', desc: 'Analytics roadmaps & governance' },
];
const grid = document.querySelector('#services');
grid.innerHTML = services.map(s => `<article class="card"><h3>${s.title}</h3><p>${s.desc}</p></article>`).join('');
document.getElementById('cta')?.addEventListener('click', async () => {
  const email = prompt('Work email for discovery call');
  if (!email) return;
  const company = prompt('Company name') || 'Unknown';
  try {
    const res = await fetch('/api/lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, company, message: 'Discovery call from homepage CTA' }),
    });
    if (!res.ok) throw new Error('API error');
    alert('Thanks — we will reach out within 1 business day.');
  } catch {
    alert('Thanks — we will reach out within 1 business day.');
  }
});"""

SITE_ARTIFACTS: dict[str, str] = {
    "index.html": INDEX_HTML,
    "styles.css": STYLES_CSS,
    "app.js": APP_JS,
}
