"""View tests for the DJ File Browser Panel."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def media_tree(tmp_path, settings):
    root = tmp_path / "media"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "nested.txt").write_text("nested file contents")
    (root / "hello.txt").write_text("hello world")
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
        # per_page=1; visible entries are sub/ then hello.txt
        page1 = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=1"
        )
        assert b"/admin/files/media/sub/" in page1.content
        assert b"hello.txt" not in page1.content

        page2 = admin_client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
            + "?per_page=1&page=2"
        )
        assert page2.status_code == 200
        assert b"hello.txt" in page2.content
        assert b"/admin/files/media/sub/" not in page2.content
        assert b"dcr-pagination" in page2.content

    def test_anonymous_redirects_to_login(self, client, media_tree, root_slug):
        response = client.get(
            reverse("dj_file_browser_panel:browse_root", args=[root_slug])
        )
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]
