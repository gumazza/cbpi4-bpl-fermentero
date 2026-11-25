# API HTTP — cbpi4-bpl-fermentero

Base URL: `http://<CBPi>:8000/api/bpl/v1`

Documentação Swagger do CBPi: `http://<CBPi>:8000/api/doc` (rotas aparecem após instalar o plugin).

## Equipamento padrão

- **deviceId:** `Fermentero` (hostname padrão MAZZA)
- O usuário pode renomear via `PUT /devices/{deviceId}` (ex.: `Fermentero_2`)

## Endpoints

| Método | Caminho | Descrição |
|--------|---------|-----------|
| GET | `/health` | Status do plugin |
| GET | `/devices` | Lista equipamentos BPL (+ telemetria e tópicos) |
| POST | `/devices` | Cadastra novo equipamento |
| GET | `/devices/{deviceId}` | Config + última telemetria |
| PUT | `/devices/{deviceId}` | Atualiza ou renomeia equipamento |
| DELETE | `/devices/{deviceId}` | Remove equipamento (não o único padrão) |
| GET | `/devices/{deviceId}/telemetry` | Último pacote de telemetria |
| POST | `/devices/{deviceId}/command` | Envia setpoints ao BPL (MQTT) |
| POST | `/telemetry` | BPL envia telemetria por HTTP |

### POST `/telemetry`

Corpo (JSON, v1):

```json
{
  "deviceId": "Fermentero",
  "beerTemp": 18.2,
  "fridgeTemp": 5.1,
  "beerSet": 18.0,
  "controlSource": "cbpi",
  "modeLabel": "Controle CBPi"
}
```

Resposta: `204 No Content`

### POST `/devices/Fermentero/command`

```json
{
  "beerSet": 18.0,
  "pressurePsi": 15.0,
  "humidityRh": 70,
  "engage": true
}
```

Campos omitidos não são alterados no BPL (comportamento futuro do firmware v1).