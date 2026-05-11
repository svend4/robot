from adapters.orbit_event_bridge import to_enterprise_event

def replay(events: list[str], skill_id: str) -> list[dict]:
    return [to_enterprise_event(e, skill_id) for e in events]
