"""
tests/test_media_service.py
───────────────────────────
Tests for MediaService and the _sniff_extension helper.

Split into two tiers:

  Pure unit tests — _sniff_extension (no I/O, no fixtures)
    _sniff_extension lives in media_routes.py because it's tightly coupled
    to the upload guard logic, but it's a pure function and testing it
    directly catches regressions without needing a real upload flow.

    Covers every recognised magic-byte sequence plus several edge cases:
      JPEG  (FF D8 FF)
      PNG   (89 50 4E 47 0D 0A 1A 0A)
      MP4   (ISO-BMFF: bytes 4–8 == b"ftyp")
      Unknown / too-short / garbage → None

  MediaService.list_accessible_media tests (filesystem, no DB/Redis)
    Uses pytest's tmp_path fixture and monkeypatches Config.MEDIA_DIR so
    no real shared_media directory is touched and tests are fully isolated.

    Covers:
      Filtering     — only allowed extensions returned, others ignored
      Sorting       — filenames returned in lexicographic order
      Pagination    — correct page/offset/limit slicing
      Page math     — pages count, total, page_size reflected correctly
      Empty dir     — returns empty items list, pages=1
      Page overflow — page beyond last returns empty items, correct metadata
"""

import math
from pathlib import Path

import pytest

from src.config import Config
from src.media.media_routes import _sniff_extension

# ══════════════════════════════════════════════════════════════════════════════
# Pure unit tests — _sniff_extension
# ══════════════════════════════════════════════════════════════════════════════


class TestSniffExtension:
    # ── Recognised types ──────────────────────────────────────────────────────

    def test_jpeg_magic_bytes_returns_jpg(self):
        head = b"\xff\xd8\xff\xe0" + b"\x00" * 12
        assert _sniff_extension(head) == ".jpg"

    def test_jpeg_exif_variant_returns_jpg(self):
        # Many cameras write FF D8 FF E1 (Exif marker) instead of FF D8 FF E0
        head = b"\xff\xd8\xff\xe1" + b"\x00" * 12
        assert _sniff_extension(head) == ".jpg"

    def test_jpeg_arbitrary_third_byte_returns_jpg(self):
        # Any byte after FF D8 FF is a valid JPEG marker; we only check first 3
        head = b"\xff\xd8\xff\xdb" + b"\x00" * 12
        assert _sniff_extension(head) == ".jpg"

    def test_png_magic_bytes_returns_png(self):
        png_sig = b"\x89PNG\r\n\x1a\n"
        head = png_sig + b"\x00" * 8
        assert _sniff_extension(head) == ".png"

    def test_mp4_ftyp_box_returns_mp4(self):
        # Minimal ISO-BMFF header: 4-byte box size + b"ftyp" + brand bytes
        head = b"\x00\x00\x00\x20" + b"ftyp" + b"isom" + b"\x00" * 4
        assert _sniff_extension(head) == ".mp4"

    def test_mp4_different_size_still_detected(self):
        # Box size field (first 4 bytes) doesn't affect detection
        head = b"\x00\x00\x01\x00" + b"ftyp" + b"mp42" + b"\x00" * 4
        assert _sniff_extension(head) == ".mp4"

    # ── Unrecognised types → None ─────────────────────────────────────────────

    def test_pdf_returns_none(self):
        head = b"%PDF-1.4" + b"\x00" * 8
        assert _sniff_extension(head) is None

    def test_gif_returns_none(self):
        head = b"GIF89a" + b"\x00" * 10
        assert _sniff_extension(head) is None

    def test_zip_returns_none(self):
        head = b"PK\x03\x04" + b"\x00" * 12
        assert _sniff_extension(head) is None

    def test_plain_text_returns_none(self):
        head = b"Hello, world!\n" + b"\x00" * 2
        assert _sniff_extension(head) is None

    def test_all_zeros_returns_none(self):
        assert _sniff_extension(b"\x00" * 16) is None

    def test_empty_bytes_returns_none(self):
        assert _sniff_extension(b"") is None

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_too_short_for_mp4_check_returns_none(self):
        # Needs at least 12 bytes for the ftyp check; 11 must not crash
        head = b"\x00\x00\x00\x00" + b"ftyp" + b"\x00"  # 9 bytes total
        assert _sniff_extension(head) is None

    def test_exactly_12_bytes_mp4_detected(self):
        head = b"\x00\x00\x00\x20" + b"ftyp" + b"\x00\x00\x00\x00"
        assert _sniff_extension(head) == ".mp4"

    def test_mp4_check_only_uses_bytes_4_to_8(self):
        # Prefix doesn't start with JPEG or PNG magic; only ftyp check applies
        head = b"\x00\x00\x00\x00" + b"ftyp" + b"\x00" * 6
        assert _sniff_extension(head) == ".mp4"

    def test_jpeg_prefix_takes_priority_over_ftyp(self):
        # Pathological: JPEG magic in first 3 bytes, ftyp at offset 4
        # JPEG check fires first and wins
        head = b"\xff\xd8\xff" + b"\x00" + b"ftyp" + b"\x00" * 6
        assert _sniff_extension(head) == ".jpg"


# ══════════════════════════════════════════════════════════════════════════════
# MediaService.list_accessible_media
#
# Each test class gets a fresh tmp_path subtree and patches Config.MEDIA_DIR
# so MediaService reads from the isolated temp directory.
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def media_dir(tmp_path: Path, monkeypatch) -> Path:
    """
    Create an isolated media directory and redirect Config.MEDIA_DIR to it.
    Yields the Path so tests can create files inside it.
    """
    d = tmp_path / "media"
    d.mkdir()
    monkeypatch.setattr(Config, "MEDIA_DIR", str(d))
    return d


def touch(directory: Path, name: str) -> Path:
    """Create an empty file at directory/name and return its path."""
    p = directory / name
    p.write_bytes(b"")
    return p


class TestListAccessibleMediaFiltering:
    async def test_jpg_files_included(self, media_svc, media_dir: Path):
        touch(media_dir, "photo.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "photo.jpg" in result.items

    async def test_jpeg_files_included(self, media_svc, media_dir: Path):
        touch(media_dir, "scan.jpeg")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "scan.jpeg" in result.items

    async def test_png_files_included(self, media_svc, media_dir: Path):
        touch(media_dir, "image.png")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "image.png" in result.items

    async def test_mp4_files_included(self, media_svc, media_dir: Path):
        touch(media_dir, "video.mp4")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "video.mp4" in result.items

    async def test_txt_files_excluded(self, media_svc, media_dir: Path):
        touch(media_dir, "readme.txt")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "readme.txt" not in result.items

    async def test_pdf_files_excluded(self, media_svc, media_dir: Path):
        touch(media_dir, "doc.pdf")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "doc.pdf" not in result.items

    async def test_exe_files_excluded(self, media_svc, media_dir: Path):
        touch(media_dir, "malware.exe")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "malware.exe" not in result.items

    async def test_no_extension_excluded(self, media_svc, media_dir: Path):
        touch(media_dir, "noextension")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "noextension" not in result.items

    async def test_mixed_dir_only_returns_allowed(self, media_svc, media_dir: Path):
        touch(media_dir, "keep.jpg")
        touch(media_dir, "keep.png")
        touch(media_dir, "skip.txt")
        touch(media_dir, "skip.log")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert set(result.items) == {"keep.jpg", "keep.png"}

    async def test_extension_case_insensitive(self, media_svc, media_dir: Path):
        touch(media_dir, "PHOTO.JPG")
        touch(media_dir, "image.PNG")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert "PHOTO.JPG" in result.items
        assert "image.PNG" in result.items


class TestListAccessibleMediaSorting:
    async def test_files_returned_in_lexicographic_order(self, media_svc, media_dir: Path):
        touch(media_dir, "c_third.jpg")
        touch(media_dir, "a_first.jpg")
        touch(media_dir, "b_second.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert result.items == ["a_first.jpg", "b_second.jpg", "c_third.jpg"]

    async def test_numeric_names_sorted_lexicographically(self, media_svc, media_dir: Path):
        # Lexicographic: "10.jpg" < "2.jpg" (because "1" < "2")
        touch(media_dir, "10.jpg")
        touch(media_dir, "2.jpg")
        touch(media_dir, "1.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert result.items == ["1.jpg", "10.jpg", "2.jpg"]


class TestListAccessibleMediaPagination:
    async def test_page_1_returns_first_limit_items(self, media_svc, media_dir: Path):
        for i in range(5):
            touch(media_dir, f"file_{i:02d}.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=3)
        assert result.items == ["file_00.jpg", "file_01.jpg", "file_02.jpg"]

    async def test_page_2_returns_next_items(self, media_svc, media_dir: Path):
        for i in range(5):
            touch(media_dir, f"file_{i:02d}.jpg")
        result = await media_svc.list_accessible_media(page=2, limit=3)
        assert result.items == ["file_03.jpg", "file_04.jpg"]

    async def test_page_beyond_last_returns_empty_items(self, media_svc, media_dir: Path):
        touch(media_dir, "only.jpg")
        result = await media_svc.list_accessible_media(page=99, limit=10)
        assert result.items == []

    async def test_limit_1_returns_single_item(self, media_svc, media_dir: Path):
        touch(media_dir, "alpha.jpg")
        touch(media_dir, "beta.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=1)
        assert result.items == ["alpha.jpg"]

    async def test_limit_larger_than_total_returns_all(self, media_svc, media_dir: Path):
        touch(media_dir, "a.jpg")
        touch(media_dir, "b.png")
        result = await media_svc.list_accessible_media(page=1, limit=100)
        assert len(result.items) == 2


class TestListAccessibleMediaMetadata:
    async def test_total_reflects_allowed_file_count(self, media_svc, media_dir: Path):
        touch(media_dir, "a.jpg")
        touch(media_dir, "b.png")
        touch(media_dir, "c.txt")  # excluded
        result = await media_svc.list_accessible_media(page=1, limit=10)
        assert result.total == 2

    async def test_pages_calculated_correctly(self, media_svc, media_dir: Path):
        for i in range(7):
            touch(media_dir, f"f{i}.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=3)
        assert result.pages == math.ceil(7 / 3)  # 3

    async def test_page_size_reflects_limit_param(self, media_svc, media_dir: Path):
        touch(media_dir, "a.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=5)
        assert result.page_size == 5

    async def test_page_reflects_requested_page(self, media_svc, media_dir: Path):
        touch(media_dir, "a.jpg")
        result = await media_svc.list_accessible_media(page=2, limit=5)
        assert result.page == 2

    async def test_empty_dir_returns_pages_1(self, media_svc, media_dir: Path):
        result = await media_svc.list_accessible_media(page=1, limit=5)
        assert result.pages == 1
        assert result.total == 0
        assert result.items == []

    async def test_exact_multiple_of_limit_page_count(self, media_svc, media_dir: Path):
        # 6 files, limit=3 → exactly 2 pages (no ceiling rounding needed)
        for i in range(6):
            touch(media_dir, f"f{i}.jpg")
        result = await media_svc.list_accessible_media(page=1, limit=3)
        assert result.pages == 2

    async def test_overflow_page_still_has_correct_total(self, media_svc, media_dir: Path):
        touch(media_dir, "only.jpg")
        result = await media_svc.list_accessible_media(page=99, limit=10)
        assert result.total == 1
        assert result.pages == 1
        assert result.items == []
