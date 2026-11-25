# cbpi4-bpl-fermentero

Plugin CraftBeerPi 4 para integrar o **Fermentero BrewPiLess (BPL)** como controlador de campo.

- **CBPi**: perfil de fermentação, rampas, datas, etapas, registro e interface.
- **BPL**: leitura, PID, relés, spunding, umidade — controle local completo.
- **CBPi → BPL**: apenas setpoints (temperatura cerveja/refrigeração, pressão, umidade).
- **BPL → CBPi**: telemetria (temperaturas, densidade, pressão, estado, etc.).

Os registros do CBPi ficam no CBPi; os registros do BPL ficam só no BPL.

Documentação do contrato MQTT: [docs/MQTT_v1.md](docs/MQTT_v1.md)  
API HTTP no CBPi: [docs/API.md](docs/API.md)  
Visão geral: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Device ID padrão:** `Fermentero` (ajuste no CBPi ou via API se o equipamento tiver outro nome).

## Instalação (Raspberry Pi com CBPi4)

```bash
pipx runpip cbpi4 install https://github.com/gumazza/cbpi4-bpl-fermentero/archive/main.zip
```

Reinicie o CraftBeerPi:

```bash
sudo systemctl restart cbpi
# ou, em desenvolvimento:
cbpi start
```

Instalação local (desenvolvimento):

```bash
pipx runpip cbpi4 install -e ./cbpi4-bpl-fermentero
```

## Interface web (vários BPL)

Após instalar o plugin, abra no navegador (mesma rede do Pi):

`http://<IP-do-Pi>:8080/cbpi_bpl_fermentero/static/index.html`  
(Se não abrir, tente `/cbpi_bplfermentero/static/index.html` — confira em `GET /api/bpl/v1/health`.)

Cadastre `Fermentero`, `Fermentero_2`, etc. com o IP do broker MQTT (ex.: `localhost` se Mosquitto está no Pi). **Não precisa de internet.**

## Configuração inicial

1. Broker MQTT acessível pelo Pi e por cada BPL na LAN (ex.: Mosquitto no Raspberry).
2. Página **Equipamentos BPL** ou `GET/POST /api/bpl/v1/devices` — um registro por fermentero.
3. Sensores **BPL – …** com **DeviceId** igual ao cadastro e **UseRegistry = Yes** (broker herdado do cadastro).
4. Fermentador com lógica **BPL Supervisor (MAZZA)** — mesmo **DeviceId**; envia setpoints; não comanda relés do Pi.
5. Perfil de fermentação no CBPi; a lógica reenvia `target_temp` e, se existirem no passo, pressão/umidade.

> O firmware do BPL ainda usará o preset “Integração CBPi” (próxima fase). Enquanto isso, dá para testar com o MQTT genérico do BPL (`docs/MQTT_v1.md` — modo legado).

## Desenvolvimento

```bash
git clone https://github.com/gumazza/cbpi4-bpl-fermentero.git
cd cbpi4-bpl-fermentero
pipx runpip cbpi4 install -e .
```

## Licença

MIT — ver [LICENSE](LICENSE).