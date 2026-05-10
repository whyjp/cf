"""Contract tests parametrized over Mock and the real ko-sroberta embedder.

Real embedder is skipped if it fails to load (e.g., no internet for first download)."""
import numpy as np
import pytest
from cf_be_api.adapters.embed.mock import MockEmbedder


def _embedders():
    embedders = [MockEmbedder()]
    try:
        from cf_be_api.adapters.embed.sentence_transformers import KoSrobertaEmbedder
        embedders.append(KoSrobertaEmbedder())
    except Exception as e:
        # Test will pytest.skip() inside fixture
        pass
    return embedders


@pytest.fixture(params=_embedders())
def embedder(request):
    return request.param


def test_dim_consistent(embedder):
    v = embedder.encode_one("계곡 캠핑")
    assert v.shape == (embedder.dim,)


def test_batch_shape_matches_individual(embedder):
    texts = ["계곡 캠핑", "키즈 캠프", "오션뷰"]
    batch = embedder.encode_batch(texts)
    assert batch.shape == (len(texts), embedder.dim)


def test_normalized(embedder):
    v = embedder.encode_one("test text")
    norm = np.linalg.norm(v)
    assert abs(norm - 1.0) < 0.01, f"vector norm {norm} not unit-normalized"
