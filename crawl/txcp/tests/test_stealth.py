"""Stealth — UA pool ≥5, delay 1.5–3.0s 범위 (NFR Polite)."""
from __future__ import annotations

import statistics

from tkcp_crawl.stealth import UA_POOL, DelayConfig, average_delay


def test_ua_pool_min_5():
    """V-1: camfit-puller 동형 ≥5 UA."""
    assert len(UA_POOL) >= 5
    # 모두 distinct
    assert len(set(UA_POOL)) == len(UA_POOL)


def test_delay_config_default_1_5_to_3_0():
    cfg = DelayConfig()
    assert cfg.min_s == 1.5
    assert cfg.max_s == 3.0
    assert cfg.min_s < cfg.max_s


def test_average_delay_in_expected_range():
    avg = average_delay(samples=200)
    # uniform [1.5, 3.0] 기댓값 = 2.25, 200 sample 시 ±0.15 마진 충분
    assert 2.05 <= avg <= 2.45


def test_average_delay_respects_custom_config():
    cfg = DelayConfig(min_s=0.5, max_s=1.0)
    avg = average_delay(samples=200, cfg=cfg)
    assert 0.6 <= avg <= 0.9
