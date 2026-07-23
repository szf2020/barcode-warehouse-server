"""ESC/P command builder for Epson LQ-635C dot matrix printer.

Reference: Epson ESC/P Reference Manual
- 80-column mode: 10 CPI (characters per inch)
- 132-column mode: 17 CPI (condensed)
- Paper: continuous form or single sheet A4
- Interface: USB (/dev/usb/lp0)
"""

from typing import List


class ESCPBuilder:
    """Builds ESC/P byte sequences for Epson LQ-635C."""

    def __init__(self):
        self._buffer: bytearray = bytearray()

    @property
    def data(self) -> bytes:
        """Get the accumulated ESC/P data."""
        return bytes(self._buffer)

    def reset(self) -> "ESCPBuilder":
        """Reset printer to default settings (ESC @)."""
        self._buffer.extend(b'\x1b\x40')
        return self

    # ─── Character Formatting ─────────────────────────────────────────────

    def bold_on(self) -> "ESCPBuilder":
        """Enable bold (ESC E)."""
        self._buffer.extend(b'\x1b\x45')
        return self

    def bold_off(self) -> "ESCPBuilder":
        """Disable bold (ESC F)."""
        self._buffer.extend(b'\x1b\x46')
        return self

    def condensed_on(self) -> "ESCPBuilder":
        """Enable condensed mode — 17 CPI, 132 cols (SI)."""
        self._buffer.extend(b'\x0f')
        return self

    def condensed_off(self) -> "ESCPBuilder":
        """Disable condensed mode — back to 10 CPI (DC2)."""
        self._buffer.extend(b'\x12')
        return self

    def double_width_on(self) -> "ESCPBuilder":
        """Enable double-width for current line (ESC W 1)."""
        self._buffer.extend(b'\x1b\x57\x01')
        return self

    def double_width_off(self) -> "ESCPBuilder":
        """Disable double-width (ESC W 0)."""
        self._buffer.extend(b'\x1b\x57\x00')
        return self

    def underline_on(self) -> "ESCPBuilder":
        """Enable underline (ESC - 1)."""
        self._buffer.extend(b'\x1b\x2d\x01')
        return self

    def underline_off(self) -> "ESCPBuilder":
        """Disable underline (ESC - 0)."""
        self._buffer.extend(b'\x1b\x2d\x00')
        return self

    # ─── Line Spacing ─────────────────────────────────────────────────────

    def line_spacing(self, n: int = 24) -> "ESCPBuilder":
        """Set line spacing to n/180 inch (ESC 3 n). Default n=24 ≈ 1/6 inch."""
        self._buffer.extend(b'\x1b\x33' + bytes([n]))
        return self

    def line_spacing_default(self) -> "ESCPBuilder":
        """Reset to 1/6 inch line spacing (ESC 2)."""
        self._buffer.extend(b'\x1b\x32')
        return self

    # ─── Page / Form ──────────────────────────────────────────────────────

    def form_feed(self) -> "ESCPBuilder":
        """Advance to next page (FF)."""
        self._buffer.extend(b'\x0c')
        return self

    def set_page_length_lines(self, lines: int = 66) -> "ESCPBuilder":
        """Set page length in lines (ESC C n). Default 66 lines for 11-inch paper."""
        self._buffer.extend(b'\x1b\x43' + bytes([lines]))
        return self

    def set_page_length_inches(self, inches: int = 11) -> "ESCPBuilder":
        """Set page length in inches (ESC C 0 n)."""
        self._buffer.extend(b'\x1b\x43\x00' + bytes([inches]))
        return self

    def set_margins(self, left: int = 0, right: int = 80) -> "ESCPBuilder":
        """Set left and right margins (ESC l n, ESC Q n)."""
        self._buffer.extend(b'\x1b\x6c' + bytes([left]))
        self._buffer.extend(b'\x1b\x51' + bytes([right]))
        return self

    # ─── Text Output ──────────────────────────────────────────────────────

    def text(self, s: str, encoding: str = "big5") -> "ESCPBuilder":
        """Write text string. Default encoding Big5 for Traditional Chinese."""
        self._buffer.extend(s.encode(encoding, errors="replace"))
        return self

    def newline(self) -> "ESCPBuilder":
        """Carriage return + line feed (CR LF)."""
        self._buffer.extend(b'\x0d\x0a')
        return self

    def cr(self) -> "ESCPBuilder":
        """Carriage return only."""
        self._buffer.extend(b'\x0d')
        return self

    # ─── Table Helpers ────────────────────────────────────────────────────

    def line(self, char: str = "-", width: int = 80) -> "ESCPBuilder":
        """Print a horizontal line."""
        self.text(char * width)
        self.newline()
        return self

    def row(self, columns: List[str], widths: List[int], aligns: List[str] = None) -> "ESCPBuilder":
        """Print a table row with fixed-width columns.

        Args:
            columns: Column values
            widths: Column widths in characters
            aligns: Alignment per column ('l'=left, 'r'=right, 'c'=center)
        """
        if aligns is None:
            aligns = ['l'] * len(columns)

        parts = []
        for i, (col, w, align) in enumerate(zip(columns, widths, aligns)):
            # Truncate if too long
            display = col[:w] if len(col) > w else col
            if align == 'r':
                parts.append(display.rjust(w))
            elif align == 'c':
                parts.append(display.center(w))
            else:
                parts.append(display.ljust(w))

        self.text("".join(parts))
        self.newline()
        return self

    # ─── Convenience ──────────────────────────────────────────────────────

    def header(self, title: str, width: int = 80) -> "ESCPBuilder":
        """Print a centered bold header."""
        self.bold_on()
        self.double_width_on()
        self.text(title.center(width // 2))
        self.newline()
        self.double_width_off()
        self.bold_off()
        return self

    def init_chinese(self) -> "ESCPBuilder":
        """Initialize printer for Chinese printing (select Big5 character set)."""
        # ESC R 0 = select default character table
        # Most LQ-635C models handle Big5 natively when raw bytes sent
        self.reset()
        self.line_spacing_default()
        return self
