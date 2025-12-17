from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

_LOGGER = logging.getLogger(__name__)

# ECHONET Lite constants (minimal set)
EHD1 = 0x10
EHD2 = 0x81

# Service codes
ESV_GET = 0x62      # Get
ESV_GET_RES = 0x72  # Get response

# Default ECHONET UDP port
DEFAULT_ECHONET_PORT = 3610


@dataclass
class V2HStatus:
    """Basic snapshot of V2H real-time status."""

    charging_power_kw: float | None = None
    discharging_power_kw: float | None = None
    mode: str | None = None          # "charging" / "discharging" / "idle" / None
    raw_hex: str | None = None       # raw response payload
    updated_at: datetime | None = None


class NichiconV2HClient:
    """Low-level ECHONET Lite client for Nichicon V2H.

    This class handles:
      - UDP send/receive
      - ECHONET frame construction
      - Basic response decoding placeholder

    Higher-level coordination (polling, HA entities) will live in the integration.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_ECHONET_PORT,
        timeout: float = 3.0,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._loop = loop or asyncio.get_event_loop()
        self._tid = 1  # transaction ID

        # These are the Echonet object codes for the V2H unit.
        # From V2H_debug.py: SEOJ=0EF001, DEOJ=027E01
        self._seoj = (0x0E, 0xF0, 0x01)  # Controller object
        self._deoj = (0x02, 0x7E, 0x01)  # Nichicon V2H object

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _next_tid(self) -> Tuple[int, int]:
        """Return next transaction ID as two bytes."""
        self._tid = (self._tid + 1) & 0xFFFF
        return (self._tid >> 8) & 0xFF, self._tid & 0xFF

    def _build_get_frame(self, epcs: List[int]) -> bytes:
        """Build a simple ECHONET Lite GET frame for given EPCs."""
        tid_hi, tid_lo = self._next_tid()

        props = bytearray()
        for epc in epcs:
            # Each GET property: EPC, PDC=0 (no data)
            props.extend([epc, 0x00])

        opc = len(epcs)

        frame = bytearray(
            [
                EHD1,
                EHD2,
                tid_hi,
                tid_lo,
                *self._seoj,
                *self._deoj,
                ESV_GET,
                opc,
            ]
        )
        frame.extend(props)
        return bytes(frame)

    async def _send_and_recv(self, payload: bytes) -> bytes:
        """Send a UDP packet and await a single response."""
        _LOGGER.debug("Sending ECHONET frame: %s", payload.hex())
        loop = self._loop

        def _exchange() -> bytes:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self._timeout)
                sock.sendto(payload, (self._host, self._port))
                data, _addr = sock.recvfrom(1024)
                return data

        try:
            data: bytes = await loop.run_in_executor(None, _exchange)
            _LOGGER.debug("Received ECHONET frame: %s", data.hex())
            return data
        except socket.timeout:
            _LOGGER.warning("Timeout talking to V2H %s", self._host)
            raise
        except OSError as err:
            _LOGGER.error("Socket error talking to V2H %s: %s", self._host, err)
            raise

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def get_realtime_status(self) -> V2HStatus:
        """Query real-time power and return a status object.

        This uses a placeholder EPC list and parser. We will align this with
        your existing debug script and Nichicon manual once we plug it in.
        """

        # TODO: Replace EPCs with the correct ones from your working script.
        # Ask for EPC D3 (charge) and D4 (discharge), just like V2H_debug.py
        epcs = [0xD3, 0xD4]

        frame = self._build_get_frame(epcs)
        resp = await self._send_and_recv(frame)

        status = self._parse_realtime_response(resp)
        return status

    # -------------------------------------------------------------------------

    def _parse_realtime_response(self, data: bytes) -> V2HStatus:
        """Parse the ECHONET response and extract power values.

        This mirrors the logic used in V2H_debug.py:
          - EPC 0xD3: real-time charging power (scaled by 1/1000)
          - EPC 0xD4: real-time discharging power (scaled by 1/1000)
        """

        response_hex = data.hex()
        _LOGGER.debug("V2H response hex: %s", response_hex)

        charging_kw: float | None = None
        discharging_kw: float | None = None

        # Parse EPC 0xD3 (Real-Time Charging Power)
        if "d3" in response_hex:
            idx = response_hex.index("d3")
            try:
                pdc = int(response_hex[idx + 2 : idx + 4], 16)
                edt_hex = response_hex[idx + 4 : idx + 4 + pdc * 2]
                charging_kw = int(edt_hex, 16) / 1000.0
                _LOGGER.debug("Parsed charging power: %s kW", charging_kw)
            except Exception as err:
                _LOGGER.warning("Failed to parse charging power from %s: %s", response_hex, err)

        # Parse EPC 0xD4 (Real-Time Discharging Power)
        if "d4" in response_hex:
            idx = response_hex.index("d4")
            try:
                pdc = int(response_hex[idx + 2 : idx + 4], 16)
                edt_hex = response_hex[idx + 4 : idx + 4 + pdc * 2]
                discharging_kw = int(edt_hex, 16) / 1000.0
                _LOGGER.debug("Parsed discharging power: %s kW", discharging_kw)
            except Exception as err:
                _LOGGER.warning("Failed to parse discharging power from %s: %s", response_hex, err)

        mode: str | None = None
        if charging_kw is not None and charging_kw > 0:
            mode = "charging"
        elif discharging_kw is not None and discharging_kw > 0:
            mode = "discharging"
        else:
            mode = "idle"

        return V2HStatus(
            charging_power_kw=charging_kw,
            discharging_power_kw=discharging_kw,
            mode=mode,
            raw_hex=response_hex,
            updated_at=datetime.utcnow(),
        )
