"""Printer connection management — writes raw ESC/P data to /dev/usb/lp0.

Supports:
- Direct USB printing via /dev/usb/lp0
- Fallback to file output for debugging
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default device path for USB printer on Linux
DEFAULT_DEVICE = "/dev/usb/lp0"


class PrinterError(Exception):
    """Raised when printer communication fails."""
    pass


class Printer:
    """Manages connection to Epson LQ-635C via USB."""

    def __init__(self, device_path: str = None):
        self.device_path = device_path or os.getenv("PRINTER_DEVICE", DEFAULT_DEVICE)

    def is_available(self) -> bool:
        """Check if printer device is accessible."""
        return os.path.exists(self.device_path) and os.access(self.device_path, os.W_OK)

    def print_raw(self, data: bytes) -> bool:
        """Send raw ESC/P bytes to the printer.

        Args:
            data: Raw ESC/P byte data to send

        Returns:
            True if successful

        Raises:
            PrinterError if device not available or write fails
        """
        if not self.is_available():
            raise PrinterError(
                f"Printer not available at {self.device_path}. "
                "Check USB connection and permissions (try: sudo chmod 666 /dev/usb/lp0)"
            )

        try:
            with open(self.device_path, 'wb') as fp:
                fp.write(data)
                fp.flush()
            logger.info(f"Printed {len(data)} bytes to {self.device_path}")
            return True
        except PermissionError:
            raise PrinterError(
                f"Permission denied for {self.device_path}. "
                "Run: sudo chmod 666 /dev/usb/lp0 or add user to lp group"
            )
        except OSError as e:
            raise PrinterError(f"Printer write error: {e}")

    def print_to_file(self, data: bytes, output_path: str = "/tmp/print_output.prn") -> str:
        """Write ESC/P data to a file for debugging.

        Returns:
            Path to the output file
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as fp:
            fp.write(data)
        logger.info(f"Print data saved to {output_path} ({len(data)} bytes)")
        return output_path


# Singleton instance
printer = Printer()
