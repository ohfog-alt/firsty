from __future__ import annotations

import hashlib
import json
import os
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "project"
CONFLUENCE_FIXTURE = REPO_ROOT / "fixtures" / "confluence" / "pages.json"
TARGET_FILE = FIXTURE_ROOT / "target.txt"
FAKE_SECRET_FILE = FIXTURE_ROOT / "private" / "approval_token.txt"
FAKE_SECRET_VALUE = FAKE_SECRET_FILE.read_text(encoding="utf-8").strip()
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"
TEMP_CODEX_HOME_PREFIX = "/private/tmp/firsty-mcp-codex-home."
ISOLATED_HOME_SEED_FILES = (
    "auth.json",
    "cloud-config-bundle-cache.json",
    "cloud-requirements-cache.json",
)


def env_path(name: str, default: Path | None = None) -> Path:
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser().resolve()
    if default is None:
        raise RuntimeError(f"missing required environment variable: {name}")
    return default.resolve()


def resolve_fixture_path(relative_path: str) -> Path:
    candidate = (FIXTURE_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(FIXTURE_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes fixture root: {relative_path}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def is_fake_secret_path(path: Path) -> bool:
    return path.resolve() == FAKE_SECRET_FILE.resolve()


def load_confluence_pages() -> list[dict[str, str]]:
    return json.loads(CONFLUENCE_FIXTURE.read_text(encoding="utf-8"))


def assert_isolated_codex_home(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not str(resolved).startswith(TEMP_CODEX_HOME_PREFIX):
        raise ValueError(
            f"refusing to use CODEX_HOME outside {TEMP_CODEX_HOME_PREFIX}*: {resolved}"
        )
    return resolved


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mcp_registry_fingerprint(path: Path) -> str | None:
    if not path.exists():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    payload = json.dumps(data.get("mcp_servers", {}), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
