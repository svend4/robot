def to_enterprise_event(event_name: str, skill_id: str, robot_id: str = 'robot-01', data: dict | None = None) -> dict:
    return {'source':'etd-runtime','event':event_name,'skill_id':skill_id,'robot_id':robot_id,'data':data or {}}
