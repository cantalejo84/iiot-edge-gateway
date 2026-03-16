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


def _friendly_error(e):
    msg = str(e)
    if "Errno 111" in msg or "Connect call failed" in msg:
        return "Server unreachable — connection refused"
    if (
        "Errno 110" in msg
        or "timed out" in msg.lower()
        or "TimeoutError" in type(e).__name__
    ):
        return "Connection timed out — check endpoint and network"
    if (
        "Errno -2" in msg
        or "Name or service not known" in msg
        or "nodename nor servname" in msg
    ):
        return "Hostname not found — check the endpoint URL"
    if "BadUserAccessDenied" in msg or "BadIdentityTokenRejected" in msg:
        return "Authentication failed — check credentials"
    if "BadSecurityChecksFailed" in msg or "BadCertificate" in msg:
        return "Security/certificate error"
    if "BadTcpEndpointUrlInvalid" in msg or "Invalid URL" in msg:
        return "Invalid endpoint URL"
    return "Connection failed — server not available"


async def test_connection(config):
    try:
        client = _build_client(config)
        async with client:
            server_name = await client.nodes.server.read_browse_name()
            return {"ok": True, "server": server_name.Name}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(e), "detail": str(e)}


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
            result.append(
                {
                    "node_id": child.nodeid.to_string(),
                    "display_name": browse_name.Name,
                    "node_class": node_class.name,
                    "has_children": has_children,
                }
            )
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

            # --- Extended OPC UA attributes ---

            try:
                al = await node.get_attribute(ua.AttributeIds.AccessLevel)
                details["access_level"] = (
                    int(al.Value.Value) if al.Value.Value is not None else None
                )
            except Exception:
                details["access_level"] = None

            try:
                desc = await node.get_attribute(ua.AttributeIds.Description)
                details["description"] = (
                    desc.Value.Value.Text if desc.Value.Value else None
                )
            except Exception:
                details["description"] = None

            try:
                vr = await node.get_attribute(ua.AttributeIds.ValueRank)
                details["value_rank"] = (
                    int(vr.Value.Value) if vr.Value.Value is not None else None
                )
            except Exception:
                details["value_rank"] = None

            try:
                msi = await node.get_attribute(ua.AttributeIds.MinimumSamplingInterval)
                details["min_sampling_interval"] = (
                    float(msi.Value.Value) if msi.Value.Value is not None else None
                )
            except Exception:
                details["min_sampling_interval"] = None

            try:
                hist = await node.get_attribute(ua.AttributeIds.Historizing)
                details["historizing"] = (
                    bool(hist.Value.Value) if hist.Value.Value is not None else None
                )
            except Exception:
                details["historizing"] = None

            try:
                dv = await node.get_attribute(ua.AttributeIds.Value)
                try:
                    details["status_code"] = dv.StatusCode.name
                except AttributeError:
                    details["status_code"] = (
                        str(dv.StatusCode) if dv.StatusCode else None
                    )
                details["source_timestamp"] = (
                    dv.SourceTimestamp.isoformat() if dv.SourceTimestamp else None
                )
                details["server_timestamp"] = (
                    dv.ServerTimestamp.isoformat() if dv.ServerTimestamp else None
                )
            except Exception:
                details["status_code"] = None
                details["source_timestamp"] = None
                details["server_timestamp"] = None

            details["engineering_units"] = None
            try:
                eu_children = await node.get_children(refs=ua.ObjectIds.HasProperty)
                for ch in eu_children:
                    bn = await ch.read_browse_name()
                    if bn.Name == "EngineeringUnits":
                        eu_dv = await ch.get_attribute(ua.AttributeIds.Value)
                        eu_val = eu_dv.Value.Value
                        if (
                            eu_val
                            and hasattr(eu_val, "DisplayName")
                            and eu_val.DisplayName.Text
                        ):
                            details["engineering_units"] = eu_val.DisplayName.Text
                        break
            except Exception:
                pass

        return details


async def read_namespace_array(config):
    client = _build_client(config)
    async with client:
        ns_node = client.get_node("ns=0;i=2255")
        ns_array = await ns_node.read_value()
        return [{"index": i, "uri": uri} for i, uri in enumerate(ns_array)]


async def read_node_value(config, node_id_str):
    client = _build_client(config)
    async with client:
        node = client.get_node(node_id_str)
        dv = await node.get_attribute(ua.AttributeIds.Value)
        try:
            status_code = dv.StatusCode.name
        except AttributeError:
            status_code = str(dv.StatusCode) if dv.StatusCode else None
        return {
            "value": str(dv.Value.Value) if dv.Value.Value is not None else None,
            "status_code": status_code,
            "source_timestamp": dv.SourceTimestamp.isoformat()
            if dv.SourceTimestamp
            else None,
            "server_timestamp": dv.ServerTimestamp.isoformat()
            if dv.ServerTimestamp
            else None,
        }
