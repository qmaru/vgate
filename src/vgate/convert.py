import argparse
import json
import re
from pathlib import Path
from typing import Any

from vgate.cli import pem_block


def build_endpoint(tag: str, config: str) -> dict:
    directives: dict[str, list[str]] = {}
    for line in config.splitlines():
        parts = line.split()
        if parts and parts[0] not in directives:
            directives[parts[0]] = parts[1:]

    tls: dict[str, Any] = {
        "certificate": pem_block(config, "ca"),
        "client_certificate": pem_block(config, "cert"),
        "client_key": pem_block(config, "key"),
    }
    endpoint: dict[str, Any] = {
        "type": "openvpn-client",
        "tag": tag,
        "server": directives["remote"][0],
        "server_port": int(directives["remote"][1]),
        "network": "tcp" if directives.get("proto", ["udp"])[0].startswith("tcp") else "udp",
        "tls": tls,
    }
    for name in ("tls-crypt", "tls-auth"):
        if f"<{name}>" in config:
            tls["control_wrap"] = {
                "type": name.replace("-", "_"),
                "key": pem_block(config, name),
            }
    if "cipher" in directives:
        endpoint["data_ciphers_fallback"] = directives["cipher"][0]
    if "data-ciphers" in directives:
        endpoint["data_ciphers"] = directives["data-ciphers"][0].split(":")
    if "auth" in directives:
        endpoint["auth"] = directives["auth"][0]
    return endpoint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert OpenVPN .ovpn configs to sing-box openvpn-client endpoints."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="one or more .ovpn files, or folders containing .ovpn files",
    )
    parser.add_argument(
        "--tag",
        metavar="TAG",
        help="urltest group tag for all files; default: filename prefix without trailing -N",
    )
    parser.add_argument(
        "--username", metavar="USER", help="OpenVPN username added to every endpoint"
    )
    parser.add_argument(
        "--password", metavar="PASS", help="OpenVPN password added to every endpoint"
    )
    parser.add_argument(
        "--output", metavar="PATH", help="write JSON to this file instead of stdout"
    )
    args = parser.parse_args()
    if bool(args.username) != (args.password is not None):
        parser.error("--username and --password must be given together")

    files = []
    for item in args.paths:
        path = Path(item)
        files += sorted(path.glob("*.ovpn")) if path.is_dir() else [path]
    if not files:
        parser.error("no .ovpn files found")

    endpoints = []
    groups: dict[str, list[str]] = {}
    for path in files:
        tag = path.name.split(".")[0]
        endpoint = build_endpoint(tag, path.read_text(encoding="utf-8"))
        if args.username:
            endpoint["username"] = args.username
            endpoint["password"] = args.password
        endpoints.append(endpoint)
        group = args.tag or re.sub(r"-\d+$", "", tag)
        groups.setdefault(group, []).append(tag)

    outbounds = [
        {"type": "urltest", "tag": group, "outbounds": tags, "interval": "1m"}
        for group, tags in groups.items()
    ]
    text = json.dumps({"endpoints": endpoints, "outbounds": outbounds}, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
