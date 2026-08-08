"""M4 research provenance capture (D7 / M4.18-21).

Responsible for:
- git code state (commit, dirty, patch, patch sha256) including relevant
  untracked source/config files (git diff alone silently drops untracked code);
- dependency versions (vectorbt / pandas / numpy);
- deterministic config_sha256 over the actual file CONTENTS of the strategy
  spec + validation gates + cost + market + instrument configs (never over
  file paths alone, so a config whose version id changes but content drifts is
  still caught).

Definition of "code dirty": tracked or untracked changes under the research
code/config scope (src/, config/, strategies/, tests/). Experiment outputs
(experiments/, experiment_registry.parquet, reports/) are PROVENANCE, not the
code that produced the result, so they never make a run "dirty".
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Dirs that count as research code/config for the dirty determination. A change
# anywhere else (experiments/, reports/, derived parquet) is an output, not a
# code drift, and must not mark a run non-reproducible.
_DIRTY_SCOPE = ("src/", "config/", "strategies/", "tests/")


class ProvenanceError(RuntimeError):
    """Raised when research provenance cannot be captured completely."""


@dataclass(frozen=True)
class GitState:
    commit: str
    code_dirty: bool
    dirty_paths: tuple[str, ...] = ()
    patch: str = ""
    patch_sha256: str = ""


def _run_git(repo_root: Path, *args: str) -> tuple[str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ProvenanceError(
            f"git {' '.join(args)} failed: {proc.stderr.strip()}"
        )
    return proc.stdout, proc.stderr


def repo_root(experiments_root: str | Path) -> Path:
    """Walk up from experiments_root to the git working tree root."""
    cur = Path(experiments_root).resolve()
    for d in [cur, *cur.parents]:
        if (d / ".git").exists():
            return d
    raise ProvenanceError(f"no git repository found above {experiments_root}")


def _in_scope(rel_path: str) -> bool:
    return rel_path.startswith(_DIRTY_SCOPE)


def _untracked_in_scope(repo_root: Path) -> list[str]:
    out, _ = _run_git(repo_root, "status", "--porcelain", "--untracked-files=all")
    paths: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        code = line[:2].strip()
        rel = line[3:]
        if code == "??" and _in_scope(rel):
            paths.append(rel)
    return sorted(paths)


def git_state(experiments_root: str | Path) -> GitState:
    """Capture current git research-code state.

    - code_commit = stripped `git rev-parse HEAD` (40-hex, no trailing newline).
    - code_dirty = tracked or untracked change under the code scope.
    - patch = `git diff HEAD -- <scope>` (HEAD -> final worktree, which already
      includes BOTH staged and unstaged changes) plus, for each untracked
      code-scope file, a proper `git apply`-able new-file diff (blob hash +
      hunk header). Applying this patch to the recorded code_commit therefore
      reconstructs the exact research code that produced the run. If the repo
      is dirty but the patch is empty/missing, a ProvenanceError is raised
      (a `code_dirty: true` without a reproducible patch cannot be reproduced).
    """
    root = repo_root(experiments_root)
    commit, _ = _run_git(root, "rev-parse", "HEAD")
    commit = commit.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ProvenanceError(f"unexpected git commit format: {commit!r}")

    # `git diff HEAD -- <scope>` = HEAD -> worktree, covering staged AND
    # unstaged tracked edits in one well-formed, git-apply-able diff (M4 rev2).
    diff_head, _ = _run_git(root, "diff", "HEAD", "--", *_DIRTY_SCOPE)
    tracked_dirty = bool(diff_head.strip())

    untracked = _untracked_in_scope(root)
    code_dirty = tracked_dirty or bool(untracked)

    patch_parts: list[str] = [diff_head.rstrip("\n")] if diff_head.strip() else []
    for rel in untracked:
        patch_parts.append(_untracked_diff(root, rel))

    patch = "\n".join(p for p in patch_parts if p)
    if code_dirty and not patch:
        raise ProvenanceError(
            "repo is dirty but no reproducible patch could be captured; "
            "refusing to record a non-reproducible run"
        )
    patch_sha256 = hashlib.sha256(patch.encode("utf-8")).hexdigest() if patch else ""
    return GitState(
        commit=commit,
        code_dirty=code_dirty,
        dirty_paths=tuple(sorted([*_untracked_in_scope(root), *tracked_dirty_paths(root)])),
        patch=patch,
        patch_sha256=patch_sha256,
    )


def tracked_dirty_paths(repo_root: Path) -> list[str]:
    out, _ = _run_git(repo_root, "status", "--porcelain")
    paths: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        code = line[:2].strip()
        rel = line[3:]
        if code in ("M", "A", "D", "R", "C") and _in_scope(rel):
            paths.append(rel)
    return sorted(set(paths))


def _untracked_diff(repo_root: Path, rel: str) -> str:
    """A proper `git apply`-able new-file diff for an untracked code-scope file,
    so the recorded patch reconstructs its content (blob hash + hunk header)."""
    fp = repo_root / rel
    try:
        content = fp.read_bytes()
    except OSError as exc:  # pragma: no cover - defensive
        raise ProvenanceError(
            f"repo dirty with untracked {rel} but cannot read it: {exc}"
        ) from exc
    blob, _ = _run_git(repo_root, "hash-object", "--", str(fp))
    blob = blob.strip()
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()
    n = len(lines)
    body = "\n".join("+" + line for line in lines)
    return (
        f"diff --git a/{rel} b/{rel}\n"
        f"new file mode 100644\n"
        f"index 0000000..{blob}\n"
        f"--- /dev/null\n"
        f"+++ b/{rel}\n"
        f"@@ -0,0 +1,{n} @@\n"
        f"{body}\n"
    )


def dependency_versions() -> dict[str, str]:
    """vectorbt / pandas / numpy versions (D7 provenance)."""
    import importlib.metadata

    out: dict[str, str] = {}
    for pkg in ("vectorbt", "pandas", "numpy"):
        try:
            out[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            out[pkg] = "unknown"
    return out


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def config_hashes(
    spec_path: str | Path,
    gates_path: str | Path,
    cost_path: str | Path,
    market_path: str | Path,
    instrument_paths: list[str | Path],
) -> dict[str, Any]:
    """Per-file sha256 over actual file contents, plus an aggregate
    config_sha256. Deterministic: aggregation order is fixed (spec, gates,
    cost, market, then instruments sorted by path)."""
    files: list[tuple[str, Path]] = [(str(spec_path), Path(spec_path))]
    files.append((str(gates_path), Path(gates_path)))
    files.append((str(cost_path), Path(cost_path)))
    files.append((str(market_path), Path(market_path)))
    for p in sorted(instrument_paths, key=str):
        files.append((str(p), Path(p)))

    per_file: dict[str, str] = {}
    blob = hashlib.sha256()
    for label, path in files:
        sha = _file_sha256(path)
        per_file[label] = sha
        blob.update(label.encode("utf-8"))
        blob.update(b"\x00")
        blob.update(sha.encode("utf-8"))
        blob.update(b"\x00")
    return {"per_file": per_file, "config_sha256": blob.hexdigest()}