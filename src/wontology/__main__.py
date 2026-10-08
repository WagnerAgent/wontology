"""Command-line entry point; no cloud access occurs until a scan is requested."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Wontology — your cloud infrastructure, mapped locally"
    )
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("WONTOLOGY_DATA_DIR", Path.home() / ".wontology")),
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--container",
        action="store_true",
        help="Bind inside a container. Publish the port on host 127.0.0.1 only.",
    )
    args = parser.parse_args()
    from .server import run

    run(args.port, args.data_dir, not args.no_browser, args.container)


if __name__ == "__main__":
    main()
