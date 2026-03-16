# <img src="app/static/img/logo-white.png" height="42" alt="logo"> IIoT Edge Gateway

**Connect your industrial machines to the cloud**

IIoT Edge Gateway is a self-hosted web application that bridges industrial equipment (OPC UA and Modbus TCP) with cloud IoT platforms. Configure your data pipeline through a clean web UI, and let [Telegraf](https://www.influxdata.com/time-series-platform/telegraf/) handle the heavy lifting.

```
OPC UA Machines  ─┐
                  ├──►  IIoT Edge Gateway   ──►  AWS IoT Core
Modbus Devices   ─┘      (Telegraf agent)   ──►  Azure IoT Hub
                                            ──►  Any MQTT broker
```

![IIoT Edge Gateway Dashboard](screenshots/dashboard.png)

---

## Features

- **OPC UA support** — Browse the node tree and select variables with a point-and-click interface
- **Modbus TCP support** — Configure holding/input/coil/discrete registers with a register map table
- **Simultaneous inputs** — Read from OPC UA and Modbus at the same time, merged into a single MQTT stream
- **Cloud-ready** — Built-in support for AWS IoT Core and Azure IoT Hub with TLS certificate management
- **Live message tail** — Subscribe to your broker in real time to verify data is flowing
- **Pipeline dashboard** — Monitor reads per source, buffer usage, MQTT delivery, and system health
- **Zero-config deploy** — One click generates `telegraf.conf` and restarts the agent
- **Auto-save** — All configuration changes are saved automatically as you type
- **Docker-native** — Runs on any Linux edge server or gateway hardware

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- One or more industrial devices (OPC UA server and/or Modbus TCP device)
- An MQTT broker (AWS IoT Core, Azure IoT Hub, or any standard broker)

---

## Quick Start

Install a specific release (recommended):

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/cantalejo84/iiot-edge-gateway.git
cd iiot-edge-gateway
docker compose up -d
```

Or clone the latest development version:

```bash
git clone https://github.com/cantalejo84/iiot-edge-gateway.git
cd iiot-edge-gateway
docker compose up -d
```

Open **http://localhost:8050** in your browser.

> Demo servers for OPC UA and Modbus TCP are included, plus a Mosquitto MQTT broker. No external services needed to try it out.

---

## User Guide

### 1 — Connect your OPC UA server

Go to **INPUT → OPC UA → Connection** and enter your server endpoint:

```
opc.tcp://your-plc-or-scada:4840
```

Supports Anonymous, Username/Password, and X.509 Certificate authentication. Use **Use Demo Server** to auto-fill with the built-in OPC UA simulator.

### 2 — Browse and select variables

Use **Browse Nodes** to navigate the address space of your machine. Click any variable node to inspect it, then add it to your selection.

In **Acquisition**, choose between two collection modes:

- **Polling** — Telegraf reads all nodes on a fixed interval (e.g. every 30 s)
- **Subscription** — The OPC UA server pushes changes as they happen (event-driven, lower latency)

You can also configure the **Message Format**: send each variable as an individual message, or group all variables into a single timestamped payload per cycle.

### 3 — Connect your Modbus TCP devices

Go to **INPUT → Modbus TCP → Connection** and enter the device address (`host:port`, default port 502) and slave ID. Then add your registers:

| Field | Description |
|---|---|
| Name | Metric field name (e.g. `temperature`) |
| Register Type | `holding`, `input`, `coil`, or `discrete` |
| Address | **0-based** address. Note: manuals often show 1-based (40001 = address 0) |
| Data Type | `UINT16`, `INT16`, `UINT32`, `INT32`, `FLOAT32`, `FLOAT64`, `BOOL` |
| Byte Order | `ABCD` (Big Endian, most common), `DCBA`, `BADC`, or `CDAB` |

Multi-register types (`UINT32`, `INT32`, `FLOAT32`, `FLOAT64`) occupy 2–4 consecutive registers — make sure addresses don't overlap.

Use **Use Demo Server** to auto-fill with the built-in Modbus simulator and a set of example registers (temperature, pressure, motor speed, voltage, current).

> OPC UA and Modbus TCP can run simultaneously. Both inputs are merged into a single MQTT stream.

### 4 — Configure your MQTT output

Go to **OUTPUT → MQTT → Connection** and enter your broker endpoint:

| Platform | Endpoint format |
|---|---|
| AWS IoT Core | `mqtts://xxxx-ats.iot.eu-west-1.amazonaws.com:8883` |
| Azure IoT Hub | `mqtts://your-hub.azure-devices.net:8883` |
| Generic broker | `mqtt://your-broker:1883` |

Configure the topic pattern, QoS level, and data format (JSON or InfluxDB Line Protocol). Upload your TLS certificates in the collapsible **TLS Certificates** section if your broker requires them.

Use the **Demo** button to quick-fill with the built-in Mosquitto broker.

### 5 — Deploy

Click **Deploy config** in the sidebar. The gateway generates `telegraf.conf` from your current configuration and restarts the Telegraf agent automatically. A status badge below the button shows whether the running config is in sync with your latest settings.

### 6 — Monitor the Dashboard

The Dashboard provides a live view of your data pipeline:

- **Pipeline Health** — Data flow from each input source through to MQTT delivery, with per-cycle message counts and error indicators
- **System Health** — CPU, memory, disk, and network I/O of the gateway host
- **Gateway Info** — Container status, Telegraf uptime, last deploy time, and restart history

---

## Integrations

### AWS IoT Core

Upload your device certificate, CA, and private key in the TLS section. The gateway auto-generates a scoped IAM policy based on your topic pattern — paste it directly into the AWS console.

### Azure IoT Hub

The gateway auto-generates the required MQTT username (`{hub}.azure-devices.net/{device_id}/?api-version=2021-04-12`) and the correct topic format (`devices/{device_id}/messages/events/`). Supports both SAS token and X.509 certificate authentication.

### Generic MQTT Broker

Standard MQTT (1883) and MQTTS (8883) supported. Compatible with Mosquitto, HiveMQ, EMQX, and any MQTT 3.1.1-compliant broker.

---

## Releases

| Version | Notes |
|---|---|
| `v0.2.0` | Modbus TCP, Acquisition Mode (Polling/Subscription), Configuration page |
| `v0.1.0` | Initial release — OPC UA + MQTT |

---

## Operations

### Updating

To update to a new release on a running server:

```bash
cd iiot-edge-gateway

# Fetch all tags and switch to the new release
git fetch --tags
git checkout v0.2.0

# Rebuild and restart the gateway container (Telegraf and data are untouched)
docker compose up --build -d gateway
```

If the release includes changes to `docker-compose.yml` (e.g. new services or volume mounts), restart the full stack instead:

```bash
docker compose up --build -d
```

Your configuration data (`data/config.json`, certificates) and the running Telegraf agent are not affected by a gateway-only rebuild.

### Uninstall

To completely remove the application, all containers, images, volumes, and configuration data:

```bash
# Stop and remove containers, networks and volumes
docker compose down -v

# Remove the Docker images built for this project
docker compose down --rmi all

# Delete all local data (config, certificates, generated Telegraf config)
rm -rf data/ telegraf/telegraf.conf

# Delete the repository
cd .. && rm -rf iiot-edge-gateway
```

> **Note:** `rm -rf data/` permanently deletes your OPC UA and MQTT configuration and any uploaded TLS certificates. Back up `data/config.json` and `data/certs/` before proceeding if you want to restore them later.

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
