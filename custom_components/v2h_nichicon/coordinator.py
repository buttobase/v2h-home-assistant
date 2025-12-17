from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant

from .v2h_api import NichiconV2HClient, V2HStatus

_LOGGER = logging.getLogger(__name__)

# Polling every 2 seconds
POLL_INTERVAL = timedelta(seconds=2)


class V2HCoordinator(DataUpdateCoordinator[V2HStatus]):
    """Coordinator to manage V2H polling."""

    def __init__(self, hass: HomeAssistant, client: NichiconV2HClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Nichicon V2H Coordinator",
            update_interval=POLL_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> V2HStatus:
        """Fetch updated data from the V2H."""
        try:
            status = await self.client.get_realtime_status()
            return status
        except Exception as err:
            raise UpdateFailed(f"Error updating V2H data: {err}") from err
