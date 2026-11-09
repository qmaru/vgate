from collections import Counter
from datetime import datetime


def build_report(endpoints: list[dict], fmt: str) -> str:
    counts = Counter(ep["tag"].split("-")[1].upper() for ep in endpoints)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if fmt == "markdown":
        lines = ['<div align="center">', "", "### VPN Gate Servers", "", f"Generated at: {now}", "", "| Region | Servers |", "| :-: | :-: |"]
        lines += [f"| {region} | {n} |" for region, n in counts.items()]
        lines += ["", "</div>"]
        return "\n".join(lines)
    lines = ["VPN Gate Servers", f"Generated at: {now}", "", "Region  Servers"]
    lines += [f"{region:<8}{n}" for region, n in counts.items()]
    return "\n".join(lines)
