def to_oem_request(skill_command: dict, station_id: str = 'unknown') -> dict:
    forbidden = {'servo_torque','collision_disable','emergency_stop_override'}
    if any(k in skill_command for k in forbidden):
        raise ValueError('unsafe low-level command rejected')
    return {'request_type':'skill_intent','station_id':station_id,'bounded':True,'payload':skill_command}
