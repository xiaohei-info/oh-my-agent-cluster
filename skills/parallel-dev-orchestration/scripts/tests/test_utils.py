# commit_manifest real-git-path tests via tmp_path, no mock.
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import commit_manifest, git_sync_enabled


@pytest.fixture(autouse=True)
def _enable_git_sync(monkeypatch):
    """git 回写默认关闭；本模块大多数用例测的是 git 路径，故默认开启。
    单独验证开关行为的用例自行用 monkeypatch.delenv 关掉。"""
    monkeypatch.setenv("ORCH_GIT_SYNC", "1")


def _git(args, cwd):
    subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _init_repo(tmp_path):
    """Init a temp git repo with an initial commit."""
    _git(["git", "init"], str(tmp_path))
    _git(["git", "config", "user.email", "test@test.com"], str(tmp_path))
    _git(["git", "config", "user.name", "Test"], str(tmp_path))
    f = tmp_path / "manifest.yaml"
    f.write_text("initial\n")
    _git(["git", "add", "."], str(tmp_path))
    _git(["git", "commit", "-m", "init"], str(tmp_path))


def test_commit_success(tmp_path):
    """Changes -> add + commit + push succeed -> True."""
    _init_repo(tmp_path)
    f = tmp_path / "manifest.yaml"
    f.write_text("changed\n")
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
        capture_output=True, text=True
    ).stdout.strip()

    result = commit_manifest("manifest.yaml", "test commit", str(tmp_path))
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
        capture_output=True, text=True
    ).stdout.strip()

    assert result is True
    assert after != before, "should have a new commit"


def test_no_changes_skipped(tmp_path):
    """No changes -> skip -> False."""
    _init_repo(tmp_path)
    result = commit_manifest("manifest.yaml", "no-op", str(tmp_path))
    assert result is False


def test_push_failure_does_not_interrupt(tmp_path):
    """Push fails -> warn but no interrupt -> True."""
    _init_repo(tmp_path)
    _git(["git", "remote", "add", "origin", "/nonexistent/path"], str(tmp_path))
    f = tmp_path / "manifest.yaml"
    f.write_text("changed\n")
    result = commit_manifest("manifest.yaml", "push-fail", str(tmp_path))
    assert result is True, "commit succeeded even though push failed"


def test_add_failure(tmp_path):
    """git add nonexistent path -> False."""
    _init_repo(tmp_path)
    result = commit_manifest("nonexistent.yaml", "fail-add", str(tmp_path))
    assert result is False


def test_sync_off_by_default_skips_git(tmp_path, monkeypatch):
    """ORCH_GIT_SYNC 未设 -> 默认关 -> 跳过 git，不产生新 commit -> False。"""
    monkeypatch.delenv("ORCH_GIT_SYNC", raising=False)
    _init_repo(tmp_path)
    f = tmp_path / "manifest.yaml"
    f.write_text("changed\n")
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
                            capture_output=True, text=True).stdout.strip()
    result = commit_manifest("manifest.yaml", "should-skip", str(tmp_path))
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
                           capture_output=True, text=True).stdout.strip()
    assert result is False
    assert after == before, "默认关时不应产生新 commit"
    assert git_sync_enabled() is False


def test_sync_toggle_truthy_values(monkeypatch):
    """开关识别 1/true/yes/on（大小写无关），其它值视为关。"""
    for v in ("1", "true", "TRUE", "Yes", "on"):
        monkeypatch.setenv("ORCH_GIT_SYNC", v)
        assert git_sync_enabled() is True, v
    for v in ("0", "false", "off", "", "no"):
        monkeypatch.setenv("ORCH_GIT_SYNC", v)
        assert git_sync_enabled() is False, v
