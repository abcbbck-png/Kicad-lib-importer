# -*- coding: utf-8 -*-
"""KiCad ActionPlugin entry point."""

from __future__ import annotations

import logging
import os


LOG_PATH = os.path.expanduser("~/.kicad_connector_generator_plugin.log")
logger = logging.getLogger("connector_generator_plugin")

if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    try:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except Exception:
        pass


try:
    import pcbnew

    _ActionPluginBase = pcbnew.ActionPlugin
except ImportError:

    class _ActionPluginBase:
        def register(self):
            pass

        def defaults(self):
            pass

        def Run(self):
            pass


class ConnectorGeneratorPlugin(_ActionPluginBase):
    """Open the connector generator dialog."""

    def defaults(self):
        self.name = "Generate Connector Symbols"
        self.category = "Library Tools"
        self.description = "Генерация регулярных символов разъемов KiCad"
        self.show_toolbar_button = True

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        self.icon_file_name = icon_path if os.path.isfile(icon_path) else ""

    def Run(self):
        logger.info("Plugin launched")
        try:
            import wx

            from .ui import ConnectorGeneratorDialog

            parent = None
            app = wx.GetApp()
            if app is not None and hasattr(app, "GetTopWindow"):
                try:
                    parent = app.GetTopWindow()
                except Exception:
                    parent = None

            dlg = ConnectorGeneratorDialog(parent)
            dlg.ShowModal()
            dlg.Destroy()
        except Exception:
            logger.exception("Unhandled plugin error")
            try:
                import wx

                wx.MessageBox(
                    "Ошибка плагина Connector Generator.\n"
                    f"Подробности: {LOG_PATH}",
                    "Connector Generator",
                    wx.OK | wx.ICON_ERROR,
                )
            except Exception:
                pass


def _standalone():
    import wx

    from connector_generator_plugin.ui import ConnectorGeneratorDialog

    app = wx.App(False)
    dlg = ConnectorGeneratorDialog(None)
    dlg.ShowModal()
    dlg.Destroy()
    app.MainLoop()


if __name__ == "__main__":
    _standalone()
