"""ETD Skill Execution Visualizer.

Two output modes:
  1. ASCII timeline — always available, no dependencies beyond stdlib
  2. Matplotlib chart — available when matplotlib is installed

Usage:
    python sim/visualizer.py                     # ASCII for all 8 skill packages
    python sim/visualizer.py --skill etd.pickplace.basic
    python sim/visualizer.py --plot              # matplotlib chart
    python sim/visualizer.py --plot --save out.png
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, load_runtime_context


# ── Execution tracing ─────────────────────────────────────────────────────────

@dataclass
class PrimitiveTrace:
    name: str
    start: float
    end: float = 0.0
    status: str = 'ok'
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


@dataclass
class SkillTrace:
    skill_id: str
    profile: str
    start: float
    end: float = 0.0
    status: str = 'running'
    primitives: List[PrimitiveTrace] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> float:
        return max(self.end - self.start, 0.0)


class TracingMiddleware:
    """Middleware that records all events and publishes nothing to hardware."""

    def __init__(self, trace: SkillTrace):
        self._trace = trace
        self._current_primitive: Optional[PrimitiveTrace] = None
        self._safety: Dict[str, Any] = {
            'human_in_forbidden_zone': False,
            'human_ready_signal': True,
            'human_in_safety_radius': False,
            'human_distance_m': 2.0,
            'normal_force_n': 12.0,
            'confidence': 0.96,
            'aligned': True,
        }
        self._camera_frame_count = 0

    def publish(self, topic: str, msg: Any) -> None:
        ts = time.time()
        if topic == 'telemetry.events':
            event = msg.get('event', '')
            self._trace.events.append({'event': event, 'ts': ts, **{k: v for k, v in msg.items() if k != 'event'}})
            if event == 'primitive.entered':
                prim = PrimitiveTrace(name=msg.get('primitive', '?'), start=ts)
                self._trace.primitives.append(prim)
                self._current_primitive = prim
            elif event == 'primitive.exited' and self._current_primitive:
                self._current_primitive.end = ts
                self._current_primitive.status = 'ok'
                self._current_primitive = None
            elif event in ('skill.aborted', 'skill.failed') and self._current_primitive:
                self._current_primitive.end = ts
                self._current_primitive.status = event.split('.')[1]

    def read(self, topic: str) -> Any:
        if topic == 'state.safety_state':
            return dict(self._safety)
        if topic == 'force_control.contact_feedback':
            return {'normal_force_n': self._safety['normal_force_n']}
        if topic == 'perception.part_alignment':
            return {'confidence': self._safety['confidence'], 'offset_mm': 0.15, 'aligned': True}
        if topic == 'perception.camera_frame':
            self._camera_frame_count += 1
            return {'frame_id': self._camera_frame_count, 'width': 1920, 'height': 1080}
        # Atlas / humanoid topics
        if topic == 'perception.scene_map':
            return {'map_ready': True, 'obstacles': []}
        if topic == 'state.balance_state':
            return {'stable': True, 'com_margin': 0.12, 'gait': 'stand'}
        if topic == 'perception.object_pose':
            return {'confidence': 0.96, 'x': 3.0, 'y': 1.5, 'z': 0.8,
                    'object_class': 'automotive_part', 'mass_estimate_kg': 4.5}
        # Hyundai WIA welding topics
        if topic == 'perception.seam_tracker':
            return {'confidence': 0.96, 'offset_mm': 0.3, 'seam_found': True}
        if topic == 'vision.weld_inspection':
            return {'pass': True, 'defects': [], 'confidence': 0.97}
        # MobED transport topics
        if topic == 'perception.obstacle_detector':
            return {'obstacles': [], 'clear': True}
        if topic == 'navigation.path_planner':
            return {'path_ready': True, 'estimated_time_s': 30}
        if topic == 'manipulation.lift_control':
            return {'lift_ready': True, 'current_height_mm': 0}
        # Exoskeleton topics
        if topic == 'state.exo_joint_state':
            return {'calibrated': True, 'torque_within_limits': True}
        if topic == 'perception.intent_detector':
            return {'confidence': self._safety.get('confidence', 0.96),
                    'mode': 'overhead', 'direction': 'up'}
        if topic == 'state.fatigue_monitor':
            return {'fatigue_pct': self._safety.get('fatigue_pct', 20), 'session_sec': 0}
        if topic == 'perception.imu_pose':
            return {'valid': True, 'roll_deg': 0.2, 'pitch_deg': 0.1, 'yaw_deg': 0.0}
        return None


def _load_adapter_run(skill_id: str):
    pkg_path = ROOT / 'examples' / skill_id
    skill_json = json.loads((pkg_path / 'skill.json').read_text())
    entrypoint = skill_json.get('entrypoint', 'policies/chs_adapter.py:run')
    module_rel, func_name = entrypoint.split(':')
    mod_name = f'etd_viz_{skill_id.replace(".", "_")}'
    spec = importlib.util.spec_from_file_location(mod_name, pkg_path / module_rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return getattr(module, func_name)


def run_traced(skill_id: str, profile: str) -> SkillTrace:
    """Run a skill with a tracing middleware and return the execution trace."""
    import random
    random.seed(42)  # deterministic classification confidence in visualizer
    trace = SkillTrace(skill_id=skill_id, profile=profile, start=time.time())
    mw = TracingMiddleware(trace)
    run_fn = _load_adapter_run(skill_id)
    result = run_fn({'chsProfile': profile, 'priority': 'normal'}, middleware=mw)
    trace.end = time.time()
    trace.status = result.get('status', 'unknown')
    trace.result = result
    if mw._current_primitive:
        mw._current_primitive.end = trace.end
    return trace


# ── ASCII visualization ────────────────────────────────────────────────────────

_STATUS_ICON = {'ok': '✓', 'aborted': '✗', 'failed': '✗', 'running': '…'}
_BAR_WIDTH = 40


def _bar(fraction: float, width: int = _BAR_WIDTH, char: str = '█', empty: str = '░') -> str:
    filled = max(0, min(width, round(fraction * width)))
    return char * filled + empty * (width - filled)


def ascii_timeline(traces: List[SkillTrace]) -> str:
    lines: List[str] = []
    lines.append('\n' + '═' * 70)
    lines.append('  ETD Skill Execution Timeline')
    lines.append('═' * 70)

    for trace in traces:
        total = trace.total_duration or 1.0
        status_sym = '✓' if trace.status == 'completed' else '✗'
        lines.append(f'\n  {status_sym} {trace.skill_id}  [profile: {trace.profile}]  {total*1000:.0f} ms total')
        lines.append(f'  {"─"*65}')

        for prim in trace.primitives:
            dur = prim.duration
            frac = dur / total if total > 0 else 0
            bar = _bar(frac, width=30)
            icon = _STATUS_ICON.get(prim.status, '?')
            lines.append(f'  {icon} {prim.name:<28} {bar}  {dur*1000:>6.1f} ms')

        lines.append(f'  Events: {" → ".join(e["event"].split(".")[-1] for e in trace.events[:8])}')
        if trace.result:
            summary_keys = [k for k in ('pass_qc', 'payload_kg', 'confidence', 'handover_accepted') if k in trace.result]
            if summary_keys:
                parts = ', '.join(f'{k}={trace.result[k]}' for k in summary_keys)
                lines.append(f'  Result: {parts}')

    lines.append('\n' + '═' * 70)
    return '\n'.join(lines)


# ── Matplotlib visualization ──────────────────────────────────────────────────

def _plot_gantt(traces: List[SkillTrace], save_path: Optional[str] = None) -> None:
    try:
        import matplotlib
        matplotlib.use('Agg' if save_path else 'TkAgg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print('matplotlib not installed. Run: pip install matplotlib')
        return

    colors = {
        'ok':      '#4CAF50',
        'aborted': '#F44336',
        'failed':  '#FF9800',
        'running': '#2196F3',
    }

    n_skills = len(traces)
    fig, axes = plt.subplots(n_skills, 1, figsize=(12, 3 * n_skills), squeeze=False)
    fig.suptitle('ETD Skill Execution — Primitive Gantt Chart', fontsize=13, fontweight='bold')

    for ax, trace in zip(axes[:, 0], traces):
        t0 = trace.start
        for i, prim in enumerate(trace.primitives):
            start_ms = (prim.start - t0) * 1000
            dur_ms   = max(prim.duration * 1000, 2.0)
            color = colors.get(prim.status, '#9E9E9E')
            ax.barh(i, dur_ms, left=start_ms, height=0.6, color=color, edgecolor='white', linewidth=0.5)
            ax.text(start_ms + dur_ms / 2, i, f'{dur_ms:.0f}ms',
                    ha='center', va='center', fontsize=7, color='white', fontweight='bold')

        ax.set_yticks(range(len(trace.primitives)))
        ax.set_yticklabels([p.name for p in trace.primitives], fontsize=9)
        ax.set_xlabel('Time (ms)', fontsize=9)
        status_sym = '✓' if trace.status == 'completed' else '✗'
        ax.set_title(f'{status_sym} {trace.skill_id}  [{trace.profile}]  {trace.total_duration*1000:.0f} ms', fontsize=10)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)

    legend_patches = [mpatches.Patch(color=c, label=s) for s, c in colors.items()]
    fig.legend(handles=legend_patches, loc='lower right', fontsize=9)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f'Chart saved: {save_path}')
    else:
        plt.show()


# ── Entry point ───────────────────────────────────────────────────────────────

_SKILL_PROFILES = [
    ('etd.pickplace.basic',              'fragile_item'),
    ('etd.assembly.precision',           'peg_in_hole'),
    ('etd.inspect.vision',               'defect_scan'),
    ('etd.cobot.safeassist',             'safe_handover'),
    ('etd.hyundai.wia_welding',          'standard_seam'),
    ('etd.hyundai.mobed_transport',      'standard_carry'),
    ('etd.atlas.humanoid_walkfetch',     'sequencing_carry'),
    ('etd.hyundai.vest_exoskeleton',     'overhead_assembly'),
]


def main() -> None:
    ap = argparse.ArgumentParser(description='ETD Skill Execution Visualizer')
    ap.add_argument('--skill', default=None, help='Run only this skill ID')
    ap.add_argument('--profile', default=None, help='Use this CHS profile')
    ap.add_argument('--plot', action='store_true', help='Show matplotlib Gantt chart')
    ap.add_argument('--save', default=None, metavar='FILE', help='Save chart to PNG file')
    args = ap.parse_args()

    pairs = _SKILL_PROFILES
    if args.skill:
        profile = args.profile or next((p for s, p in _SKILL_PROFILES if s == args.skill), 'default')
        pairs = [(args.skill, profile)]

    print('Running skill traces...')
    traces: List[SkillTrace] = []
    for skill_id, profile in pairs:
        print(f'  {skill_id} [{profile}] ', end='', flush=True)
        try:
            trace = run_traced(skill_id, profile)
            traces.append(trace)
            print(f'→ {trace.status}  {trace.total_duration*1000:.0f} ms')
        except Exception as exc:
            print(f'ERROR: {exc}')

    print(ascii_timeline(traces))

    if args.plot or args.save:
        _plot_gantt(traces, save_path=args.save)


if __name__ == '__main__':
    main()
