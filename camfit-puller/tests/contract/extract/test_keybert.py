"""Contract tests for ConceptExtractor port — covers KeyBERT and Mock impls.

KeyBERT is parametrized with the MockEmbedder so the test is deterministic
(no model download). Real ko-sroberta validation happens in integration tests."""
import numpy as np
from camfit_puller.adapters.embed.mock import MockEmbedder
from camfit_puller.adapters.extract.keybert import KeyBertExtractor
from camfit_puller.adapters.extract.mock import MockConceptExtractor
from camfit_puller.domain.models import Concept


class FakeRepo:
    def __init__(self, cs): self._c = cs
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, *_): return []
    def all(self): return self._c


def _vocab():
    return [
        Concept(id="kids", name="키즈캠핑", source="manual"),
        Concept(id="valley", name="계곡", source="manual"),
        Concept(id="trampoline", name="트램펄린", source="manual"),
    ]


def test_keybert_extracts_some_top_k():
    repo = FakeRepo(_vocab())
    ext = KeyBertExtractor(MockEmbedder(), repo)
    out = ext.extract("계곡과 키즈가 좋은 캠프", top_k=3, min_score=-1.0)
    # With MockEmbedder, scores are essentially random. We assert structural
    # contract only: returns up to top_k items with valid ids/scores.
    assert len(out) <= 3
    for cid, score in out:
        assert cid in {"kids", "valley", "trampoline"}
        assert isinstance(score, float)


def test_keybert_returns_empty_for_empty_vocab():
    ext = KeyBertExtractor(MockEmbedder(), FakeRepo([]))
    out = ext.extract("any text", top_k=5)
    assert out == []


def test_keybert_min_score_filters_low_sim():
    repo = FakeRepo(_vocab())
    ext = KeyBertExtractor(MockEmbedder(), repo)
    # min_score=2.0 is impossible with normalized vectors (max sim = 1)
    out = ext.extract("anything", top_k=5, min_score=2.0)
    assert out == []


def test_keybert_vocab_caches():
    repo = FakeRepo(_vocab())
    ext = KeyBertExtractor(MockEmbedder(), repo)
    v1 = ext.vocabulary()
    v2 = ext.vocabulary()
    assert v1 is v2  # same list object → cache hit
    ext.invalidate()
    v3 = ext.vocabulary()
    assert v3 is not v1  # invalidate forced refresh


def test_mock_extractor_substring_match():
    vocab = _vocab()
    ext = MockConceptExtractor(vocab)
    out = ext.extract("계곡과 키즈캠핑 좋은 곳", top_k=10)
    ids = {cid for cid, _ in out}
    assert "kids" in ids
    assert "valley" in ids
    # trampoline NOT in text → not returned
    assert "trampoline" not in ids


def test_mock_extractor_min_score_filter():
    vocab = _vocab()
    ext = MockConceptExtractor(vocab)
    # Whole-word matches give 1.0; partial matches 0.5
    out = ext.extract("키즈캠핑 좋다", top_k=10, min_score=0.6)
    # only kids (1.0) survives the 0.6 cutoff
    ids = {cid for cid, _ in out}
    assert "kids" in ids
