"""Independent integrity guard for the frozen one-shot T03 C2 launcher."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = REPO_ROOT / "src/t03_c2_search_run.py"
RENDERER_PATH = REPO_ROOT / "src/t03_c2_cumulative_result.py"

# These are the reviewed source identities. Update only with a new audited run packet.
PINNED_LAUNCHER_SHA256 = "3711eccc7ff567aa47f7c068092b0782755a0a3d71dd9d5c9982ee9a91b957b2"
PINNED_RENDERER_SHA256 = "d0d61ff3668fd6b174cfcbf185b9668eec837c484b9a6bbc44ccd3e2646d9673"


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_executable_integrity(
    *,
    launcher_path: Path = LAUNCHER_PATH,
    renderer_path: Path = RENDERER_PATH,
    expected_launcher_sha256: str = PINNED_LAUNCHER_SHA256,
    expected_renderer_sha256: str = PINNED_RENDERER_SHA256,
) -> dict[str, str]:
    """Verify both mutable executables against this separately pinned guard."""
    launcher_path = Path(launcher_path).resolve(strict=True)
    renderer_path = Path(renderer_path).resolve(strict=True)
    if _sha(launcher_path) != expected_launcher_sha256:
        raise RuntimeError("EXECUTION_GUARD_LAUNCHER_SHA256_MISMATCH")
    if _sha(renderer_path) != expected_renderer_sha256:
        raise RuntimeError("EXECUTION_GUARD_RENDERER_SHA256_MISMATCH")
    return {
        "launcher_sha256": expected_launcher_sha256,
        "renderer_sha256": expected_renderer_sha256,
    }


def run_guarded(
    run_id: str,
    *,
    launcher_path: Path = LAUNCHER_PATH,
    renderer_path: Path = RENDERER_PATH,
    expected_launcher_sha256: str = PINNED_LAUNCHER_SHA256,
    expected_renderer_sha256: str = PINNED_RENDERER_SHA256,
    launch: Callable[[str], int],
) -> int:
    """Call the entry point only after both executable digests are verified."""
    verify_executable_integrity(
        launcher_path=launcher_path,
        renderer_path=renderer_path,
        expected_launcher_sha256=expected_launcher_sha256,
        expected_renderer_sha256=expected_renderer_sha256,
    )
    return launch(run_id)


def _invoke_launcher(run_id: str) -> int:
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("t03_c2_search_run_guarded", LAUNCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("EXECUTION_GUARD_LAUNCHER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    previous = os.environ.get("T03_C2_EXECUTION_GUARD")
    os.environ["T03_C2_EXECUTION_GUARD"] = "T03_C2_SEARCH_GUARD_V1"
    try:
        return int(module.main(["--run-id", run_id]))
    finally:
        if previous is None:
            os.environ.pop("T03_C2_EXECUTION_GUARD", None)
        else:
            os.environ["T03_C2_EXECUTION_GUARD"] = previous


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        return run_guarded(args.run_id, launch=_invoke_launcher)
    except BaseException as exc:
        print(f"T03_C2_SEARCH_GUARD_ABORTED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
