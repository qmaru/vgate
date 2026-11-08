import argparse
import base64
import csv
import json
import re
import sys

import httpx2

API_URL = "https://www.vpngate.net/api/iphone/"


def pem_block(config: str, name: str) -> list[str]:
    match = re.search(rf"<{name}>\s*(.*?)\s*</{name}>", config, re.DOTALL)
    return match.group(1).splitlines() if match else []


def build_endpoint(region: str, config: str) -> dict:
    directives: dict[str, list[str]] = {}
    for line in config.splitlines():
        parts = line.split()
        if parts and parts[0] not in directives:
            directives[parts[0]] = parts[1:]

    endpoint = {
        "type": "openvpn-client",
        "tag": f"vpngate-{region.lower()}",
        "server": directives["remote"][0],
        "server_port": int(directives["remote"][1]),
        "network": "tcp" if directives.get("proto", ["udp"])[0].startswith("tcp") else "udp",
        "username": "vpn",
        "password": "vpn",
        "block_ipv6": True,
        "domain_resolver": {"server": "google-dns", "strategy": "ipv4_only"},
        "tls": {
            "certificate": pem_block(config, "ca"),
            "client_certificate": pem_block(config, "cert"),
            "client_key": pem_block(config, "key"),
        },
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
        description="Print sing-box OpenVPN endpoints with the top-scored VPN Gate server per region."
    )
    parser.add_argument(
        "--region",
        required=True,
        nargs="+",
        metavar="CC",
        help="2-letter country codes, e.g. JP KR",
    )
    parser.add_argument(
        "--output", metavar="PATH", help="write JSON to this file instead of stdout"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        metavar="N",
        help="endpoints per region; N>1 also adds a urltest outbound per region",
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")

    regions = [r.upper() for r in args.region]
    if any(len(r) != 2 or not r.isalpha() for r in regions):
        parser.error("--region must be 2-letter country codes")

    columns: dict[str, int] = {}
    candidates: dict[str, list[tuple[int, str]]] = {}

    with httpx2.stream("GET", API_URL, timeout=30) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("#HostName"):
                columns = {name: i for i, name in enumerate(next(csv.reader([line[1:]])))}
                continue
            if not columns or not line or line.startswith("*"):
                continue

            fields = next(csv.reader([line]))
            region = fields[columns["CountryShort"]]
            config = fields[columns["OpenVPN_ConfigData_Base64"]]
            if region not in regions or not config:
                continue
            candidates.setdefault(region, []).append((int(fields[columns["Score"]]), config))

    if not candidates:
        print(f"No OpenVPN servers found for regions {', '.join(regions)}", file=sys.stderr)
        sys.exit(1)

    endpoints = []
    outbounds = []
    for region, items in candidates.items():
        top = sorted(items, key=lambda item: item[0], reverse=True)[: args.count]
        tags = []
        for i, (_, config) in enumerate(top, 1):
            endpoint = build_endpoint(region, base64.b64decode(config).decode())
            if args.count > 1:
                endpoint["tag"] = f"vpngate-{region.lower()}-{i}"
            tags.append(endpoint["tag"])
            endpoints.append(endpoint)
        if args.count > 1:
            outbounds.append(
                {
                    "type": "urltest",
                    "tag": f"vpngate-{region.lower()}",
                    "outbounds": tags,
                    "interval": "1m",
                }
            )

    data = (
        {"endpoints": endpoints, "outbounds": outbounds}
        if args.count > 1
        else {"endpoints": endpoints}
    )
    text = json.dumps(data, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
