"""C5 root_redirect — UA + cookie 기반 진입 라우팅 단위 테스트.

fe/dist/index.html 이 없는 환경에서도 UA mobile + 데스크톱 UA + cookie
override 세 분기를 모두 검증.
"""
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import cf_be_for_fe.api as api_mod


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    # fe_dir 를 tmp 로 가리키고 index.html stub 만 하나 둔다 — FileResponse
    # 가 read 할 수 있게.
    monkeypatch.setattr(api_mod._settings, "fe_dir", tmp_path)
    (tmp_path / "index.html").write_text("<!doctype html><html>desktop</html>")
    return TestClient(api_mod.app, follow_redirects=False)


IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def test_mobile_ua_redirects_to_m_html(client):
    r = client.get("/", headers={"user-agent": IPHONE_UA})
    assert r.status_code == 302
    assert r.headers["location"] == "/m.html"


def test_desktop_ua_serves_index(client):
    r = client.get("/", headers={"user-agent": DESKTOP_UA})
    assert r.status_code == 200
    assert "desktop" in r.text


def test_mobile_ua_with_prefer_desktop_serves_index(client):
    r = client.get(
        "/",
        headers={"user-agent": IPHONE_UA},
        cookies={"prefer_desktop": "1"},
    )
    assert r.status_code == 200
    assert "desktop" in r.text


def test_desktop_ua_with_prefer_mobile_redirects(client):
    r = client.get(
        "/",
        headers={"user-agent": DESKTOP_UA},
        cookies={"prefer_mobile": "1"},
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/m.html"


def test_android_ua_redirects(client):
    r = client.get(
        "/",
        headers={"user-agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537"},
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/m.html"


def test_empty_ua_serves_index(client):
    r = client.get("/", headers={"user-agent": ""})
    assert r.status_code == 200
