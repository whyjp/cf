"""txcp-crawl — m.thankqcamping.com 캠핑장 메타 크롤러.

camfit-puller 와 동급의 사이트 어댑터. 후속 PR 에서 `crawlers/` 루트로 이동 예정.
"""
from txcp_crawl.models import CampRecord
from txcp_crawl.adapter import TkcpAdapter
from txcp_crawl.crawler import pull, PullSummary
from txcp_crawl.csv_writer import write_camps_csv
from txcp_crawl.fetcher import Fetcher, HttpxFetcher

__all__ = [
    "CampRecord",
    "TkcpAdapter",
    "pull",
    "PullSummary",
    "write_camps_csv",
    "Fetcher",
    "HttpxFetcher",
]
__version__ = "0.1.0"
