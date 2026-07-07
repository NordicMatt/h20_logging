# nRF54H20 multi-core logging over a single UART

A minimal nRF Connect SDK sample for the **nRF54H20** that demonstrates how to
collect log messages from **four cores** — the Application core, Radio core,
PPR (Peripheral Processor) and FLPR (Fast Lightweight Processor) — and stream
them out of the device through **one UART**.

The aggregation is done in hardware by the SoC's ARM CoreSight **System Trace
Macrocell (STM)**, so the application code on each core is just ordinary Zephyr
logging (`LOG_INF()`, `LOG_DBG()`, …). No inter-core messaging, ring buffers or
custom forwarding code is required.

## How it works

```
  cpuapp ──┐
  cpurad ──┤                       ┌─ ETR (RAM circular buffer)
  cpuppr ──┼─► STMESP ─► STM ──────┤
  cpuflpr ─┘   (per core)  (mux)   └─ Application core (proxy)
                                          │  drains buffer
                                          ▼
                                     UART (uart136 / VCOM)
                                          │
                                          ▼
                                    host: nrfutil trace stm  ─►  decoded logs
```

1. Every core writes its log records to its own **STM Extended Stimulus Port
   (STMESP)** using the Zephyr logging *frontend* — there is no backend or
   string formatting on the local cores.
2. The STM hardware multiplexes all the streams (MIPI STPv2 format) into a
   single **Embedded Trace Router (ETR)** circular buffer in RAM.
3. The **Application core acts as the proxy**: it drains the ETR buffer and
   sends the data out over its console UART (`uart136`, routed to the DK's
   VCOM port).
4. On the host, `nrfutil trace stm` receives the single UART stream and decodes
   it back into per-core, human-readable log lines. Each line is tagged with a
   prefix identifying the originating core (`app`, `rad`, `ppr`, `flpr`).

Each core runs the same small application (`src/main.c`) that prints a periodic
heartbeat, so once running you see interleaved log lines from all four cores in
a single terminal.

## Repository layout

```
.
├── CMakeLists.txt                 # Application-core (default) image
├── prj.conf                       # Common Kconfig for every image
├── sysbuild.conf                  # Sysbuild-level Kconfig
├── sysbuild.cmake                 # Adds the radio / PPR / FLPR images
├── Kconfig.sysbuild               # Options to enable/disable each extra core
├── src/
│   └── main.c                     # Shared app built for all four cores
└── boards/
    ├── nrf54h20dk_nrf54h20_cpuapp.conf      # STM frontend + ETR proxy + UART
    ├── nrf54h20dk_nrf54h20_cpuapp.overlay   # Launch PPR/FLPR, enable STM/ETR
    ├── nrf54h20dk_nrf54h20_cpurad.conf      # Radio core: STM frontend only
    ├── nrf54h20dk_nrf54h20_cpurad.overlay
    ├── nrf54h20dk_nrf54h20_cpuppr.conf      # PPR core: STM frontend only
    ├── nrf54h20dk_nrf54h20_cpuppr.overlay
    ├── nrf54h20dk_nrf54h20_cpuflpr.conf     # FLPR core: STM frontend only
    └── nrf54h20dk_nrf54h20_cpuflpr.overlay
```

The build uses **sysbuild** to produce four images from a single source tree.
`sysbuild.cmake` adds the Radio, PPR and FLPR images (each can be turned off via
the `SB_CONFIG_APP_CPU*_RUN` options in `Kconfig.sysbuild`). The Application
core image launches the PPR and FLPR cores (by enabling their VPR nodes) and
boots the Radio core (`CONFIG_SOC_NRF54H20_CPURAD_ENABLE=y`).

## Requirements

- nRF Connect SDK **v3.3.1** (tested) with its matching toolchain.
- An **nRF54H20 DK**.
- **nRF Util** with the `trace` command (`nrfutil-trace` v2.10.0 or later) for
  decoding the log stream on the host.

## Building

From the project root, with the nRF Connect SDK environment available:

```bash
west build -b nrf54h20dk/nrf54h20/cpuapp --sysbuild .
```

This produces four images — `h20_logging` (cpuapp), `h20_logging_cpurad`,
`h20_logging_cpuppr` and `h20_logging_cpuflpr`.

## Flashing

```bash
west flash
```

All images are flashed in the correct order automatically.

## Viewing the aggregated logs

This sample uses **standalone** STM logging: the application core decodes the
ETR data on-chip and prints ready-to-read, per-core log lines on its console
VCOM UART. No host decoder or dictionary database is needed — just open the
port. Each line is prefixed with the originating core (`app`, `rad`, `ppr`,
`flpr`).

The console UART runs at **1000000 baud** (see
`boards/nrf54h20dk_nrf54h20_cpuapp.overlay`). Open the **highest-numbered** VCOM
the DK exposes, for example with a plain terminal:

```bash
nrfutil device reset          # optional: to capture from boot
# then read the VCOM at 1 Mbaud with your terminal of choice
```

Typical output, all four cores interleaved on one port:

```
[00:00:01.000,000] <inf> app/h20_log: heartbeat 10
[00:00:01.000,123] <inf> rad/h20_log: heartbeat 10
[00:00:01.000,210] <inf> ppr/h20_log: heartbeat 10
[00:00:01.000,298] <inf> flpr/h20_log: heartbeat 10
```

### Timestamp rollover (`scripts/h20_logmon.py`)

The nRF54H20 CoreSight STM stamps records with a **32-bit hardware timestamp at
40 MHz**. That counter overflows every `2^32 / 40e6 = 107.3741824 s`, so the
printed log time **rolls back to `00:00:00` about every 1 min 47 s**. This is a
display artifact only — the device does **not** reset: the per-core counters
increment straight through the wrap. The on-chip decoder cannot widen the
hardware counter, and the STM timestamp clock is not application-configurable,
so the rollover is unwrapped on the host instead.

`scripts/h20_logmon.py` reads the VCOM (or an existing capture), detects each
rollover, and rewrites the timestamp as a continuous time since start:

```bash
# Live (uv/pipx auto-installs pyserial from the script's inline deps)
uv run scripts/h20_logmon.py --port /dev/ttyACM1 --baud 1000000

# Or re-process a capture file
uv run scripts/h20_logmon.py --infile capture.log
```

With it, the clock climbs past `00:01:47` continuously (verified on hardware:
heartbeat 1450 lands at `00:02:24`, matching 1450 × 100 ms). Rare STM decode
glitches (~0.1 % of lines, documented by Nordic) are passed through unchanged
rather than being mistaken for a rollover.

## Customising

- **Add or remove a core** from the aggregation by toggling the
  `SB_CONFIG_APP_CPURAD_RUN`, `SB_CONFIG_APP_CPUPPR_RUN` or
  `SB_CONFIG_APP_CPUFLPR_RUN` options (for example via `menuconfig` or an
  `-DSB_CONFIG_…=n` build argument).
- **Change what is logged** by editing `src/main.c`; the same source is built
  for every core.
- **Adjust log verbosity** per core through its `boards/*.conf` file.

## References

- nRF Connect SDK: *Configuring logging on the nRF54H20*
- Zephyr: *Multi-domain logging using ARM CoreSight STM*
- nRF Util: *Capturing STM trace data*
