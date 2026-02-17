from asyncua import Client, ua


def _build_client(config):
    client = Client(url=config["endpoint"])
    timeout = config.get("connect_timeout", "10s")
    client.session_timeout = int(timeout.replace("s", "")) * 1000

    security_policy = config.get("security_policy", "None")
    security_mode = config.get("security_mode", "None")

    if security_policy != "None" and security_mode != "None":
        cert = config.get("certificate", "")
        key = config.get("private_key", "")
        if cert and key:
            policy_map = {
                "Basic128Rsa15": ua.SecurityPolicyType.Basic128Rsa15_SignAndEncrypt,
                "Basic256": ua.SecurityPolicyType.Basic256_SignAndEncrypt,
                "Basic256Sha256": ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            }
            if security_mode == "Sign":
                policy_map = {
                    "Basic128Rsa15": ua.SecurityPolicyType.Basic128Rsa15_Sign,
                    "Basic256": ua.SecurityPolicyType.Basic256_Sign,
                    "Basic256Sha256": ua.SecurityPolicyType.Basic256Sha256_Sign,
                }
            policy_type = policy_map.get(security_policy)
            if policy_type:
                client.set_security(policy_type, cert, key)

    auth_method = config.get("auth_method", "Anonymous")
    if auth_method == "UserName":
        client.set_user(config.get("username", ""))
        client.set_password(config.get("password", ""))

    return client


async def test_connection(config):
    try:
        client = _build_client(config)
        async with client:
            server_state = await client.nodes.server.read_browse_name()
            return {"ok": True, "server": str(server_state)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def browse_children(config, node_id_str):
    client = _build_client(config)
    async with client:
        node = client.get_node(node_id_str)
        children = await node.get_children()
        result = []
        for child in children:
            browse_name = await child.read_browse_name()
            node_class = await child.read_node_class()
            has_children = len(await child.get_children()) > 0
            result.append({
                "node_id": child.nodeid.to_string(),
                "display_name": browse_name.Name,
                "node_class": node_class.name,
                "has_children": has_children,
            })
        return result


async def read_node_details(config, node_id_str):
    client = _build_client(config)
    async with client:
        node = client.get_node(node_id_str)
        browse_name = await node.read_browse_name()
        node_class = await node.read_node_class()

        details = {
            "node_id": node.nodeid.to_string(),
            "display_name": browse_name.Name,
            "namespace": node.nodeid.NamespaceIndex,
            "node_class": node_class.name,
        }

        if node_class == ua.NodeClass.Variable:
            try:
                value = await node.read_value()
                details["value"] = str(value)
            except Exception:
                details["value"] = None

            try:
                data_type_node = await node.read_data_type()
                dt_browse = await client.get_node(data_type_node).read_browse_name()
                details["data_type"] = dt_browse.Name
            except Exception:
                details["data_type"] = "Unknown"

            # Parse identifier info for node selection
            nodeid = node.nodeid
            if nodeid.NodeIdType == ua.NodeIdType.String:
                details["identifier_type"] = "s"
                details["identifier"] = nodeid.Identifier
            elif nodeid.NodeIdType == ua.NodeIdType.Numeric:
                details["identifier_type"] = "i"
                details["identifier"] = str(nodeid.Identifier)
            elif nodeid.NodeIdType == ua.NodeIdType.Guid:
                details["identifier_type"] = "g"
                details["identifier"] = str(nodeid.Identifier)
            else:
                details["identifier_type"] = "b"
                details["identifier"] = str(nodeid.Identifier)

        return details
