"""Provides the NZBGet DataUpdateCoordinator."""

import asyncio
from datetime import timedelta
import logging

from pynzbgetapi import NZBGetAPI, NZBGetAPIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NZBGetDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching NZBGet data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize global NZBGet data updater."""
        self.nzbget = NZBGetAPI(
            config_entry.data[CONF_HOST],
            config_entry.data.get(CONF_USERNAME),
            config_entry.data.get(CONF_PASSWORD),
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
            config_entry.data[CONF_PORT],
        )

        self._completed_downloads_init = False
        self._completed_downloads = set[tuple]()

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )

    def _check_completed_downloads(self, history):
        """Check history for newly completed downloads."""
        actual_completed_downloads = {
            (x["Name"], x["Category"], x["Status"]) for x in history
        }

        if self._completed_downloads_init:
            tmp_completed_downloads = list(
                actual_completed_downloads.difference(self._completed_downloads)
            )

            for download in tmp_completed_downloads:
                self.hass.bus.fire(
                    "nzbget_download_complete",
                    {
                        "name": download[0],
                        "category": download[1],
                        "status": download[2],
                    },
                )

        self._completed_downloads = actual_completed_downloads
        self._completed_downloads_init = True

    async def _async_update_data(self) -> dict:
        """Fetch data from NZBGet."""

        def _update_data() -> dict:
            """Fetch data from NZBGet via sync functions."""
            status = self.nzbget.status()
            history = self.nzbget.history()

            self._check_completed_downloads(history)

            return {
                "status": status,
                "downloads": history,
            }

        try:
            async with asyncio.timeout(4):
                return await self.hass.async_add_executor_job(_update_data)
        except NZBGetAPIException as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
