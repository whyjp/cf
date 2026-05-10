"""cf-be-api-py — Python clean-arch core (domain / ports / usecases / adapters).

SP-D D-8 cutover (2026-05-11): the FastAPI HTTP runtime (formerly api.py) was
deleted; the live be-api on :8071 is now the Go binary at backend/be-api/.
This package remains as a library only — consumed by cf-pipeline CLI tooling
(ingest_camps, seed_concepts, seed_filter_mapping). Distribution name is
`cf-be-api-py`; Python import path stays `cf_be_api` for stability.
"""
__version__ = "0.1.0"
