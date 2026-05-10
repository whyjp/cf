"""etago_adapter — subprocess wrapping + cache + concurrency cap.

We don't depend on the live etago binary in unit tests. Instead we monkeypatch
``asyncio.create_subprocess_exec`` with an in-memory fake that records call
order so we can assert concurrency/cache behavior.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from camfit_crawl import etago_adapter as ea


class _FakeProc:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0, delay: float = 0.0):
        self._out = stdout
        self._err = stderr
        self.returncode = returncode
        self._delay = delay

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._out, self._err

    def kill(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _provide_bin(monkeypatch, tmp_path):
    fake_bin = tmp_path / "etago-fake.exe"
    fake_bin.write_bytes(b"")
    monkeypatch.setenv("ETAGO_BIN", str(fake_bin))
    yield


@pytest.mark.asyncio
async def test_fetch_parses_etago_json(monkeypatch):
    payload = json.dumps({"start": "강남역", "end": "수원시청", "duration_min": 31, "source": "kakao"}).encode()

    async def fake_create(*args, **kw):
        return _FakeProc(stdout=payload + b"\n")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    client = ea.EtagoClient()
    r = await client.fetch("강남역", "수원시청")
    assert r.minutes == 31
    assert r.source == "kakao"
    assert r.error is None
    assert r.start == "강남역"
    assert r.end == "수원시청"


@pytest.mark.asyncio
async def test_cache_skips_repeat_subprocess(monkeypatch):
    payload = json.dumps({"start": "A", "end": "B", "duration_min": 7, "source": "kakao"}).encode()
    calls = 0

    async def fake_create(*args, **kw):
        nonlocal calls
        calls += 1
        return _FakeProc(stdout=payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    client = ea.EtagoClient()
    r1 = await client.fetch("A", "B")
    r2 = await client.fetch("A", "B")
    assert calls == 1, "second call must hit the cache"
    assert r1.minutes == 7 and r2.minutes == 7


@pytest.mark.asyncio
async def test_nonzero_exit_records_error(monkeypatch):
    async def fake_create(*args, **kw):
        return _FakeProc(stdout=b"", stderr=b"etago: external failure", returncode=3)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    client = ea.EtagoClient()
    r = await client.fetch("X", "Y")
    assert r.minutes is None
    assert r.error and "external failure" in r.error


@pytest.mark.asyncio
async def test_timeout_kills_subprocess(monkeypatch):
    async def fake_create(*args, **kw):
        return _FakeProc(stdout=b"never", delay=10.0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    client = ea.EtagoClient(default_timeout_s=0.05)
    r = await client.fetch("S", "E", timeout_s=0.05)
    assert r.minutes is None
    assert r.error == "timeout"


@pytest.mark.asyncio
async def test_concurrency_cap_holds(monkeypatch):
    payload = json.dumps({"start": "x", "end": "y", "duration_min": 1, "source": "k"}).encode()
    in_flight = 0
    peak = 0

    async def fake_create(*args, **kw):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return _FakeProc(stdout=payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    client = ea.EtagoClient()
    dests = [(f"id-{i}", f"place-{i}") for i in range(20)]
    out = await client.fetch_many("origin", dests, concurrency=4)
    assert len(out) == 20
    assert peak <= 4, f"semaphore breached: peak={peak}"


def test_resolve_bin_returns_env_override(monkeypatch, tmp_path):
    p = tmp_path / "custom-etago"
    p.write_bytes(b"")
    monkeypatch.setenv("ETAGO_BIN", str(p))
    assert ea._resolve_bin() == str(p)


def test_unavailable_when_no_bin(monkeypatch):
    monkeypatch.setenv("ETAGO_BIN", "definitely-missing-xyz.exe")
    monkeypatch.setattr(ea.shutil, "which", lambda _: None)
    monkeypatch.setattr(ea, "_REPO_ROOT_GUESS", ea.Path("/nonexistent-root-xyz"))
    with pytest.raises(ea.EtagoUnavailable):
        ea.EtagoClient()
