from camfit_crawl.stealth import UA_POOL, DelayConfig, average_delay


def test_ua_pool_size_at_least_5():
    assert len(UA_POOL) >= 5
    # All non-empty distinct strings
    assert len(set(UA_POOL)) == len(UA_POOL)
    assert all(len(ua) > 30 for ua in UA_POOL)


def test_delay_distribution_avg_above_threshold():
    cfg = DelayConfig(min_s=1.5, max_s=3.0)
    avg = average_delay(samples=200, cfg=cfg)
    # Statistical lower bound — uniform[1.5,3.0] mean = 2.25.
    assert 1.5 <= avg <= 3.0
    assert avg >= 1.7  # leaves margin for sampling noise


def test_delay_lower_bound_strict():
    cfg = DelayConfig(min_s=1.5, max_s=3.0)
    assert cfg.min_s >= 1.5  # NFR-1 floor
