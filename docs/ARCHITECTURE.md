# Arquitetura CBPi ↔ BPL (MAZZA)

## Papéis

| | CBPi | BPL |
|---|------|-----|
| Perfil (etapas, rampas, datas) | Sim | Não (modo supervisado) |
| Registro histórico “oficial” | Sim, só no CBPi | Sim, só no BPL (independente) |
| PID / relés / válvulas | Não | Sim |
| Enviar setpoints | Sim | Recebe |

## Modo no BPL

Quando o BPL estiver sob supervisão do CBPi, a interface do BPL deve mostrar modo **「Controle CBPi」** (valor interno acordado no MQTT: `controlSource: "cbpi"`).

O BPL continua executando BrewPi localmente; apenas os **alvos** vêm do CBPi.

## Fluxo de dados

1. BPL publica telemetria no intervalo configurado.
2. Plugin CBPi atualiza sensores virtuais e grava no log do fermentador CBPi.
3. Motor de perfil / fermentador no CBPi calcula temperatura, pressão e umidade da etapa atual.
4. Plugin publica **comando** JSON no broker.
5. BPL aplica setpoints e mantém controle de hardware.

## O que o CBPi **não** faz

- Não usa MQTTActor para ligar aquecimento/resfriamento no BPL.
- Não duplica perfil ativo no BPL (perfil só no CBPi).