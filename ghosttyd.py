#!/usr/bin/env python3
import argparse

from ghostty.daemon import run_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("serve", nargs="?", default="serve")
    parser.parse_args()
    run_server()


if __name__ == "__main__":
    main()
