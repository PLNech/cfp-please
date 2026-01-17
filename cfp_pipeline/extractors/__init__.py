"""URL → CFP extraction engine.

This module provides a unified extraction pipeline that:
1. Fetches HTML from conference URLs
2. Extracts CFP metadata using multiple strategies:
   - Schema.org JSON-LD / microdata
   - OpenGraph meta tags
   - Platform-specific parsers (Sessionize, PaperCall, etc.)
   - HTML heuristics (deadline patterns, CFP keywords)
3. Returns normalized CFP data
"""

from cfp_pipeline.extractors.fetch import fetch_url, fetch_urls_parallel, FetchResult
from cfp_pipeline.extractors.structured import extract_structured_data
from cfp_pipeline.extractors.platforms import extract_platform_specific
from cfp_pipeline.extractors.heuristics import extract_heuristics
from cfp_pipeline.extractors.pipeline import extract_cfp_from_url, extract_cfps_batch
from cfp_pipeline.extractors.url_store import URLStore

__all__ = [
    "fetch_url",
    "fetch_urls_parallel",
    "extract_structured_data",
    "extract_platform_specific",
    "extract_heuristics",
    "extract_cfp_from_url",
    "extract_cfps_batch",
    "URLStore",
]
