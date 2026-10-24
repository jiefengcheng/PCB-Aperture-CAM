"""Small strict value and validation helpers for the local CAM Agent ABI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict


OPERATIONS = (
    "cam_describe",
    "cam_inspect",
    "cam_plan",
    "cam_run",
    "cam_verify",
    "cam_compare",
    "cam_review",
)
REQUEST_KEYS = {
    "abi_version", "operation", "profile_id", "site_id",
    "left_profile_id", "right_profile_id", "overrides",
}


class SourceBinding(TypedDict):
    path: str
    sha256: str


class EvidenceReference(TypedDict):
    path: str
    sha256: str


class CAMRequest(TypedDict):
    abi_version: Literal["0.1"]
    operation: str
    profile_id: str | None
    site_id: str | None
    left_profile_id: str | None
    right_profile_id: str | None
    overrides: dict[str, Any] | None


class StatusDimensions(TypedDict):
    owner_review: str
    technical_geometry: str
    t01_behavior: str
    engineering: str
    manufacturing: str


class PlanStep(TypedDict):
    step_id: str
    status: Literal["PLANNED", "NOT_RUN"]
    effect: str


class ABIError(Exception):
    def __init__(self, code: str, message: str, *, status: str = "REJECTED") -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Response:
    abi_version: str
    operation: str
    status: str
    result: dict[str, Any] | None
    error: dict[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "abi_version": self.abi_version,
            "operation": self.operation,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


def exact_int(value: Any) -> bool:
    """JSON booleans are integers in Python; ABI counts must exclude them."""
    return type(value) is int


def exact_pass(value: Any) -> bool:
    """Only a JSON boolean true is a pass; truthy strings/numbers are invalid."""
    return type(value) is bool and value is True


def require_object(value: Any, code: str = "REQUEST_NOT_OBJECT") -> dict[str, Any]:
    if type(value) is not dict:
        raise ABIError(code, "Request must be a JSON object.")
    return value


def validate_request(request: Any) -> CAMRequest:
    obj = require_object(request)
    if set(obj) != REQUEST_KEYS:
        missing = sorted(REQUEST_KEYS - set(obj))
        extra = sorted(set(obj) - REQUEST_KEYS)
        raise ABIError("REQUEST_SHAPE_INVALID", f"Request keys must be exact; missing={missing}, extra={extra}.")
    if obj["abi_version"] != "0.1" or type(obj["abi_version"]) is not str:
        raise ABIError("ABI_VERSION_UNSUPPORTED", "abi_version must be the string '0.1'.")
    if type(obj["operation"]) is not str or obj["operation"] not in OPERATIONS:
        raise ABIError("OPERATION_UNKNOWN", "operation is not registered in CAM Agent ABI v0.1.")
    for name in ("profile_id", "site_id", "left_profile_id", "right_profile_id"):
        if obj[name] is not None and type(obj[name]) is not str:
            raise ABIError("REQUEST_FIELD_TYPE_INVALID", f"{name} must be a string or null.")
    if obj["overrides"] is not None and type(obj["overrides"]) is not dict:
        raise ABIError("REQUEST_FIELD_TYPE_INVALID", "overrides must be an object or null.")
    if obj["overrides"] not in (None, {}):
        raise ABIError("POLICY_CHANGE_REQUIRED", "ABI v0.1 accepts no caller overrides; revise and review a separately pinned policy first.")
    applicable_fields = {
        "cam_describe": set(),
        "cam_inspect": {"profile_id", "site_id"},
        "cam_plan": {"profile_id"},
        "cam_run": {"profile_id"},
        "cam_verify": {"profile_id"},
        "cam_compare": {"left_profile_id", "right_profile_id"},
        "cam_review": {"profile_id"},
    }[obj["operation"]]
    for name in ("profile_id", "site_id", "left_profile_id", "right_profile_id"):
        if name not in applicable_fields and obj[name] is not None:
            raise ABIError("REQUEST_FIELD_NOT_APPLICABLE", f"{name} is not used by {obj['operation']} and must be null.")
        if type(obj[name]) is str and not obj[name]:
            raise ABIError("REQUEST_FIELD_VALUE_INVALID", f"{name} must be non-empty when provided.")
    for name in ("profile_id",) if obj["operation"] in {"cam_inspect", "cam_plan", "cam_review"} else ():
        if not obj[name]:
            raise ABIError("PROFILE_ID_REQUIRED", f"{name} must be a non-empty string for {obj['operation']}.")
    if obj["operation"] == "cam_compare" and (not obj["left_profile_id"] or not obj["right_profile_id"]):
        raise ABIError("COMPARISON_PROFILE_IDS_REQUIRED", "cam_compare requires non-empty left_profile_id and right_profile_id values.")
    return obj  # type: ignore[return-value]
