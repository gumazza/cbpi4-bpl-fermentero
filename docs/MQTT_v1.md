# Contrato MQTT v1 (rascunho)

Prefixo por equipamento: `cbpi/bpl/{deviceId}/`

## Telemetria (BPL → CBPi)

Tópico: `cbpi/bpl/{deviceId}/telemetry`  
Payload JSON (exemplo):

```json
{
  "v": 1,
  "deviceId": "fermentero2",
  "ts": 1732521600,
  "controlSource": "cbpi",
  "modeLabel": "Controle CBPi",
  "mode": "b",
  "state": 4,
  "beerTemp": 18.2,
  "fridgeTemp": 5.1,
  "roomTemp": 22.0,
  "beerSet": 18.0,
  "fridgeSet": 5.0,
  "gravity": 1.042,
  "plato": 10.5,
  "auxTemp": 18.1,
  "pressurePsi": 12.3,
  "humidityRh": 65,
  "roomHumidityRh": 55
}
```

`controlSource`: `"local"` | `"cbpi"`  
`modeLabel`: texto para LCD/web (ex.: `Controle CBPi`)

## Comando (CBPi → BPL)

Tópico: `cbpi/bpl/{deviceId}/command`  
Campos omitidos não alteram o valor atual no BPL.

```json
{
  "v": 1,
  "beerSet": 18.0,
  "fridgeSet": null,
  "pressurePsi": 15.0,
  "humidityRh": 70,
  "engage": true
}
```

`engage: true` — BPL entra em supervisão CBPi (`modeLabel` = Controle CBPi).  
`engage: false` — volta ao controle local (detalhes no firmware).

## Modo legado (BPL atual, sem preset CBPi)

Até o firmware MAZZA ter o preset Registros:

| Dado | Leitura (Individual Topic) | Escrita |
|------|---------------------------|---------|
| Temp. cerveja | `{base}/beerTemp` | `{baseCmd}/beerSet` (número texto) |
| Temp. refrig. | `{base}/fridgeTemp` | `{baseCmd}/fridgeSet` |
| Modo | `{base}/mode` | `{baseCmd}/mode` (`b` = beer constant) |
| Pressão (spunding) | `{base}/pressure` | cap path conforme BPL |
| JSON completo | `{base}` Whole as JSON | — |

Ver `docs/I0.MQTT.md` no repositório BrewPiLess.