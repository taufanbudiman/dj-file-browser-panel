from typing import ClassVar

from dj_control_room_base.core import PanelPlugin


class FileBrowserPanel(PanelPlugin):
    name = "File Browser Panel"
    description = "Browse media and static files read-only from Django admin"
    icon = "layers"
    icon_color = "accent"
    features: ClassVar[list] = [
        "Browse configured filesystem roots from the admin",
        "Directory listings with breadcrumbs and pagination",
        "File metadata: size, modified time, and MIME type",
        "Strictly read-only with path sandboxing",
    ]

    app_name = "dj_file_browser_panel"
    docs_url = "https://github.com/taufanbudiman/dj-file-browser-panel"
    pypi_url = "https://pypi.org/project/dj-file-browser-panel/"

    def get_url_name(self):
        return "index"

    def get_config(self):
        from .conf import panel_config

        return panel_config
