def mock_state(human_too_close: bool = False) -> dict:
    return {'body_pose': {'at_target_zone': False, 'payload_stable': True}, 'arm_state': {'pregrasp_ready': False}, 'wrist_state': {'object_secured': False}, 'object_pose': {'x':0.4,'y':0.1,'z':0.9}, 'target_pose': {'x':0.6,'y':-0.1,'z':1.0}, 'safety_state': {'human_too_close': human_too_close}}
