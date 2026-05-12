# ETD Middleware Developer Guide

This guide covers how to implement an OEM middleware adapter so that ETD skill
packages can run on a new robot platform.  After reading it you will be able to:

- subclass `ETDMiddleware` and wire topics to your robot's communication layer
- plug a `TelemetrySink` into your adapter for streaming skill events
- validate and load your adapter at runtime
- test your adapter without physical hardware using the dry-run / inject pattern

---

## 1. Concepts

### What is an ETD middleware adapter?

ETD skill packages communicate with the robot through a two-method interface:

```
middleware.read(topic: str)  → dict     # pull latest value from robot
middleware.publish(topic: str, msg: dict)  # push command or event to robot
```

An **OEM middleware adapter** maps these ETD service topic names to whatever
communication primitives your robot uses — ROS 2 topics, gRPC calls, proprietary
SDKs, shared memory, REST endpoints, etc.

ETD defines a service topic naming convention.  Each skill package declares the
topics it needs in `capabilities.json` under `requiresServices`.  Your adapter
must handle every topic listed there.

### Topic naming convention

ETD topics follow a `<namespace>.<leaf>` pattern:

| Namespace | Meaning |
|---|---|
| `state.*` | Robot sensor / status reads |
| `perception.*` | Vision, force, intent detection |
| `command.*` | Actuation commands (intent-only, ETD never sends raw motion) |
| `force_control.*` | Force/torque feedback and commands |
| `telemetry.*` | Skill lifecycle events emitted by the skill |
| `safety.*` | Safety zone monitoring, human presence |
| `navigation.*` | AMR path planning and waypoint events |
| `welding.*` | Arc-welding specific topics (WIA H-Motion) |
| `assist.*` | Wearable-assist intent and torque events (H-MEX) |

---

## 2. Implementing an adapter

### 2.1 Minimal adapter

```python
# adapters/my_robot_adapter.py
from etd_middleware_contract import ETDMiddleware

class MyRobotAdapter(ETDMiddleware):
    required_topics = [
        'state.safety_state',
        'command.skill_intent',
        'telemetry.events',
    ]

    def read(self, topic: str) -> dict:
        if topic == 'state.safety_state':
            return self._robot_sdk.get_safety_state()
        return {}

    def publish(self, topic: str, message: dict) -> None:
        if topic == 'command.skill_intent':
            self._robot_sdk.execute_intent(message)
```

### 2.2 Load and validate at startup

```python
from etd_middleware_contract import load_middleware_adapter

mw = load_middleware_adapter(MyRobotAdapter())
# raises TypeError  if MyRobotAdapter does not subclass ETDMiddleware
# raises RuntimeError if any required_topic is unavailable (per validate())
```

### 2.3 Override validate() for live connectivity checks

```python
def validate(self) -> None:
    if not self._robot_sdk.is_connected():
        raise RuntimeError("Robot SDK not connected")
    unavailable = [t for t in self.required_topics
                   if not self._robot_sdk.topic_exists(t)]
    if unavailable:
        raise RuntimeError(f"Topics not available: {unavailable}")
```

### 2.4 Map to your platform's topic namespace

The reference adapters follow the pattern `_ETD_TO_<PLATFORM>: dict`:

```python
_ETD_TO_MYPLATFORM = {
    'state.safety_state':   '/myrobot/safety/state',
    'command.skill_intent': '/myrobot/skill/intent',
    'telemetry.events':     '/myrobot/etd/telemetry',
}

def read(self, topic: str) -> dict:
    ros_topic = _ETD_TO_MYPLATFORM.get(topic, topic)
    return self._ros2_read(ros_topic)
```

---

## 3. Telemetry sink

Attach a `TelemetrySink` to stream `telemetry.events` publishes to file, MQTT,
or any custom destination — independently of the underlying middleware transport.

```python
from adapters.telemetry_sink import FileSink, MQTTSink, MultiSink

# Write to file and MQTT simultaneously
sink = MultiSink([
    FileSink('telemetry/skill_run.jsonl'),
    MQTTSink('192.168.1.100', topic_prefix='factory/robot01/etd'),
])

mw = MyRobotAdapter(telemetry_sink=sink)
```

### Route telemetry.events to the sink in publish()

```python
def publish(self, topic: str, message: dict) -> None:
    if topic == 'telemetry.events':
        event_name = message.get('event', topic)
        self._sink.emit(event_name, {k: v for k, v in message.items()
                                     if k != 'event'})
    # … normal publish path …
```

### Available sinks

| Class | Description |
|---|---|
| `NullSink` | Discards all events (tests, benchmarks) |
| `ConsoleSink` | Prints JSON to stdout |
| `FileSink(path)` | Appends JSON Lines; creates parent dirs |
| `MQTTSink(broker, port, topic_prefix)` | MQTT; stubs to stdout if paho-mqtt absent |
| `MultiSink([sink, …])` | Fan-out; swallows per-sink errors |

---

## 4. Dry-run and testability

All three Hyundai reference adapters follow the same testable pattern.
Adopt it in your adapter to get tests for free:

```python
class MyRobotAdapter(ETDMiddleware):
    def __init__(self, dry_run: bool = True, telemetry_sink=None):
        self._dry_run = dry_run
        self._mock = {
            'state.safety_state': {
                'human_in_forbidden_zone': False, 'estop_active': False,
            },
        }
        self.published = []
        self._sink = telemetry_sink or NullSink()
        if not dry_run:
            self._init_real_connection()

    def read(self, topic: str) -> dict:
        if self._dry_run:
            return dict(self._mock.get(topic, {}))
        return self._live_read(topic)

    def publish(self, topic: str, message: dict) -> None:
        if topic == 'telemetry.events':
            self._sink.emit(message.get('event', ''), message)
        if self._dry_run:
            self.published.append({'topic': topic, 'message': message})
            return
        self._live_publish(topic, message)

    def inject_state(self, topic: str, patch: dict) -> None:
        """Merge patch into mock state — used in tests."""
        self._mock[topic] = {**self._mock.get(topic, {}), **patch}
```

Then in tests:

```python
adapter = MyRobotAdapter(dry_run=True)
adapter.inject_state('state.safety_state', {'human_in_forbidden_zone': True})
result = my_skill.run({'chsProfile': 'default'}, middleware=adapter)
assert result['status'] == 'aborted'
```

---

## 5. Reference adapters

Three production-ready reference adapters ship with the ETD runtime:

| Adapter | Platform | Topics | Module |
|---|---|---|---|
| `HyundaiWIAAdapter` | H-Motion welding cobot | 16 ETD → `/hmotion/*` | `adapters/hyundai_wia_adapter.py` |
| `HyundaiMobEDAdapter` | MobED H-Rise AMR | 17 ETD → `/hrise/*` | `adapters/hyundai_mobed_adapter.py` |
| `HyundaiExoAdapter` | VEX / H-MEX exoskeleton | 18 ETD → `/hmex/*` | `adapters/hyundai_exo_adapter.py` |

All three:
- subclass `ETDMiddleware`
- declare `required_topics`
- implement `read` / `publish` with dry-run mock
- accept a `telemetry_sink` parameter
- expose `inject_state()` / platform-specific convenience helpers
- stub `_ros2_read` / `_ros2_publish` for live rclpy integration

---

## 6. Safety boundary contract

Every ETD adapter **must** enforce the following regardless of platform:

1. **Never route `command.servo_torque`, `command.joint_limit_override`, or
   `command.collision_disable` to the robot.** These topics are in the ETD
   forbidden-capabilities list; a skill package that writes them would have
   failed validation before reaching the adapter.

2. **Never replace the OEM safety kernel.** ETD sits above the real-time
   control layer.  Your adapter routes `command.skill_intent` (a bounded,
   validated intent) — not raw motion commands.

3. **Forward all `telemetry.events` publishes from the skill.** This is the
   audit trail.  Dropping events violates the ETD compliance contract.

4. **Return `{}` for unknown topics rather than raising.**  Skills use default
   values when a topic returns empty; an exception would abort the skill
   unexpectedly.

```python
def read(self, topic: str) -> dict:
    result = self._live_read(topic)
    return result if isinstance(result, dict) else {}
```

---

## 7. Checklist

Before submitting an adapter for ETD marketplace review:

- [ ] Subclasses `ETDMiddleware`
- [ ] All `required_topics` declared and present in topic mapping
- [ ] `validate()` overridden with platform connectivity check
- [ ] `dry_run=True` mode implemented with injectable mock state
- [ ] `telemetry_sink` parameter accepted; `telemetry.events` forwarded
- [ ] `inject_state()` or equivalent test helper present
- [ ] Tests cover: happy path, abort on safety event, telemetry sink output
- [ ] Forbidden capabilities (`command.servo_torque`, etc.) rejected or absent
- [ ] `_ros2_read` / `_ros2_publish` stubs raise `NotImplementedError` with
      actionable message rather than silently returning
