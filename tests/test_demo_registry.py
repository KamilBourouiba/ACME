from acme.demo.registry import SquadRegistry


def test_hire_agent():
    reg = SquadRegistry.default()
    before = len(reg.list_agents())
    agent = reg.hire_agent(
        name="Quinn",
        role="Platform Engineer",
        channels=["engineering", "ops"],
    )
    assert agent.id
    assert agent.tenant_id == f"demo-belief-{agent.id}"
    assert len(reg.list_agents()) == before + 1
    assert reg.get_agent(agent.id) is agent


def test_create_channel_then_hire():
    reg = SquadRegistry.default()
    ch = reg.create_channel(name="war-room", topic="Incidents", emoji="🎯")
    assert reg.get_channel(ch.id) is ch
    agent = reg.hire_agent(
        name="Taylor",
        role="Incident Commander",
        channels=[ch.id],
    )
    assert ch.id in agent.channels
