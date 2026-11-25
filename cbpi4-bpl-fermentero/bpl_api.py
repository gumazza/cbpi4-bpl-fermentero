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


class BPLApiExtension(CBPiExtension):
    def __init__(self, cbpi):
        self.cbpi = cbpi
        device_registry.init_from_cbpi(cbpi)
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
        return web.json_response({"devices": device_registry.list_devices()})

    @request_mapping(path="/devices/{deviceId}", method="GET", auth_required=False)
    async def get_device(self, request):
        device_id = request.match_info["deviceId"]
        dev = self._device_or_404(device_id)
        if dev is None:
            return web.json_response({"error": "device not found"}, status=404)
        tel = _telemetry_by_device.get(device_id, {})
        return web.json_response({"device": dev, "telemetry": tel})

    @request_mapping(path="/devices/{deviceId}", method="PUT", auth_required=False)
    async def put_device(self, request):
        """
        Atualiza nome, broker, prefixo MQTT, etc. O `id` (ex. Fermentero_2) pode ser alterado pelo usuário.
        """
        device_id = request.match_info["deviceId"]
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        body["id"] = body.get("id", device_id)
        if body["id"] != device_id and not device_registry.get_device(device_id):
            return web.json_response({"error": "device not found"}, status=404)
        # renomear id: remove antigo se mudou
        if body["id"] != device_id:
            new_dev = device_registry.upsert_device(self.cbpi, body)
            return web.json_response({"device": new_dev})
        dev = device_registry.upsert_device(self.cbpi, {**body, "id": device_id})
        return web.json_response({"device": dev})

    @request_mapping(path="/devices/{deviceId}/telemetry", method="GET", auth_required=False)
    async def get_telemetry(self, request):
        device_id = request.match_info["deviceId"]
        if self._device_or_404(device_id) is None:
            return web.json_response({"error": "device not found"}, status=404)
        return web.json_response(_telemetry_by_device.get(device_id, {}))

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
        data["ts"] = data.get("ts", int(time.time()))
        _telemetry_by_device[device_id] = data
        # partilha com bridge MQTT (leituras de sensores plugin)
        mqtt_bridge.update_telemetry(data)
        return web.json_response(status=204)

    @request_mapping(path="/health", method="GET", auth_required=False)
    async def health(self, request):
        return web.json_response(
            {
                "service": "cbpi4-bpl-fermentero",
                "defaultDeviceId": device_registry.DEFAULT_DEVICE_ID,
            }
        )