"""Tests for the PanelPlugin entry point declaration."""

from dj_file_browser_panel.panel import FileBrowserPanel


def test_panel_plugin_contract():
    panel = FileBrowserPanel()
    panel.validate()
    assert panel.name == "File Browser Panel"
    assert panel.app_name == "dj_file_browser_panel"
    assert panel.get_url_name() == "index"
    assert panel.docs_url
    assert panel.pypi_url
    assert panel.features


def test_panel_get_config():
    panel = FileBrowserPanel()
    config = panel.get_config()
    assert config is not None
    assert config.settings_key == "DJ_FILE_BROWSER_PANEL_SETTINGS"
