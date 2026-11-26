"""View tests for the DJ File Browser Panel."""

import os

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def media_tree(tmp_path, settings):
    root = tmp_path / "media"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "nested.txt").write_text("nested file contents")
    (root / "hello.txt").write_text("hello world")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfakepng")
    (root / "doc.pdf").write_bytes(b"%PDF-1.4 fake pdf")
    (root / ".hidden").write_text("secret")
    settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
        "ROOTS": [{"name": "Media", "path": str(root)}],
        "PAGE_SIZE": 100,
        "PREVIEW_ENABLED": True,
        "PREVIEW_TYPES": ["text/plain"],
        "PREVIEW_MAX_BYTES": 1024,
    }
    return root


@pytest.fixture
def root_slug(media_tree):
    return "media"


@pytest.mark.django_db
class TestIndex:
    def test_index_ok(self, admin_client, media_tree):
        response = admin_client.get(reverse("dj_file_browser_panel:index"))
        assert response.status_code == 200
        assert b"Media" in response.content
        assert str(media_tree.resolve()).encode() in response.content

    def test_index_empty_state(self, admin_client, settings):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {"ROOTS": []}
        # ROOTS=[] falls back to MEDIA_ROOT/STATIC_ROOT; point them nowhere
        settings.MEDIA_ROOT = "/nonexistent/path"
        settings.STATIC_ROOT = None
        response = admin_client.get(reverse("dj_file_browser_panel:index"))
        assert response.status_code == 200
        assert b"No browsable roots" in response.content

    def test_index_anonymous_redirects(self, client, media_tree):
        response = client.get(reverse("dj_file_browser_panel:index"))
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_index_non_staff_forbidden(self, client, media_tree, db):
        user = get_user_model().objects.create_user(
            username="regular", password="pw", is_staff=False
        )
        client.force_login(user)
        response = client.get(reverse("dj_file_browser_panel:index"))
        assert response.status_code == 403

    def test_index_staff_allowed(self, client, media_tree, db):
        user = get_user_model().objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        client.force_login(user)
        response = client.get(reverse("dj_file_browser_panel:index"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestBrowse:
    def test_browse_root(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
        )
        assert response.status_code == 200
        assert b"hello.txt" in response.content
        assert b"sub" in response.content
        # dotfiles hidden by default
        assert b".hidden" not in response.content

    def test_browse_subdirectory(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "sub"])
        )
        assert response.status_code == 200
        assert b"nested.txt" in response.content

    def test_file_detail(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "hello.txt"])
        )
        assert response.status_code == 200
        assert b"hello world" in response.content  # preview enabled in fixture
        assert b"text/plain" in response.content

    def test_file_detail_preview_disabled(
        self, admin_client, media_tree, root_slug, settings
    ):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            **settings.DJ_FILE_BROWSER_PANEL_SETTINGS,
            "PREVIEW_ENABLED": False,
        }
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "hello.txt"])
        )
        assert response.status_code == 200
        assert b"hello world" not in response.content

    def test_unknown_root_404(self, admin_client, media_tree):
        response = admin_client.get("/admin/files/nope/")
        assert response.status_code == 404

    def test_traversal_shows_error_state(self, admin_client, media_tree, root_slug):
        response = admin_client.get(f"/admin/files/{root_slug}/..%2F")
        # %2F may be decoded to '/', either way the path must not escape
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert b"outside the configured root" in response.content

    def test_dotdot_segment_rejected(self, admin_client, media_tree, root_slug):
        response = admin_client.get(f"/admin/files/{root_slug}/../")
        assert response.status_code == 200
        assert b"outside the configured root" in response.content

    def test_missing_path_error_state(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "missing-dir"])
        )
        assert response.status_code == 200
        assert b"Path does not exist" in response.content

    def test_hidden_toggle(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug]) + "?hidden=1"
        )
        assert response.status_code == 200
        assert b".hidden" in response.content

    def test_pagination(self, admin_client, media_tree, root_slug):
        for i in range(10):
            (media_tree / f"file-{i:02d}.txt").write_text("x")
        # per_page=10; dirs first (sub/), then files case-insensitively:
        # doc.pdf, file-00..file-09, hello.txt, logo.png (14 entries total)
        page1 = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=10"
        )
        assert b"/admin/files/media/sub/" in page1.content
        assert b"doc.pdf" in page1.content
        assert b"file-07.txt" in page1.content
        assert b"file-08.txt" not in page1.content
        assert b"hello.txt" not in page1.content

        page2 = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=10&page=2"
        )
        assert page2.status_code == 200
        assert b"file-08.txt" in page2.content
        assert b"file-09.txt" in page2.content
        assert b"hello.txt" in page2.content
        assert b"logo.png" in page2.content
        assert b"/admin/files/media/sub/" not in page2.content
        assert b"dcr-pagination" in page2.content

    def test_page_size_selector(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
        )
        assert response.status_code == 200
        content = response.content
        assert b'name="per_page"' in content
        assert b'class="dcr-pagination__per-page-select"' in content
        for size in (b"10", b"25", b"50", b"100", b"250"):
            assert b'value="%s"' % size in content

    def test_page_size_selector_marks_current(
        self, admin_client, media_tree, root_slug
    ):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=25"
        )
        assert response.status_code == 200
        assert b'<option value="25" selected>25</option>' in response.content

    def test_per_page_outside_options_falls_back(
        self, admin_client, media_tree, root_slug
    ):
        # per_page=2 is not one of the selector options; it is ignored and
        # the configured PAGE_SIZE default (100) is used instead.
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=2"
        )
        assert response.status_code == 200
        assert response.context["per_page"] == 100

    def test_page_size_selector_preserves_hidden(
        self, admin_client, media_tree, root_slug
    ):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug]) + "?hidden=1"
        )
        assert response.status_code == 200
        assert b'name="hidden" value="1"' in response.content

    def test_embed_preview_image(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "logo.png"])
        )
        assert response.status_code == 200
        assert b"<img" in response.content
        assert b"?content=1" in response.content

    def test_embed_preview_pdf(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "doc.pdf"])
        )
        assert response.status_code == 200
        assert b"<embed" in response.content
        assert b"application/pdf" in response.content

    def test_embed_preview_disabled(
        self, admin_client, media_tree, root_slug, settings
    ):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            **settings.DJ_FILE_BROWSER_PANEL_SETTINGS,
            "PREVIEW_ENABLED": False,
        }
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse", args=[root_slug, "logo.png"])
        )
        assert response.status_code == 200
        assert b"<img" not in response.content

    def test_content_endpoint_serves_image(self, admin_client, media_tree, root_slug):
        url = (
            reverse("dj_file_browser_panel:browse", args=[root_slug, "logo.png"])
            + "?content=1"
        )
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert b"".join(response.streaming_content) == b"\x89PNG\r\n\x1a\nfakepng"

    def test_content_endpoint_serves_pdf(self, admin_client, media_tree, root_slug):
        url = (
            reverse("dj_file_browser_panel:browse", args=[root_slug, "doc.pdf"])
            + "?content=1"
        )
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_content_endpoint_rejects_text(self, admin_client, media_tree, root_slug):
        url = (
            reverse("dj_file_browser_panel:browse", args=[root_slug, "hello.txt"])
            + "?content=1"
        )
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_content_endpoint_rejects_when_disabled(
        self, admin_client, media_tree, root_slug, settings
    ):
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            **settings.DJ_FILE_BROWSER_PANEL_SETTINGS,
            "PREVIEW_ENABLED": False,
        }
        url = (
            reverse("dj_file_browser_panel:browse", args=[root_slug, "logo.png"])
            + "?content=1"
        )
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_content_endpoint_rejects_directory(
        self, admin_client, media_tree, root_slug
    ):
        url = (
            reverse("dj_file_browser_panel:browse", args=[root_slug, "sub"])
            + "?content=1"
        )
        response = admin_client.get(url)
        # directories go to the listing view, which ignores ?content=1
        assert response.status_code == 200
        assert b"nested.txt" in response.content

    def test_hidden_toggle_off_override(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug]) + "?hidden=0"
        )
        assert response.status_code == 200
        assert b".hidden" not in response.content

    def test_many_pages_smart_range(
        self, admin_client, media_tree, root_slug, settings
    ):
        # PAGE_SIZE is the admin-configured default and may be any value;
        # only URL per_page values are restricted to the selector options.
        settings.DJ_FILE_BROWSER_PANEL_SETTINGS = {
            **settings.DJ_FILE_BROWSER_PANEL_SETTINGS,
            "PAGE_SIZE": 2,
        }
        for i in range(25):
            (media_tree / f"file-{i:02d}.txt").write_text("x")
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug]) + "?page=7"
        )
        assert response.status_code == 200
        assert b"&hellip;" in response.content

    def test_permission_denied_directory(self, admin_client, media_tree, root_slug):
        noperm = media_tree / "noperm"
        noperm.mkdir()
        (noperm / "secret.txt").write_text("x")
        os.chmod(noperm, 0o000)
        try:
            response = admin_client.get(
                reverse("dj_file_browser_panel:browse", args=[root_slug, "noperm"])
            )
        finally:
            os.chmod(noperm, 0o755)
        assert response.status_code == 200
        assert b"Permission denied" in response.content

    def test_bad_page_param_falls_back(self, admin_client, media_tree, root_slug):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug]) + "?page=abc"
        )
        assert response.status_code == 200

    def test_per_page_outside_options_ignored(
        self, admin_client, media_tree, root_slug
    ):
        response = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=99999"
        )
        assert response.status_code == 200
        assert response.context["per_page"] == 100

    def test_anonymous_redirects_to_login(self, client, media_tree, root_slug):
        response = client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
        )
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]
