"""
Focused tests for OneGo: config, matcher, partial logic, and reporting.
"""

import json
import tempfile
from pathlib import Path

import pytest


# ── Config: uploading_target ─────────────────────────────────────────────


class TestConfigUploadingTarget:
    """Test uploading_target in CreatorConfig."""

    def test_default_is_zero(self, tmp_path):
        from modules.creator_profiles.config_manager import CreatorConfig
        cfg = CreatorConfig(tmp_path / "creator_a")
        assert cfg.uploading_target == 0

    def test_set_and_persist(self, tmp_path):
        folder = tmp_path / "creator_b"
        folder.mkdir()
        from modules.creator_profiles.config_manager import CreatorConfig
        cfg = CreatorConfig(folder)
        cfg.data["uploading_target"] = 10
        cfg.save()

        cfg2 = CreatorConfig(folder)
        assert cfg2.uploading_target == 10

    def test_backward_compat_missing_key(self, tmp_path):
        """Old JSON file without uploading_target should default to 0."""
        folder = tmp_path / "creator_c"
        folder.mkdir()
        config_file = folder / "creator_config.json"
        config_file.write_text(json.dumps({
            "creator_url": "https://facebook.com/test",
            "n_videos": 3,
        }), encoding="utf-8")

        from modules.creator_profiles.config_manager import CreatorConfig
        cfg = CreatorConfig(folder)
        assert cfg.uploading_target == 0
        assert cfg.n_videos == 3
        assert cfg.creator_url == "https://facebook.com/test"

    def test_property_type(self, tmp_path):
        from modules.creator_profiles.config_manager import CreatorConfig
        cfg = CreatorConfig(tmp_path / "creator_d")
        cfg.data["uploading_target"] = "5"
        assert cfg.uploading_target == 5
        assert isinstance(cfg.uploading_target, int)


# ── Name Matcher ─────────────────────────────────────────────────────────


class TestNameMatcher:
    """Test bookmark/folder name normalization and matching."""

    def test_normalize_basic(self):
        from modules.creator_profiles.onego.name_matcher import normalize_name
        assert normalize_name("My Page") == "my page"
        assert normalize_name("  My Page  ") == "my page"

    def test_normalize_separators(self):
        from modules.creator_profiles.onego.name_matcher import normalize_name
        assert normalize_name("my_page") == "my page"
        assert normalize_name("my-page") == "my page"
        assert normalize_name("my--page") == "my page"
        assert normalize_name("my___page") == "my page"
        assert normalize_name("my - page") == "my page"

    def test_normalize_case(self):
        from modules.creator_profiles.onego.name_matcher import normalize_name
        assert normalize_name("MY PAGE") == "my page"
        assert normalize_name("My_Page") == "my page"

    def test_normalize_empty(self):
        from modules.creator_profiles.onego.name_matcher import normalize_name
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""
        assert normalize_name(None) == ""

    def test_build_folder_map(self):
        from modules.creator_profiles.onego.name_matcher import build_folder_map
        fm = build_folder_map(["My Page", "other_page", "THIRD-Page"])
        assert "my page" in fm
        assert fm["my page"] == "My Page"
        assert fm["other page"] == "other_page"
        assert fm["third page"] == "THIRD-Page"

    def test_match_bookmark(self):
        from modules.creator_profiles.onego.name_matcher import (
            build_folder_map, match_bookmark_to_folder
        )
        fm = build_folder_map(["Creators Page", "Test_Account", "My-FB-Page"])
        assert match_bookmark_to_folder("creators_page", fm) == "Creators Page"
        assert match_bookmark_to_folder("Test Account", fm) == "Test_Account"
        assert match_bookmark_to_folder("my fb page", fm) == "My-FB-Page"
        assert match_bookmark_to_folder("nonexistent", fm) is None

    def test_no_partial_match(self):
        """Verify no fuzzy/partial matching — only exact normalized match."""
        from modules.creator_profiles.onego.name_matcher import (
            build_folder_map, match_bookmark_to_folder
        )
        fm = build_folder_map(["My Page Full"])
        assert match_bookmark_to_folder("My Page", fm) is None
        assert match_bookmark_to_folder("Page Full", fm) is None


# ── Partial Upload Logic ─────────────────────────────────────────────────


class TestPartialLogic:
    """Test collect_video_files and partial upload scenarios."""

    def test_collect_no_folder(self):
        from modules.creator_profiles.onego.upload_executor import collect_video_files
        result = collect_video_files(Path("/nonexistent_xyz_123"))
        assert result == []

    def test_collect_empty_folder(self, tmp_path):
        from modules.creator_profiles.onego.upload_executor import collect_video_files
        folder = tmp_path / "empty"
        folder.mkdir()
        assert collect_video_files(folder) == []

    def test_collect_with_limit(self, tmp_path):
        from modules.creator_profiles.onego.upload_executor import collect_video_files
        folder = tmp_path / "vids"
        folder.mkdir()
        for i in range(5):
            (folder / f"vid_{i}.mp4").write_text("fake")
        result = collect_video_files(folder, limit=3)
        assert len(result) == 3

    def test_collect_filters_non_video(self, tmp_path):
        from modules.creator_profiles.onego.upload_executor import collect_video_files
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / "video.mp4").write_text("fake")
        (folder / "image.png").write_text("fake")
        (folder / "doc.txt").write_text("fake")
        (folder / "clip.mov").write_text("fake")
        result = collect_video_files(folder)
        assert len(result) == 2
        names = {f.name for f in result}
        assert names == {"video.mp4", "clip.mov"}

    def test_delete_video_file(self, tmp_path):
        from modules.creator_profiles.onego.upload_executor import delete_video_file
        f = tmp_path / "todelete.mp4"
        f.write_text("fake")
        assert f.exists()
        assert delete_video_file(f) is True
        assert not f.exists()

    def test_delete_missing_file(self, tmp_path):
        from modules.creator_profiles.onego.upload_executor import delete_video_file
        assert delete_video_file(tmp_path / "nonexistent.mp4") is False


# ── Report Schema ────────────────────────────────────────────────────────


class TestReport:
    """Test OneGoReport aggregation and serialization."""

    def test_empty_report(self):
        from modules.creator_profiles.onego.models import OneGoReport
        r = OneGoReport(mode="upload_only")
        d = r.to_dict()
        assert d["mode"] == "upload_only"
        assert d["total_uploaded"] == 0
        assert d["total_skipped"] == 0
        assert d["total_partial"] == 0
        assert d["total_failed"] == 0
        assert d["profiles_processed"] == 0

    def test_mixed_report(self):
        from modules.creator_profiles.onego.models import (
            OneGoReport, ProfileResult, PageResult, PageStatus, SkipReason
        )
        r = OneGoReport(mode="download_upload")
        pr = ProfileResult(profile_name="profile1")
        pr.pages.append(PageResult(
            page_name="p1", target=5, available=5, uploaded=5,
            status=PageStatus.SUCCESS,
        ))
        pr.pages.append(PageResult(
            page_name="p2", target=5, available=3, uploaded=3,
            status=PageStatus.PARTIAL,
            reason=SkipReason.INSUFFICIENT_VIDEOS_PARTIAL.value,
        ))
        pr.pages.append(PageResult(
            page_name="p3", target=0,
            status=PageStatus.SKIPPED,
            reason=SkipReason.TARGET_ZERO.value,
        ))
        pr.pages.append(PageResult(
            page_name="p4", target=5, available=5, uploaded=0,
            status=PageStatus.FAILED,
            reason=SkipReason.UPLOAD_ACTION_FAILED.value,
        ))
        r.profiles.append(pr)

        d = r.to_dict()
        assert d["profiles_processed"] == 1
        assert d["total_pages"] == 4
        assert d["total_uploaded"] == 8
        assert d["total_skipped"] == 1
        assert d["total_partial"] == 1
        assert d["total_failed"] == 1

    def test_report_serialization_roundtrip(self):
        from modules.creator_profiles.onego.models import (
            OneGoReport, ProfileResult, PageResult, PageStatus
        )
        r = OneGoReport(mode="upload_only")
        pr = ProfileResult(profile_name="test")
        pr.pages.append(PageResult(page_name="pg1", target=3, uploaded=2,
                                   status=PageStatus.PARTIAL))
        r.profiles.append(pr)

        d = r.to_dict()
        j = json.dumps(d)
        parsed = json.loads(j)
        assert parsed["total_uploaded"] == 2
        assert parsed["profiles"][0]["profile_name"] == "test"

    def test_report_reasons_explicit(self):
        from modules.creator_profiles.onego.models import SkipReason
        expected = {
            "target_zero", "folder_not_found", "bookmark_not_found",
            "no_videos", "insufficient_videos_partial",
            "profile_open_failed", "upload_action_failed",
        }
        actual = {r.value for r in SkipReason}
        assert actual == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
