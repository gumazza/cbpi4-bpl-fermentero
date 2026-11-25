# -*- coding: utf-8 -*-
"""
Lógica de fermentador: calcula setpoints no CBPi e envia ao BPL.
Não comanda relés — o BPL mantém o PID.
"""

import asyncio
import logging

from cbpi.api import CBPiFermenterLogic, Property, parameters

from . import device_registry, mqtt_bridge

logger = logging.getLogger(__name__)


def _step_props(fermenter) -> dict:
    try:
        data = fermenter.data or {}
    except AttributeError:
        return {}
    step = data.get("step") or data.get("active_step") or {}
    if isinstance(step, dict):
        props = step.get("props") or step.get("properties") or {}
        return props if isinstance(props, dict) else {}
    return {}


@parameters(
    [
        Property.Text(
            label="Broker",
            configurable=True,
            default_value="localhost",
        ),
        Property.Number(label="Port", configurable=True, default_value=1883),
        Property.Text(
            label="DeviceId",
            configurable=True,
            default_value="Fermentero",
        ),
        Property.Text(
            label="TopicPrefix",
            configurable=True,
            default_value="cbpi/bpl",
        ),
        Property.Select(label="Protocol", options=["v1", "legacy"]),
        Property.Select(
            label="UseRegistry",
            options=["Yes", "No"],
            default_value="Yes",
            description="Sim = MQTT do cadastro BPL (página Equipamentos)",
        ),
        Property.Number(
            label="CommandInterval",
            configurable=True,
            default_value=30,
            description="Reenvio do setpoint ao BPL (s)",
        ),
        Property.Number(
            label="PressurePsi",
            configurable=True,
            default_value=-1,
            description="SP pressão spunding; -1 = usar passo do perfil se existir",
        ),
        Property.Number(
            label="HumidityRh",
            configurable=True,
            default_value=-1,
            description="SP umidade %; -1 = usar passo do perfil se existir",
        ),
        Property.Select(
            label="SetpointField",
            options=["beer", "fridge"],
            description="Qual setpoint enviar quando TargetTemp mudar",
        ),
    ]
)
class BPLSupervisorFermenterLogic(CBPiFermenterLogic):
    def __init__(self, cbpi, id, props):
        super(BPLSupervisorFermenterLogic, self).__init__(cbpi, id, props)
        self.interval = int(self.props.get("CommandInterval", 30))
        self.setpoint_field = self.props.get("SetpointField", "beer")

    def _device_id(self) -> str:
        return self.props.get("DeviceId", device_registry.DEFAULT_DEVICE_ID)

    def _configure_mqtt(self):
        device_id = self._device_id()
        if self.props.get("UseRegistry", "Yes") == "Yes":
            reg = device_registry.get_device(device_id)
            if reg:
                mqtt_bridge.configure(
                    broker=reg.get("broker", "localhost"),
                    port=int(reg.get("port", 1883)),
                    device_id=device_id,
                    topic_prefix=reg.get("topicPrefix", "cbpi/bpl"),
                    use_v1=reg.get("protocol", "v1") == "v1",
                )
                return
        mqtt_bridge.configure(
            broker=self.props.get("Broker", "localhost"),
            port=int(self.props.get("Port", 1883)),
            device_id=device_id,
            topic_prefix=self.props.get("TopicPrefix", "cbpi/bpl"),
            use_v1=self.props.get("Protocol", "v1") == "v1",
        )

    def _pressure_humidity(self, step_props: dict):
        pressure = float(self.props.get("PressurePsi", -1))
        humidity = float(self.props.get("HumidityRh", -1))
        if pressure < 0:
            for key in ("PressurePsi", "pressurePsi", "Pressure", "pressure"):
                if key in step_props:
                    try:
                        pressure = float(step_props[key])
                    except (TypeError, ValueError):
                        pass
                    else:
                        break
        if humidity < 0:
            for key in ("HumidityRh", "humidityRh", "Humidity", "humidity"):
                if key in step_props:
                    try:
                        humidity = float(step_props[key])
                    except (TypeError, ValueError):
                        pass
                    else:
                        break
        return pressure, humidity

    def _publish_setpoints(self, target_temp: float, step_props: dict) -> None:
        pressure, humidity = self._pressure_humidity(step_props)
        beer = target_temp if self.setpoint_field == "beer" else None
        fridge = target_temp if self.setpoint_field == "fridge" else None
        mqtt_bridge.publish_command(
            beer_set=beer,
            fridge_set=fridge,
            pressure_psi=pressure if pressure >= 0 else None,
            humidity_rh=humidity if humidity >= 0 else None,
            engage=True,
            device_id=self._device_id(),
        )

    async def run(self):
        self._configure_mqtt()
        last_target = None
        last_props_key = None
        while self.running:
            fermenter = self.get_fermenter(self.id)
            step_props = _step_props(fermenter)
            try:
                target = float(fermenter.data.get("target_temp", 0))
            except (TypeError, ValueError, AttributeError):
                target = 0.0

            props_key = (
                target,
                step_props.get("PressurePsi"),
                step_props.get("HumidityRh"),
            )
            if target != last_target or props_key != last_props_key:
                self._publish_setpoints(target, step_props)
                last_target = target
                last_props_key = props_key
                logger.info(
                    "BPL supervisor: setpoint %.2f enviado (fermentador %s, BPL %s)",
                    target,
                    self.id,
                    self._device_id(),
                )

            if self.state:
                self._publish_setpoints(target, step_props)

            await asyncio.sleep(self.interval)