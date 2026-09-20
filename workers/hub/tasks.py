"""Home & IoT worker — Workstream F.

S0 skeleton. The Home Assistant adapter and Nest readings land in S3; MQTT
publish-back, the Lunette feed and the calendar push adapters in S9.

The adapter is deliberately written against Home Assistant *entity ids* rather
than against Nest or HomeKit directly, so open decision 2 (ADR 0006) can be
answered either way without a code change.
"""

from typing import ClassVar

#: The metrics the rest of the app knows how to use. Anything else is ignored
#: rather than stored, so a chatty HA instance cannot flood the hypertable.
SUPPORTED_METRICS = {
    "temperature_c",
    "humidity_pct",
    "soil_moisture_pct",
    "soil_temperature_c",
    "illuminance_lux",
    "soil_ec",
}

MQTT_PREFIX = "herbology"
DISCOVERY_PREFIX = "homeassistant"


def state_topic(kind: str, key: str) -> str:
    """See contracts/events/mqtt.md — the topic layout is contract, not detail."""
    return f"{MQTT_PREFIX}/{kind}/{key}"


def discovery_topic(component: str, object_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/{component}/{MQTT_PREFIX}/{object_id}/config"


def object_id_for(specimen_id: str) -> str:
    """Stable across restarts, so HA keeps its entity history."""
    return f"specimen_{specimen_id.replace('-', '')}"


async def poll_home_assistant(ctx: dict) -> None:  # pragma: no cover - S3
    raise NotImplementedError("S3 (F): HA REST/WebSocket adapter")


async def publish_to_mqtt(ctx: dict) -> None:  # pragma: no cover - S9
    raise NotImplementedError("S9 (F): MQTT discovery and publish-back")


class WorkerSettings:
    functions: ClassVar[list] = [poll_home_assistant, publish_to_mqtt]
