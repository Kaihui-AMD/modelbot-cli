"""Local pre-checks before uploading a patch: the server repeats them (and the runner is
authoritative), but failing here saves a round trip and a queue slot."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_DIFF = re.compile(r'^diff --git (?:"?a/(.+?)"?) (?:"?b/(.+?)"?)$')
_SIDE = re.compile(r"^(?:rename|copy) (?:from|to) (.+)$")
_SPECIAL_MODE = re.compile(r"^(?:new file mode|deleted file mode|old mode|new mode) (120000|160000)$")


@dataclass
class LocalCheck:
    ok: bool
    problems: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def patch_paths(text: str) -> tuple[list[str], list[str]]:
    """Paths touched by a git-style patch, and other problems found in its headers."""
    paths, problems = [], []
    for line in text.splitlines():
        m = _DIFF.match(line)
        if m:
            paths += [m.group(1), m.group(2)]
            continue
        m = _SIDE.match(line)
        if m:
            paths.append(m.group(1).strip('"'))
            continue
        if _SPECIAL_MODE.match(line):
            problems.append(f"symlinks and submodules are not allowed ({line})")
        if line.startswith("GIT binary patch") or (line.startswith("Binary files ") and line.endswith(" differ")):
            problems.append("binary changes are not allowed")
    seen = []
    for p in paths:
        if p not in seen:
            seen.append(p)
    return seen, problems


def check_local(patch: Path, allowed: list[str], max_bytes: int, base_dir: Path | None = None) -> LocalCheck:
    data = patch.read_bytes()
    if not data:
        return LocalCheck(False, ["the patch is empty"])
    if len(data) > max_bytes:
        return LocalCheck(False, [f"the patch is {len(data)} bytes, the limit is {max_bytes}"])
    paths, problems = patch_paths(data.decode("utf-8", "replace"))
    if not paths:
        problems.append("no `diff --git` headers found; create the patch with `git diff`")
    for p in paths:
        if p.startswith("/") or ".." in p.split("/") or not any(p.startswith(a) for a in allowed):
            problems.append(f"{p}: outside the allowed paths ({', '.join(allowed)})")
    if base_dir is not None and not problems:
        proc = subprocess.run(["git", "-C", str(base_dir), "apply", "--check", str(patch.resolve())],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            problems.append("does not apply to the base checkout: " + proc.stderr.strip()[-1000:])
    return LocalCheck(not problems, problems, paths)
