# -*- coding: utf-8 -*-
"""
Lógica de fermentador: calcula setpoints no CBPi e envia ao BPL.
Não comanda relés — o BPL mantém o PID.
"""

import asyncio
import logging

from cbpi.api import CBPiFermenterLogic, Property, parameters

from . import mqtt_bridge

logger = logging.getLogger(__name__)


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
            default_value="fermentero1",
        ),
        Property.Text(
            label="TopicPrefix",
            configurable=True,
            default_value="cbpi/bpl",
        ),
        Property.Select(label="Protocol", options=["v1", "legacy"]),
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
            description="SP pressão spunding; -1 = não enviar",
        ),
        Property.Number(
            label="HumidityRh",
            configurable=True,
            default_value=-1,
            description="SP umidade %; -1 = não enviar",
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

    def _configure_mqtt(self):
        mqtt_bridge.configure(
            broker=self.props.get("Broker", "localhost"),
            port=int(self.props.get("Port", 1883)),
            device_id=self.props.get("DeviceId", "fermentero1"),
            topic_prefix=self.props.get("TopicPrefix", "cbpi/bpl"),
            use_v1=self.props.get("Protocol", "v1") == "v1",
        )

    def _publish_setpoints(self, target_temp: float) -> None:
        pressure = float(self.props.get("PressurePsi", -1))
        humidity = float(self.props.get("HumidityRh", -1))
        beer = target_temp if self.setpoint_field == "beer" else None
        fridge = target_temp if self.setpoint_field == "fridge" else None
        mqtt_bridge.publish_command(
            beer_set=beer,
            fridge_set=fridge,
            pressure_psi=pressure if pressure >= 0 else None,
            humidity_rh=humidity if humidity >= 0 else None,
            engage=True,
        )

    async def run(self):
        self._configure_mqtt()
        last_target = None
        while self.running:
            fermenter = self.get_fermenter(self.id)
            try:
                target = float(fermenter.data.get("target_temp", 0))
            except (TypeError, ValueError, AttributeError):
                target = 0.0

            if target != last_target:
                self._publish_setpoints(target)
                last_target = target
                logger.info(
                    "BPL supervisor: setpoint %.2f enviado (fermentador %s)",
                    target,
                    self.id,
                )

            if self.state:
                self._publish_setpoints(target)

            await asyncio.sleep(self.interval)