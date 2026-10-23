"""Create a sealed, domain-neutral intake profile from a received directory.

This records custody and file-level identity only. It does not parse or qualify
the contents, register the result in the workbench, or run project scripts.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath


class ProfileError(ValueError):
    """Input cannot be safely profiled under this contract."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not name or any(part in (".", "..") for part in path.parts):
        raise ProfileError(f"Unsafe source path: {name}")
    return path


def _inventory(source):
    rows = []
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if path.is_symlink():
            raise ProfileError(f"Symbolic links are unsupported: {path.relative_to(source)}")
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        _safe_relative(relative)
        before = path.stat()
        digest = _sha(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ProfileError(f"Source changed while profiling: {relative}")
        rows.append({"path": relative, "bytes": after.st_size, "sha256": digest,
                     "file_type_hint": path.suffix.lower() or "[no extension]"})
    if not rows:
        raise ProfileError("Selected directory contains no regular files")
    return rows


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def profile_directory(project_root, source_directory, dataset_id, output_directory):
    """Copy, inventory, describe, and seal one directory under project_root/out or dataset.

    Destination must be new. The resulting profile is a draft and is not
    automatically admitted to contracts/ingestion_packages_v1.json.
    """
    root = Path(project_root).resolve()
    source_input = Path(source_directory).expanduser()
    if source_input.is_symlink():
        raise ProfileError("Selected source directory cannot be a symbolic link")
    source = source_input.resolve(strict=True)
    output = Path(output_directory).expanduser().resolve()
    if not source.is_dir():
        raise ProfileError("Selected source must be a directory")
    if not isinstance(dataset_id, str) or not dataset_id.strip() or "\n" in dataset_id:
        raise ProfileError("A non-empty, single-line dataset identity is required")
    if not (output.is_relative_to(root / "out") or output.is_relative_to(root / "dataset")):
        raise ProfileError("Profile output must be inside this checkout's out/ or dataset/ directory")
    if output.exists():
        raise ProfileError("Output already exists; profiles are immutable")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ProfileError("Source and output directories must not overlap")

    entries = _inventory(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        raw_root = output / "raw"
        raw_root.mkdir()
        for row in entries:
            relative = _safe_relative(row["path"])
            src = source.joinpath(*relative.parts)
            dst = raw_root.joinpath(*relative.parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            if dst.stat().st_size != row["bytes"] or _sha(dst) != row["sha256"]:
                raise ProfileError(f"Source changed during preservation: {row['path']}")

        tree_identity = hashlib.sha256(_canonical(entries)).hexdigest()
        profile = {
            "schema": "pcb-cam-general-intake-profile-v1",
            "dataset_id": dataset_id.strip(),
            "source_directory_label": source.name,
            "profile_kind": "generic-directory-intake",
            "okf_alignment": {
                "standard": "Google Open Knowledge Format",
                "version": "0.2",
                "use": "knowledge-document front matter and navigable profile; local extensions record binary custody and hashes",
                "qualification": "OKF alignment is descriptive; this output is not claimed to be a fully OKF-conformant corpus"
            },
            "intake": {
                "status": "PROFILED",
                "preservation": "PASS",
                "inventory": "PASS",
                "source_identity": "sha256-tree-v1",
                "tree_sha256": tree_identity,
                "file_count": len(entries),
                "total_bytes": sum(row["bytes"] for row in entries),
                "source_paths_are_relative_to_selected_directory": True,
                "qualification": "NOT_RUN",
                "native_extraction": "NOT_RUN",
                "workbench_registration": "NOT_RUN",
                "engineering_or_manufacturing_acceptance": "NOT_ESTABLISHED"
            },
            "files": entries,
            "registration_recipe": {
                "path": "metadata/registration_recipe.json",
                "status": "GENERATED_AND_INCLUDED_IN_PACKAGE_SEAL",
                "qualification": "NOT_RUN",
                "workbench_registration": "NOT_RUN"
            },
            "limits": [
                "File extensions are hints only; contents and semantics were not parsed.",
                "No parser, CAM operation, board query, comparison, or qualification was run.",
                "This staged profile is not a workbench restoration recipe."
            ]
        }
        _json(output / "metadata/profile.json", profile)
        _json(output / "metadata/manifest.json", {
            "schema": "pcb-cam-general-intake-manifest-v1",
            "dataset_id": dataset_id.strip(),
            "hash_algorithm": "sha256",
            "hash_scope": "all files except metadata/manifest.json and SHA256SUMS",
            "raw_tree_sha256": tree_identity,
            "raw_tree_identity_algorithm": "sha256 of UTF-8 canonical JSON array of file inventory rows sorted by relative path; keys sorted; compact separators",
            "source_files": [{**row, "package_path": f"raw/{row['path']}"} for row in entries],
            "files": []
        })
        _json(output / "metadata/provenance.json", {
            "schema": "pcb-cam-general-intake-provenance-v1",
            "dataset_id": dataset_id.strip(),
            "source_directory": str(source),
            "source_directory_label": source.name,
            "method": "local byte-for-byte directory copy; relative paths retained",
            "source_tree_sha256": tree_identity,
            "source_file_count": len(entries),
            "source_bytes": sum(row["bytes"] for row in entries),
            "filesystem_timestamps": "not used as design revision identity",
            "content_interpretation": "NOT_RUN"
        })
        package_root = output.relative_to(root).as_posix()
        recipe_sources = [{'path': f"{package_root}/raw/{row['path']}", 'sha256': row['sha256']}
                          for row in entries]
        (output / "qualification/index.md").parent.mkdir(parents=True, exist_ok=True)
        qualification_doc = (
            '# Qualification status\n\n**NOT_RUN.** This intake profile confirms copied bytes and inventory integrity only. '
            'No native/Gerber parsing, source matching, geometry, connectivity, DRC, manufacturing or engineering acceptance was performed.\n')
        (output / "qualification/index.md").write_text(qualification_doc, encoding="utf-8")
        recipe_evidence = [
            {'path': f'{package_root}/metadata/profile.json', 'sha256': _sha(output / 'metadata/profile.json')},
            {'path': f'{package_root}/metadata/provenance.json', 'sha256': _sha(output / 'metadata/provenance.json')},
            {'path': f'{package_root}/qualification/index.md', 'sha256': _sha(output / 'qualification/index.md')}
        ]
        _json(output / "metadata/registration_recipe.json", {
            "schema": "pcb-cam-general-intake-registration-recipe-v1",
            "package_root": package_root,
            "seal_path": f"{package_root}/SHA256SUMS",
            "dataset": {
                "id": dataset_id.strip(),
                "label": source.name,
                "qualification": "Intake profile sealed; content parsing and qualification are NOT_RUN. Engineering acceptance is NOT_ESTABLISHED.",
                "intent": "Unknown. Original folder structure is preserved; source roles and revision correspondence have not been assessed.",
                "sources": recipe_sources,
                "evidence": recipe_evidence,
                "intake_status": "PROFILED_NOT_QUALIFIED"
            },
            "admission_scope": "File custody and profile registration only; no parser, native extraction, comparison, CAM operation or qualification is run"
        })
        _json(output / "metadata/versions.json", {
            "schema": "pcb-cam-general-intake-versions-v1",
            "profile_schema": "pcb-cam-general-intake-profile-v1",
            "manifest_schema": "pcb-cam-general-intake-manifest-v1",
            "registration_recipe_schema": "pcb-cam-general-intake-registration-recipe-v1",
            "hash_algorithm": "sha256"
        })
        _json(output / "metadata/okf_standard.json", {
            "standard_name": "Google Open Knowledge Format",
            "version": "0.2",
            "use": "OKF-style Markdown front matter and navigable knowledge documents; binary inventory, hashing and invocation are local extensions",
            "conformance_claim": "This package is OKF-aligned documentation, not a claim of full OKF corpus conformance"
        })
        for folder in ("sources", "qualification", "evidence", "runbooks"):
            (output / folder).mkdir(parents=True, exist_ok=True)
        (output / "dataset.md").write_text(
            f'# Dataset identity: {dataset_id.strip()}\n\n'
            f'Intake snapshot from `{source}`. The source directory was copied byte-for-byte into `raw/` '
            'with its internal relative paths preserved. No content parser or engineering qualification was run.\n',
            encoding="utf-8")
        (output / "log.md").write_text(
            '# Intake history\n\n- Initial local profile generated; source inventory and package seal recorded. '
            'No design revision is inferred from filesystem timestamps.\n', encoding="utf-8")
        (output / "sources/index.md").write_text(
            f'# Preserved source files\n\n{len(entries)} files ({sum(row["bytes"] for row in entries)} bytes) are under `../raw/`. '
            'See [manifest](../metadata/manifest.json) for each relative path, size, type hint and SHA-256. '
            'File type hints do not imply successful parsing or a layer assignment.\n', encoding="utf-8")
        (output / "evidence/index.md").write_text(
            '# Evidence boundary\n\nThis package contains intake custody evidence only: source-relative file identities, '
            'the profile, the manifest and the package checksum seal. No parser receipts, comparisons or qualification evidence are present.\n',
            encoding="utf-8")
        (output / "runbooks/profiling.md").write_text(
            '# Reverify this profile\n\nFrom the project root, run:\n\n'
            '```sh\n.venv/bin/python tools/profile_dataset.py --verify ' +
            str(output.relative_to(root)) + '\n```\n\n'
            'A PASS verifies the package seal and raw-byte manifest bindings. It does not qualify the board data.\n',
            encoding="utf-8")
        (output / "index.md").write_text(
            f'---\ntype: "intake-profile"\nokf_version: "0.2"\nstatus: "PROFILED"\n---\n\n# Intake profile: {dataset_id.strip()}\n\n'
            f'Source: `{source.name}`. This profile preserves and identifies '
            f'{len(entries)} files ({sum(row["bytes"] for row in entries)} bytes).\n\n'
            'This is an intake inventory, not content interpretation or engineering qualification. '
            'Qualification and native extraction are **NOT_RUN**; engineering acceptance is **NOT_ESTABLISHED**.\n\n'
            '- [Dataset description](dataset.md)\n'
            '- [Sources](sources/index.md)\n'
            '- [Qualification status](qualification/index.md)\n'
            '- [Evidence boundary](evidence/index.md)\n'
            '- [Reverification runbook](runbooks/profiling.md)\n'
            '- [Machine-readable profile](metadata/profile.json)\n'
            '- [Preserved-file manifest](metadata/manifest.json)\n'
            '- [Sealed registration recipe](metadata/registration_recipe.json)\n'
            '- [Provenance](metadata/provenance.json)\n'
            '- [SHA-256 seal](SHA256SUMS)\n', encoding="utf-8")

        names = sorted(path.relative_to(output).as_posix() for path in output.rglob("*")
                       if path.is_file() and path.name != "SHA256SUMS")
        manifest_path = output / "metadata/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"] = [
            {"path": name, "bytes": (output / name).stat().st_size, "sha256": _sha(output / name),
             "role": "preserved-source-byte" if name.startswith("raw/") else "generated-intake-metadata"}
            for name in names if name != "metadata/manifest.json"
        ]
        _json(manifest_path, manifest)
        names = sorted(path.relative_to(output).as_posix() for path in output.rglob("*")
                       if path.is_file() and path.name != "SHA256SUMS")
        sums = "".join(f"{_sha(output / name)}  {name}\n" for name in names)
        (output / "SHA256SUMS").write_text(sums, encoding="utf-8")
        return {
            "status": "PROFILED",
            "dataset_id": dataset_id.strip(),
            "output": str(output),
            "file_count": len(entries),
            "total_bytes": sum(row["bytes"] for row in entries),
            "tree_sha256": tree_identity,
            "seal_sha256": _sha(output / "SHA256SUMS"),
            "qualification": "NOT_RUN",
            "workbench_registration": "NOT_RUN"
        }
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def verify_profile(directory):
    """Verify a staged profile's seal, manifest coverage and preserved bytes."""
    root = Path(directory).resolve(strict=True)
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        raise ProfileError("Profile seal is missing")
    expected = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        relative = _safe_relative(name)
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest) or name in expected or name == "SHA256SUMS":
            raise ProfileError("Invalid checksum seal")
        expected[name] = digest
    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ProfileError("Profile contains an unsupported symbolic link")
        if path.is_file() and path != sums_path:
            actual[path.relative_to(root).as_posix()] = _sha(path)
    if set(actual) != set(expected) or any(actual[name] != digest for name, digest in expected.items()):
        raise ProfileError("Profile seal coverage or checksum mismatch")
    manifest = json.loads((root / "metadata/manifest.json").read_text(encoding="utf-8"))
    rows = manifest.get("source_files", [])
    raw = {name[4:]: digest for name, digest in actual.items() if name.startswith("raw/")}
    profile = json.loads((root / "metadata/profile.json").read_text(encoding="utf-8"))
    recipe_path = root / "metadata/registration_recipe.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8")) if recipe_path.is_file() else None
    if manifest.get("schema") != "pcb-cam-general-intake-manifest-v1" or len(rows) != len(raw):
        raise ProfileError("Unsupported manifest or raw inventory mismatch")
    if (profile.get("schema") != "pcb-cam-general-intake-profile-v1"
            or profile.get("intake", {}).get("qualification") != "NOT_RUN"
            or profile.get("intake", {}).get("workbench_registration") != "NOT_RUN"
            or profile.get("intake", {}).get("engineering_or_manufacturing_acceptance") != "NOT_ESTABLISHED"
            or len({row.get("path") for row in rows}) != len(rows)
            or [{key: value for key, value in row.items() if key != "package_path"} for row in rows] != profile.get("files")):
        raise ProfileError("Profile metadata is incomplete or inconsistent")
    if recipe is not None:
        if (recipe.get("schema") != "pcb-cam-general-intake-registration-recipe-v1"
                or recipe.get("dataset", {}).get("id") != profile.get("dataset_id")
                or recipe.get("dataset", {}).get("intake_status") != "PROFILED_NOT_QUALIFIED"
                or not all(row.get("path", "").startswith(recipe.get("package_root", "") + "/")
                           and actual.get(row["path"][len(recipe["package_root"]) + 1:]) == row.get("sha256")
                           for row in recipe.get("dataset", {}).get("evidence", []))):
            raise ProfileError("Registration recipe identity or evidence binding mismatch")
        package_root = recipe.get("package_root")
        expected_sources = [{"path": f"{package_root}/raw/{row['path']}", "sha256": row["sha256"]}
                            for row in profile["files"]]
        if (recipe.get("seal_path") != f"{package_root}/SHA256SUMS"
                or recipe.get("dataset", {}).get("sources") != expected_sources
                or recipe.get("dataset", {}).get("qualification", "").find("NOT_RUN") < 0):
            raise ProfileError("Sealed registration recipe does not match the profiled source inventory")
    package_rows = manifest.get("files", [])
    expected_package_paths = set(actual) - {"metadata/manifest.json"}
    if (len({row.get("path") for row in package_rows}) != len(package_rows)
            or {row.get("path") for row in package_rows} != expected_package_paths
            or any(actual[row["path"]] != row.get("sha256") for row in package_rows)
            or any(row.get("path") not in raw or raw[row["path"]] != row.get("sha256")
                   or row.get("package_path") != f"raw/{row.get('path')}" for row in rows)
            or hashlib.sha256(_canonical([{k: v for k, v in row.items() if k != "package_path"} for row in rows])).hexdigest() != manifest.get("raw_tree_sha256")
            or profile.get("intake", {}).get("tree_sha256") != manifest.get("raw_tree_sha256")):
        raise ProfileError("Preserved raw bytes do not match the manifest")
    return {"status": "PASS", "file_count": len(rows), "seal_sha256": _sha(sums_path),
            "qualification": "NOT_RUN", "engineering_acceptance": "NOT_ESTABLISHED"}
