"""SP-A A3 회귀 테스트.

A3 진행 *전* 에 캡처한 be-api 직접 응답 fixtures (tests/fixtures/regression/
before_a3_*.json) 와 새 BFF /sites* 응답이 byte-수준 동일해야 함.

실 DB + falkor + embedder 가 살아있어야 의미가 있음 → RUN_INTEGRATION=1
환경변수가 set 된 경우에만 실행. CI 의 평이한 단위 잡에서는 자동 skip.

배경:
- A2 시점: be-api 가 fe 친화 응답 직접 반환 (projection 포함)
- A3 후:   be-api 가 raw Camp dict 반환, BFF 가 projection
- 검증:    최종 fe 응답 byte 동일 (sort_keys 정규화 후 ==)

⚠️  P6 (2026-05-10): /sites 가 `is_camping_facility` 필터를 적용하기 시작.
    fixtures (before_a3_*) 는 P6 *이전* 캡처 — 펜션 only / unknown only 이
    포함돼 있어 byte 동일이 더 이상 성립 안 함. 필요 시 새 baseline 으로
    재캡처 (RUN_INTEGRATION=1 + 라이브 스택). 그 전까지는 RUN_INTEGRATION
    이 set 돼도 _이 모듈은 skip_ 해도 안전 (회귀 검증 의미 없음).
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "regression"

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION") != "1",
        reason="integration test — set RUN_INTEGRATION=1 (live DB stack)",
    ),
    pytest.mark.skip(
        reason=(
            "P6 (2026-05-10): /sites is_camping_facility filter changed the "
            "response set; fixtures pre-date the filter. Re-capture for new "
            "baseline as needed. Skipping by default to avoid lying about "
            "regressions."
        ),
    ),
]


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_health(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.5)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.5)
    raise RuntimeError(f"health-check timeout for {url}: {last_err}")


@pytest.fixture(scope="module")
def stack() -> Iterator[None]:
    """be-api :8071 + bff :8070 동시 부팅. teardown 시 두 프로세스 모두 정리."""
    procs: list[subprocess.Popen] = []
    if not _port_open("127.0.0.1", 8071):
        a = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "cf_be_api.api:app",
             "--port", "8071", "--log-level", "warning"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(a)
    if not _port_open("127.0.0.1", 8070):
        b = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "cf_be_for_fe.api:app",
             "--port", "8070", "--log-level", "warning"],
            env={**os.environ, "BFF_BE_API_BASE_URL": "http://localhost:8071"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(b)
    try:
        _wait_health("http://localhost:8071/healthz", timeout_s=30)
        _wait_health("http://localhost:8070/healthz", timeout_s=30)
        yield
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def _normalize(d):
    """JSON 비교: 키 순서 무관. 값/타입은 정확히 일치해야."""
    return json.loads(json.dumps(d, sort_keys=True, ensure_ascii=False))


@pytest.mark.parametrize("fixture_name,path", [
    ("before_a3_sites_gangwon.json", "/sites?region=강원"),
    ("before_a3_sites_valley.json", "/sites?concept=valley"),
    ("before_a3_sites_gangwon_valley.json", "/sites?region=강원&concept=valley"),
])
def test_sites_projection_regression(stack, fixture_name, path):
    """`/sites?...` BFF 응답이 사전 캡처와 byte 동일."""
    fpath = FIXTURES / fixture_name
    if not fpath.exists():
        pytest.skip(f"fixture missing: {fixture_name}")
    expected_raw = json.loads(fpath.read_text(encoding="utf-8"))
    if not expected_raw:
        pytest.skip(f"fixture empty (no data captured): {fixture_name}")
    expected = _normalize(expected_raw)
    actual = _normalize(httpx.get(f"http://localhost:8070{path}", timeout=30).json())
    assert actual == expected, (
        f"{fixture_name}: BFF projection 결과가 사전 캡처와 다름 — "
        "byte-identical contract 위반"
    )


def test_site_detail_regression(stack):
    """`/sites/{id}` BFF 응답이 사전 캡처와 byte 동일."""
    fpath = FIXTURES / "before_a3_site_detail.json"
    if not fpath.exists():
        pytest.skip("detail fixture 없음")
    expected_raw = json.loads(fpath.read_text(encoding="utf-8"))
    if not expected_raw or not expected_raw.get("id"):
        pytest.skip("detail fixture 비어있음")
    site_id = expected_raw["id"]
    expected = _normalize(expected_raw)
    actual = _normalize(httpx.get(f"http://localhost:8070/sites/{site_id}", timeout=30).json())
    assert actual == expected


def test_site_search_regression(stack):
    """`/sites/search?q=...` BFF 응답이 사전 캡처와 byte 동일."""
    fpath = FIXTURES / "before_a3_sites_search.json"
    if not fpath.exists():
        pytest.skip("search fixture 없음")
    expected_raw = json.loads(fpath.read_text(encoding="utf-8"))
    expected = _normalize(expected_raw)
    actual = _normalize(httpx.get("http://localhost:8070/sites/search?q=강원&k=5", timeout=30).json())
    assert actual == expected


def test_site_similar_regression(stack):
    """`/sites/{id}/similar` BFF 응답이 사전 캡처와 byte 동일.

    embedding 미생성 시 be-api 가 404 → BFF 가 503 으로 변환. fixture 가
    error dict (`{"detail": ...}`) 면 BFF 도 같은 에러 흐름이어야 하므로
    skip (회귀 의미 없음).
    """
    fpath = FIXTURES / "before_a3_site_similar.json"
    if not fpath.exists():
        pytest.skip("similar fixture 없음")
    expected_raw = json.loads(fpath.read_text(encoding="utf-8"))
    if isinstance(expected_raw, dict) and "detail" in expected_raw:
        pytest.skip("similar fixture 가 error 응답 (embedding 미생성) — 비교 의미 없음")
    if not expected_raw:
        pytest.skip("similar fixture empty")
    detail_fp = FIXTURES / "before_a3_site_detail.json"
    if not detail_fp.exists():
        pytest.skip("detail fixture 없음 (id 못 정함)")
    site_id = json.loads(detail_fp.read_text(encoding="utf-8"))["id"]
    expected = _normalize(expected_raw)
    actual = _normalize(
        httpx.get(f"http://localhost:8070/sites/{site_id}/similar?k=5", timeout=30).json(),
    )
    assert actual == expected
