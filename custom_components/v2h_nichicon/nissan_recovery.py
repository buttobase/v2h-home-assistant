from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class RecoveryStep(str, Enum):
    IDLE = "idle"
    STEP1_TIMER_TOGGLE = "step1_timer_toggle"
    STEP2_START_DISCHARGE = "step2_start_discharge"
    STEP3_CONNECTOR_RESET = "step3_connector_reset"
    STEP4_START_CHARGE = "step4_start_charge"
    DONE = "done"
    FAILED = "failed"


@dataclass
class NissanObservedState:
    # Derived from sensors (coordinator data)
    connected: bool
    cable_locked: bool
    soc: float | None
    charging_kw: float
    discharging_kw: float
    grid_sold_kw: float
    grid_bought_kw: float


@dataclass
class RecoveryConfig:
    # thresholds / timing
    chg_on_kw: float = 0.2
    dis_on_kw: float = 0.2

    stuck_after: timedelta = timedelta(minutes=3)
    cooldown_after_success: timedelta = timedelta(minutes=10)
    cooldown_after_failure: timedelta = timedelta(minutes=30)

    # waits between actions
    wait_after_step1: timedelta = timedelta(seconds=60)
    wait_after_step2: timedelta = timedelta(seconds=60)
    wait_between_unlock_lock: timedelta = timedelta(seconds=15)
    wait_after_step3: timedelta = timedelta(seconds=60)
    step4_charge_duration: timedelta = timedelta(minutes=10)
    wait_after_step4_stop: timedelta = timedelta(seconds=10)

    # retries
    max_attempts: int = 2


class NissanRecoveryController:
    """
    Stateless-internals-recovery controller.
    - Called periodically from coordinator update loop.
    - Never blocks (no sleeps). Uses timestamps.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        cfg: RecoveryConfig,
        *,
        domain: str,
        services: dict[str, str],
        supports_timer_toggles: bool,
    ) -> None:
        """
        services: mapping from logical action -> HA service call string.
        Example:
          "lock": "button.press"
          "unlock": "button.press"
        We’ll call via hass.services.async_call(domain/service, data)
        but for buttons/switches we’ll use standard domains.
        """
        self.hass = hass
        self.cfg = cfg
        self.domain = domain
        self.services = services
        self.supports_timer_toggles = supports_timer_toggles

        self._step: RecoveryStep = RecoveryStep.IDLE
        self._attempt: int = 0
        self._since_idle_wrong: dt_util.dt.datetime | None = None
        self._next_action_at: dt_util.dt.datetime | None = None
        self._cooldown_until: dt_util.dt.datetime | None = None

    # -----------------
    # Public interface
    # -----------------

    @property
    def step(self) -> str:
        return self._step.value

    @property
    def attempt(self) -> int:
        return self._attempt

    def in_cooldown(self) -> bool:
        return self._cooldown_until is not None and dt_util.utcnow() < self._cooldown_until

    async def tick(self, obs: NissanObservedState) -> None:
        """Run one supervisor tick."""
        now = dt_util.utcnow()

        # Basic eligibility gates
        if not obs.connected:
            self._reset("not connected")
            return

        if not obs.cable_locked:
            # Connector lock is allowed outside recovery (safety + prerequisite)
            await self._press_button("lock_connector")
            # Don’t enter recovery until locked; give it time
            return

        # Cooldown gate
        if self.in_cooldown():
            return

        active = self._is_active(obs)
        should_be_active = self._should_be_active(obs)

        # Track "idle when should be active" duration
        if should_be_active and not active:
            if self._since_idle_wrong is None:
                self._since_idle_wrong = now
        else:
            self._since_idle_wrong = None

        stuck = (
            should_be_active
            and not active
            and self._since_idle_wrong is not None
            and (now - self._since_idle_wrong) >= self.cfg.stuck_after
        )

        # If not stuck and not recovering, nothing to do
        if self._step == RecoveryStep.IDLE and not stuck:
            return

        # If stuck and not recovering, start recovery
        if self._step == RecoveryStep.IDLE and stuck:
            self._attempt += 1
            if self._attempt > self.cfg.max_attempts:
                _LOGGER.warning("Recovery: max attempts exceeded -> cooldown(failure)")
                self._enter_cooldown(failure=True)
                self._step = RecoveryStep.FAILED
                return

            _LOGGER.warning("Recovery: starting attempt %s", self._attempt)
            self._step = RecoveryStep.STEP1_TIMER_TOGGLE if self.supports_timer_toggles else RecoveryStep.STEP2_START_DISCHARGE
            self._next_action_at = now  # act immediately

        # If recovering: run step machine
        await self._run_steps(obs, now)

    # -----------------
    # Step machine
    # -----------------

    async def _run_steps(self, obs: NissanObservedState, now) -> None:
        # Wait gate
        if self._next_action_at is not None and now < self._next_action_at:
            return

        # Success condition at any time
        if self._is_active(obs):
            _LOGGER.warning("Recovery: success (active detected) -> cooldown(success)")
            self._step = RecoveryStep.DONE
            self._enter_cooldown(failure=False)
            return

        if self._step == RecoveryStep.STEP1_TIMER_TOGGLE:
            # Best-effort: toggle if exposed; ignore failures
            await self._toggle_optional_timers()
            self._next_action_at = now + self.cfg.wait_after_step1
            self._step = RecoveryStep.STEP2_START_DISCHARGE
            return

        if self._step == RecoveryStep.STEP2_START_DISCHARGE:
            await self._press_button("start_discharge")
            self._next_action_at = now + self.cfg.wait_after_step2
            self._step = RecoveryStep.STEP3_CONNECTOR_RESET
            return

        if self._step == RecoveryStep.STEP3_CONNECTOR_RESET:
            await self._press_button("unlock_connector")
            self._next_action_at = now + self.cfg.wait_between_unlock_lock
            self._step = RecoveryStep.STEP3_CONNECTOR_RESET + "_LOCK"  # sentinel
            return

        if self._step == (RecoveryStep.STEP3_CONNECTOR_RESET + "_LOCK"):  # type: ignore[operator]
            await self._press_button("lock_connector")
            self._next_action_at = now + self.cfg.wait_after_step3
            self._step = RecoveryStep.STEP4_START_CHARGE
            return

        if self._step == RecoveryStep.STEP4_START_CHARGE:
            await self._press_button("start_charge")
            self._next_action_at = now + self.cfg.step4_charge_duration
            self._step = RecoveryStep.STEP4_START_CHARGE + "_STOP"  # sentinel
            return

        if self._step == (RecoveryStep.STEP4_START_CHARGE + "_STOP"):  # type: ignore[operator]
            await self._press_button("stop")
            self._next_action_at = now + self.cfg.wait_after_step4_stop
            # After step4, loop back: try step1 again if supported, else step2
            self._step = RecoveryStep.STEP1_TIMER_TOGGLE if self.supports_timer_toggles else RecoveryStep.STEP2_START_DISCHARGE
            return

        # If we got here with an unknown step, reset safely
        _LOGGER.error("Recovery: unknown step %s, resetting", self._step)
        self._reset("unknown step")

    # -----------------
    # Decision helpers
    # -----------------

    def _is_active(self, obs: NissanObservedState) -> bool:
        return (obs.charging_kw >= self.cfg.chg_on_kw) or (obs.discharging_kw >= self.cfg.dis_on_kw)

    def _should_be_active(self, obs: NissanObservedState) -> bool:
        # We ignore Nichicon timers. We decide "should be active" purely from grid.
        # If selling OR buying, Nichicon has an opportunity to act.
        return (obs.grid_sold_kw > 0.05) or (obs.grid_bought_kw > 0.05)

    # -----------------
    # Actuators
    # -----------------

    async def _press_button(self, logical: str) -> None:
        entity_id = self.services.get(logical)
        if not entity_id:
            _LOGGER.debug("Recovery: no entity configured for %s", logical)
            return
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=False,
        )

    async def _toggle_optional_t_
