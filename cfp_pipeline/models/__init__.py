"""Data models for CFP pipeline."""

from cfp_pipeline.models.cfp import CFP, Location, GeoLoc, RawCAPRecord
from cfp_pipeline.models.talk import Talk, talk_to_algolia

__all__ = [
    "CFP",
    "Location",
    "GeoLoc",
    "RawCAPRecord",
    "Talk",
    "talk_to_algolia",
]
