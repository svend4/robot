"""Humanoid-first cross-platform compatibility layer.

ETD acts as the neutral application-layer adapter between enterprise workflow
systems and OEM robot middleware.  This module extends that role to *cross-
platform portability*: given a skill written for one robot (e.g. Boston
Dynamics Atlas) determine whether it can run on another (e.g. Unitree G1) and
what topic/namespace remappings are required.

Key concepts
------------
``HumanoidPlatform``
    Describes one robot platform: which ETD primitive names it implements,
    which skill families it supports, its ROS 2 topic namespace, and a set of
    capability flags (e.g. ``bipedal_locomotion``, ``force_control``).

``PlatformCompatResult``
    The result of a single source→target compatibility check for one skill.
    Includes: overall ``compatible`` flag, list of ``missing_primitives``,
    ``topic_remappings`` dict, ``warnings``, and ``adaptation_notes``.

``HumanoidRegistry``
    Central registry of known platforms.  Ships with six built-in platforms
    (Atlas, Unitree G1, Unitree H1, Hyundai H-MEX, Hyundai MobED, Hyundai WIA)
    and supports runtime registration of custom platforms.

    Key methods:
    - ``check_compat(skill_info, source_id, target_id)`` — compatibility check
    - ``compat_matrix(families)`` — full NxN matrix across all platforms
    - ``register(platform)`` / ``unregister(platform_id)``

Skill info dict
---------------
The ``skill_info`` argument accepted by ``check_compat`` is a plain dict::

    {
        "skillId":        "etd.atlas.humanoid_walkfetch",
        "family":         "humanoid",
        "primitiveOrder": ["walk_to_target", "grasp_object", ...],
    }

Alternatively pass a ``pathlib.Path`` pointing to a skill package directory
and ``load_skill_info`` will read ``skill.json`` automatically.

Usage::

    from marketplace.cross_platform import HumanoidRegistry, load_skill_info
    from pathlib import Path

    reg    = HumanoidRegistry()
    skill  = load_skill_info(Path('examples/etd.atlas.humanoid_walkfetch'))
    result = reg.check_compat(skill, source='atlas', target='unitree_g1')
    print(result.summary())

    matrix = reg.compat_matrix()
    for row in matrix:
        print(row)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set


# ── Platform descriptor ───────────────────────────────────────────────────────

@dataclass
class HumanoidPlatform:
    """Descriptor for one robot platform registered in the ETD marketplace."""
    platform_id: str
    name: str
    robot_class: str                    # 'humanoid' | 'amr' | 'cobot' | 'exoskeleton' | ...
    families: FrozenSet[str]            # skill families this platform supports
    topic_namespace: str                # ROS 2 topic prefix, e.g. '/atlas'
    supported_primitives: FrozenSet[str]
    capability_flags: FrozenSet[str]    # e.g. {'bipedal_locomotion', 'vision'}

    def supports_family(self, family: str) -> bool:
        return family in self.families

    def supports_primitive(self, primitive: str) -> bool:
        return primitive in self.supported_primitives

    def to_dict(self) -> Dict[str, Any]:
        return {
            'platform_id': self.platform_id,
            'name': self.name,
            'robot_class': self.robot_class,
            'families': sorted(self.families),
            'topic_namespace': self.topic_namespace,
            'supported_primitives': sorted(self.supported_primitives),
            'capability_flags': sorted(self.capability_flags),
        }


# ── Compat result ─────────────────────────────────────────────────────────────

@dataclass
class PlatformCompatResult:
    """Result of a cross-platform compatibility check for one skill."""
    skill_id: str
    source_platform: str
    target_platform: str
    compatible: bool
    missing_primitives: List[str] = field(default_factory=list)
    topic_remappings: Dict[str, str] = field(default_factory=dict)
    missing_capability_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    adaptation_notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = 'COMPATIBLE' if self.compatible else 'INCOMPATIBLE'
        lines = [
            f'{status}  {self.skill_id}  {self.source_platform} → {self.target_platform}',
        ]
        if self.missing_primitives:
            lines.append(f'  Missing primitives  : {", ".join(self.missing_primitives)}')
        if self.missing_capability_flags:
            lines.append(f'  Missing capabilities: {", ".join(self.missing_capability_flags)}')
        if self.topic_remappings:
            for src, dst in self.topic_remappings.items():
                lines.append(f'  Remap  {src} → {dst}')
        for w in self.warnings:
            lines.append(f'  ⚠  {w}')
        for n in self.adaptation_notes:
            lines.append(f'  ℹ  {n}')
        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id,
            'source_platform': self.source_platform,
            'target_platform': self.target_platform,
            'compatible': self.compatible,
            'missing_primitives': self.missing_primitives,
            'topic_remappings': self.topic_remappings,
            'missing_capability_flags': self.missing_capability_flags,
            'warnings': self.warnings,
            'adaptation_notes': self.adaptation_notes,
        }


# ── Built-in platform definitions ─────────────────────────────────────────────

def _platform(platform_id, name, robot_class, families, topic_namespace,
               supported_primitives, capability_flags) -> HumanoidPlatform:
    return HumanoidPlatform(
        platform_id=platform_id,
        name=name,
        robot_class=robot_class,
        families=frozenset(families),
        topic_namespace=topic_namespace,
        supported_primitives=frozenset(supported_primitives),
        capability_flags=frozenset(capability_flags),
    )


BUILTIN_PLATFORMS: List[HumanoidPlatform] = [
    _platform(
        platform_id='atlas',
        name='Boston Dynamics Atlas',
        robot_class='humanoid',
        families=['humanoid', 'manipulator', 'pickplace', 'inspect'],
        topic_namespace='/atlas',
        supported_primitives=[
            # humanoid_walkfetch
            'localize_target', 'plan_walk_path', 'walk_to_target', 'stabilize_stance',
            'approach_object', 'grasp_object', 'secure_carry_posture',
            'walk_to_destination', 'deposit_or_handover',
            # inspect.vision
            'approach_viewpoint', 'scan_target', 'capture_evidence', 'classify_result',
            'report_quality',
            # pickplace.basic
            'approach_arc', 'guarded_grasp', 'lift_stabilize', 'transport_safe',
            'place_release',
        ],
        capability_flags=[
            'bipedal_locomotion', 'dexterous_manipulation', 'vision',
            'force_control', 'human_aware_mode',
        ],
    ),
    _platform(
        platform_id='unitree_g1',
        name='Unitree G1',
        robot_class='humanoid',
        families=['humanoid', 'manipulator', 'pickplace', 'inspect'],
        topic_namespace='/unitree/g1',
        supported_primitives=[
            # humanoid_walkfetch
            'localize_target', 'plan_walk_path', 'walk_to_target', 'stabilize_stance',
            'approach_object', 'grasp_object', 'secure_carry_posture',
            'walk_to_destination', 'deposit_or_handover',
            # pickplace.basic
            'approach_arc', 'guarded_grasp', 'lift_stabilize', 'transport_safe',
            'place_release',
            # inspect.vision (partial — G1 has a head camera)
            'approach_viewpoint', 'scan_target', 'capture_evidence', 'classify_result',
            'report_quality',
        ],
        capability_flags=[
            'bipedal_locomotion', 'dexterous_manipulation', 'vision',
            'force_control',
        ],
    ),
    _platform(
        platform_id='unitree_h1',
        name='Unitree H1',
        robot_class='humanoid',
        families=['humanoid', 'inspect'],
        topic_namespace='/unitree/h1',
        supported_primitives=[
            # locomotion only — H1 has no dexterous hands in baseline config
            'localize_target', 'plan_walk_path', 'walk_to_target', 'stabilize_stance',
            'walk_to_destination',
            # basic vision
            'approach_viewpoint', 'scan_target',
        ],
        capability_flags=[
            'bipedal_locomotion', 'vision',
        ],
    ),
    _platform(
        platform_id='hyundai_mex',
        name='Hyundai H-MEX / VEX Exoskeleton',
        robot_class='exoskeleton',
        families=['assist', 'cobot'],
        topic_namespace='/hmex',
        supported_primitives=[
            # vest_exoskeleton
            'calibrate_fit', 'detect_intent', 'engage_assist', 'monitor_fatigue',
            'adapt_gain', 'disengage_assist',
            # cobot.safeassist
            'detect_human_ready', 'approach_handover_zone', 'hold_for_transfer',
            'release_on_confirmation', 'retreat_safe',
        ],
        capability_flags=[
            'wearable', 'force_assist', 'human_intent_sensing', 'fatigue_sensing',
            'human_aware_mode',
        ],
    ),
    _platform(
        platform_id='hyundai_mobed',
        name='Hyundai MobED AMR',
        robot_class='amr',
        families=['transport'],
        topic_namespace='/hrise',
        supported_primitives=[
            'navigate_to_pickup', 'dock_and_lift', 'navigate_to_destination',
            'dock_and_lower', 'confirm_delivery',
        ],
        capability_flags=[
            'wheeled_locomotion', 'load_bearing', 'nav_stack', 'human_aware_mode',
        ],
    ),
    _platform(
        platform_id='hyundai_wia',
        name='Hyundai WIA H-Motion Cobot',
        robot_class='cobot',
        families=['weld', 'cobot', 'assembly'],
        topic_namespace='/hwia',
        supported_primitives=[
            # wia_welding
            'approach_seam_start', 'torch_align', 'ignite_arc', 'weld_traverse',
            'extinguish_arc', 'post_weld_inspect', 'retract_clear',
            # assembly.precision
            'approach_align', 'contact_probe', 'micro_adjust', 'controlled_insert',
            'settle_and_verify', 'release_safe',
            # cobot.safeassist
            'detect_human_ready', 'approach_handover_zone', 'hold_for_transfer',
            'release_on_confirmation', 'retreat_safe',
        ],
        capability_flags=[
            'force_control', 'arc_welding', 'vision', 'cobot_safety', 'human_aware_mode',
        ],
    ),
]

_BUILTIN_BY_ID: Dict[str, HumanoidPlatform] = {p.platform_id: p for p in BUILTIN_PLATFORMS}


# ── Skill info loader ─────────────────────────────────────────────────────────

def load_skill_info(package_path: Path) -> Dict[str, Any]:
    """Load skill metadata from ``skill.json`` in *package_path*."""
    p = package_path if isinstance(package_path, Path) else Path(package_path)
    skill_json = p / 'skill.json'
    if not skill_json.exists():
        raise FileNotFoundError(f'skill.json not found in {p}')
    return json.loads(skill_json.read_text(encoding='utf-8'))


# ── Registry ──────────────────────────────────────────────────────────────────

class HumanoidRegistry:
    """Registry of known robot platforms for cross-platform compat checks.

    Ships with six built-in platforms.  Custom platforms can be registered at
    runtime.
    """

    def __init__(self) -> None:
        self._platforms: Dict[str, HumanoidPlatform] = dict(_BUILTIN_BY_ID)

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, platform: HumanoidPlatform) -> None:
        """Register (or replace) a platform."""
        self._platforms[platform.platform_id] = platform

    def unregister(self, platform_id: str) -> None:
        """Remove a platform.  Silently ignored if not registered."""
        self._platforms.pop(platform_id, None)

    def get(self, platform_id: str) -> Optional[HumanoidPlatform]:
        return self._platforms.get(platform_id)

    def list_platforms(self) -> List[HumanoidPlatform]:
        return list(self._platforms.values())

    @property
    def platform_count(self) -> int:
        return len(self._platforms)

    # ── Compat check ──────────────────────────────────────────────────────────

    def check_compat(
        self,
        skill_info: Dict[str, Any],
        source: str,
        target: str,
    ) -> PlatformCompatResult:
        """Check whether *skill_info* can run on *target* given it was designed for *source*.

        Parameters
        ----------
        skill_info:
            Dict with at least ``skillId``, ``family``, and ``primitiveOrder``.
            Obtain via :func:`load_skill_info` or build manually.
        source:
            Platform ID the skill was originally written for.
        target:
            Platform ID to check portability to.

        Returns
        -------
        PlatformCompatResult
            ``compatible=True`` if the target platform supports the skill's
            family and all its primitives.
        """
        skill_id = skill_info.get('skillId', '<unknown>')
        family = skill_info.get('family', '')
        primitives: List[str] = list(skill_info.get('primitiveOrder', []))

        src_platform = self._platforms.get(source)
        tgt_platform = self._platforms.get(target)

        warnings: List[str] = []
        adaptation_notes: List[str] = []
        topic_remappings: Dict[str, str] = {}

        if src_platform is None:
            warnings.append(f'source platform {source!r} is not registered')
        if tgt_platform is None:
            return PlatformCompatResult(
                skill_id=skill_id,
                source_platform=source,
                target_platform=target,
                compatible=False,
                warnings=[f'target platform {target!r} is not registered'],
            )

        # Trivially compatible if same platform
        if source == target:
            return PlatformCompatResult(
                skill_id=skill_id,
                source_platform=source,
                target_platform=target,
                compatible=True,
                adaptation_notes=['same platform — no adaptation required'],
            )

        # Family check
        if family and not tgt_platform.supports_family(family):
            return PlatformCompatResult(
                skill_id=skill_id,
                source_platform=source,
                target_platform=target,
                compatible=False,
                warnings=[
                    f'target platform {tgt_platform.name!r} does not support '
                    f'family {family!r} (supports: {sorted(tgt_platform.families)})'
                ],
            )

        # Primitive check
        missing = [p for p in primitives if not tgt_platform.supports_primitive(p)]

        # Capability flag diff
        src_flags = src_platform.capability_flags if src_platform else frozenset()
        missing_flags = sorted(src_flags - tgt_platform.capability_flags)

        # Topic remappings
        if src_platform and src_platform.topic_namespace != tgt_platform.topic_namespace:
            for prim in primitives:
                src_topic = f'{src_platform.topic_namespace}/{prim}'
                tgt_topic = f'{tgt_platform.topic_namespace}/{prim}'
                topic_remappings[src_topic] = tgt_topic
            adaptation_notes.append(
                f'Remap topic namespace '
                f'{src_platform.topic_namespace} → {tgt_platform.topic_namespace}'
            )

        if missing_flags:
            warnings.append(
                f'Target lacks capability flags present on source: '
                f'{", ".join(missing_flags)}'
            )

        compatible = len(missing) == 0

        if compatible and not missing_flags:
            adaptation_notes.append(
                f'Full primitive coverage on {tgt_platform.name}; '
                'topic remapping sufficient for portability'
            )
        elif compatible and missing_flags:
            adaptation_notes.append(
                'Primitives fully covered but some capability flags absent — '
                'runtime behaviour may differ'
            )

        return PlatformCompatResult(
            skill_id=skill_id,
            source_platform=source,
            target_platform=target,
            compatible=compatible,
            missing_primitives=missing,
            topic_remappings=topic_remappings,
            missing_capability_flags=missing_flags,
            warnings=warnings,
            adaptation_notes=adaptation_notes,
        )

    # ── Compat matrix ─────────────────────────────────────────────────────────

    def compat_matrix(
        self,
        skill_info: Optional[Dict[str, Any]] = None,
        families: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate a cross-platform compatibility matrix.

        Parameters
        ----------
        skill_info:
            If provided, evaluate this skill across all source→target pairs.
        families:
            Filter to platforms whose ``families`` intersect *families*.
            ``None`` means all platforms.

        Returns
        -------
        List of row dicts: ``{source, target, compatible, missing_count}``.
        """
        platforms = [
            p for p in self._platforms.values()
            if families is None or p.families & families
        ]
        rows: List[Dict[str, Any]] = []
        for src in platforms:
            for tgt in platforms:
                if src.platform_id == tgt.platform_id:
                    continue
                if skill_info is not None:
                    result = self.check_compat(skill_info, src.platform_id, tgt.platform_id)
                    rows.append({
                        'source': src.platform_id,
                        'source_name': src.name,
                        'target': tgt.platform_id,
                        'target_name': tgt.name,
                        'compatible': result.compatible,
                        'missing_count': len(result.missing_primitives),
                        'missing_primitives': result.missing_primitives,
                    })
                else:
                    # Family-overlap check only
                    overlap = bool(src.families & tgt.families)
                    rows.append({
                        'source': src.platform_id,
                        'source_name': src.name,
                        'target': tgt.platform_id,
                        'target_name': tgt.name,
                        'family_overlap': sorted(src.families & tgt.families),
                        'compatible': overlap,
                        'missing_count': 0,
                        'missing_primitives': [],
                    })
        return rows

    def render_matrix_ascii(
        self,
        skill_info: Optional[Dict[str, Any]] = None,
        families: Optional[Set[str]] = None,
    ) -> str:
        """Return a compact ASCII table of the compat matrix."""
        platforms = [
            p for p in self._platforms.values()
            if families is None or p.families & families
        ]
        ids = [p.platform_id for p in platforms]
        col_w = max(len(i) for i in ids) + 2
        header = ' ' * col_w + ''.join(f'{i:^{col_w}}' for i in ids)
        lines = [header, '─' * len(header)]
        for src in platforms:
            row = f'{src.platform_id:<{col_w}}'
            for tgt in platforms:
                if src.platform_id == tgt.platform_id:
                    cell = '·'
                elif skill_info is not None:
                    res = self.check_compat(skill_info, src.platform_id, tgt.platform_id)
                    cell = '✓' if res.compatible else '✗'
                else:
                    overlap = bool(src.families & tgt.families)
                    cell = '≈' if overlap else '—'
                row += f'{cell:^{col_w}}'
            lines.append(row)
        return '\n'.join(lines)
