# IIoT Edge Gateway

Industrial IoT Edge Gateway that reads OPC UA data and converts it to MQTT for AWS IoT Core, powered by Telegraf.

## Architecture

```
Flask Gateway (config UI + REST API)
        │
        ├── Configures → Telegraf (OPC UA input → MQTT output)
        ├── Monitors   → System health (CPU/RAM) + Telegraf metrics
        └── Persists   → JSON config + TLS certificates
```

## Quick Start

### Development (with test OPC UA server + MQTT broker)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This starts:
- **Gateway UI**: http://localhost:5000
- **OPC UA Test Server**: opc.tcp://localhost:4840
- **Mosquitto MQTT Broker**: mqtt://localhost:1883
- **Telegraf**: with health endpoint on :8080

### Local Development (without Docker)

```bash
pip install -r requirements.txt
FLASK_APP=app FLASK_DEBUG=1 flask run
```

### Production

```bash
docker compose up --build -d
```

## Usage

1. **Configure OPC UA** (`/opcua/config`): Set the OPC UA server endpoint, authentication, and security settings. Test the connection.
2. **Browse Nodes** (`/opcua/browser`): Navigate the OPC UA node tree. Click nodes to see details. Add variables to your selection.
3. **Select Nodes** (`/opcua/nodes`): Configure polling/subscription mode, intervals, and deadband for each selected node.
4. **Configure MQTT** (`/mqtt/config`): Set the AWS IoT Core endpoint, topic pattern, QoS. Upload TLS certificates.
5. **Preview & Apply**: Preview the generated `telegraf.conf`, then apply it.
6. **Restart Telegraf**: `docker compose restart telegraf`
7. **Monitor** (`/dashboard`): Watch system health and Telegraf metrics.

## Project Structure

```
app/
  __init__.py          # Flask app factory
  config.py            # Default configuration values
  routes/              # Flask blueprints (opcua, mqtt, telegraf, dashboard)
  services/            # Business logic (config_store, opcua_client, mqtt_client, etc.)
  templates/           # Jinja2 HTML templates
  static/              # CSS + JavaScript
  telegraf/            # telegraf.conf.j2 template
data/
  config.json          # Persisted configuration (auto-generated)
  certs/               # TLS certificates (mqtt/ and opcua/)
telegraf/
  telegraf.conf        # Generated Telegraf config (mounted into container)
test_infra/
  opcua_server/        # asyncua-based test OPC UA server
  mosquitto/           # Mosquitto broker config for local testing
```

## Tech Stack

- **Backend**: Python 3.11, Flask, asyncua, paho-mqtt, psutil
- **Frontend**: Bootstrap 5, vanilla JS, Jinja2 templates
- **Processing**: Telegraf (OPC UA input → MQTT output)
- **Persistence**: JSON files
