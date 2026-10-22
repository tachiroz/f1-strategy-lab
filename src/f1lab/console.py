"""Console helpers shared by the command line entry points."""

import io
import sys


def tolerate_console_encoding() -> None:
    """Avoid crashes on consoles that cannot print names like 'Pérez' (e.g. cp1251)."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="backslashreplace")
