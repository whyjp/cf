from cf_backend.domain.models import Camp, Region, Review
from cf_backend.domain.embed_text import build_embed_text, text_hash


def _mk(**kw):
    base = dict(id="x", name="X", region=Region(sido="강원", sigungu="평창군"))
    base.update(kw)
    return Camp(**base)


def test_includes_name_and_address():
    c = _mk(address="강원 평창군 진부면 1-2", brief="좋은곳")
    out = build_embed_text(c, [])
    assert "X" in out
    assert "강원 평창군 진부면 1-2" in out
    assert "좋은곳" in out


def test_deterministic():
    c = _mk(brief="b", description="d")
    a = build_embed_text(c, [])
    b = build_embed_text(c, [])
    assert a == b


def test_top_reviews_sorted_by_score():
    c = _mk()
    rs = [
        Review(id="r1", camp_id="x", text="low", score=10),
        Review(id="r2", camp_id="x", text="high", score=99),
    ]
    out = build_embed_text(c, rs)
    assert out.find("high") < out.find("low")


def test_text_hash_changes_when_content_changes():
    c1 = _mk(brief="a")
    c2 = _mk(brief="b")
    assert text_hash(build_embed_text(c1, [])) != text_hash(build_embed_text(c2, []))
