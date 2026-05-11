"""ETD Skill Action Server for ROS 2.

Bridges between the ROS 2 action interface and the ETD skill runtime.
Each ETD skill package runs as a ROS 2 action server — callers send a
SkillGoal, receive SkillFeedback during execution, and get a SkillResult
when done.

Architecture:
    ROS 2 Action Client (workflow node)
        └─► SkillActionServer (this node)
                └─► ETDReferenceValidator (validate before execute)
                └─► chs_adapter.run()    (skill execution)
                └─► ROS 2 middleware     (publish skill_intent to OEM stack)

NOTE: This file is a standalone stub. It does NOT import rclpy at module level
so it can be read and tested without a full ROS 2 installation.
The actual ROS 2 action message types (ExecuteSkill.action) must be generated
from the action definition in this package.

To use with a real ROS 2 installation:
    source /opt/ros/humble/setup.bash
    colcon build --packages-select etd_ros2_bridge
    ros2 run etd_ros2_bridge skill_action_server --skill etd.pickplace.basic
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[4]


class ETDSkillActionServer:
    """ROS 2 action server wrapper for an ETD skill package.

    In real usage, inherit from rclpy and use action_msgs types.
    Here the class is framework-agnostic so it can be tested without ROS.
    """

    def __init__(self, skill_id: str, node_name: Optional[str] = None):
        self.skill_id = skill_id
        self.node_name = node_name or f'etd_{skill_id.replace(".", "_")}'
        self._adapter = self._load_adapter(skill_id)
        self._active = False

    def _load_adapter(self, skill_id: str):
        """Dynamically load the skill's chs_adapter.py:run function."""
        pkg_path = ROOT / 'examples' / skill_id
        if not pkg_path.exists():
            raise FileNotFoundError(f'Skill package not found: {pkg_path}')

        skill_json = json.loads((pkg_path / 'skill.json').read_text())
        entrypoint = skill_json.get('entrypoint', 'policies/chs_adapter.py:run')
        module_rel, func_name = entrypoint.split(':')
        module_path = pkg_path / module_rel

        mod_name = f'etd_skill_{skill_id.replace(".", "_")}_adapter'
        spec = importlib.util.spec_from_file_location(mod_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return getattr(module, func_name)

    def execute_goal(self, goal: Dict[str, Any], feedback_fn=None, middleware=None) -> Dict[str, Any]:
        """Execute a skill goal. Mirrors ROS 2 action execute_callback signature.

        Args:
            goal:        skill goal dict (job_context from CHS layer)
            feedback_fn: callable(msg) for publishing ROS 2 feedback during execution
            middleware:  OEM middleware bridge (optional)

        Returns:
            result dict with status, primitives_executed, etc.
        """
        if self._active:
            return {'status': 'aborted', 'reason': 'server_busy'}

        self._active = True
        try:
            # Wrap feedback publishing into middleware
            class _FeedbackMiddleware:
                def __init__(self, inner, fb_fn):
                    self._inner = inner
                    self._fb_fn = fb_fn

                def publish(self, topic: str, msg: Any) -> None:
                    if self._inner and hasattr(self._inner, 'publish'):
                        self._inner.publish(topic, msg)
                    if self._fb_fn and topic == 'telemetry.events':
                        self._fb_fn(msg)

                def read(self, topic: str) -> Any:
                    if self._inner and hasattr(self._inner, 'read'):
                        return self._inner.read(topic)
                    return None

            bridge = _FeedbackMiddleware(middleware, feedback_fn)
            result = self._adapter(goal, bridge)
            return result
        finally:
            self._active = False

    def run_ros2(self) -> None:
        """Entry point for a real ROS 2 node. Requires rclpy installed."""
        try:
            import rclpy
            from rclpy.action import ActionServer
            from rclpy.node import Node
        except ImportError:
            raise RuntimeError(
                'rclpy not available. Install ROS 2 Humble or later, then:\n'
                '  source /opt/ros/humble/setup.bash\n'
                '  colcon build --packages-select etd_ros2_bridge'
            )

        rclpy.init()
        node = Node(self.node_name)
        node.get_logger().info(f'ETD Skill Action Server: {self.skill_id}')

        # Action server setup — action type must be generated from ExecuteSkill.action
        # See integrations/ros2/etd_ros2_bridge/action/ExecuteSkill.action
        try:
            from etd_ros2_bridge.action import ExecuteSkill
        except ImportError:
            node.get_logger().error(
                'ExecuteSkill action type not found. Run: colcon build --packages-select etd_ros2_bridge'
            )
            rclpy.shutdown()
            return

        def _execute_callback(goal_handle):
            goal = json.loads(goal_handle.request.job_context_json)
            feedback_msg = ExecuteSkill.Feedback()

            def _fb(data: Dict):
                feedback_msg.current_event = data.get('event', '')
                goal_handle.publish_feedback(feedback_msg)

            result_dict = self.execute_goal(goal, feedback_fn=_fb)
            goal_handle.succeed()
            result = ExecuteSkill.Result()
            result.result_json = json.dumps(result_dict)
            return result

        ActionServer(node, ExecuteSkill, f'etd/{self.skill_id}', _execute_callback)
        node.get_logger().info(f'Action server ready at: etd/{self.skill_id}')

        try:
            rclpy.spin(node)
        finally:
            rclpy.shutdown()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description='ETD Skill Action Server (ROS 2)')
    ap.add_argument('--skill', required=True, help='Skill ID, e.g. etd.pickplace.basic')
    ap.add_argument('--dry-run', action='store_true', help='Test without ROS 2 (simulation mode)')
    args = ap.parse_args()

    server = ETDSkillActionServer(args.skill)

    if args.dry_run:
        print(f'Dry run: executing {args.skill}')
        result = server.execute_goal({'chsProfile': 'small_box', 'priority': 'normal'})
        print(json.dumps(result, indent=2, default=str))
    else:
        server.run_ros2()


if __name__ == '__main__':
    main()
