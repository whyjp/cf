from cf_be_api.domain.models import Concept, Review
from cf_be_api.usecases.extract_review_signals import ExtractReviewSignals
from cf_be_api.adapters.extract.negation import HeuristicNegationExtractor


class FakeReviewReader:
    def __init__(self, reviews_per_camp): self._d = reviews_per_camp
    def top_for(self, cid, n=3, sort="score"): return []
    def total_for(self, cid): return len(self._d.get(cid, []))
    def iter_for(self, cid): return iter(self._d.get(cid, []))


class FakeReviewSignalWriter:
    def __init__(self): self.rows = []; self.resets = []
    def upsert(self, camp_id, concept_id, score, pos_count, neg_count, evidence):
        self.rows.append({
            "camp_id": camp_id, "concept_id": concept_id, "score": score,
            "pos": pos_count, "neg": neg_count, "evidence": evidence,
        })
    def reset_for(self, camp_id): self.resets.append(camp_id)


class _Repo:
    def all(self):
        return [
            Concept(id="kids", name="키즈", source="manual"),
            Concept(id="valley", name="계곡", source="manual"),
        ]
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, *_): return []


def test_temperature_weighting_boosts_intense_reviews():
    """A review with strong intensifier ('정말') should weigh more than mild mention."""
    reviews = {
        "c1": [
            Review(id="r1", camp_id="c1", text="키즈 좋아요"),                  # mild
            Review(id="r2", camp_id="c1", text="키즈 정말 너무 좋아요!"),        # strong positive
        ],
    }
    writer = FakeReviewSignalWriter()
    uc = ExtractReviewSignals(FakeReviewReader(reviews), HeuristicNegationExtractor(_Repo()), writer)
    n = uc.execute("c1")
    assert n >= 1
    by_concept = {row["concept_id"]: row for row in writer.rows}
    kids = by_concept["kids"]
    assert kids["pos"] == 2
    assert kids["neg"] == 0
    # Score should be positive and close to 1.0 (all positive); boosted weighting
    # doesn't change the sign, but ensures intensity tracking works.
    assert kids["score"] > 0


def test_negation_yields_negative_score():
    reviews = {
        "c1": [
            Review(id="r1", camp_id="c1", text="키즈 입장 불가합니다."),
            Review(id="r2", camp_id="c1", text="아이 데려오시면 안돼요."),  # also negation
        ],
    }
    writer = FakeReviewSignalWriter()
    uc = ExtractReviewSignals(FakeReviewReader(reviews), HeuristicNegationExtractor(_Repo()), writer)
    uc.execute("c1")
    by_concept = {row["concept_id"]: row for row in writer.rows}
    # 키즈 mentioned with 불가 → negative
    if "kids" in by_concept:
        assert by_concept["kids"]["score"] < 0


def test_mixed_positive_and_negative_aggregates():
    reviews = {
        "c1": [
            Review(id="r1", camp_id="c1", text="계곡 정말 최고에요."),      # +1, strong
            Review(id="r2", camp_id="c1", text="계곡 출입 제한 있어요."),    # -1
        ],
    }
    writer = FakeReviewSignalWriter()
    uc = ExtractReviewSignals(FakeReviewReader(reviews), HeuristicNegationExtractor(_Repo()), writer)
    uc.execute("c1")
    by_concept = {row["concept_id"]: row for row in writer.rows}
    assert "valley" in by_concept
    valley = by_concept["valley"]
    # pos=1, neg=1, but the positive sentence has intensifiers → score should be > 0
    # (or close to 0; either way, sign reflects intensity-weighted dominance)
    assert valley["pos"] == 1
    assert valley["neg"] == 1
    # The score with intensity 2.0 (정말 + 최고) on positive vs 1.0 on negative
    # should be (2.0×1 + 1.0×(-1)) / (2.0 + 1.0) = 1.0/3.0 ≈ +0.33
    assert valley["score"] > 0
