"""ETD Skill Action Client for ROS 2.

Sends skill execution goals to an ETDSkillActionServer node and waits for result.
Can also be used in framework-agnostic mode (--dry-run) without ROS 2.

Usage (with ROS 2):
    ros2 run etd_ros2_bridge skill_action_client \\
        --skill etd.pickplace.basic \\
        --profile small_box

Usage (dry run, no ROS 2):
    python skill_action_client.py --skill etd.pickplace.basic --dry-run
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


class ETDSkillActionClient:
    """ROS 2 action client for ETD skill execution.

    In real usage, wraps rclpy.action.ActionClient.
    In dry-run mode, calls ETDSkillActionServer directly.
    """

    def __init__(self, skill_id: str, timeout_sec: float = 30.0):
        self.skill_id = skill_id
        self.timeout_sec = timeout_sec

    def send_goal(self, job_context: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Send a skill goal and wait for result.

        Args:
            job_context: CHS job dict (chsProfile, payloadKg, destination, ...)
            dry_run:     if True, execute locally without ROS 2

        Returns:
            Result dict from the server
        """
        if dry_run:
            return self._local_execute(job_context)
        return self._ros2_execute(job_context)

    def _local_execute(self, job_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill locally (test/simulation mode)."""
        _bridge_dir = Path(__file__).resolve().parent
        if str(_bridge_dir) not in sys.path:
            sys.path.insert(0, str(_bridge_dir))
        from skill_action_server import ETDSkillActionServer
        server = ETDSkillActionServer(self.skill_id)
        print(f'[ETD Client] Sending goal to {self.skill_id}')
        print(f'[ETD Client] Job context: {json.dumps(job_context, indent=2)}')

        def _on_feedback(fb: Dict) -> None:
            print(f'[ETD Feedback] {fb.get("event", "")}')

        result = server.execute_goal(job_context, feedback_fn=_on_feedback)
        print(f'[ETD Client] Result: {json.dumps(result, indent=2, default=str)}')
        return result

    def _ros2_execute(self, job_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill via ROS 2 action protocol."""
        try:
            import rclpy
            from rclpy.action import ActionClient
            from rclpy.node import Node
        except ImportError:
            raise RuntimeError('rclpy not available. Use --dry-run or install ROS 2.')

        try:
            from etd_ros2_bridge.action import ExecuteSkill
        except ImportError:
            raise RuntimeError('ExecuteSkill action type not built. Run: colcon build')

        rclpy.init()
        node = Node(f'etd_client_{self.skill_id.replace(".", "_")}')
        client = ActionClient(node, ExecuteSkill, f'etd/{self.skill_id}')

        node.get_logger().info(f'Waiting for action server: etd/{self.skill_id}')
        if not client.wait_for_server(timeout_sec=self.timeout_sec):
            rclpy.shutdown()
            raise TimeoutError(f'Action server not available: etd/{self.skill_id}')

        goal_msg = ExecuteSkill.Goal()
        goal_msg.job_context_json = json.dumps(job_context)

        feedback_received: list = []
        def _fb_callback(fb):
            feedback_received.append(fb.feedback.current_event)
            node.get_logger().info(f'Feedback: {fb.feedback.current_event}')

        future = client.send_goal_async(goal_msg, feedback_callback=_fb_callback)
        rclpy.spin_until_future_complete(node, future)
        goal_handle = future.result()

        if not goal_handle.accepted:
            rclpy.shutdown()
            return {'status': 'rejected', 'reason': 'goal_rejected_by_server'}

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future)
        result = json.loads(result_future.result().result.result_json)

        rclpy.shutdown()
        return result


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description='ETD Skill Action Client (ROS 2)')
    ap.add_argument('--skill', required=True, help='Skill ID, e.g. etd.pickplace.basic')
    ap.add_argument('--profile', default='small_box', help='CHS profile name')
    ap.add_argument('--dry-run', action='store_true', help='Execute locally without ROS 2')
    args = ap.parse_args()

    client = ETDSkillActionClient(args.skill)
    job = {'chsProfile': args.profile, 'priority': 'normal'}
    result = client.send_goal(job, dry_run=args.dry_run)
    sys.exit(0 if result.get('status') == 'completed' else 1)


if __name__ == '__main__':
    main()
