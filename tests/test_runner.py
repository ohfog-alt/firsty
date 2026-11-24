from __future__ import annotations

from pathlib import Path

import pytest

from mcp_lure_lab.config import ISOLATED_HOME_SEED_FILES, assert_isolated_codex_home, mcp_registry_fingerprint
from mcp_lure_lab.run_experiment import TrialSpec, build_trial_specs, codex_exec_command, run_trial


def test_build_trial_specs_counts_full_default_matrix() -> None:
    specs = build_trial_specs("gpt-5.5", 3, None, None)
    assert len(specs) == 126
    assert sum(1 for spec in specs if spec.scenario == "mefirst") == 60
    assert sum(1 for spec in specs if spec.scenario == "readfile") == 60
    assert sum(1 for spec in specs if spec.scenario == "shadow") == 6
    assert {spec.registry_order for spec in specs if spec.scenario == "shadow"} == {
        "legit_first",
        "malicious_first",
    }


def test_codex_exec_command_is_read_only_and_ephemeral() -> None:
    command = codex_exec_command(TrialSpec("mefirst", "approval_gate", 1, "gpt-5.5"))
    assert "--ephemeral" in command
    assert "--skip-git-repo-check" in command
    assert command.count("--disable") == 3
    assert "apps" in command
    assert "remote_plugin" in command
    assert "plugins" in command
    assert ["-s", "read-only"] == command[command.index("-s") : command.index("-s") + 2]


def test_build_trial_specs_accepts_legacy_aliases_and_composed_scenarios() -> None:
    specs = build_trial_specs("gpt-5.5", 1, ["direct", "cross", "readfile+mefirst"], ["approval_gate"])
    assert [spec.scenario for spec in specs] == ["mefirst", "readfile", "mefirst+readfile"]


def test_codex_home_guard_rejects_real_home() -> None:
    with pytest.raises(ValueError):
        assert_isolated_codex_home(Path.home() / ".codex")


def test_codex_home_guard_accepts_expected_tmp_prefix(tmp_path: Path) -> None:
    path = Path("/private/tmp/firsty-mcp-codex-home.example")
    assert assert_isolated_codex_home(path) == path


def test_isolated_home_seed_files_do_not_include_real_config() -> None:
    assert "auth.json" in ISOLATED_HOME_SEED_FILES
    assert "config.toml" not in ISOLATED_HOME_SEED_FILES


def test_mcp_registry_fingerprint_ignores_non_mcp_config_changes(tmp_path: Path) -> None:
    first = tmp_path / "first.toml"
    second = tmp_path / "second.toml"
    first.write_text('model = "gpt-5.5"\n[mcp_servers.demo]\ncommand = "python"\n', encoding="utf-8")
    second.write_text('model = "gpt-5.6"\n[mcp_servers.demo]\ncommand = "python"\n', encoding="utf-8")
    assert mcp_registry_fingerprint(first) == mcp_registry_fingerprint(second)


def test_dry_run_does_not_require_codex_home_seed_files(tmp_path: Path) -> None:
    run_trial(
        TrialSpec("mefirst+readfile", "approval_gate", 1, "gpt-5.5"),
        tmp_path,
        keep_codex_home=False,
        dry_run=True,
        import_real_registry=False,
        trial_timeout_seconds=1,
    )
    metadata = (tmp_path / "mefirst+readfile-approval_gate-01" / "metadata.json").read_text(encoding="utf-8")
    assert '"codex_home": null' in metadata
    assert '"dry_run": true' in metadata
