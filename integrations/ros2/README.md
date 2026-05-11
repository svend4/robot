# ETD ROS 2 Integration

ETD skill packages can be executed as **ROS 2 action servers** using this bridge package.
Each skill runs in its own node and exposes a `ExecuteSkill` action endpoint.

---

## Architecture

```
ROS 2 Workflow Node
    └─► ros2 action send_goal  etd/etd.pickplace.basic  ExecuteSkill  '{...}'
            └─► SkillActionServer node
                    ├─► ETDReferenceValidator (validate before execute)
                    ├─► chs_adapter.run()    (skill runtime)
                    └─► skill_intent publisher (→ OEM middleware topic)
```

The bridge does **not** bypass OEM middleware — it publishes `command.skill_intent`
messages that the OEM stack consumes and translates into certified motor commands.

---

## Build (ROS 2 Humble or later)

```bash
source /opt/ros/humble/setup.bash

# Place this package in your ROS 2 workspace
cp -r integrations/ros2/etd_ros2_bridge ~/ros2_ws/src/

cd ~/ros2_ws
colcon build --packages-select etd_ros2_bridge
source install/setup.bash
```

---

## Run

**Start the action server for pickplace:**
```bash
ros2 run etd_ros2_bridge skill_action_server --skill etd.pickplace.basic
```

**Send a goal from another terminal:**
```bash
ros2 action send_goal /etd/etd.pickplace.basic \
  etd_ros2_bridge/action/ExecuteSkill \
  '{"job_context_json": "{\"chsProfile\": \"small_box\", \"destination\": \"bin_A\"}"}'
```

**Or use the Python client:**
```bash
ros2 run etd_ros2_bridge skill_action_client \
  --skill etd.pickplace.basic \
  --profile fragile_item
```

---

## Dry run (no ROS 2 needed)

Test the adapter without installing ROS 2:

```bash
python integrations/ros2/etd_ros2_bridge/etd_ros2_bridge/skill_action_server.py \
  --skill etd.pickplace.basic --dry-run

python integrations/ros2/etd_ros2_bridge/etd_ros2_bridge/skill_action_client.py \
  --skill etd.inspect.vision --profile barcode_qa --dry-run
```

---

## Action type: ExecuteSkill.action

```
# Goal
string job_context_json     # JSON-encoded CHS job context
string skill_id             # optional override

# Feedback
string current_event        # e.g. "primitive.entered"
string current_primitive    # e.g. "guarded_grasp"

# Result
string result_json          # JSON-encoded result dict
string status               # completed | aborted | failed
string reason               # abort/failure reason (empty if completed)
```

---

## Safety boundary

The bridge respects ETD safety rules:
- never publishes forbidden capabilities (`command.servo_torque`, etc.)
- respects `requiresHumanAwareBehavior` by monitoring `state.safety_state`
- on abort, publishes `skill.aborted` event before returning
