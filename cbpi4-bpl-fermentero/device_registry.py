# -*- coding: utf-8 -*-
"""Cadastro de equipamentos BPL (ID MQTT padrão: Fermentero)."""

import json
import logging
import re
import threading
from copy import deepcopy
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

DEFAULT_DEVICE_ID = "Fermentero"
CONFIG_KEY = "bpl_devices_json"

_lock = threading.Lock()
_devices: List[Dict[str, Any]] = []


def _default_devices() -> List[Dict[str, Any]]:
    return [
        {
            "id": DEFAULT_DEVICE_ID,
            "name": DEFAULT_DEVICE_ID,
            "topicPrefix": "cbpi/bpl",
            "protocol": "v1",
            "broker": "localhost",
            "port": 1883,
        }
    ]


def init_from_cbpi(cbpi) -> None:
    """Carrega dispositivos do config global do CBPi ou cria o padrão Fermentero."""
    global _devices
    with _lock:
        raw = None
        try:
            raw = cbpi.config.get(CONFIG_KEY, None)
        except Exception as e:
            logger.warning("bpl_devices: config.get falhou: %s", e)
        if raw:
            try:
                _devices = json.loads(raw)
                if not isinstance(_devices, list) or not _devices:
                    _devices = _default_devices()
            except json.JSONDecodeError:
                _devices = _default_devices()
        else:
            _devices = _default_devices()
            try:
                cbpi.config.set(CONFIG_KEY, json.dumps(_devices))
            except Exception as e:
                logger.warning("bpl_devices: config.set falhou: %s", e)


def _save(cbpi) -> None:
    if cbpi is None:
        return
    try:
        cbpi.config.set(CONFIG_KEY, json.dumps(_devices))
    except Exception as e:
        logger.warning("bpl_devices: não foi possível salvar: %s", e)


def list_devices() -> List[Dict[str, Any]]:
    with _lock:
        return deepcopy(_devices)


def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        for d in _devices:
            if d.get("id") == device_id:
                return deepcopy(d)
    return None


def normalize_id(device_id: str) -> str:
    device_id = (device_id or DEFAULT_DEVICE_ID).strip()
    if not _ID_RE.match(device_id):
        raise ValueError(f"id inválido: {device_id!r}")
    return device_id


def upsert_device(
    cbpi, data: Dict[str, Any], previous_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cria ou atualiza equipamento. `id` obrigatório (padrão Fermentero)."""
    device_id = normalize_id(data.get("id") or DEFAULT_DEVICE_ID)
    lookup = previous_id or device_id
    with _lock:
        for i, d in enumerate(_devices):
            if d.get("id") == lookup:
                merged = {
                    **d,
                    **data,
                    "id": device_id,
                    "port": int(data.get("port", d.get("port", 1883))),
                }
                if lookup != device_id:
                    for other in _devices:
                        if other.get("id") == device_id and other is not d:
                            raise ValueError(
                                f"já existe equipamento com id {device_id}"
                            )
                _devices[i] = merged
                _save(cbpi)
                return deepcopy(merged)
        entry = {
            "id": device_id,
            "name": data.get("name", device_id),
            "topicPrefix": data.get("topicPrefix", "cbpi/bpl"),
            "protocol": data.get("protocol", "v1"),
            "broker": data.get("broker", "localhost"),
            "port": int(data.get("port", 1883)),
        }
        entry.update({k: v for k, v in data.items() if v is not None})
        for d in _devices:
            if d.get("id") == device_id:
                raise ValueError(f"já existe equipamento com id {device_id}")
        _devices.append(entry)
        _save(cbpi)
        return deepcopy(entry)


def remove_device(cbpi, device_id: str) -> bool:
    device_id = normalize_id(device_id)
    with _lock:
        for i, d in enumerate(_devices):
            if d.get("id") == device_id:
                if device_id == DEFAULT_DEVICE_ID and len(_devices) == 1:
                    raise ValueError(
                        "não é possível remover o único equipamento padrão"
                    )
                _devices.pop(i)
                _save(cbpi)
                return True
    return False