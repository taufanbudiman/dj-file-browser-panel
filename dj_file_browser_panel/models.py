from dj_control_room_base.core import PanelPlaceholderModel


class FileBrowserPanelPlaceholder(PanelPlaceholderModel):
    """
    Fake model used to create an entry in the admin panel for the file
    browser panel. The admin class redirects the changelist to the panel's
    main view, so no database table is ever created.
    """

    class Meta(PanelPlaceholderModel.Meta):
        verbose_name = "DJ File Browser Panel"
        verbose_name_plural = "DJ File Browser Panel"
