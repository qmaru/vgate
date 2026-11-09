import argparse

from vgate import convert, core, radarhub


def main() -> None:
    parser = argparse.ArgumentParser(prog="vgate")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in (core, convert, radarhub):
        module.add_subparser(subparsers)

    args = parser.parse_args()
    args.run(args)
