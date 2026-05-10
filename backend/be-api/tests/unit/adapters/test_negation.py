from cf_be_api.adapters.extract.negation import HeuristicNegationExtractor
from cf_be_api.domain.models import Concept


class FakeRepo:
    def all(self):
        return [
            Concept(id="kids", name="키즈", source="manual"),
            Concept(id="pets", name="반려동물", source="manual"),
            Concept(id="valley", name="계곡", source="manual"),
        ]
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, *_): return []


def test_positive_mention_yields_plus_one():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("아이들과 함께하는 키즈 캠핑이 좋아요")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("kids") == 1


def test_negation_yields_minus_one():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("반려동물 입장 불가합니다.")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("pets") == -1


def test_no_kids_phrasing():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("노키즈 캠핑장 입니다. 아이들 입장 안됩니다.")
    polarities = {c: p for c, p, _ in out}
    assert polarities.get("kids") == -1


def test_evidence_snippet_returned():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("계곡이 정말 좋아요!")
    by_id = {c: (p, ev) for c, p, ev in out}
    assert "valley" in by_id
    pol, ev = by_id["valley"]
    assert pol == 1
    assert "계곡" in ev


def test_no_match_returns_empty():
    ex = HeuristicNegationExtractor(FakeRepo())
    out = ex.extract_with_polarity("일반 텍스트, concept 없음.")
    assert out == []
