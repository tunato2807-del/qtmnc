"""Compatibility import for the packaged dashboard."""
import sys
from device_monitor import ui
sys.modules[__name__] = ui
