# IIoT Edge Gateway

**Connect your industrial OPC UA machines to the cloud — no code required.**

IIoT Edge Gateway is a self-hosted web application that bridges OPC UA equipment with cloud IoT platforms. Configure your data pipeline through a clean web UI, and let [Telegraf](https://www.influxdata.com/time-series-platform/telegraf/) handle the heavy lifting.

---

## What it does

Industrial machines speak OPC UA. Cloud platforms speak MQTT. IIoT Edge Gateway sits in the middle:

```
OPC UA Machines  ──►  IIoT Edge Gateway  ──►  AWS IoT Core
                        (Telegraf agent)   ──►  Azure IoT Hub
                                           ──►  Any MQTT broker
```

You browse your OPC UA node tree, pick the variables you want to stream, set your cloud endpoint, and deploy. The gateway generates and manages the Telegraf configuration automatically.

![IIoT Edge Gateway Dashboard](screenshots/dashboard.png)

---

## Features

- **Visual node browser** — Navigate the OPC UA address space and select variables with a point-and-click interface
- **Cloud-ready** — Built-in support for AWS IoT Core (auto-generates IAM policies) and Azure IoT Hub (auto-generates connection config)
- **TLS certificate management** — Upload and manage client certificates directly from the UI
- **Live message tail** — Subscribe to your broker in real time to verify data is flowing
- **Pipeline dashboard** — Monitor OPC UA reads, buffer usage, MQTT delivery, and system health (CPU, RAM, disk, network)
- **Zero-config deploy** — One click generates `telegraf.conf` and restarts the agent
- **Auto-save** — All configuration changes are saved automatically as you type
- **Docker-native** — Runs on any Linux edge server or gateway hardware

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- A reachable OPC UA server
- An MQTT broker (AWS IoT Core, Azure IoT Hub, or any standard broker)

---

## Quick Start

```bash
git clone https://github.com/your-org/iiot-edge-gateway.git
cd iiot-edge-gateway
docker compose up -d
```

Open **http://localhost:8050** in your browser.

> A demo OPC UA server and Mosquitto MQTT broker are included for testing. No external services needed to try it out.

---

## Getting Started

### 1 — Connect your OPC UA server

Go to **OPC UA Config → Connection** and enter your server endpoint:

```
opc.tcp://your-plc-or-scada:4840
```

Supports Anonymous, Username/Password, and X.509 Certificate authentication.

### 2 — Browse and select variables

Use **Browse Nodes** to navigate the address space of your machine. Click any variable node to inspect it, then add it to your selection. In **Node Selection**, configure the polling interval and deadband per variable.

### 3 — Configure your MQTT output

Go to **MQTT Config → Connection** and enter your broker endpoint:

| Platform | Endpoint format |
|---|---|
| AWS IoT Core | `mqtts://xxxx-ats.iot.eu-west-1.amazonaws.com:8883` |
| Azure IoT Hub | `mqtts://your-hub.azure-devices.net:8883` |
| Generic broker | `mqtt://your-broker:1883` |

Upload your TLS certificates if required. Use **Generate AWS IoT Policy** or **Generate Azure IoT Config** to get the exact configuration needed for your cloud platform.

### 4 — Deploy

Click **Deploy config** in the sidebar. The gateway generates `telegraf.conf` and restarts the Telegraf agent. The Dashboard shows pipeline health in real time.

---

## Dashboard

The Dashboard provides a live view of your data pipeline:

- **Pipeline Health** — OPC UA reads → buffer → MQTT delivery, with per-cycle message counts
- **System Health** — CPU, memory, disk, and network I/O of the gateway host
- **Data Quality** — OPC UA read success/error rates and loss percentage
- **Component Status** — Running state of all Docker containers in the stack

---

## Supported Integrations

### AWS IoT Core
Upload your device certificate, CA, and private key. The gateway auto-generates a scoped IAM policy based on your topic pattern — paste it directly into the AWS console.

### Azure IoT Hub
The gateway auto-generates the required MQTT username (`{hub}.azure-devices.net/{device_id}/?api-version=2021-04-12`) and the correct topic format (`devices/{device_id}/messages/events/`). Supports both SAS token and X.509 certificate authentication.

### Any MQTT Broker
Standard MQTT (1883) and MQTTS (8883) supported. Compatible with Mosquitto, HiveMQ, EMQX, and any MQTT 3.1.1-compliant broker.

---

## Configuration Reference

| Setting | Description |
|---|---|
| OPC UA Endpoint | `opc.tcp://host:port/path` |
| Auth method | Anonymous, Username/Password, Certificate |
| Topic pattern | Supports Telegraf template vars: `{{ .Hostname }}`, `{{ .PluginName }}` |
| QoS | 0 (at most once), 1 (at least once), 2 (exactly once) |
| Data format | JSON or InfluxDB Line Protocol |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data agent | [Telegraf](https://github.com/influxdata/telegraf) |
| OPC UA | [asyncua](https://github.com/FreeOpcUa/opcua-asyncio) |
| MQTT | [paho-mqtt](https://github.com/eclipse/paho.mqtt.python) |
| Web UI | Flask + Bootstrap 5 |
| Runtime | Docker |

---

## License

MIT
