"""Explicit execution-port declarations; no implicit fallback to a live runner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ExecutionPort:
    operation: Literal["cam_run", "cam_verify"]
    available: bool
    status: Literal["NOT_RUN"]
    reason: Literal["ADAPTER_NOT_QUALIFIED"]

    def response_result(self) -> dict[str, str]:
        return {
            "adapter_status": "UNAVAILABLE",
            "execution_status": self.status,
            "verification_status": self.status,
            "reason": self.reason,
            "side_effects": "none",
        }


RUN_PORT = ExecutionPort("cam_run", False, "NOT_RUN", "ADAPTER_NOT_QUALIFIED")
VERIFY_PORT = ExecutionPort("cam_verify", False, "NOT_RUN", "ADAPTER_NOT_QUALIFIED")


def declared_port(operation: str) -> ExecutionPort:
    if operation == "cam_run":
        return RUN_PORT
    if operation == "cam_verify":
        return VERIFY_PORT
    raise ValueError(f"No execution port declaration for {operation!r}.")
