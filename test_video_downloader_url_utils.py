"""Tests for URL extraction helpers used by the downloader."""

from modules.video_downloader.url_utils import extract_urls, normalize_url, quality_to_format


def test_extract_urls_accepts_mixed_delimiters_and_case():
    raw = """
    HTTPS://example.com/video1  ,
    www.test.com/video2
    random text https://foo.bar/watch?v=abc123def45 end
    """

    urls = extract_urls(raw)

    assert urls == [
        "https://example.com/video1",
        "https://www.test.com/video2",
        "https://foo.bar/watch?v=abc123def45",
    ]


def test_extract_urls_from_iterables_and_deduplicates():
    data = [
        {"url": "https://tiktok.com/video/123"},
        " https://tiktok.com/video/123 ?utm_source=feed ",
        "instagram.com/p/abc123",
    ]

    urls = extract_urls(data)

    assert urls == [
        "https://tiktok.com/video/123",
        "https://instagram.com/p/abc123",
    ]


def test_normalize_url_handles_platform_specific_patterns():
    assert normalize_url("https://www.tiktok.com/@user/video/123456") == "tiktok_123456"
    assert normalize_url("https://youtu.be/abc123def45") == "youtube_abc123def45"
    assert normalize_url("https://www.instagram.com/p/SomeId/?utm_source=ig") == "instagram_SomeId"


def test_quality_mapping_to_format_strings():
    assert quality_to_format("HD") == "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]"
    assert quality_to_format("4k") == "bestvideo[height<=2160][ext=mp4]+bestaudio/best[height<=2160]"
    assert quality_to_format("unknown") is None
