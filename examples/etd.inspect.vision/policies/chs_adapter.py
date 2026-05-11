from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class RobotState:
    body_pose: Dict[str, Any]
    arm_state: Dict[str, Any]
    wrist_state: Dict[str, Any]
    object_pose: Dict[str, Any]
    target_pose: Dict[str, Any]
    safety_state: Dict[str, Any]

@dataclass
class SkillCommand:
    body_mode: str
    arm_mode: str
    wrist_mode: str
    primitive: str
    target_pose: Dict[str, Any]
    speed_profile: str
    force_profile: str
    timeout_sec: int

def run(job_context: Dict[str, Any], robot_state: RobotState) -> SkillCommand:
    fragility = job_context.get('fragility', 'low')
    gentle = fragility == 'high'
    return SkillCommand(
        body_mode='micro_stable' if gentle else 'stable_reach',
        arm_mode='slow_arc' if gentle else 'guarded_arc',
        wrist_mode='minimal_force' if gentle else 'adaptive_contact',
        primitive=job_context.get('primitive', 'approach_arc'),
        target_pose=job_context.get('target_pose', {'x': 0.62, 'y': -0.14, 'z': 1.08, 'qx': 0, 'qy': 0, 'qz': 0, 'qw': 1}),
        speed_profile='gentle' if gentle else 'industrial_safe',
        force_profile='bounded_contact',
        timeout_sec=int(job_context.get('timeout_sec', 18)),
    )
