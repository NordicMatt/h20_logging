# /// script
# dependencies = [
#   "pyserial~=3.5",
# ]
# ///
"""Read nRF54H20 aggregated STM logs and unwrap the rolling timestamp.

The nRF54H20 CoreSight STM stamps every log record with a 32-bit hardware
timestamp clocked at 40 MHz. That counter overflows every 2**32 / 40e6 =
107.3741824 s, so the decoded log time rolls back to 00:00:00 roughly every
1 min 47 s even though the device keeps running (the per-core message counters
increment straight through the wrap). This is a display artifact, not a reboot,
and the on-chip decoder cannot widen the hardware counter.

This tool reads the proxy UART (or an existing capture file), detects each
rollover, and rewrites the leading "[HH:MM:SS.mmm,uuu]" timestamp as a
monotonic time since start so long runs read correctly.

Usage:
    # Live, matching the 1 Mbaud console overlay in this sample
    uv run scripts/h20_logmon.py --port /dev/ttyACM1 --baud 1000000

    # Re-process an existing capture
    uv run scripts/h20_logmon.py --infile capture.log

license: "SPDX-License-Identifier: Apache-2.0"
"""

import argparse
import re
import sys

# 32-bit STM timestamp at 40 MHz -> one wrap every 2**32 / 40e6 seconds.
STM_TS_HZ = 40_000_000
WRAP_PERIOD = (2**32) / STM_TS_HZ  # 107.3741824 s
# A genuine rollover has a distinct physical signature: the time was near the
# top of the range and lands near the bottom. Requiring all of {came from near
# the top, dropped by most of a period, landed near the bottom} means the rare
# mid-range STM decode glitches (which Nordic documents, ~0.1% of lines here)
# cannot be mistaken for a rollover. Glitches are passed through unchanged --
# they are a pre-existing decode artifact, independent of the rollover fix.
WRAP_NEAR_TOP = 0.85 * WRAP_PERIOD
WRAP_NEAR_BOTTOM = 0.15 * WRAP_PERIOD
WRAP_MIN_DROP = 0.5 * WRAP_PERIOD

TS_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\.(\d{3}),(\d{3})\]")


def _to_seconds(m: re.Match) -> float:
    h, mi, s, ms, us = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1e3 + us / 1e6


def _fmt(total: float) -> str:
    us = round(total * 1e6)
    h, us = divmod(us, 3600_000_000)
    mi, us = divmod(us, 60_000_000)
    s, us = divmod(us, 1_000_000)
    ms, us = divmod(us, 1000)
    return f"[{h:02d}:{mi:02d}:{s:02d}.{ms:03d},{us:03d}]"


class Unwrapper:
    """Rewrite the rolling 32-bit STM time as elapsed time since start.

    Each detected rollover adds one period to a running offset; the emitted time
    is simply raw + offset, so individual records stay faithful to the device
    (any stray decode glitch shows as-is rather than being silently rewritten).
    """

    def __init__(self) -> None:
        self.offset = 0.0
        self.prev = None          # previous line's raw timestamp
        self.wraps = 0

    def process(self, line: str) -> str:
        m = TS_RE.match(line)
        if not m:
            return line
        raw = _to_seconds(m)
        if (self.prev is not None
                and self.prev > WRAP_NEAR_TOP
                and raw < WRAP_NEAR_BOTTOM
                and (self.prev - raw) > WRAP_MIN_DROP):
            self.offset += WRAP_PERIOD
            self.wraps += 1
        self.prev = raw
        return _fmt(raw + self.offset) + line[m.end():]


def _run(lines, out, err) -> None:
    uw = Unwrapper()
    for line in lines:
        out.write(uw.process(line))
        out.flush()
    if uw.wraps:
        err.write(f"\n[h20_logmon] unwrapped {uw.wraps} timestamp rollover(s) "
                  f"(+{WRAP_PERIOD:.6f}s each)\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", help="Serial port, e.g. /dev/ttyACM1")
    p.add_argument("--baud", type=int, default=1000000,
                   help="Baud rate (default: 1000000, matching the sample overlay)")
    p.add_argument("--infile", help="Process an existing capture file instead of a port")
    args = p.parse_args()

    if args.infile:
        with open(args.infile, errors="replace") as f:
            _run(f, sys.stdout, sys.stderr)
        return

    if not args.port:
        p.error("one of --port or --infile is required")

    try:
        import serial
    except ImportError:
        sys.exit("pyserial not found. Run with 'uv run' / 'pipx run', or: pip install pyserial")

    ser = serial.Serial(args.port, args.baud, timeout=1.0)
    ser.dtr = True  # Nordic DK UART lines are tri-stated until DTR is asserted.
    print(f"[h20_logmon] reading {args.port} @ {args.baud} baud (Ctrl+C to stop)",
          file=sys.stderr)

    def _lines():
        while True:
            raw = ser.readline()
            if raw:
                yield raw.decode(errors="replace")

    try:
        _run(_lines(), sys.stdout, sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()
