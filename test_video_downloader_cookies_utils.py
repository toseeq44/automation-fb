"""Tests for the cookie utility helpers used by the video downloader."""

from pathlib import Path

from modules.video_downloader.cookies_utils import ensure_netscape_cookie


def test_ensure_netscape_cookie_keeps_valid_file(tmp_path: Path):
    cookie_file = tmp_path / "instagram.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tabc123\n",
        encoding="utf-8",
    )

    result = ensure_netscape_cookie(cookie_file, "instagram")

    assert result == str(cookie_file)


def test_ensure_netscape_cookie_converts_simple_format(tmp_path: Path):
    cookie_file = tmp_path / "instagram_simple.txt"
    cookie_file.write_text("sessionid=abc123\ncsrftoken=xyz789\n", encoding="utf-8")

    result = ensure_netscape_cookie(cookie_file, "instagram")

    assert result is not None
    assert result != str(cookie_file)

    converted = Path(result)
    assert converted.exists()
    content = converted.read_text(encoding="utf-8")
    assert ".instagram.com" in content
    assert "sessionid\tabc123" in content
    assert "csrftoken\txyz789" in content


def test_ensure_netscape_cookie_rejects_unparseable(tmp_path: Path):
    cookie_file = tmp_path / "bad.txt"
    cookie_file.write_text("nonsense", encoding="utf-8")

    result = ensure_netscape_cookie(cookie_file, "instagram")

    assert result is None
