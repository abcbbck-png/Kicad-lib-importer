# -*- coding: utf-8 -*-
"""KiCad ActionPlugin registration for the connector generator."""

try:
    import pcbnew  # noqa: F401

    from .main import ConnectorGeneratorPlugin

    ConnectorGeneratorPlugin().register()
except ImportError:
    pass
except Exception as exc:
    import logging

    logging.getLogger("connector_generator_plugin").error("Failed to register plugin: %s", exc)
