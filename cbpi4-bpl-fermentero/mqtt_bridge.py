# -*- coding: utf-8 -*-
"""Cliente MQTT partilhado entre sensores BPL (telemetria v1 + modo legado)."""

import json
import logging
import threading
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

_telemetry: Dict[str, Any] = {}
_lock = threading.Lock()
_client: Optional[mqtt.Client] = None
_broker: str = "localhost"
_port: int = 1883
_username: Optional[str] = None
_password: Optional[str] = None
_prefix: str = "cbpi/bpl"
_device_id: str = "Fermentero"
_use_v1: bool = True


def configure(
    broker: str,
    port: int = 1883,
    username: Optional[str] = None,
    password: Optional[str] = None,
    device_id: str = "Fermentero",
    topic_prefix: str = "cbpi/bpl",
    use_v1: bool = True,
) -> None:
    global _broker, _port, _username, _password, _device_id, _prefix, _use_v1
    _broker = broker
    _port = int(port)
    _username = username or None
    _password = password or None
    _device_id = device_id
    _prefix = topic_prefix.rstrip("/")
    _use_v1 = use_v1


def _on_message(_client, _userdata, msg) -> None:
    topic = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace").strip()
    with _lock:
        if topic.endswith("/telemetry"):
            try:
                data = json.loads(payload)
                _telemetry.update(data)
            except json.JSONDecodeError:
                logger.warning("MQTT: telemetry JSON inválido em %s", topic)
            return
        # Modo legado: tópico simples com número
        key = topic.split("/")[-1]
        try:
            if payload.startswith("{"):
                _telemetry.update(json.loads(payload))
            else:
                _telemetry[key] = float(payload)
        except (ValueError, json.JSONDecodeError):
            _telemetry[key] = payload


def ensure_connected() -> None:
    global _client
    if _client is not None and _client.is_connected():
        return
    try:
        _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        _client = mqtt.Client()
    if _username:
        _client.username_pw_set(_username, _password)
    _client.on_message = _on_message
    _client.connect(_broker, _port, keepalive=60)
    if _use_v1:
        _client.subscribe(f"{_prefix}/{_device_id}/telemetry", qos=1)
    else:
        base = f"{_prefix}/{_device_id}"
        for suffix in (
            "beerTemp",
            "fridgeTemp",
            "roomTemp",
            "beerSet",
            "fridgeSet",
            "gravity",
            "plato",
            "pressure",
            "fridgeHumidity",
            "roomHumidity",
            "mode",
            "state",
        ):
            _client.subscribe(f"{base}/{suffix}", qos=1)
        _client.subscribe(base, qos=1)
    _client.loop_start()
    logger.info("MQTT bridge: %s:%s device=%s", _broker, _port, _device_id)


def update_telemetry(data: Dict[str, Any]) -> None:
    with _lock:
        _telemetry.update(data)


def snapshot_telemetry() -> Dict[str, Any]:
    with _lock:
        return dict(_telemetry)


def get_field(field: str) -> Optional[float]:
    with _lock:
        val = _telemetry.get(field)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def publish_command(
    beer_set: Optional[float] = None,
    fridge_set: Optional[float] = None,
    pressure_psi: Optional[float] = None,
    humidity_rh: Optional[float] = None,
    engage: Optional[bool] = None,
) -> None:
    ensure_connected()
    if _client is None:
        return
    if _use_v1:
        body: Dict[str, Any] = {"v": 1}
        if beer_set is not None:
            body["beerSet"] = beer_set
        if fridge_set is not None:
            body["fridgeSet"] = fridge_set
        if pressure_psi is not None:
            body["pressurePsi"] = pressure_psi
        if humidity_rh is not None:
            body["humidityRh"] = humidity_rh
        if engage is not None:
            body["engage"] = engage
        topic = f"{_prefix}/{_device_id}/command"
        _client.publish(topic, json.dumps(body), qos=1, retain=False)
    else:
        base = f"{_prefix}/{_device_id}/cmd"
        if beer_set is not None:
            _client.publish(f"{base}/beerSet", f"{beer_set:.1f}", qos=1)
        if fridge_set is not None:
            _client.publish(f"{base}/fridgeSet", f"{fridge_set:.1f}", qos=1)
        if engage:
            _client.publish(f"{base}/mode", "b", qos=1)