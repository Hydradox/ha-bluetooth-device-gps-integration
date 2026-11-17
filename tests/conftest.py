"""Shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ARG001
    """Let Home Assistant load the integration from `custom_components/`."""
    return
