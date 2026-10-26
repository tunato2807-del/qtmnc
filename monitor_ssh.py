#!/usr/bin/env python3
"""Compatibility entry point. New CLI: python -m device_monitor."""
import sys
from device_monitor import app

if __name__ == "__main__":
    raise SystemExit(app.main())
else:
    sys.modules[__name__] = app
