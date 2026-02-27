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
