"""Mock robot state generator — produces realistic robot state snapshots and transitions.

Used by acceptance tests, simulation demos, and visualizer to drive adapters
without real hardware.

Usage::

    from sim.mock_robot_state_generator import RobotStateGenerator

    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    state = gen.at('approach')         # state at a given primitive
    state = gen.step()                 # advance one primitive
    for state in gen.walk():           # iterate through full execution
        ...
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional


@dataclass
class RobotStateGenerator:
    """Generates deterministic (or optionally noisy) robot state for a named skill.

    States are keyed by primitive name; unknown primitives return the default idle state.
    Call ``at(primitive)`` for a snapshot or ``walk()`` to iterate through all primitives.
    """
    skill_id:   str
    robot_id:   str = 'robot-01'
    noise:      bool = False   # add small float noise to pose values when True
    _index:     int  = field(default=0, init=False, repr=False)

    # ── Canonical state tables ─────────────────────────────────────────────────

    _PICKPLACE: ClassVar[Dict[str, Any]] = {
        'approach':       {'arm': 'moving',  'grasp': False, 'at_zone': False, 'secured': False},
        'grasp':          {'arm': 'closing', 'grasp': True,  'at_zone': False, 'secured': False},
        'lift':           {'arm': 'lifting', 'grasp': True,  'at_zone': False, 'secured': True},
        'move_to_place':  {'arm': 'moving',  'grasp': True,  'at_zone': True,  'secured': True},
        'place':          {'arm': 'opening', 'grasp': False, 'at_zone': True,  'secured': False},
        'retreat':        {'arm': 'retracting','grasp': False,'at_zone': True,  'secured': False},
    }
    _WELD: ClassVar[Dict[str, Any]] = {
        'move_to_seam':   {'arm': 'moving',  'arc_on': False, 'seam_found': False, 'at_seam': False},
        'torch_align':    {'arm': 'aligning','arc_on': False, 'seam_found': True,  'at_seam': True},
        'arc_ignite':     {'arm': 'hold',    'arc_on': True,  'seam_found': True,  'at_seam': True},
        'weld_traverse':  {'arm': 'welding', 'arc_on': True,  'seam_found': True,  'at_seam': True},
        'arc_extinguish': {'arm': 'hold',    'arc_on': False, 'seam_found': True,  'at_seam': True},
        'inspect_seam':   {'arm': 'scanning','arc_on': False, 'seam_found': True,  'at_seam': True},
        'retreat':        {'arm': 'retracting','arc_on': False,'seam_found': False, 'at_seam': False},
    }
    _TRANSPORT: ClassVar[Dict[str, Any]] = {
        'navigate_to_pickup': {'driving': True,  'loaded': False, 'at_pickup': False, 'at_dropoff': False},
        'lift_payload':       {'driving': False, 'loaded': True,  'at_pickup': True,  'at_dropoff': False},
        'navigate_to_dropoff':{'driving': True,  'loaded': True,  'at_pickup': False, 'at_dropoff': False},
        'lower_payload':      {'driving': False, 'loaded': False, 'at_pickup': False, 'at_dropoff': True},
        'confirm_delivery':   {'driving': False, 'loaded': False, 'at_pickup': False, 'at_dropoff': True},
    }
    _HUMANOID: ClassVar[Dict[str, Any]] = {
        'nav_to_pick':    {'walking': True,  'at_pick': False, 'holding': False, 'at_place': False},
        'reach_and_grasp':{'walking': False, 'at_pick': True,  'holding': True,  'at_place': False},
        'nav_to_place':   {'walking': True,  'at_pick': False, 'holding': True,  'at_place': False},
        'place_object':   {'walking': False, 'at_pick': False, 'holding': False, 'at_place': True},
        'return_to_base': {'walking': True,  'at_pick': False, 'holding': False, 'at_place': False},
    }

    _FAMILY_TABLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'pickplace': _PICKPLACE,
        'weld':      _WELD,
        'transport': _TRANSPORT,
        'humanoid':  _HUMANOID,
    }

    def _table(self) -> Dict[str, Any]:
        for family, table in self._FAMILY_TABLES.items():
            if family in self.skill_id:
                return table
        return self._PICKPLACE

    def _noisy(self, v: float) -> float:
        return v + random.uniform(-0.01, 0.01) if self.noise else v

    def _pose(self, x: float, y: float, z: float) -> Dict[str, float]:
        return {'x': self._noisy(x), 'y': self._noisy(y), 'z': self._noisy(z)}

    def at(self, primitive: str) -> Dict[str, Any]:
        """Return a full robot state snapshot for *primitive*."""
        table = self._table()
        specific = table.get(primitive, {})
        safe = not specific.get('human_in_zone', False)
        return {
            'robot_id':     self.robot_id,
            'primitive':    primitive,
            'body_pose':    {**self._pose(0.4, 0.1, 0.0), 'at_target_zone': specific.get('at_zone', False)},
            'arm_state':    {'mode': specific.get('arm', 'idle'),
                             'pregrasp_ready': specific.get('arm', '') in ('moving', 'aligning')},
            'wrist_state':  {'object_secured': specific.get('secured', False),
                             'grasp_closed':   specific.get('grasp', False)},
            'object_pose':  self._pose(0.4, 0.1, 0.9),
            'target_pose':  self._pose(0.6, -0.1, 1.0),
            'safety_state': {
                'human_in_forbidden_zone': False,
                'human_ready_signal':      True,
                'emergency_stop':          False,
                'protective_pause':        False,
                'safe_to_proceed':         safe,
            },
            'balance_state': {'stable': True, 'lean_deg': self._noisy(0.3)},
            'skill_specific': specific,
        }

    def primitives(self) -> List[str]:
        """Return ordered primitive names for this skill family."""
        return list(self._table().keys())

    def step(self) -> Optional[Dict[str, Any]]:
        """Advance to the next primitive and return its state, or None if exhausted."""
        prims = self.primitives()
        if self._index >= len(prims):
            return None
        state = self.at(prims[self._index])
        self._index += 1
        return state

    def walk(self):
        """Yield state snapshots for each primitive in order."""
        self._index = 0
        while True:
            s = self.step()
            if s is None:
                break
            yield s

    def reset(self) -> None:
        self._index = 0


def mock_state(human_too_close: bool = False) -> dict:
    """Legacy one-liner helper — preserved for backward compatibility."""
    gen = RobotStateGenerator(skill_id='etd.pickplace.basic')
    state = gen.at('approach')
    state['safety_state']['human_in_forbidden_zone'] = human_too_close
    return state
