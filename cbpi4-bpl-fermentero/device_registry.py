# -*- coding: utf-8 -*-
"""Cadastro de equipamentos BPL (ID MQTT padrão: Fermentero)."""

import json
import logging
import threading
from copy import deepcopy
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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


def upsert_device(cbpi, data: Dict[str, Any]) -> Dict[str, Any]:
    """Cria ou atualiza equipamento. `id` obrigatório (padrão Fermentero)."""
    device_id = data.get("id") or DEFAULT_DEVICE_ID
    with _lock:
        for i, d in enumerate(_devices):
            if d.get("id") == device_id:
                merged = {**d, **data, "id": device_id}
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
        _devices.append(entry)
        _save(cbpi)
        return deepcopy(entry)