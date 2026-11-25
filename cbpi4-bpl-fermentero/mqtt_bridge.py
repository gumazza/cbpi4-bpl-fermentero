# -*- coding: utf-8 -*-
"""Cliente MQTT partilhado — suporta vários equipamentos BPL no mesmo broker."""

import json
import logging
import re
import threading
from typing import Any, Dict, Optional, Tuple

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

_telemetry_by_device: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
_registered: Dict[str, Dict[str, Any]] = {}
_clients: Dict[Tuple[str, int], mqtt.Client] = {}


def _device_key(broker: str, port: int) -> Tuple[str, int]:
    return (broker or "localhost", int(port))


def register_listener(
    device_id: str,
    broker: str,
    port: int = 1883,
    username: Optional[str] = None,
    password: Optional[str] = None,
    topic_prefix: str = "cbpi/bpl",
    use_v1: bool = True,
) -> None:
    """Regista um BPL para telemetria MQTT (vários listeners no mesmo broker)."""
    if not device_id or not _ID_RE.match(device_id):
        logger.warning("MQTT bridge: deviceId inválido: %s", device_id)
        return
    with _lock:
        _registered[device_id] = {
            "broker": broker or "localhost",
            "port": int(port),
            "username": username,
            "password": password,
            "prefix": (topic_prefix or "cbpi/bpl").rstrip("/"),
            "use_v1": bool(use_v1),
        }
        _telemetry_by_device.setdefault(device_id, {})
    _ensure_subscriptions()


def configure(
    broker: str,
    port: int = 1883,
    username: Optional[str] = None,
    password: Optional[str] = None,
    device_id: str = "Fermentero",
    topic_prefix: str = "cbpi/bpl",
    use_v1: bool = True,
) -> None:
    """Compatível com sensores/lógica — regista o device e prepara publicação de comando."""
    register_listener(
        device_id=device_id,
        broker=broker,
        port=port,
        username=username,
        password=password,
        topic_prefix=topic_prefix,
        use_v1=use_v1,
    )


def _make_on_message(broker_key: Tuple[str, int]):
    def _on_message(_client, _userdata, msg) -> None:
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        device_id = None
        with _lock:
            for did, cfg in _registered.items():
                if _device_key(cfg["broker"], cfg["port"]) != broker_key:
                    continue
                prefix = cfg["prefix"]
                if topic == f"{prefix}/{did}/telemetry" or topic.startswith(
                    f"{prefix}/{did}/"
                ):
                    device_id = did
                    break
        if device_id is None:
            parts = topic.split("/")
            if len(parts) >= 3:
                device_id = parts[2]
        if device_id is None:
            return
        with _lock:
            bucket = _telemetry_by_device.setdefault(device_id, {})
            if topic.endswith("/telemetry"):
                try:
                    data = json.loads(payload)
                    bucket.update(data)
                except json.JSONDecodeError:
                    logger.warning("MQTT: telemetry JSON inválido em %s", topic)
                return
            key = topic.split("/")[-1]
            try:
                if payload.startswith("{"):
                    bucket.update(json.loads(payload))
                else:
                    bucket[key] = float(payload)
            except (ValueError, json.JSONDecodeError):
                bucket[key] = payload

    return _on_message


def _subscribe_client(client: mqtt.Client, broker_key: Tuple[str, int]) -> None:
    with _lock:
        for did, cfg in _registered.items():
            if _device_key(cfg["broker"], cfg["port"]) != broker_key:
                continue
            prefix = cfg["prefix"]
            if cfg["use_v1"]:
                client.subscribe(f"{prefix}/{did}/telemetry", qos=1)
            else:
                base = f"{prefix}/{did}"
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
                    client.subscribe(f"{base}/{suffix}", qos=1)
                client.subscribe(base, qos=1)


def _ensure_subscriptions() -> None:
    with _lock:
        brokers: Dict[Tuple[str, int], Dict[str, Any]] = {}
        for cfg in _registered.values():
            key = _device_key(cfg["broker"], cfg["port"])
            brokers.setdefault(key, cfg)

    for broker_key, sample in brokers.items():
        broker, port = broker_key
        client = _clients.get(broker_key)
        if client is not None and client.is_connected():
            _subscribe_client(client, broker_key)
            continue
        if client is not None:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
        try:
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            except AttributeError:
                client = mqtt.Client()
            if sample.get("username"):
                client.username_pw_set(
                    sample["username"], sample.get("password")
                )
            client.on_message = _make_on_message(broker_key)
            client.connect(broker, port, keepalive=60)
            _subscribe_client(client, broker_key)
            client.loop_start()
            _clients[broker_key] = client
            logger.info("MQTT bridge conectado %s:%s (%s device(s))", broker, port, sum(1 for c in _registered.values() if _device_key(c["broker"], c["port"]) == broker_key))
        except Exception as e:
            logger.warning("MQTT bridge: falha ao conectar %s:%s — %s", broker, port, e)


def ensure_connected() -> None:
    _ensure_subscriptions()


def register_all_from_registry(devices: list) -> None:
    global _registered
    ids = {d.get("id", "Fermentero") for d in devices}
    with _lock:
        for stale in list(_registered.keys()):
            if stale not in ids:
                _registered.pop(stale, None)
                _telemetry_by_device.pop(stale, None)
    for d in devices:
        register_listener(
            device_id=d.get("id", "Fermentero"),
            broker=d.get("broker", "localhost"),
            port=int(d.get("port", 1883)),
            topic_prefix=d.get("topicPrefix", "cbpi/bpl"),
            use_v1=d.get("protocol", "v1") == "v1",
        )


def update_telemetry(data: Dict[str, Any]) -> None:
    device_id = data.get("deviceId", "Fermentero")
    with _lock:
        _telemetry_by_device.setdefault(device_id, {}).update(data)


def snapshot_telemetry(device_id: Optional[str] = None) -> Dict[str, Any]:
    with _lock:
        if device_id:
            return dict(_telemetry_by_device.get(device_id, {}))
        return {k: dict(v) for k, v in _telemetry_by_device.items()}


def get_field(field: str, device_id: Optional[str] = None) -> Optional[float]:
    with _lock:
        if device_id:
            val = _telemetry_by_device.get(device_id, {}).get(field)
        else:
            val = None
            for bucket in _telemetry_by_device.values():
                if field in bucket:
                    val = bucket[field]
                    break
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _publish_client_for(device_id: str) -> Optional[mqtt.Client]:
    with _lock:
        cfg = _registered.get(device_id)
        if cfg is None:
            return None
        key = _device_key(cfg["broker"], cfg["port"])
        client = _clients.get(key)
    if client is None or not client.is_connected():
        ensure_connected()
        with _lock:
            client = _clients.get(key)
    return client


def publish_command(
    beer_set: Optional[float] = None,
    fridge_set: Optional[float] = None,
    pressure_psi: Optional[float] = None,
    humidity_rh: Optional[float] = None,
    engage: Optional[bool] = None,
    device_id: Optional[str] = None,
) -> None:
    did = device_id
    if did is None:
        with _lock:
            if len(_registered) == 1:
                did = next(iter(_registered))
            else:
                did = "Fermentero"
    with _lock:
        cfg = _registered.get(did)
    if cfg is None:
        logger.warning("MQTT publish_command: device %s não registrado", did)
        return
    ensure_connected()
    client = _publish_client_for(did)
    if client is None:
        return
    prefix = cfg["prefix"]
    use_v1 = cfg["use_v1"]
    if use_v1:
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
        topic = f"{prefix}/{did}/command"
        client.publish(topic, json.dumps(body), qos=1, retain=False)
    else:
        base = f"{prefix}/{did}/cmd"
        if beer_set is not None:
            client.publish(f"{base}/beerSet", f"{beer_set:.1f}", qos=1)
        if fridge_set is not None:
            client.publish(f"{base}/fridgeSet", f"{fridge_set:.1f}", qos=1)
        if engage:
            client.publish(f"{base}/mode", "b", qos=1)