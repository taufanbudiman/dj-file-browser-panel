"""
URL configuration for example_project project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/files/", include("dj_file_browser_panel.urls")),
    path("admin/dj-control-room-base/", include("dj_control_room_base.urls")),
    # Uncomment when dj-control-room (the hub) is installed:
    # path("admin/dj-control-room/", include("dj_control_room.urls")),
    path("admin/", admin.site.urls),
]
