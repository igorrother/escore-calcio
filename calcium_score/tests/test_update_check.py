"""Unit tests for the update_check module — no network access."""

from __future__ import annotations

import pytest

from calcium_score.update_check import (
    RELEASES_PAGE_URL,
    UpdateInfo,
    is_newer_version,
    parse_release_payload,
    parse_version,
)


class TestParseVersion:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1.0", (1, 0)),
            ("v1.0", (1, 0)),
            ("V1.2.3", (1, 2, 3)),
            ("1", (1,)),
            ("v1.2.3-beta", (1, 2, 3)),
            ("1.2.3+build5", (1, 2, 3)),
            ("  v2.0  ", (2, 0)),
        ],
    )
    def test_parses_common_forms(self, text: str, expected: tuple[int, ...]):
        assert parse_version(text) == expected

    @pytest.mark.parametrize("text", ["", "   ", "vbeta", "not-a-version", "v"])
    def test_returns_none_for_garbage(self, text: str):
        assert parse_version(text) is None


class TestIsNewerVersion:
    def test_newer_patch(self):
        assert is_newer_version("v1.0.1", "1.0.0") is True

    def test_newer_minor(self):
        assert is_newer_version("v1.1", "1.0") is True

    def test_newer_major(self):
        assert is_newer_version("v2.0", "1.9.9") is True

    def test_same_version_is_not_newer(self):
        assert is_newer_version("v1.0", "1.0") is False
        assert is_newer_version("1.0.0", "1.0") is False

    def test_older_is_not_newer(self):
        assert is_newer_version("v0.9", "1.0") is False
        assert is_newer_version("v1.0", "1.0.1") is False

    def test_unparseable_returns_false(self):
        # Better to miss an update than to nag with a bad tag.
        assert is_newer_version("garbage", "1.0") is False
        assert is_newer_version("v1.0", "garbage") is False

    def test_prerelease_suffix_is_ignored(self):
        # Pragmatic: we don't support semver pre-release ordering in v1.
        # A "v1.0.0-beta" tag compares as 1.0.0 — equal, not newer.
        assert is_newer_version("v1.0.0-beta", "1.0.0") is False


class TestParseReleasePayload:
    def test_extracts_tag_and_url(self):
        payload = {
            "tag_name": "v1.1",
            "html_url": "https://github.com/igorrother/escore-calcio/releases/tag/v1.1",
            "name": "Release 1.1",
        }
        info = parse_release_payload(payload)
        assert info == UpdateInfo(
            latest_version="v1.1",
            release_url="https://github.com/igorrother/escore-calcio/releases/tag/v1.1",
        )

    def test_falls_back_to_releases_page_url(self):
        payload = {"tag_name": "v1.1"}
        info = parse_release_payload(payload)
        assert info is not None
        assert info.release_url == RELEASES_PAGE_URL

    def test_missing_tag_returns_none(self):
        assert parse_release_payload({}) is None
        assert parse_release_payload({"tag_name": ""}) is None
        assert parse_release_payload({"tag_name": None}) is None
