from cf_be_api.domain.intensifier_lexicon import (
    INTENSIFIER_NEGATIVE,
    INTENSIFIER_POSITIVE,
)


def test_lexicon_non_empty_and_disjoint():
    pos = set(INTENSIFIER_POSITIVE)
    neg = set(INTENSIFIER_NEGATIVE)
    assert len(pos) >= 5
    assert len(neg) >= 3
    overlap = pos & neg
    assert overlap == set(), f"polarity overlap: {overlap}"


def test_lexicon_has_expected_strong_positives():
    # Sanity: at least one canonical strong positive must be present
    pos = set(INTENSIFIER_POSITIVE)
    assert pos & {"최고", "강추", "정말"}, "expected core strong positives missing"
