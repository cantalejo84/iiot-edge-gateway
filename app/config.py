DEFAULT_CONFIG = {
    "opcua": {
        "endpoint": "opc.tcp://opcua-demo-server:4840/freeopcua/server/",
        "auth_method": "Anonymous",
        "username": "",
        "password": "",
        "security_policy": "None",
        "security_mode": "None",
        "connect_timeout": "10s",
        "request_timeout": "5s",
        "certificate": "",
        "private_key": "",
    },
    "nodes": [],
    "publishing": {"mode": "individual", "group_interval": "10s"},
    "modbus": {
        "enabled": False,
        "controller": "modbus-demo-server:502",
        "slave_id": 1,
        "timeout": "5s",
        "registers": [],
    },
    "mqtt": {
        "endpoint": "",
        "topic_pattern": "iiot/gateway/{{ .Hostname }}/{{ .PluginName }}",
        "qos": 1,
        "data_format": "json",
        "tls_ca": "",
        "tls_cert": "",
        "tls_key": "",
        "username": "",
        "password": "",
    },
    "_meta": {"last_modified": None, "last_applied": None},
}

OPCUA_AUTH_METHODS = ["Anonymous", "UserName", "Certificate"]
OPCUA_SECURITY_POLICIES = ["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"]
OPCUA_SECURITY_MODES = ["None", "Sign", "SignAndEncrypt"]
MQTT_QOS_OPTIONS = [0, 1, 2]
MQTT_DATA_FORMATS = ["json", "influx"]

MODBUS_REGISTER_TYPES = ["holding", "input", "coil", "discrete"]
MODBUS_DATA_TYPES = ["UINT16", "INT16", "UINT32", "INT32", "FLOAT32", "FLOAT64", "BOOL"]
MODBUS_BYTE_ORDERS = ["ABCD", "DCBA", "BADC", "CDAB"]
