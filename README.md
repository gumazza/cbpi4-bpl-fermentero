# cbpi4-bpl-fermentero

Plugin CraftBeerPi 4 para integrar o **Fermentero BrewPiLess (BPL)** como controlador de campo.

- **CBPi**: perfil de fermentação, rampas, datas, etapas, registro e interface.
- **BPL**: leitura, PID, relés, spunding, umidade — controle local completo.
- **CBPi → BPL**: apenas setpoints (temperatura cerveja/refrigeração, pressão, umidade).
- **BPL → CBPi**: telemetria (temperaturas, densidade, pressão, estado, etc.).

Os registros do CBPi ficam no CBPi; os registros do BPL ficam só no BPL.

Documentação do contrato MQTT: [docs/MQTT_v1.md](docs/MQTT_v1.md)  
Visão geral: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

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

## Configuração inicial (preview)

1. Broker MQTT acessível pelo Pi e pelo BPL (ex.: Mosquitto).
2. No CBPi, criar sensores do tipo **BPL – …** (cerveja, refrigeração, densidade, pressão, etc.).
3. Criar fermentador com lógica **BPL Supervisor (MAZZA)** — envia setpoints ao BPL; não comanda relés locais do Pi.
4. Perfil de fermentação no CBPi; o plugin publica temperatura/pressão/umidade da etapa atual no tópico de comando.

> O firmware do BPL ainda usará o preset “Integração CBPi” (próxima fase). Enquanto isso, dá para testar com o MQTT genérico do BPL (`docs/MQTT_v1.md` — modo legado).

## Desenvolvimento

```bash
git clone https://github.com/gumazza/cbpi4-bpl-fermentero.git
cd cbpi4-bpl-fermentero
pipx runpip cbpi4 install -e .
```

## Licença

MIT — ver [LICENSE](LICENSE).