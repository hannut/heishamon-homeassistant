"""Definitions for HeishaMon sensors added to MQTT."""
from __future__ import annotations
from functools import partial
import json

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional
import logging

from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.number import NumberEntityDescription


from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)

from .models import HEATPUMP_MODELS
from .const import DeviceType

_LOGGER = logging.getLogger(__name__)

OPERATING_MODE_TO_STRING = {
    "0": "Heat only",
    # "1": "Cool only",
    "2": "Auto(Heat)",
    "3": "DHW only",
    "4": "Heat+DWH",
    # "5": "Cool+DHW",
    "6": "Auto(Heat)+DHW",
    # "7": "Auto(Cool)",
    # "8": "Auto(Cool)+DHW",
}


def operating_mode_to_state(value):
    """
    We intentionally don't support all modes for now
    """
    options = [
        mode for (mode, string) in OPERATING_MODE_TO_STRING.items() if string == value
    ]
    if len(options) == 0:
        return None
    return options[0]


def read_operating_mode_state(value):
    return OPERATING_MODE_TO_STRING.get(value, f"Unknown operating mode value: {value}")


def read_power_mode_time(value):
    return int(value) * 30


def read_threeway_valve(value: str) -> Optional[str]:
    if value == "0":
        return "Room"
    elif value == "1":
        return "Tank"
    else:
        _LOGGER.info(f"Reading unhandled value for ThreeWay Valve state: '{value}'")
        return None


@dataclass
class HeishaMonEntityDescription:
    heishamon_topic_id: str | None = None

    # a method called when receiving a new value
    state: Callable | None = None

    # device sensor belong to
    device: DeviceType = DeviceType.HEATPUMP


@dataclass
class HeishaMonSensorEntityDescription(
    HeishaMonEntityDescription, SensorEntityDescription
):
    """Sensor entity description for HeishaMon."""

    # a method called when receiving a new value. With a lot of context. Used to update device info for instance
    on_receive: Callable | None = None


@dataclass
class HeishaMonSwitchEntityDescription(
    HeishaMonEntityDescription, SwitchEntityDescription
):
    """Switch entity description for HeishaMon."""

    command_topic: str = "void/topic"
    qos: int = 0
    payload_on: str = "1"
    payload_off: str = "0"
    retain: bool = False
    encoding: str = "utf-8"


@dataclass
class HeishaMonBinarySensorEntityDescription(
    HeishaMonEntityDescription, BinarySensorEntityDescription
):
    """Binary sensor entity description for HeishaMon."""

    pass


@dataclass
class HeishaMonSelectEntityDescription(
    HeishaMonEntityDescription, SelectEntityDescription
):
    """Select entity description for HeishaMon"""

    command_topic: str = "void/topic"
    retain: bool = False
    encoding: str = "utf-8"
    qos: int = 0
    # function to transform selected option in value sent via mqtt
    state_to_mqtt: Optional[Callable] = None


@dataclass
class HeishaMonNumberEntityDescription(
    HeishaMonEntityDescription, NumberEntityDescription
):
    """Number entity description for HeishaMon"""

    command_topic: str = "void/topic"
    retain: bool = False
    encoding: str = "utf-8"
    qos: int = 0
    # function to transform selected option in value sent via mqtt
    state_to_mqtt: Optional[Callable] = None


def bit_to_bool(value: str) -> Optional[bool]:
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return None


def read_quiet_mode(value: str) -> str:
    # values range from 0 to 4
    if value == "4":
        return "Scheduled"
    elif value == "0":
        return "Off"
    return value


def read_heatpump_model(value: str) -> str:
    return HEATPUMP_MODELS.get(value, "Unknown model for HeishaMon")


def write_quiet_mode(selected_value: str):
    if selected_value == "Off":
        return 0
    elif selected_value == "Scheduled":
        return 4
    else:
        return int(selected_value)


NUMBERS: tuple[HeishaMonNumberEntityDescription, ...] = (
    HeishaMonNumberEntityDescription(
        heishamon_topic_id="SET11",
        key="panasonic_heat_pump/main/DHW_Target_Temp",
        command_topic="panasonic_heat_pump/commands/SetDHWTemp",
        name="DHW Target Temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        native_min_value=48,
        native_max_value=60,
        state=int,
        state_to_mqtt=int,
    ),
)

SELECTS: tuple[HeishaMonSelectEntityDescription, ...] = (
    HeishaMonSelectEntityDescription(
        heishamon_topic_id="SET3",  # also corresponds to TOP18
        key="panasonic_heat_pump/main/Quiet_Mode_Level",
        command_topic="panasonic_heat_pump/commands/SetQuietMode",
        name="Aquarea Quiet Mode",
        entity_category=EntityCategory.CONFIG,
        state=read_quiet_mode,
        state_to_mqtt=write_quiet_mode,
        options=["Off", "1", "2", "3", "Scheduled"],
    ),
    HeishaMonSelectEntityDescription(
        heishamon_topic_id="SET9",
        key="panasonic_heat_pump/main/Operating_Mode_State",
        command_topic="panasonic_heat_pump/commands/SetOperationMode",
        name="Aquarea Mode",
        state=read_operating_mode_state,
        state_to_mqtt=operating_mode_to_state,
        options=list(OPERATING_MODE_TO_STRING.values()),
    ),
)


MQTT_SWITCHES: tuple[HeishaMonSwitchEntityDescription, ...] = (
    HeishaMonSwitchEntityDescription(
        heishamon_topic_id="TOP19",
        key="panasonic_heat_pump/main/Holiday_Mode_State",
        command_topic="panasonic_heat_pump/main/Holiday_Mode_State",
        name="Aquarea Holiday Mode",
        entity_category=EntityCategory.CONFIG,
        state=bit_to_bool,
    ),
    HeishaMonSwitchEntityDescription(
        heishamon_topic_id="TOP0",
        key="panasonic_heat_pump/main/Heatpump_State",
        command_topic="panasonic_heat_pump/commands/SetHeatpump",
        name="Aquarea Main Power",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    HeishaMonSwitchEntityDescription(
        heishamon_topic_id="TOP2",
        key="panasonic_heat_pump/main/Force_DHW_State",
        command_topic="panasonic_heat_pump/commands/SetForceDHW",
        name="Aquarea Force DHW Mode",
        entity_category=EntityCategory.CONFIG,
        state=bit_to_bool,
    ),
    HeishaMonSwitchEntityDescription(
        heishamon_topic_id="SET24",  # corresponds to "TOP13"
        key="panasonic_heat_pump/main/Main_Schedule_State",
        command_topic="panasonic_heat_pump/commands/SetMainSchedule",
        name="Aquarea Main thermosthat schedule",
        entity_category=EntityCategory.CONFIG,
        state=bit_to_bool,
    ),
)

BINARY_SENSORS: tuple[HeishaMonBinarySensorEntityDescription, ...] = (
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP3",
        key="panasonic_heat_pump/main/Quiet_Mode_Schedule",
        name="Aquarea Quiet Mode Schedule",
        state=bit_to_bool,
    ),
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP26",
        key="panasonic_heat_pump/main/Defrosting_State",
        name="Aquarea Defrost State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP58",
        key="panasonic_heat_pump/main/DHW_Heater_State",
        name="Aquarea Tank Heater Enabled",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP59",
        key="panasonic_heat_pump/main/Room_Heater_State",
        name="Aquarea Room Heater Enabled",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP60",
        key="panasonic_heat_pump/main/Internal_Heater_State",
        name="Aquarea Internal Heater State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    HeishaMonBinarySensorEntityDescription(
        heishamon_topic_id="TOP61",
        key="panasonic_heat_pump/main/External_Heater_State",
        name="Aquarea External Heater State",
        state=bit_to_bool,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
)


def update_device_model(
    hass: HomeAssistant, entity: SensorEntity, config_entry_id: str, model: str
):
    _LOGGER.debug("Set model")

    device_registry = dr.async_get(hass)
    identifiers = None
    if entity.device_info is not None and "identifiers" in entity.device_info:
        identifiers = entity.device_info["identifiers"]
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id, identifiers=identifiers, model=model
    )


def read_stats_json(field_name: str, json_doc: str) -> Optional[float]:
    field_value = json.loads(json_doc).get(field_name, None)
    if field_value:
        return float(field_value)
    return None


def ms_to_secs(value: Optional[float]) -> Optional[float]:
    if value:
        return value / 1000
    return None


SENSORS: tuple[HeishaMonSensorEntityDescription, ...] = (
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP1",
        key="panasonic_heat_pump/main/Pump_Flow",
        name="Aquarea Pump Flow",
        native_unit_of_measurement="L/min",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP4",
        key="panasonic_heat_pump/main/Operating_Mode_State",
        name="Aquarea Mode",
        # state_class=SensorStateClass.MEASUREMENT,
        # device_class=SensorDeviceClass.ENERGY,
        # icon= "mdi:on"
        # entity_registry_enabled_default=True,
        # native_unit_of_measurement="L/min",
        state=read_operating_mode_state,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP5",
        key="panasonic_heat_pump/main/Main_Inlet_Temp",
        name="Aquarea Inlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP6",
        key="panasonic_heat_pump/main/Main_Outlet_Temp",
        name="Aquarea Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP7",
        key="panasonic_heat_pump/main/Main_Target_Temp",
        name="Aquarea Outlet Target Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP8",
        key="panasonic_heat_pump/main/Compressor_Freq",
        name="Aquarea Compressor Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement="Hz",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP9",
        key="panasonic_heat_pump/main/DHW_Target_Temp",
        name="Aquarea Tank Set Temperature",
        entity_category=EntityCategory.CONFIG,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP10",
        key="panasonic_heat_pump/main/DHW_Temp",
        name="Aquarea Tank Actual Tank Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP11",
        key="panasonic_heat_pump/main/Operations_Hours",
        name="Aquarea Compressor Operating Hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="Hours",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP12",
        key="panasonic_heat_pump/main/Operations_Counter",
        name="Aquarea Compressor Start/Stop Counter",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP14",
        key="panasonic_heat_pump/main/Outside_Temp",
        name="Aquarea Outdoor Ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP15",
        key="panasonic_heat_pump/main/Heat_Energy_Production",
        name="Aquarea Power Produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP16",
        key="panasonic_heat_pump/main/Heat_Energy_Consumption",
        name="Aquarea Power Consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP17",
        key="panasonic_heat_pump/main/Powerful_Mode_Time",
        name="Aquarea Powerful Mode",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="Min",
        state=read_power_mode_time,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP20",
        key="panasonic_heat_pump/main/ThreeWay_Valve_State",
        name="Aquarea 3-way Valve",
        state=read_threeway_valve,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP21",
        key="panasonic_heat_pump/main/Outside_Pipe_Temp",
        name="Aquarea Outdoor Pipe Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP22",
        key="panasonic_heat_pump/main/DHW_Heat_Delta",
        name="Aquarea DHW heating delta",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP23",
        key="panasonic_heat_pump/main/Heat_Delta",
        name="Aquarea Heat delta",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP24",
        key="panasonic_heat_pump/main/Cool_Delta",
        name="Aquarea Cool delta",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP25",
        key="panasonic_heat_pump/main/DHW_Holiday_Shift_Temp",
        name="Aquarea DHW Holiday shift temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP27",
        key="panasonic_heat_pump/main/Z1_Heat_Request_Temp",
        # it can be relative (-5 -> +5, or absolute [20, ..[)
        name="Aquarea Zone 1 Heat Requested shift",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP28",
        # it can be relative (-5 -> +5, or absolute [5, 20])
        key="panasonic_heat_pump/main/Z1_Cool_Request_Temp",
        name="Aquarea Zone 1 Cool Requested shift",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP29",
        key="panasonic_heat_pump/main/Z1_Heat_Curve_Target_High_Temp",
        name="Aquarea Zone 1 Target temperature at lowest point on heating curve",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP30",
        key="panasonic_heat_pump/main/Z1_Heat_Curve_Target_Low_Temp",
        name="Aquarea Zone 1 Target temperature at highest point on heating curve",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP31",
        key="panasonic_heat_pump/main/Z1_Heat_Curve_Outside_High_Temp",
        name="Aquarea Zone 1 Lowest outside temperature on the heating curve",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP32",
        key="panasonic_heat_pump/main/Z1_Heat_Curve_Outside_Low_Temp",
        name="Aquarea Zone 1 Highest outside temperature on the heating curve",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP33",
        key="panasonic_heat_pump/main/Room_Thermostat_Temp",
        name="Aquarea Remote control thermosthat temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP34",
        key="panasonic_heat_pump/main/Z2_Heat_Request_Temp",
        # it can be relative (-5 -> +5, or absolute [20, ..[)
        name="Aquarea Zone 2 Heat Requested shift",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP35",
        # it can be relative (-5 -> +5, or absolute [5, 20])
        key="panasonic_heat_pump/main/Z2_Cool_Request_Temp",
        name="Aquarea Zone 2 Cool Requested shift",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP36",
        key="panasonic_heat_pump/main/Z1_Water_Temp",
        name="Aquarea Zone 1 water outlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP37",
        key="panasonic_heat_pump/main/Z2_Water_Temp",
        name="Aquarea Zone 2 water outlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP38",
        key="panasonic_heat_pump/main/Cool_Energy_Production",
        name="Aquarea Thermal Cooling power production",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP39",
        key="panasonic_heat_pump/main/Cool_Energy_Consumption",
        name="Aquarea Thermal Cooling power consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP40",
        key="panasonic_heat_pump/main/DHW_Energy_Production",
        name="Aquarea DHW Power Produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP41",
        key="panasonic_heat_pump/main/DHW_Energy_Consumption",
        name="Aquarea DHW Power Consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
        # original template states "force_update" FIXME
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP42",
        key="panasonic_heat_pump/main/Z1_Water_Target_Temp",
        name="Aquarea Zone 1 water target temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP43",
        key="panasonic_heat_pump/main/Z2_Water_Target_Temp",
        name="Aquarea Zone 2 water target temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP44",
        key="panasonic_heat_pump/main/Error",
        name="Aquarea Last Error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP45",
        key="panasonic_heat_pump/main/Room_Holiday_Shift_Temp",
        name="Aquarea Room heating Holiday shift temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP46",
        key="panasonic_heat_pump/main/Buffer_Temp",
        name="Aquarea Actual Buffer temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP47",
        key="panasonic_heat_pump/main/Solar_Temp",
        name="Aquarea Actual Solar temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP48",
        key="panasonic_heat_pump/main/Pool_Temp",
        name="Aquarea Actual Pool temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP49",
        key="panasonic_heat_pump/main/Main_Hex_Outlet_Temp",
        name="Aquarea Main HEX Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP50",
        key="panasonic_heat_pump/main/Discharge_Temp",
        name="Aquarea Discharge Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP51",
        key="panasonic_heat_pump/main/Inside_Pipe_Temp",
        name="Aquarea Inside Pipe Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP52",
        key="panasonic_heat_pump/main/Defrost_Temp",
        name="Aquarea Defrost Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP53",
        key="panasonic_heat_pump/main/Eva_Outlet_Temp",
        name="Aquarea Eva Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP54",
        key="panasonic_heat_pump/main/Bypass_Outlet_Temp",
        name="Aquarea Bypass Outlet Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP55",
        key="panasonic_heat_pump/main/Ipm_Temp",
        name="Aquarea Ipm Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP56",
        key="panasonic_heat_pump/main/Z1_Temp",
        name="Aquarea Zone1: Actual Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP57",
        key="panasonic_heat_pump/main/Z2_Temp",
        name="Aquarea Zone1: Actual Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP62",
        key="panasonic_heat_pump/main/Fan1_Motor_Speed",
        name="Aquarea Fan 1 Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP63",
        key="panasonic_heat_pump/main/Fan2_Motor_Speed",
        name="Aquarea Fan 2 Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP64",
        key="panasonic_heat_pump/main/High_Pressure",
        name="Aquarea High pressure",
        native_unit_of_measurement="Kgf/cm2",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP65",
        key="panasonic_heat_pump/main/Pump_Speed",
        name="Aquarea Pump Speed",
        native_unit_of_measurement="R/min",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP66",
        key="panasonic_heat_pump/main/Low_Pressure",
        name="Aquarea Low Pressure",
        native_unit_of_measurement="Kgf/cm2",
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP67",
        key="panasonic_heat_pump/main/Compressor_Current",
        name="Aquarea Compressor Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="TOP92",
        key="panasonic_heat_pump/main/Heat_Pump_Model",
        name="Aquarea Heatpump model",
        state=read_heatpump_model,
        on_receive=update_device_model,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_rssi",
        key="panasonic_heat_pump/stats",
        name="HeishaMon RSSI",
        state=partial(read_stats_json, "wifi"),
        device=DeviceType.HEISHAMON,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_uptime",
        key="panasonic_heat_pump/stats",
        name="HeishaMon Uptime",
        state=lambda json_doc: ms_to_secs(read_stats_json("uptime", json_doc)),
        device=DeviceType.HEISHAMON,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_total_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon Total reads",
        state=partial(read_stats_json, "total reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_good_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon Good reads",
        state=partial(read_stats_json, "good reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_badcrc_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon bad CRC reads",
        state=partial(read_stats_json, "bad crc reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_badheader_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon bad header reads",
        state=partial(read_stats_json, "bad header reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_tooshort_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon too short reads",
        state=partial(read_stats_json, "too short reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_toolong_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon too long reads",
        state=partial(read_stats_json, "too long reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_timeout_reads",
        key="panasonic_heat_pump/stats",
        name="HeishaMon timeout reads",
        state=partial(read_stats_json, "timeout reads"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_voltage",
        key="panasonic_heat_pump/stats",
        name="HeishaMon voltage",
        state=partial(read_stats_json, "voltage"),
        device=DeviceType.HEISHAMON,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_freememory",
        key="panasonic_heat_pump/stats",
        name="HeishaMon free memory",
        state=partial(read_stats_json, "free memory"),
        device=DeviceType.HEISHAMON,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1_freeheap",
        key="panasonic_heat_pump/stats",
        name="HeishaMon free heap",
        state=partial(read_stats_json, "free heap"),
        device=DeviceType.HEISHAMON,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HeishaMonSensorEntityDescription(
        heishamon_topic_id="STAT1-mqttreconnects",
        key="panasonic_heat_pump/stats",
        name="HeishaMon mqtt reconnects",
        state=partial(read_stats_json, "mqtt reconnects"),
        device=DeviceType.HEISHAMON,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
