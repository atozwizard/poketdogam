from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os
import sys


SCHEMA_VERSION = 1


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attach_artifact_manifest(
    meta_path: Path,
    artifacts: dict[str, Path],
) -> dict[str, object]:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["schema_version"] = SCHEMA_VERSION
    metadata["artifacts"] = {
        name: {
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in sorted(artifacts.items())
        if path.exists()
    }
    temporary = meta_path.with_name(f".{meta_path.name}.tmp")
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, meta_path)
    return metadata


def verify_artifact_manifest(
    meta_path: Path,
    artifacts: dict[str, Path],
) -> dict[str, object]:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    manifest = metadata.get("artifacts") or {}
    failures: list[str] = []
    for name, path in artifacts.items():
        expected = manifest.get(name) or {}
        if not path.exists():
            failures.append(f"{name}:missing")
            continue
        if int(expected.get("size_bytes") or -1) != path.stat().st_size:
            failures.append(f"{name}:size")
            continue
        if str(expected.get("sha256") or "") != file_sha256(path):
            failures.append(f"{name}:sha256")
    return {
        "valid": not failures,
        "schema_version": metadata.get("schema_version"),
        "failures": failures,
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    meta_path = project_root / "data" / "dex.meta.json"
    artifacts = {
        "dex.sqlite": project_root / "data" / "dex.sqlite",
        "gen1_visual_index.json": project_root / "data" / "vision" / "gen1_visual_index.json",
        "mobilenet_v3_small.tflite": (
            project_root / "data" / "vision" / "mobilenet_v3_small.tflite"
        ),
    }
    result = verify_artifact_manifest(meta_path, artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["valid"] or result["schema_version"] != SCHEMA_VERSION:
        sys.exit(1)


if __name__ == "__main__":
    main()
