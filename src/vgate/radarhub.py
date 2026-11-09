import argparse
import base64
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import httpx2

REGION_URL = "https://radarhub.top/regions/{region}.txt"
URLTEST_URL = "https://www.gstatic.com/generate_204"


def build_outbound(tag: str, uri: str) -> dict:
    url = urlsplit(uri)
    params = dict(parse_qsl(url.query))
    tls = {"enabled": True, "insecure": params.get("insecure") == "1"}
    if "sni" in params:
        tls["server_name"] = params["sni"]

    outbound = {
        "type": "hysteria2",
        "tag": tag,
        "server": url.hostname,
        "server_port": url.port,
        "password": unquote(url.username or ""),
        "tls": tls,
    }
    if params.get("obfs") == "salamander":
        outbound["obfs"] = {"type": "salamander", "password": params["obfs-password"]}
    return outbound


def add_subparser(subparsers) -> None:
    parser = subparsers.add_parser(
        "radarhub",
        help="convert radarhub hysteria2 nodes",
        description="Convert radarhub hysteria2 nodes to sing-box hysteria2 outbounds with a urltest outbound per region.",
    )
    parser.add_argument(
        "--region",
        required=True,
        nargs="+",
        metavar="CC",
        help="2-letter country codes, e.g. HK JP",
    )
    parser.add_argument(
        "--output", metavar="PATH", help="write JSON to this file instead of stdout"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> None:
    outbounds = []
    for region in args.region:
        region = region.upper()
        response = httpx2.get(REGION_URL.format(region=region), timeout=30)
        response.raise_for_status()
        uris = [
            line
            for line in base64.b64decode(response.text).decode("utf-8").splitlines()
            if line.startswith("hysteria2://")
        ]
        if not uris:
            print(f"No hysteria2 servers found for region {region}", file=sys.stderr)
            sys.exit(1)

        tags = []
        for i, uri in enumerate(uris, 1):
            tag = f"radarhub-{region.lower()}-{i}"
            outbounds.append(build_outbound(tag, uri))
            tags.append(tag)
        outbounds.append(
            {
                "type": "urltest",
                "tag": f"radarhub-{region.lower()}",
                "outbounds": tags,
                "url": URLTEST_URL,
                "interval": "1m",
            }
        )

    text = json.dumps({"outbounds": outbounds}, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
