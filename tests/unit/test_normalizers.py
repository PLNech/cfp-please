"""Tests for location and topic normalizers."""

import pytest
from cfp_pipeline.models import Location
from cfp_pipeline.normalizers.location import normalize_location
from cfp_pipeline.normalizers.topics import normalize_topics, TAG_MAPPINGS


class TestLocationNormalizer:
    """Tests for location normalization."""

    @pytest.mark.parametrize("raw,expected_region", [
        ("Chicago, IL, USA", "Midwest"),
        ("Chicago, Illinois, USA", "Midwest"),
        ("San Francisco, CA, USA", "West Coast"),
        ("New York, NY, USA", "Northeast"),
        ("Austin, TX, USA", "South"),
        ("Seattle, WA, USA", "West Coast"),
    ])
    def test_us_regions(self, raw: str, expected_region: str):
        """US states are mapped to correct regions."""
        loc = Location(raw=raw)
        result = normalize_location(loc)
        assert result.region == expected_region
        assert result.continent == "North America"

    @pytest.mark.parametrize("raw,expected_country,expected_continent", [
        ("Berlin, Germany", "Germany", "Europe"),
        ("Paris, France", "France", "Europe"),
        ("London, UK", "UK", "Europe"),
        ("Tokyo, Japan", "Japan", "Asia"),
    ])
    def test_international_locations(self, raw: str, expected_country: str, expected_continent: str):
        """International locations get correct continent."""
        loc = Location(raw=raw)
        result = normalize_location(loc)
        assert result.country == expected_country
        assert result.continent == expected_continent

    def test_preserves_existing_data(self):
        """Existing location data is preserved."""
        loc = Location(
            city="Munich",
            country="Germany",
            raw="Munich, Germany",
        )
        result = normalize_location(loc)
        assert result.city == "Munich"
        assert result.country == "Germany"


class TestTopicNormalizer:
    """Tests for topic normalization."""

    @pytest.mark.parametrize("tags,expected_categories", [
        (["React", "JavaScript", "TypeScript"], ["frontend"]),
        (["Kubernetes", "Docker"], ["devops"]),
        (["Machine Learning", "AI"], ["ai-ml"]),
        (["AWS", "Azure"], ["cloud"]),
    ])
    def test_tag_to_category_mapping(self, tags: list[str], expected_categories: list[str]):
        """Tags are mapped to correct normalized categories."""
        cleaned, categories = normalize_topics(tags)
        for cat in expected_categories:
            assert cat in categories

    def test_empty_tags_filtered(self):
        """Empty or whitespace tags are filtered out."""
        tags = ["React", "", "  ", "Vue"]
        cleaned, categories = normalize_topics(tags)
        assert "" not in cleaned
        assert "  " not in cleaned

    def test_preserves_original_tags(self):
        """Original tags are preserved alongside normalized categories."""
        tags = ["React", "Next.js"]
        cleaned, categories = normalize_topics(tags)
        assert "React" in cleaned
        assert "Next.js" in cleaned


class TestTagMappings:
    """Verify tag mappings configuration."""

    def test_common_tags_mapped(self):
        """Common conference tags have mappings."""
        common_tags = ["javascript", "python", "react", "kubernetes"]
        for tag in common_tags:
            assert tag.lower() in TAG_MAPPINGS, f"Missing mapping for: {tag}"
