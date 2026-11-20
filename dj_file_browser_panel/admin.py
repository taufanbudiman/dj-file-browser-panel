from dj_control_room_base.core import BasePanelAdmin
from django.contrib import admin

from .conf import panel_config
from .models import FileBrowserPanelPlaceholder


@admin.register(FileBrowserPanelPlaceholder)
class FileBrowserPanelPlaceholderAdmin(BasePanelAdmin):
    redirect_url_name = "dj_file_browser_panel:index"
    panel_config = panel_config
