"""Data models for CFP pipeline."""

from cfp_pipeline.models.cfp import CFP, Location, GeoLoc, RawCAPRecord
from cfp_pipeline.models.talk import Talk, talk_to_algolia
from cfp_pipeline.models.speaker import Speaker, speaker_to_algolia, slugify_name

__all__ = [
    "CFP",
    "Location",
    "GeoLoc",
    "RawCAPRecord",
    "Talk",
    "talk_to_algolia",
    "Speaker",
    "speaker_to_algolia",
    "slugify_name",
]
