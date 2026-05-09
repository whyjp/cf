"""Shared resolver / auto-builder for the etago Go binary.

Two adapters need the binary — ETA (drive-time) and Geocode (Naver NCP +
Kakao K1). Centralizing the resolution + auto-build means a fresh checkout
becomes runnable with no manual `go build` step: import either adapter and
the binary will be produced on demand if it's missing or stale.

Resolution order:

1. ``$ETAGO_BIN`` env override (explicit path).
2. ``etago`` on ``$PATH`` (``shutil.which``).
3. ``<repo>/etago/etago.exe`` or ``<repo>/etago/etago``.

Auto-build trigger: candidates 2 + 3 missing OR the binary is older than
the newest ``.go`` file under ``etago/``. Build is invoked with the
explicit ``go.exe`` path even when PATH is loaded — corporate / shimmed
shells sometimes mask shutil.which() while still exposing GOROOT.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from threading import Lock
from typing import Optional

_THIS = Path(__file__).resolve().parent
# adapters/ → camfit_puller/ → src/ → camfit-puller/ → cf/
_REPO_ROOT = _THIS.parents[3]
_ETAGO_DIR = _REPO_ROOT / "etago"
_BIN_NAMES = ("etago.exe", "etago") if sys.platform == "win32" else ("etago",)

_BUILD_LOCK = Lock()  # don't race two pipeline stages building the same exe


class EtagoUnavailable(RuntimeError):
    """Raised when the etago binary cannot be located AND auto-build failed."""


def find_go() -> Optional[str]:
    """Locate ``go.exe`` even when the calling shell hasn't sourced PATH.

    Order: ``$GOROOT\\bin\\go(.exe)`` → ``shutil.which`` → common Windows
    install at ``Program Files\\Go``. Returns the full path or None.
    """
    goroot = os.environ.get("GOROOT", "").strip()
    if goroot:
        for cand in (Path(goroot) / "bin" / "go.exe", Path(goroot) / "bin" / "go"):
            if cand.exists():
                return str(cand)
    on_path = shutil.which("go")
    if on_path:
        return on_path
    if sys.platform == "win32":
        for base in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Go",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Go",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Go",
        ):
            cand = base / "bin" / "go.exe"
            if cand.exists():
                return str(cand)
    else:
        for cand in (Path("/usr/local/go/bin/go"), Path("/usr/lib/go/bin/go")):
            if cand.exists():
                return str(cand)
    return None


def _existing_bin() -> Optional[Path]:
    explicit = os.environ.get("ETAGO_BIN", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    on_path = shutil.which("etago")
    if on_path:
        return Path(on_path)
    for name in _BIN_NAMES:
        cand = _ETAGO_DIR / name
        if cand.exists():
            return cand
    return None


def _newest_source_mtime() -> float:
    newest = 0.0
    if not _ETAGO_DIR.exists():
        return newest
    for p in _ETAGO_DIR.rglob("*.go"):
        try:
            m = p.stat().st_mtime
            if m > newest:
                newest = m
        except OSError:
            continue
    return newest


def _is_stale(bin_path: Path) -> bool:
    """True if any *.go in the etago tree is newer than the binary."""
    try:
        bin_mtime = bin_path.stat().st_mtime
    except OSError:
        return True
    return _newest_source_mtime() > bin_mtime


def _build(go_exe: str) -> Optional[Path]:
    """Run ``go build`` against the etago module. Returns built-binary path or None."""
    out_name = "etago.exe" if sys.platform == "win32" else "etago"
    out_path = _ETAGO_DIR / out_name
    if not (_ETAGO_DIR / "go.mod").exists():
        return None
    cmd = [go_exe, "build", "-o", str(out_path), "./cmd/etago"]
    try:
        subprocess.run(
            cmd, cwd=str(_ETAGO_DIR),
            check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=180,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return out_path if out_path.exists() else None


def resolve_etago_bin(*, auto_build: bool = True) -> str:
    """Return a path to a runnable etago binary, building if necessary.

    With ``auto_build=False`` only the existing-binary path is consulted.
    Raises ``EtagoUnavailable`` if no binary can be located/built.
    """
    bin_path = _existing_bin()
    if bin_path and not (auto_build and _is_stale(bin_path)):
        return str(bin_path)

    if not auto_build:
        if bin_path:
            return str(bin_path)
        raise EtagoUnavailable(
            "etago binary not found. Set $ETAGO_BIN, put `etago` on PATH, "
            "or run `go build -o etago.exe ./cmd/etago` in <repo>/etago."
        )

    go_exe = find_go()
    if not go_exe:
        if bin_path:  # stale but exists — better than nothing
            return str(bin_path)
        raise EtagoUnavailable(
            "etago binary missing and `go` not found. Install Go from "
            "https://go.dev/dl/ (Windows: usually C:\\Program Files\\Go) "
            "and ensure GOROOT or PATH points at it, or set $ETAGO_BIN to "
            "a prebuilt binary."
        )

    with _BUILD_LOCK:
        # Re-check inside the lock — another thread may have built it.
        bin_path = _existing_bin()
        if bin_path and not _is_stale(bin_path):
            return str(bin_path)
        built = _build(go_exe)
        if built:
            return str(built)

    if bin_path:
        # Build failed but we have a stale binary; better than crashing.
        return str(bin_path)
    raise EtagoUnavailable(
        f"etago auto-build failed (go: {go_exe}). "
        f"Try manually: cd {_ETAGO_DIR} && go build -o etago.exe ./cmd/etago"
    )
