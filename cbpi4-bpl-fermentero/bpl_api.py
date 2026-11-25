# -*- coding: utf-8 -*-
"""
API HTTP CraftBeerPi 4 — integração Fermentero BPL (MAZZA).

Base: /api/bpl/v1
"""

import logging
import time

from aiohttp import web
from cbpi.api import CBPiExtension, request_mapping

from . import device_registry, mqtt_bridge

logger = logging.getLogger(__name__)

# telemetria por deviceId (último POST MQTT legado ou HTTP do BPL)
_telemetry_by_device: dict = {}


def _merge_telemetry(device_id: str) -> dict:
    tel = dict(_telemetry_by_device.get(device_id, {}))
    mqtt_tel = mqtt_bridge.snapshot_telemetry(device_id)
    if mqtt_tel:
        tel.update(mqtt_tel)
    return tel


class BPLApiExtension(CBPiExtension):
    def __init__(self, cbpi):
        self.cbpi = cbpi
        device_registry.init_from_cbpi(cbpi)
        mqtt_bridge.register_all_from_registry(device_registry.list_devices())
        self.cbpi.register(self, "/api/bpl/v1")

    def _device_or_404(self, device_id: str):
        dev = device_registry.get_device(device_id)
        if dev is None:
            return None
        return dev

    @request_mapping(path="/devices", method="GET", auth_required=False)
    async def list_devices(self, request):
        """
        ---
        description: Lista equipamentos BPL configurados no CBPi
        tags:
          - BPL Fermentero
        responses:
          "200":
            description: Lista de dispositivos (id padrão Fermentero)
        """
        devices = device_registry.list_devices()
        enriched = []
        for d in devices:
            did = d.get("id")
            enriched.append(
                {
                    **d,
                    "telemetry": _merge_telemetry(did) if did else {},
                    "topics": {
                        "telemetry": f"{d.get('topicPrefix', 'cbpi/bpl')}/{did}/telemetry",
                        "command": f"{d.get('topicPrefix', 'cbpi/bpl')}/{did}/command",
                    },
                }
            )
        return web.json_response({"devices": enriched})

    @request_mapping(path="/devices", method="POST", auth_required=False)
    async def create_device(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        try:
            dev = device_registry.upsert_device(self.cbpi, body)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        mqtt_bridge.register_all_from_registry(device_registry.list_devices())
        return web.json_response({"device": dev}, status=201)

    @request_mapping(path="/devices/{deviceId}", method="GET", auth_required=False)
    async def get_device(self, request):
        device_id = request.match_info["deviceId"]
        dev = self._device_or_404(device_id)
        if dev is None:
            return web.json_response({"error": "device not found"}, status=404)
        tel = _merge_telemetry(device_id)
        return web.json_response({"device": dev, "telemetry": tel})

    @request_mapping(path="/devices/{deviceId}", method="PUT", auth_required=False)
    async def put_device(self, request):
        """
        Atualiza nome, broker, prefixo MQTT, etc. O `id` (ex. Fermentero_2) pode ser alterado pelo usuário.
        """
        device_id = request.match_info["deviceId"]
        if self._device_or_404(device_id) is None:
            return web.json_response({"error": "device not found"}, status=404)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        try:
            dev = device_registry.upsert_device(
                self.cbpi, body, previous_id=device_id
            )
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        new_id = dev.get("id", device_id)
        if new_id != device_id and device_id in _telemetry_by_device:
            _telemetry_by_device[new_id] = _telemetry_by_device.pop(device_id)
        mqtt_bridge.register_all_from_registry(device_registry.list_devices())
        return web.json_response({"device": dev})

    @request_mapping(path="/devices/{deviceId}", method="DELETE", auth_required=False)
    async def delete_device(self, request):
        device_id = request.match_info["deviceId"]
        if self._device_or_404(device_id) is None:
            return web.json_response({"error": "device not found"}, status=404)
        try:
            device_registry.remove_device(self.cbpi, device_id)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        _telemetry_by_device.pop(device_id, None)
        mqtt_bridge.register_all_from_registry(device_registry.list_devices())
        return web.json_response(status=204)

    @request_mapping(path="/devices/{deviceId}/telemetry", method="GET", auth_required=False)
    async def get_telemetry(self, request):
        device_id = request.match_info["deviceId"]
        if self._device_or_404(device_id) is None:
            return web.json_response({"error": "device not found"}, status=404)
        return web.json_response(_merge_telemetry(device_id))

    @request_mapping(path="/devices/{deviceId}/command", method="POST", auth_required=False)
    async def post_command(self, request):
        """
        Envia setpoints ao BPL via MQTT (temperatura, pressão, umidade).
        """
        device_id = request.match_info["deviceId"]
        dev = self._device_or_404(device_id)
        if dev is None:
            return web.json_response({"error": "device not found"}, status=404)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        mqtt_bridge.configure(
            broker=dev.get("broker", "localhost"),
            port=int(dev.get("port", 1883)),
            device_id=device_id,
            topic_prefix=dev.get("topicPrefix", "cbpi/bpl"),
            use_v1=dev.get("protocol", "v1") == "v1",
        )
        mqtt_bridge.publish_command(
            beer_set=body.get("beerSet"),
            fridge_set=body.get("fridgeSet"),
            pressure_psi=body.get("pressurePsi"),
            humidity_rh=body.get("humidityRh"),
            engage=body.get("engage"),
            device_id=device_id,
        )
        return web.json_response({"ok": True, "deviceId": device_id})

    @request_mapping(path="/telemetry", method="POST", auth_required=False)
    async def ingest_telemetry(self, request):
        """
        Entrada HTTP de telemetria do BPL (alternativa ou complemento ao MQTT).

        Corpo JSON conforme docs/MQTT_v1.md; campo `deviceId` (padrão Fermentero).
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        device_id = data.get("deviceId", device_registry.DEFAULT_DEVICE_ID)
        if self._device_or_404(device_id) is None:
            device_registry.upsert_device(
                self.cbpi, {"id": device_id, "name": device_id}
            )
            mqtt_bridge.register_all_from_registry(device_registry.list_devices())
        data["ts"] = data.get("ts", int(time.time()))
        _telemetry_by_device[device_id] = data
        mqtt_bridge.update_telemetry(data)
        return web.json_response(status=204)

    @request_mapping(path="/health", method="GET", auth_required=False)
    async def health(self, request):
        return web.json_response(
            {
                "service": "cbpi4-bpl-fermentero",
                "version": "0.3.0",
                "defaultDeviceId": device_registry.DEFAULT_DEVICE_ID,
                "ui": [
                    "/cbpi_bpl_fermentero/static/index.html",
                    "/cbpi_bplfermentero/static/index.html",
                ],
            }
        )