"""Support for Xiaomi Mi Home Air Conditioner Companion (AC Partner).

Model: lumi.acpartner.mcn02 (KTBL03LM) — 米家空调伴侣 2

Rewritten to stay compatible with current Home Assistant releases
(2024.x / 2025.x / 2026.x, Python 3.12 - 3.14):

* dropped the hard pin ``construct==2.9.45`` (it cannot be built on
  Python 3.14, which blocked the whole platform from loading);
* replaced the removed ``SUPPORT_*`` / ``HVAC_MODE_*`` / ``TEMP_CELSIUS``
  constants with their modern equivalents;
* ``device_state_attributes`` -> ``extra_state_attributes``;
* ``async_update_ha_state`` -> ``async_write_ha_state``;
* ``async_track_state_change`` -> ``async_track_state_change_event``;
* blocking miio calls are pushed to the executor.
"""
from __future__ import annotations

import enum
import logging
from datetime import timedelta
from functools import partial
from types import SimpleNamespace
from typing import Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateEntity
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady

# ---------------------------------------------------------------------------
# Version compatibility shims
# ---------------------------------------------------------------------------
# 注意：现代 HA 的 capability_attributes 用 `in` 判断 ClimateEntityFeature，
# 因此 supported_features 必须是 IntFlag 枚举本身，不能转成 int。
SUPPORT_FLAGS: Any

try:  # Home Assistant >= 2022.5
    from homeassistant.components.climate import ClimateEntityFeature

    SUPPORT_FLAGS = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
except (ImportError, AttributeError):  # very old releases
    from homeassistant.components.climate.const import (  # type: ignore[no-redef]
        SUPPORT_FAN_MODE,
        SUPPORT_SWING_MODE,
        SUPPORT_TARGET_TEMPERATURE,
    )

    SUPPORT_FLAGS = (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
    )

try:  # Home Assistant >= 2022.12
    from homeassistant.const import UnitOfTemperature

    TEMP_CELSIUS = UnitOfTemperature.CELSIUS
except ImportError:
    from homeassistant.const import TEMP_CELSIUS  # type: ignore[no-redef]

try:
    from homeassistant.components.climate import PLATFORM_SCHEMA
except ImportError:  # pragma: no cover - defensive
    PLATFORM_SCHEMA = vol.Schema(  # type: ignore[assignment]
        {vol.Optional("platform"): cv.string}, extra=vol.ALLOW_EXTRA
    )

try:  # Home Assistant >= 2021.3
    from homeassistant.helpers.event import async_track_state_change_event
except ImportError:  # pragma: no cover - defensive
    async_track_state_change_event = None  # type: ignore[assignment]
    from homeassistant.helpers.event import async_track_state_change  # type: ignore[no-redef]

_LOGGER = logging.getLogger(__name__)

# miio is imported at module level: Home Assistant imports platform modules in
# an executor thread, so this keeps the (slow) import out of the event loop.
try:
    from miio import AirConditioningCompanionMcn02, DeviceException
except ImportError as _err:  # pragma: no cover - reported via PlatformNotReady
    AirConditioningCompanionMcn02 = None  # type: ignore[assignment]
    DeviceException = Exception  # type: ignore[assignment,misc]
    _MIIO_IMPORT_ERROR: Exception | None = _err
else:
    _MIIO_IMPORT_ERROR = None

SUCCESS = ["ok"]

DEFAULT_NAME = "Xiaomi AC Companion"
TARGET_TEMPERATURE_STEP = 1

SCAN_INTERVAL = timedelta(seconds=15)

ATTR_AIR_CONDITION_MODEL = "ac_model"
ATTR_SWING_MODE = "swing_mode"
ATTR_FAN_MODE = "fan_mode"
ATTR_LOAD_POWER = "load_power"
ATTR_HVAC_MODE = "hvac_mode"

CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_POWER_SENSOR = "power_sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=16): vol.Coerce(int),
        vol.Optional(CONF_MAX_TEMP, default=30): vol.Coerce(int),
        vol.Optional(CONF_POWER_SENSOR): cv.entity_id,
        vol.Optional("scan_interval"): cv.time_period,
    }
)


def _async_track_state_change_compat(hass, entity_ids, action):
    """Register a state-change listener across HA versions."""
    if async_track_state_change_event is not None:
        return async_track_state_change_event(hass, entity_ids, action)

    @callback
    def _handler(entity_id, old_state, new_state):
        hass.async_create_task(
            action(
                SimpleNamespace(
                    data={
                        "entity_id": entity_id,
                        "old_state": old_state,
                        "new_state": new_state,
                    }
                )
            )
        )

    return async_track_state_change(hass, entity_ids, _handler)  # type: ignore[name-defined]


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the air conditioning companion from configuration.yaml."""
    if AirConditioningCompanionMcn02 is None:
        raise PlatformNotReady(
            f"python-miio is not usable: {_MIIO_IMPORT_ERROR}"
        )

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    sensor_entity_id = config.get(CONF_SENSOR)
    power_sensor_entity_id = config.get(CONF_POWER_SENSOR)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        device = AirConditioningCompanionMcn02(host, token)
        device_info = await hass.async_add_executor_job(device.info)
        model = device_info.model
        unique_id = f"{model}-{device_info.mac_address}"
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
    except DeviceException as ex:
        _LOGGER.warning("Device %s unavailable or token incorrect: %s", host, ex)
        raise PlatformNotReady from ex
    except Exception as ex:  # noqa: BLE001 - never let one device block HA boot
        _LOGGER.warning("Cannot reach device %s: %s", host, ex)
        raise PlatformNotReady from ex

    async_add_entities(
        [
            XiaomiAirConditioningCompanion(
                hass,
                name,
                device,
                unique_id,
                model,
                sensor_entity_id,
                power_sensor_entity_id,
                min_temp,
                max_temp,
            )
        ],
        update_before_add=True,
    )


class XiaomiAirConditioningCompanion(ClimateEntity):
    """Representation of a Xiaomi Air Conditioning Companion."""

    _attr_should_poll = True
    _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = SUPPORT_FLAGS
    _attr_icon = "mdi:air-conditioner"

    def __init__(
        self,
        hass,
        name,
        device,
        unique_id,
        model,
        sensor_entity_id,
        power_sensor_entity_id,
        min_temp,
        max_temp,
    ):
        """Initialize the climate device."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._device = device
        self._air_condition_model = model
        self._sensor_entity_id = sensor_entity_id
        self._power_sensor_entity_id = power_sensor_entity_id

        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp

        self._attr_available = False
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_hvac_mode = None
        self._attr_fan_mode = None
        self._attr_swing_mode = None
        self._last_on_operation = None
        self._unsub_listeners = []

        self._attr_extra_state_attributes = {
            ATTR_AIR_CONDITION_MODEL: model,
            ATTR_LOAD_POWER: None,
            ATTR_TEMPERATURE: None,
            ATTR_SWING_MODE: None,
            ATTR_FAN_MODE: None,
            ATTR_HVAC_MODE: None,
        }

    async def async_added_to_hass(self) -> None:
        """Read initial helper-sensor state and start listening for changes."""
        await super().async_added_to_hass()

        if self._sensor_entity_id:
            state = self.hass.states.get(self._sensor_entity_id)
            if state is not None:
                await self._async_update_temp(state)
            self._unsub_listeners.append(
                _async_track_state_change_compat(
                    self.hass, [self._sensor_entity_id], self._async_sensor_changed
                )
            )

        if self._power_sensor_entity_id:
            state = self.hass.states.get(self._power_sensor_entity_id)
            if state is not None and state.state not in (
                None,
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                await self._async_update_power_state(state)
            self._unsub_listeners.append(
                _async_track_state_change_compat(
                    self.hass,
                    [self._power_sensor_entity_id],
                    self._async_power_sensor_changed,
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the state listeners."""
        for unsub in self._unsub_listeners:
            if unsub is not None:
                unsub()
        self._unsub_listeners.clear()

    # ------------------------------------------------------------------
    # helper sensors
    # ------------------------------------------------------------------
    async def _async_update_temp(self, state) -> None:
        """Update the current temperature from the external sensor."""
        if state is None or state.state in (
            None,
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
            "None",
            "",
        ):
            return

        try:
            value = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Sensor %s has a non numeric state: %s",
                self._sensor_entity_id,
                state.state,
            )
            return

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit and unit != TEMP_CELSIUS:
            try:
                from homeassistant.util.unit_conversion import TemperatureConverter

                value = TemperatureConverter.convert(value, unit, TEMP_CELSIUS)
            except Exception:  # noqa: BLE001 - fall back to the raw value
                _LOGGER.debug("Could not convert %s to %s", unit, TEMP_CELSIUS)

        self._attr_current_temperature = value

    async def _async_update_power_state(self, state) -> None:
        """Mirror an external power sensor."""
        if state is None or state.state in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        if state.state == STATE_ON:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def _async_sensor_changed(self, event) -> None:
        """Handle temperature sensor updates."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        await self._async_update_temp(new_state)
        if self.entity_id is not None:
            self.async_write_ha_state()

    async def _async_power_sensor_changed(self, event) -> None:
        """Handle power sensor updates."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        await self._async_update_power_state(new_state)
        if self.entity_id is not None:
            self.async_write_ha_state()

    # ------------------------------------------------------------------
    # commands
    # ------------------------------------------------------------------
    async def _try_command(self, mask_error: str, func, *args, **kwargs) -> bool:
        """Call a device command and swallow miio errors."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )
            _LOGGER.debug("Response received: %s", result)
            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._attr_available = False
            return False
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error(mask_error, exc)
            self._attr_available = False
            return False

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        if await self._try_command(
            "Turning the miio device on failed.", self._device.on
        ):
            if self._attr_hvac_mode in (None, "off"):
                self._attr_hvac_mode = self._last_on_operation or "cool"
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        if await self._try_command(
            "Turning the miio device off failed.", self._device.off
        ):
            self._attr_hvac_mode = "off"
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set a new HVAC mode."""
        if hvac_mode in (None, "off"):
            await self.async_turn_off()
            return

        mode_value = "wind" if hvac_mode == "fan_only" else hvac_mode
        if await self.async_send_command("set_mode", [mode_value]):
            self._attr_hvac_mode = hvac_mode
            self._last_on_operation = hvac_mode
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if temperature is not None:
            try:
                value = int(round(float(temperature)))
            except (TypeError, ValueError):
                _LOGGER.error("Invalid target temperature: %s", temperature)
                value = None
            if value is not None and await self.async_send_command(
                "set_tar_temp", [value]
            ):
                self._attr_target_temperature = value
                self._attr_extra_state_attributes[ATTR_TEMPERATURE] = value
                self.async_write_ha_state()

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        try:
            from miio.airconditioningcompanionMCN import FanSpeed

            speed = FanSpeed[fan_mode.title()]
        except (ImportError, KeyError):
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return

        if await self.async_send_command("set_fan_level", [speed.value]):
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode."""
        try:
            from miio.airconditioningcompanionMCN import SwingMode

            mode = SwingMode[swing_mode.title()]
        except (ImportError, KeyError):
            _LOGGER.error("Unsupported swing mode: %s", swing_mode)
            return

        if await self.async_send_command("set_ver_swing", [mode.name.lower()]):
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_send_command(self, command, parameters) -> bool:
        """Send an infrared command to the companion."""
        return await self._try_command(
            "Sending new air conditioner configuration failed.",
            self._device.send_command,
            command,
            parameters,
        )

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------
    async def async_update(self) -> None:
        """Poll the device."""
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
        except DeviceException as ex:
            self._attr_available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
            return
        except Exception as ex:  # noqa: BLE001
            self._attr_available = False
            _LOGGER.warning("Cannot poll %s: %s", self._attr_name, ex)
            return

        _LOGGER.debug("Got new state: %s", state)
        self._attr_available = True

        power_off = str(state.power).lower() == "off"
        try:
            self._last_on_operation = OperationMode[state.mode.name].value
        except (KeyError, AttributeError):
            self._last_on_operation = None

        self._attr_hvac_mode = (
            "off" if power_off else (self._last_on_operation or "cool")
        )
        self._attr_target_temperature = state.target_temperature

        try:
            self._attr_fan_mode = state.fan_speed.name.lower()
        except AttributeError:
            self._attr_fan_mode = None
        try:
            self._attr_swing_mode = state.swing_mode.name.lower()
        except AttributeError:
            self._attr_swing_mode = None

        self._attr_extra_state_attributes = {
            ATTR_AIR_CONDITION_MODEL: self._air_condition_model,
            ATTR_LOAD_POWER: getattr(state, "load_power", None),
            ATTR_TEMPERATURE: (
                state.target_temperature
                if state.target_temperature is not None
                and state.target_temperature <= self._attr_max_temp
                else None
            ),
            ATTR_SWING_MODE: self._attr_swing_mode,
            ATTR_FAN_MODE: self._attr_fan_mode,
            ATTR_HVAC_MODE: "off" if power_off else self._last_on_operation,
        }

    @property
    def hvac_modes(self):
        """Return the list of available HVAC modes."""
        return [mode.value for mode in OperationMode]

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        try:
            from miio.airconditioningcompanionMCN import FanSpeed

            return [speed.name.lower() for speed in FanSpeed]
        except ImportError:
            return None

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        try:
            from miio.airconditioningcompanionMCN import SwingMode

            return [mode.name.lower() for mode in SwingMode]
        except ImportError:
            return None

    @property
    def last_on_operation(self):
        """Return the last operation used while the AC was on."""
        return self._last_on_operation


class OperationMode(enum.Enum):
    """HVAC modes understood by the companion."""

    Heat = "heat"
    Cool = "cool"
    Auto = "auto"
    Dehumidify = "dry"
    Ventilate = "fan_only"
    Off = "off"
