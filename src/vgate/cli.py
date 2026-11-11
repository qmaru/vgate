import argparse
from importlib.metadata import version

from vgate import convert, core, radarhub


def print_version(args) -> None:
    print(version("vgate"))


def main() -> None:
    parser = argparse.ArgumentParser(prog="vgate")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in (core, convert, radarhub):
        module.add_subparser(subparsers)
    version = subparsers.add_parser("version", help="print vgate version")
    version.set_defaults(run=print_version)

    args = parser.parse_args()
    args.run(args)
