from django.urls import path

from . import views

app_name = "dj_file_browser_panel"

urlpatterns = [
    path("", views.index, name="index"),
    path("<str:root_slug>/", views.browse_root, name="browse_root"),
    path("<str:root_slug>/<path:rel_path>/", views.browse, name="browse"),
]
