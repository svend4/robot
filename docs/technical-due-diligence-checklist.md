# Technical Due Diligence Checklist

For technical reviewers evaluating ETD as a robotics skill runtime platform.
All items listed below are verifiable against the prototype at v0.5.0.

---

## 1. Safety boundary

- [ ] **No override of OEM safety kernels.** Every skill package declares
  `packageCanNotOverride` in `manifest.yaml`. The validator rejects any
  package whose `capabilities.json` write list includes
  `command.emergency_stop_override`, `command.balance_core_override`,
  `command.collision_disable`, or `command.joint_limit_override`.
  → Verify: `python etd_cli.py validate examples/etd.pickplace.basic`
- [ ] **Human protective stop respected.** Every CHS adapter reads
  `state.safety_state` at every primitive boundary and aborts if
  `human_in_forbidden_zone = True`. This check cannot be suppressed by the
  job context.
  → Verify: `pytest tests/test_acceptance.py -k human_in_forbidden_zone`
- [ ] **Fallback declared.** All 8 reference packages declare
  `fallbackSkill: etd.safe_stop_and_retreat` and a valid `fallbackMode`.
- [ ] **No direct joint writes.** No adapter writes `command.servo_torque`
  or `command.joint_angle`. Skills emit `command.skill_intent` only — the
  OEM controller converts these within its own safety envelope.

---

## 2. Package signing and integrity

- [ ] **Ed25519 signing.** `scripts/sign_package.py` produces a
  `package.sig` file over a deterministic SHA-256 hash of all package files.
  `scripts/verify_signature.py` verifies the signature against the publisher
  public key.
- [ ] **Release pipeline.** `scripts/release_package.py` enforces
  validate → sign → zip order. A package that fails validation cannot be
  signed; a package that fails signing cannot be zipped.
- [ ] **All 8 reference packages signed.**
  `ls examples/*/package.sig` — all 8 present.
- [ ] **Signature verification tested.**
  `pytest tests/test_signing.py` — 62 tests covering roundtrip sign/verify,
  missing-sig detection, whitespace key rejection, and manifest parse fallback.

---

## 3. Schema validation

- [ ] **JSON Schema Draft 2020-12** used for all 5 required package files
  (`manifest.yaml`, `skill.json`, `chs_profiles.json`, `capabilities.json`,
  `execution_contract.json`). Schemas in `schemas/`.
- [ ] **All 8 packages pass at level A.** Run `python etd_demo_runner.py` —
  all 8 should report `valid=True, level=A`.
- [ ] **Validator tested.** `pytest tests/test_validator.py` — 59 tests
  covering schema branches, compatibility scoring, YAML loading,
  non-dict manifest handling, and jsonschema-unavailable fallback.

---

## 4. Station compatibility

- [ ] **6 station profiles** in `station_profiles/`. Each declares
  `robotClass`, `maxPayloadKg`, `skillFamilies`, and `availableServices`.
- [ ] **Install-time gate.** `validate_for_install` cross-checks the skill's
  `requiresServices` against the station's `availableServices`. Missing
  required services cause the install to be denied.
- [ ] **Human-aware enforcement.** Stations that set `humanAware: true`
  require skills to declare `requiresHumanAwareBehavior: true` in their
  safety section.
- [ ] **Compatibility tested.** `pytest tests/test_station_profiles.py` —
  39 tests; `pytest tests/test_api.py` — station install endpoint covered.

---

## 5. Failure scenario coverage

- [ ] **39 acceptance YAML scenarios** cover both happy paths and every
  defined abort reason (`human_in_forbidden_zone`, alignment confidence,
  seam lost, balance unstable, path not ready, fatigue threshold, etc.).
  Run: `python sim/acceptance_runner.py`
- [ ] **Failure scenario module.** `sim/failure_scenarios.py` runs
  adversarial middleware injection for each adapter.
- [ ] **All 8 adapters abort safely.** No adapter returns `status:
  completed` when a forbidden-zone intrusion is injected. Verified by
  `pytest tests/test_acceptance.py -k forbidden_zone`.

---

## 6. Test coverage

- [ ] **689 pytest tests, all passing.** `python -m pytest`
- [ ] **Branch coverage ≥ 96%** across all source modules.
  `python -m pytest --cov --cov-branch --cov-report=term-missing`
- [ ] **ROS 2 bridge tested without ROS 2.** `pytest tests/test_ros2_bridge.py`
  — 43 tests; ActionServer callback capture, client feedback invocation,
  timeout/reject/happy-path, all without `rclpy` installed.
- [ ] **No test isolation issues.** Full suite is deterministic with
  `random.seed(42)` in parametrized tests. Run twice; both runs must pass.

---

## 7. API and integration surface

- [ ] **REST API.** `uvicorn api.app:app --reload` then:
  - `GET /store/skills` returns all 8 packages
  - `POST /store/install {"skillId": "etd.pickplace.basic"}` returns allowed
  - `GET /store/stations` returns all 6 station profiles
- [ ] **CLI.** `python etd_cli.py validate examples/etd.pickplace.basic`
  returns `valid=True`
- [ ] **ROS 2 stub.** `integrations/ros2/` provides `ETDSkillActionServer`
  and `ETDSkillActionClient` ready to wire into a ROS 2 workspace.

---

## 8. Dependency footprint

- [ ] **Pure Python (stdlib + 5 packages).** `pip install -r requirements.txt`
  → `fastapi`, `uvicorn`, `pyyaml`, `jsonschema`, `cryptography`. No GPU,
  no ROS, no OEM SDK required to run the validator, marketplace, or CLI.
- [ ] **ROS 2 optional.** The bridge imports `rclpy` lazily; absence raises
  `RuntimeError('rclpy not available')` with a clear message.
- [ ] **matplotlib optional.** The visualizer imports matplotlib lazily;
  absence prints `'matplotlib not installed'` and returns.

---

## 9. Code quality

- [ ] **No hardcoded credentials or secrets** in any source file.
  `git grep -i 'password\|secret\|api_key'` — should return no matches in
  source (only test fixtures).
- [ ] **Type annotations** on all public adapter functions (`run`, `main`,
  `ETDSkillActionServer`, `ETDSkillActionClient`).
- [ ] **No subprocess calls, no eval/exec, no `__import__` in skill
  adapters.** The adapter entrypoint is a plain Python function.
