# -*- coding: utf-8 -*-
import asyncio
import logging

from cbpi.api import CBPiSensor, Property, parameters

from . import mqtt_bridge

logger = logging.getLogger(__name__)

_CHANNEL = {
    "Beer Temperature": ("beerTemp", 5),
    "Fridge Temperature": ("fridgeTemp", 5),
    "Room Temperature": ("roomTemp", 5),
    "Specific Gravity": ("gravity", 15),
    "Plato": ("plato", 10),
    "Pressure (PSI)": ("pressurePsi", 5),
    "Chamber Humidity": ("humidityRh", 10),
}


def _sensor_params():
    return [
        Property.Text(
            label="Broker",
            configurable=True,
            default_value="localhost",
            description="Host MQTT (mesmo broker do config.yaml do CBPi, se possível)",
        ),
        Property.Number(
            label="Port",
            configurable=True,
            default_value=1883,
            description="Porta MQTT",
        ),
        Property.Text(
            label="DeviceId",
            configurable=True,
            default_value="fermentero1",
            description="ID do BPL (prefixo de tópicos)",
        ),
        Property.Text(
            label="TopicPrefix",
            configurable=True,
            default_value="cbpi/bpl",
            description="Prefixo dos tópicos (v1)",
        ),
        Property.Select(
            label="Channel",
            options=list(_CHANNEL.keys()),
            description="Grandeza lida da telemetria BPL",
        ),
        Property.Select(
            label="Interval",
            options=[5, 10, 15, 30, 60],
            description="Intervalo de leitura (s)",
        ),
        Property.Select(
            label="Protocol",
            options=["v1", "legacy"],
            description="v1 = JSON telemetry; legacy = tópicos BPL atuais",
        ),
    ]


@parameters(_sensor_params())
class BPLTelemetrySensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(BPLTelemetrySensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.channel = self.props.get("Channel", "Beer Temperature")
        self.interval = int(self.props.get("Interval", 10))
        self._field, self._default_precision = _CHANNEL.get(
            self.channel, ("beerTemp", 5)
        )
        if self._field == "pressurePsi":
            self._field = "pressure"
        if self._field == "humidityRh":
            self._field = "fridgeHumidity"

    def _configure_mqtt(self):
        mqtt_bridge.configure(
            broker=self.props.get("Broker", "localhost"),
            port=int(self.props.get("Port", 1883)),
            device_id=self.props.get("DeviceId", "fermentero1"),
            topic_prefix=self.props.get("TopicPrefix", "cbpi/bpl"),
            use_v1=self.props.get("Protocol", "v1") == "v1",
        )

    async def run(self):
        self._configure_mqtt()
        while self.running:
            mqtt_bridge.ensure_connected()
            reading = mqtt_bridge.get_field(self._field)
            if reading is not None:
                prec = self._default_precision
                self.value = round(reading, prec if prec < 10 else 1)
                self.push_update(self.value)
                self.log_data(self.value)
            await asyncio.sleep(self.interval)

    def get_state(self):
        return dict(value=self.value)