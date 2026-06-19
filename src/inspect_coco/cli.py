"""Backwards-compat shim — CLI moved to inspect_coco.cmd."""

from inspect_coco.cmd import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
