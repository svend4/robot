from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etd_reference_validator import ETDReferenceValidator, RuntimeContext


@dataclass
class StoreEntry:
    skillId: str
    version: str
    family: str
    packagePath: str
    publisher: str
    riskLevel: str
    certificationState: str
    targetUse: str
    licenseModel: str = "open_source"
    pricingModel: str = "free"
    sourceAvailability: str = "full_source"
    requiresEntitlement: bool = False
    requiresSignature: bool = True
    supportLevel: str = "community"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "StoreEntry":
        allowed = {name for name in cls.__dataclass_fields__.keys()}
        filtered = {k: v for k, v in payload.items() if k in allowed}
        # Compatibility with newer metadata names.
        if "requiresEntitlement" not in filtered and "requiresActivation" in payload:
            filtered["requiresEntitlement"] = bool(payload["requiresActivation"])
        if "sourceAvailability" not in filtered and "sourceAvailable" in payload:
            filtered["sourceAvailability"] = "full_source" if payload["sourceAvailable"] else "binary_or_private"
        return cls(**filtered)


@dataclass
class InstallDecision:
    skillId: str
    allowed: bool
    reason: str
    validationLevel: str
    licenseModel: str
    pricingModel: str
    requiresEntitlement: bool


class SkillStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.index_path = repo_root / "marketplace" / "skill_store_index.json"
        self.policy_path = repo_root / "marketplace" / "marketplace_policy.json"
        self.licensing_policy_path = repo_root / "marketplace" / "licensing_policy.json"
        self.index = self._load_json(self.index_path)
        self.policy = self._load_json(self.policy_path)
        self.licensing_policy = self._load_json(self.licensing_policy_path) if self.licensing_policy_path.exists() else {}

    def list_entries(self) -> List[StoreEntry]:
        return [StoreEntry.from_dict(entry) for entry in self.index.get("entries", [])]

    def list_skills(self) -> List[Dict[str, Any]]:
        return list(self.index.get("entries", []))

    def get_entry(self, skill_id: str) -> Optional[StoreEntry]:
        for entry in self.list_entries():
            if entry.skillId == skill_id:
                return entry
        return None

    def find_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.index.get("entries", []):
            if entry.get("skillId") == skill_id:
                return entry
        return None

    def validate_for_install(
        self,
        skill_id: str,
        runtime_context: RuntimeContext,
        entitlement_token: Optional[str] = None,
    ) -> InstallDecision:
        entry = self.get_entry(skill_id)
        if entry is None:
            return InstallDecision(
                skillId=skill_id,
                allowed=False,
                reason="skill_not_found",
                validationLevel="D",
                licenseModel="unknown",
                pricingModel="unknown",
                requiresEntitlement=False,
            )

        package_path = self.repo_root / entry.packagePath
        validator = ETDReferenceValidator(runtime_context)
        report = validator.validate_package(package_path)
        level = self._compat_level(report)

        if level not in {"A", "B"} or not report.valid:
            return InstallDecision(
                skillId=entry.skillId,
                allowed=False,
                reason="validation_failed",
                validationLevel=level,
                licenseModel=entry.licenseModel,
                pricingModel=entry.pricingModel,
                requiresEntitlement=entry.requiresEntitlement,
            )

        if entry.requiresEntitlement and not entitlement_token:
            return InstallDecision(
                skillId=entry.skillId,
                allowed=False,
                reason="entitlement_required",
                validationLevel=level,
                licenseModel=entry.licenseModel,
                pricingModel=entry.pricingModel,
                requiresEntitlement=True,
            )

        return InstallDecision(
            skillId=entry.skillId,
            allowed=True,
            reason="install_allowed",
            validationLevel=level,
            licenseModel=entry.licenseModel,
            pricingModel=entry.pricingModel,
            requiresEntitlement=entry.requiresEntitlement,
        )

    def validate_listing(self, skill_id: str, runtime_context: RuntimeContext) -> Dict[str, Any]:
        entry_payload = self.find_skill(skill_id)
        if entry_payload is None:
            return {"skillId": skill_id, "installAllowed": False, "reason": "skill_not_found"}
        entry = StoreEntry.from_dict(entry_payload)
        token = "demo-entitlement" if entry.requiresEntitlement else None
        decision = self.validate_for_install(skill_id, runtime_context, entitlement_token=token)
        return {
            "skillId": decision.skillId,
            "version": entry.version,
            "licenseModel": decision.licenseModel,
            "pricingModel": decision.pricingModel,
            "sourceAvailability": entry.sourceAvailability,
            "requiresEntitlement": decision.requiresEntitlement,
            "validationLevel": decision.validationLevel,
            "installAllowed": decision.allowed,
            "reason": decision.reason,
        }

    def _compat_level(self, report: Any) -> str:
        compatibility = getattr(report, "compatibility", {})
        if isinstance(compatibility, dict):
            return str(compatibility.get("level", "D"))
        return str(getattr(compatibility, "level", "D"))

    def _load_json(self, path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))


def default_runtime_context() -> RuntimeContext:
    return RuntimeContext(
        runtime_version="0.1.0",
        robot_class="humanoid",
        available_services=[
            "perception.object_pose",
            "perception.part_alignment",
            "manipulation.arm_control",
            "force_control.contact_feedback",
            "workflow.job_context",
            "state.robot_pose",
            "state.arm_state",
            "state.wrist_state",
            "state.safety_state",
            "safety.zone_monitor",
            "vision.barcode_scan",
            "quality.photo_capture",
            "telemetry.metrics",
        ],
        platform_profile="atlas_style_humanoid_v1",
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    store = SkillStore(root)
    context = default_runtime_context()
    for entry in store.list_entries():
        token = "demo-entitlement" if entry.requiresEntitlement else None
        decision = store.validate_for_install(entry.skillId, context, entitlement_token=token)
        print(json.dumps(asdict(decision), indent=2, ensure_ascii=False))
