#!/usr/bin/env python3
"""Net-SNMP extend wrapper; install beside the device_monitor package."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from device_monitor.probe import main
raise SystemExit(main())
