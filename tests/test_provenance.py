"""M4.19-20 / M4.52 dirty-code provenance tests in a temp git repo.

- clean repo -> code_dirty=false, patch empty
- tracked modification -> code_dirty=true, patch present, patch_sha256 matches
- untracked relevant source -> captured in the patch (reproducible), not
  silently dropped
- dirty-but-no-patch (unreadable untracked) -> ProvenanceError (M4.19)
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from pql.registry.provenance import ProvenanceError, git_state


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def _init_repo(root: Path) -> Path:
    (root / "src" / "pql").mkdir(parents=True)
    (root / "src" / "pql" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_clean_repo_code_dirty_false(tmp_path):
    root = _init_repo(Path(tmp_path))
    st = git_state(root / "experiments")
    assert st.code_dirty is False
    assert st.commit
    assert st.patch == ""
    assert st.patch_sha256 == ""


def test_tracked_modification_dirty_with_patch(tmp_path):
    root = _init_repo(Path(tmp_path))
    (root / "src" / "pql" / "mod.py").write_text("x = 2\n", encoding="utf-8")
    st = git_state(root / "experiments")
    assert st.code_dirty is True
    assert "mod.py" in st.patch
    assert "x = 2" in st.patch
    assert st.patch_sha256 == hashlib.sha256(st.patch.encode()).hexdigest()
    assert (root / "src" / "pql" / "mod.py") in [root / p for p in st.dirty_paths]


def test_untracked_relevant_source_captured_in_patch(tmp_path):
    root = _init_repo(Path(tmp_path))
    # an untracked research source under src/ (git diff alone would drop it)
    (root / "src" / "pql" / "new_signal.py").write_text("def f():\n    return 1\n",
                                                        encoding="utf-8")
    st = git_state(root / "experiments")
    assert st.code_dirty is True
    # the untracked file's content is part of the reproducible patch
    assert "new_signal.py" in st.patch
    assert "def f():" in st.patch
    assert st.patch_sha256


def test_untracked_out_of_scope_not_dirty(tmp_path):
    root = _init_repo(Path(tmp_path))
    (root / "experiments").mkdir()
    (root / "experiments" / "EXP-0001").mkdir()
    (root / "experiments" / "EXP-0001" / "manifest.yaml").write_text("x: 1\n",
                                                                    encoding="utf-8")
    # experiment outputs are provenance, not research code -> not dirty
    st = git_state(root / "experiments")
    assert st.code_dirty is False


def test_staged_tracked_modification_dirty_with_patch(tmp_path):
    """git add (staged) must still be recorded as dirty with a reproducible
    patch; `git diff HEAD` captures staged AND unstaged edits (M4 rev2)."""
    root = _init_repo(Path(tmp_path))
    (root / "src" / "pql" / "mod.py").write_text("x = 3\n", encoding="utf-8")
    _git(root, "add", "src/pql/mod.py")  # STAGED, not committed
    st = git_state(root / "experiments")
    assert st.code_dirty is True
    assert "mod.py" in st.patch
    assert "x = 3" in st.patch
    assert st.patch_sha256 == hashlib.sha256(st.patch.encode()).hexdigest()


def test_staged_and_unstaged_combined_into_head_diff(tmp_path):
    root = _init_repo(Path(tmp_path))
    f = root / "src" / "pql" / "mod.py"
    f.write_text("x = 4\n", encoding="utf-8")
    _git(root, "add", "src/pql/mod.py")  # staged x=4
    f.write_text("x = 5\n", encoding="utf-8")  # unstaged x=5 on top
    st = git_state(root / "experiments")
    assert st.code_dirty is True
    # `git diff HEAD` = HEAD -> worktree: the FINAL state (x=5) is what the code
    # ran, and it is what the patch reproduces.
    assert "x = 5" in st.patch
    assert "x = 1" in st.patch  # the HEAD baseline is the removed line


def _apply_patch(root: Path, patch: str) -> None:
    patch_file = root / "_provenance.patch"
    patch_file.write_text(patch, encoding="utf-8")
    subprocess.run(["git", "apply", str(patch_file)], cwd=str(root),
                   check=True, capture_output=True)


def test_patch_reconstructs_worktree_from_commit(tmp_path):
    """Applying the recorded patch to the recorded code_commit must reproduce
    the exact worktree that produced the run (staged + unstaged + untracked)."""
    root = _init_repo(Path(tmp_path))
    f = root / "src" / "pql" / "mod.py"
    f.write_text("x = 4\n", encoding="utf-8")
    _git(root, "add", "src/pql/mod.py")  # staged
    f.write_text("x = 5\n", encoding="utf-8")  # unstaged
    (root / "src" / "pql" / "new_signal.py").write_text("def f():\n    return 1\n",
                                                        encoding="utf-8")  # untracked

    st = git_state(root / "experiments")
    assert st.code_dirty is True

    # reset the worktree to the recorded commit (tracked + untracked)
    _git(root, "reset", "--hard", "-q", st.commit)
    _git(root, "clean", "-fd", "-q")
    assert (root / "src" / "pql" / "mod.py").read_text() == "x = 1\n"
    assert not (root / "src" / "pql" / "new_signal.py").exists()

    _apply_patch(root, st.patch)
    assert (root / "src" / "pql" / "mod.py").read_text() == "x = 5\n"
    assert (root / "src" / "pql" / "new_signal.py").read_text() == "def f():\n    return 1\n"


def test_commit_is_stripped_40_hex(tmp_path):
    root = _init_repo(Path(tmp_path))
    st = git_state(root / "experiments")
    assert st.commit == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True,
        text=True, check=True).stdout.strip()
    assert len(st.commit) == 40
    assert all(c in "0123456789abcdef" for c in st.commit)


def test_dirty_untracked_unreadable_raises(tmp_path, monkeypatch):
    root = _init_repo(Path(tmp_path))
    (root / "src" / "pql" / "locked.py").write_text("x = 1\n", encoding="utf-8")


    def _broken_read(fp):
        raise OSError("cannot read")

    monkeypatch.setattr(Path, "read_bytes", _broken_read)
    with pytest.raises(ProvenanceError):
        git_state(root / "experiments")