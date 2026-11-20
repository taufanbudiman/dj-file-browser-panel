"""Unit tests for the sandboxed filesystem layer."""

import os

import pytest

from dj_file_browser_panel import browser


@pytest.fixture
def media_tree(tmp_path, settings):
    """A small directory tree configured as the only browsable root."""
    root = tmp_path / "media"
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "sub" / "nested.txt").write_text("nested")
    (root / "sub" / "deep" / "leaf.txt").write_text("leaf")
    (root / "hello.txt").write_text("hello")
    (root / "zeta.bin").write_bytes(b"\x00\x01\x02")
    (root / ".hidden").write_text("secret")
    (root / ".hidden_dir").mkdir()
    settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {"ROOTS": [str(root)]}
    return root


@pytest.fixture
def root_obj(media_tree):
    roots = browser.get_roots()
    assert len(roots) == 1
    return roots[0]


class TestGetRoots:
    def test_explicit_roots(self, media_tree, root_obj):
        assert root_obj.name == "media"
        assert root_obj.slug == "media"
        assert root_obj.path == media_tree.resolve()

    def test_dict_root_spec(self, tmp_path, settings):
        target = tmp_path / "assets"
        target.mkdir()
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            "ROOTS": [
                {"name": "Assets", "path": str(target), "description": "static assets"},
            ]
        }
        roots = browser.get_roots()
        assert len(roots) == 1
        assert roots[0].name == "Assets"
        assert roots[0].slug == "assets"
        assert roots[0].description == "static assets"

    def test_missing_and_nondir_roots_skipped(self, tmp_path, settings):
        (tmp_path / "a_file").write_text("x")
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            "ROOTS": [
                str(tmp_path / "does-not-exist"),
                str(tmp_path / "a_file"),
                {"name": "Empty", "path": ""},
            ]
        }
        assert browser.get_roots() == []

    def test_default_roots_use_media_and_static(self, settings):
        # example_project.settings defines MEDIA_ROOT and STATIC_ROOT
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {}
        roots = browser.get_roots()
        names = {r.name for r in roots}
        assert "media" in names

    def test_duplicate_names_get_unique_slugs(self, tmp_path, settings):
        a = tmp_path / "one" / "same"
        b = tmp_path / "two" / "same"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {"ROOTS": [str(a), str(b)]}
        slugs = [r.slug for r in browser.get_roots()]
        assert slugs == ["same", "same-2"]


class TestResolveInRoot:
    def test_plain_relative_path(self, root_obj):
        resolved = browser.resolve_in_root(root_obj, "sub/nested.txt")
        assert resolved == root_obj.path / "sub" / "nested.txt"

    def test_dotdot_escape_rejected(self, root_obj):
        assert browser.resolve_in_root(root_obj, "..") is None
        assert browser.resolve_in_root(root_obj, "sub/../../outside") is None

    def test_absolute_path_outside_rejected(self, root_obj, tmp_path):
        assert browser.resolve_in_root(root_obj, str(tmp_path)) is None

    def test_absolute_path_inside_allowed(self, root_obj):
        inside = str(root_obj.path / "hello.txt")
        assert browser.resolve_in_root(root_obj, inside) == root_obj.path / "hello.txt"

    def test_symlink_escape_rejected(self, root_obj, tmp_path):
        outside = tmp_path / "outside.txt"
        outside.write_text("nope")
        link = root_obj.path / "escape"
        os.symlink(outside, link)
        assert browser.resolve_in_root(root_obj, "escape") is None

    def test_symlink_inside_root_allowed(self, root_obj):
        link = root_obj.path / "alias"
        os.symlink(root_obj.path / "hello.txt", link)
        assert browser.resolve_in_root(root_obj, "alias") == (
            root_obj.path / "hello.txt"
        )


class TestListDirectory:
    def test_dirs_first_then_files_case_insensitive(self, root_obj):
        listing = browser.list_directory(root_obj)
        names = [e.name for e in listing.entries]
        kinds = [(e.is_dir, e.name) for e in listing.entries]
        dir_names = [n for d, n in kinds if d]
        file_names = [n for d, n in kinds if not d]
        assert dir_names == ["sub"]
        assert file_names == ["hello.txt", "zeta.bin"]
        # hidden entries excluded by default
        assert ".hidden" not in names
        assert ".hidden_dir" not in names

    def test_show_hidden(self, root_obj):
        listing = browser.list_directory(root_obj, show_hidden=True)
        names = {e.name for e in listing.entries}
        assert ".hidden" in names
        assert ".hidden_dir" in names

    def test_subdirectory(self, root_obj):
        listing = browser.list_directory(root_obj, "sub")
        names = [e.name for e in listing.entries]
        assert names == ["deep", "nested.txt"]
        entry = listing.entries[1]
        assert entry.rel_path == "sub/nested.txt"
        assert entry.size == len("nested")
        assert entry.modified is not None

    def test_pagination(self, root_obj):
        listing = browser.list_directory(root_obj, per_page=2)
        assert listing.total == 3  # sub/, hello.txt, zeta.bin (dotfiles hidden)
        assert listing.per_page == 2
        assert listing.total_pages == 2
        assert len(listing.entries) == 2
        page2 = browser.list_directory(root_obj, per_page=2, page=2)
        assert [e.name for e in page2.entries] != [e.name for e in listing.entries]

    def test_page_clamped(self, root_obj):
        listing = browser.list_directory(root_obj, per_page=2, page=99)
        assert listing.page == listing.total_pages

    def test_outside_path_error(self, root_obj):
        listing = browser.list_directory(root_obj, "..")
        assert listing.error is not None
        assert listing.entries == []

    def test_missing_path_error(self, root_obj):
        listing = browser.list_directory(root_obj, "nope")
        assert listing.error == "Path does not exist."

    def test_file_path_error(self, root_obj):
        listing = browser.list_directory(root_obj, "hello.txt")
        assert listing.error == "Path is not a directory."

    def test_unsafe_symlink_marked(self, root_obj, tmp_path):
        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        os.symlink(outside_dir, root_obj.path / "escape_dir")
        listing = browser.list_directory(root_obj)
        entry = next(e for e in listing.entries if e.name == "escape_dir")
        assert entry.is_dir is True
        assert entry.is_safe is False
        assert entry.url == ""


class TestGetFileInfo:
    def test_file_metadata(self, root_obj):
        info, error = browser.get_file_info(root_obj, "hello.txt")
        assert error is None
        assert info.name == "hello.txt"
        assert info.rel_path == "hello.txt"
        assert info.size == 5
        assert info.mime_type == "text/plain"
        assert info.preview is None  # preview disabled by default

    def test_missing_file(self, root_obj):
        info, error = browser.get_file_info(root_obj, "nope.txt")
        assert info is None
        assert error == "File does not exist."

    def test_directory_rejected(self, root_obj):
        info, error = browser.get_file_info(root_obj, "sub")
        assert info is None
        assert error == "Path is a directory."

    def test_outside_rejected(self, root_obj):
        info, error = browser.get_file_info(root_obj, "..")
        assert info is None
        assert "outside" in error

    def test_preview_enabled(self, root_obj, settings):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            "ROOTS": [str(root_obj.path)],
            "PREVIEW_ENABLED": True,
            "PREVIEW_TYPES": ["text/plain"],
            "PREVIEW_MAX_BYTES": 1024,
        }
        info, error = browser.get_file_info(root_obj, "hello.txt")
        assert error is None
        assert info.preview == "hello"
        assert info.preview_truncated is False

    def test_preview_truncates_at_max_bytes(self, root_obj, settings):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            "ROOTS": [str(root_obj.path)],
            "PREVIEW_ENABLED": True,
            "PREVIEW_TYPES": ["text/plain"],
            "PREVIEW_MAX_BYTES": 2,
        }
        info, _ = browser.get_file_info(root_obj, "hello.txt")
        assert info.preview == "he"
        assert info.preview_truncated is True

    def test_preview_type_not_allowlisted(self, root_obj, settings):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            "ROOTS": [str(root_obj.path)],
            "PREVIEW_ENABLED": True,
            "PREVIEW_TYPES": ["application/json"],
            "PREVIEW_MAX_BYTES": 1024,
        }
        # text/plain is allowed implicitly via text/* prefix
        info, _ = browser.get_file_info(root_obj, "hello.txt")
        assert info.preview == "hello"
        # application/octet-stream is not
        info2, _ = browser.get_file_info(root_obj, "zeta.bin")
        assert info2.preview is None


class TestHumanSize:
    @pytest.mark.parametrize(
        "size,expected",
        [
            (None, "—"),
            (0, "0 B"),
            (512, "512 B"),
            (2048, "2.0 KiB"),
            (5 * 1024 * 1024, "5.0 MiB"),
        ],
    )
    def test_sizes(self, size, expected):
        assert browser.human_size(size) == expected
