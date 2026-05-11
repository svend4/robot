import json
from pathlib import Path

def load_station_profile(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))

def is_skill_allowed(profile: dict, family: str) -> bool:
    return family in profile.get('allowed_skill_families', [])
