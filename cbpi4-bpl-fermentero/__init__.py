# -*- coding: utf-8 -*-
from .bpl_api import BPLApiExtension
from .bpl_sensors import BPLTelemetrySensor
from .fermenter_logic import BPLSupervisorFermenterLogic


def setup(cbpi):
    cbpi.plugin.register("BPL Telemetry (MAZZA)", BPLTelemetrySensor)
    cbpi.plugin.register("BPL Supervisor (MAZZA)", BPLSupervisorFermenterLogic)
    cbpi.plugin.register("BPL API (MAZZA)", BPLApiExtension)