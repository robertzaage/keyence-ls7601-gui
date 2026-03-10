# Technical Documentation

## Table of Contents

1. [Architecture](#1-architecture)
2. [Connection & Serial Settings](#2-connection--serial-settings)
3. [Measurement Tab](#3-measurement-tab)
4. [Live Chart Tab](#4-live-chart-tab)
5. [Settings Tab](#5-settings-tab)
6. [Statistics Tab](#6-statistics-tab)
7. [Program Tab](#7-program-tab)
8. [Console Tab](#8-console-tab)
9. [RS-232C Command Reference](#9-rs-232c-command-reference)
10. [Response Formats](#10-response-formats)
11. [Error Codes](#11-error-codes)
12. [Measurement Value Format](#12-measurement-value-format)
13. [Environment Settings Reference](#13-environment-settings-reference)
14. [Troubleshooting](#14-troubleshooting)
15. [Code Structure](#15-code-structure)

---

## 1. Architecture

The application is a single-file Python script structured into three layers:

```
┌─────────────────────────────────────────────┐
│              LS7601App  (tkinter GUI)        │
│  Tabs: Measurement · Chart · Settings ·     │
│        Statistics · Program · Console       │
├─────────────────────────────────────────────┤
│         LS7601Commands  (command builder)   │
│  Builds command strings, parses responses  │
├─────────────────────────────────────────────┤
│         LS7601Serial  (serial transport)    │
│  pyserial wrapper, thread-safe lock        │
└─────────────────────────────────────────────┘
```

**Threading model:** The GUI runs on the main thread. Polling runs on a background daemon thread that calls `self.after(0, ...)` to push results back to the main thread safely. No blocking calls are made on the GUI thread.

---

## 2. Connection & Serial Settings

### Panel Controls

| Control | Description |
|---------|-------------|
| Port | Serial port (e.g. `COM3`, `/dev/ttyUSB0`). Click ⟳ to refresh list. |
| Baud | 1200 / 2400 / 4800 / **9600** / 19200 / 38400 / 57600 / 115200 |
| Parity | **N** (None) / E (Even) / O (Odd) |
| Stop bits | **1** / 2 |
| Data bits | 7 / **8** |
| D-MODE | **NORMAL** (CR delimiter) / PLC (STX+ETX) |

Bold = device default.

### Required Device Configuration

On the LS-7601 front panel, enter the RS-232C environment settings menu and set:

```
D-SEND  = OFF        ← mandatory for command-response mode
D-MODE  = NORMAL     ← for use with this software
BAUDRATE, PARITY, STOPBIT, D-LENGTH must match the software settings
```

If `D-SEND` is set to `S1` or `S2`, the device pushes measurements automatically and will not respond correctly to commands.

### Cable

Use **OP-35382** (9-pin D-sub) or **OP-25253** (25-pin D-sub). Wiring:

```
LS-7601 pin 2 (TXD)  ──►  PC pin 2 (RXD)
LS-7601 pin 3 (RXD)  ◄──  PC pin 3 (TXD)
LS-7601 pin 4 (GND)  ───  PC pin 5 (GND)
```

All other pins must remain **open** (unconnected).

---

## 3. Measurement Tab

### Value Display

The two large numeric displays show the most recent OUT1 and OUT2 values. The comparator result badge below each value shows the tolerance comparison result:

| Badge | Meaning | Color |
|-------|---------|-------|
| HH | Above upper-upper limit | Red |
| HI | Above upper limit | Orange |
| GO | Within tolerance | Green |
| LO | Below lower limit | Orange |
| LL | Below lower-lower limit | Red |

### Output Selector

| Value | Effect |
|-------|--------|
| Both (0) | Request OUT1 and OUT2 in one response |
| OUT1 (1) | Request OUT1 only |
| OUT2 (2) | Request OUT2 only |

This selector is independent from the sidebar "Quick Controls" channel selector.

### Output Type (r parameter)

| Value | Meaning |
|-------|---------|
| 0 | Measured value only |
| 1 | Measured value + comparator result |
| 2 | Statistically processed data (requires stats sampling to have completed) |

### Polling

Click **▶ Start Polling** to begin continuous measurement at the interval set in the sidebar spinbox. The chart automatically resets at the start of each new polling session. Click **■ Stop Polling** to halt.

Poll interval is set with the **Poll interval (s)** spinbox in the sidebar, minimum 0.1 s.

### Measurement Table

All readings are logged in the table with columns: Time, OUT1, OUT1 Comp, OUT2, OUT2 Comp, Raw. Rows are color-coded by comparator result. The table retains the last 500 entries in the UI (the full session is available for CSV export).

### CSV Export

Click **Export CSV** to save all measurement data from the current session. The output file contains columns: `time, out1, out1_comp, out2, out2_comp, raw`.

---

## 4. Live Chart Tab

Requires `matplotlib`. Install with `pip install matplotlib`.

### Y-Axis Scale

| Control | Description |
|---------|-------------|
| Auto scale (checked) | Y-axis automatically fits the data range |
| Auto scale (unchecked) | Min and Max entry fields become active |
| Min / Max | Fixed Y-axis limits (e.g. `-5.0` / `5.0`) |
| Apply | Applies the manual scale immediately |
| Clear Chart | Clears history and resets chart; also happens automatically on new polling session |

OUT1 is plotted in blue, OUT2 in green. The X-axis shows elapsed time in seconds from the start of the current polling session.

---

## 5. Settings Tab

All settings are sent immediately when the corresponding **Apply** button is clicked. The device acknowledges each command; responses are logged in the Console tab.

### Area Settings

Controls area measurement configuration.

| Field | Command | Description |
|-------|---------|-------------|
| Area number | — | 1 = AREA 1, 2 = AREA 2 |
| Measuring method | `SD,AR,a,c` | 0=DIA, 1=T-EDGE, 2=B-EDGE, 3=SEG |
| Threshold level | `SD,LE,a,gg` | Integer 10–99 |

### Output / Calculation Settings

| Field | Command | Description |
|-------|---------|-------------|
| Output number | — | 1=OUT1, 2=OUT2 |
| Calculation code | `SD,CA,h,ii` | Two-digit code; see device manual Appendix |
| Averaging code | `SD,AV,h,jj` | 00=1, 01=2, 02=4, 03=8 … 12=4096 samples |
| Measuring mode | `SD,ME,h,kk` | Two-digit code; see device manual |
| Offset value | `SD,OF,h,value` | 9-character signed value, e.g. `+00000000` |

### Tolerance — Reference Value Mode

Sets absolute upper/standard/lower tolerance limits.

| Field | Command | Value format |
|-------|---------|-------------|
| Upper (UP) | `SD,UP,h,value` | 9-char signed, e.g. `+00050000` |
| Standard (SD) | `SD,SD,h,value` | 9-char signed |
| Lower (LW) | `SD,LW,h,value` | 9-char signed |

### Tolerance — Threshold Mode

Sets HH/HI/LO/LL threshold limits.

| Field | Command |
|-------|---------|
| HH | `SD,HH,h,value` |
| HI | `SD,HI,h,value` |
| LO | `SD,LO,h,value` |
| LL | `SD,LL,h,value` |

### Confirm Current Setting (SC)

Use the SC command to read back the current value of any setting parameter.

**Examples:**

| Param | Output/Area | Reads |
|-------|-------------|-------|
| `CA` | `1` | Calculation for OUT1 |
| `AV` | `2` | Averaging for OUT2 |
| `UP` | `1` | Upper tolerance for OUT1 |
| `ME` | `1` | Measuring mode for OUT1 |
| `AR` | `1` | Area method for AREA 1 |

The raw response is displayed below the Read button and logged in the Console.

---

## 6. Statistics Tab

Statistical processing must follow this exact sequence:

```
1.  SD,ST,h,setting   Configure: set count (0000002–9999999) or External (0000001)
2.  O h               Start sampling (Stats Sampling ON)
         ... measurements occur ...
3.  R h               Stop sampling (Stats Sampling OFF)
         ... device processes ...
4.  M h,2             Read statistical result
```

Attempting to read (step 4) before completing steps 1–3 will return `ER,99` (timeout / not ready).

### Statistical Result Fields

The parsed result is displayed with labeled fields:

| Field | Description |
|-------|-------------|
| MAX | Maximum measured value |
| MIN | Minimum measured value |
| AVE | Average (mean) |
| PP | Peak-to-peak (MAX – MIN) |
| σ | Standard deviation |
| N | Total number of data items |
| N_HH | Count of HH results |
| N_HI | Count of HI results |
| N_GO | Count of GO results |
| N_LO | Count of LO results |
| N_LL | Count of LL results |

### SD,ST Setting Values

| Value | Meaning |
|-------|---------|
| `0000000` | Statistical processing OFF |
| `0000001` | External synchronization (trigger-based) |
| `0000002`–`9999999` | Internal: process this many data points |

---

## 7. Program Tab

### Program Number Select / Read

Programs 0–9 and A–F (hexadecimal) can be stored in the device.

| Command | Description |
|---------|-------------|
| `PW,v` | Select program number `v` (0–9 or A–F) |
| `PR` | Read currently active program number |

The current program number is displayed next to the **Read Current Program** button after reading.

**Requirement:** `P-SELECT=PANEL` must be set in the device's environment settings for `PW` and `PR` to be accepted.

### Key Lock

Sends `PL,1` (lock on) or `PL,0` (lock off).

**Requirement:** `P-SELECT=PANEL` must be set in the device environment settings. If the device returns `ER,20` (data length error), this feature is not enabled on your device configuration.

### Binary Settings Backup / Restore

Transfers the complete device configuration as binary data.

| Button | Command | Description |
|--------|---------|-------------|
| Read Program (SR) | `SR` | Download all program settings (988 bytes) |
| Read Env (SA) | `SA` | Download all environment settings (88 bytes) |
| Write Program (SW) | `SW,data` | Upload previously saved program settings |
| Write Env (SB) | `SB,data` | Upload previously saved environment settings |

Saved files are raw binary `.bin` files. Keep backups before writing.

**Requirement:** `D-MODE=NORMAL` is required. These commands are not available in PLC mode.

---

## 8. Console Tab

A raw RS-232C terminal. Type any command string (without the trailing CR) and press **Enter** or **Send**.

### Command History

Use **↑** and **↓** arrow keys to navigate previously sent commands.

### Log

All communication (from all tabs) is logged here with millisecond timestamps:

```
[14:23:01.452] >> M0,1
[14:23:01.468] << M0,+01.23450,GO,+02.45600,GO
```

---

## 9. RS-232C Command Reference

All commands use CR (`\r`) as delimiter in NORMAL mode. In PLC mode, STX and ETX characters wrap the command/response.

### Measurement Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| Measured value | `M q,r` | q=output (0=Both/1=OUT1/2=OUT2), r=type (0=value/1=value+comp/2=stats) |
| Measured value re-output | `MR` | Repeat previous measured value output |
| Measured value (timing) | `L q,r` | Same as M but triggers timing; see timing modes |
| Timing ON | `H q` | Turn timing input ON for output q |
| Timing OFF | `U q` | Turn timing input OFF for output q |
| Reset | `Q q` | Turn RESET input ON for output q |
| Auto Zero ON | `V q` | Turn auto zero ON for output q |
| Auto Zero OFF | `W q` | Cancel auto zero for output q |
| Statistics sampling ON | `O q` | Start statistical data sampling for output q |
| Statistics sampling OFF | `R q` | Complete/cancel statistical sampling for output q |

### Program Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| Program select | `PW,v` | Select program number v (0–9, A–F). Requires P-SELECT=PANEL |
| Program read | `PR` | Read current program number. Requires P-SELECT=PANEL |
| Key lock | `PL,w` | w=1 (lock ON) or w=0 (lock OFF). Requires P-SELECT=PANEL |
| Function output | `IS,a` | — |

### Setting Change Commands (SD)

| Sub-command | Syntax | Description |
|-------------|--------|-------------|
| Head | `SD,HE,a,b` | Set head: a=area, b=head number |
| Area | `SD,AR,a,c` | Measuring method: 0=DIA, 1=T-EDGE, 2=B-EDGE, 3=SEG |
| Edge number | `SD,SE,a,dddd e,dddd e` | Edge number/mode (SEG mode only) |
| Area check | `SD,AT,a,fff` | Number of edges |
| Level | `SD,LE,a,gg` | Threshold level 10–99 |
| Calculation | `SD,CA,h,ii` | Calculation coefficient |
| Average | `SD,AV,h,jj` | Averaging code 00–12 |
| RUN mode | `SD,ME,h,kk` | Measuring mode code |
| Self-timing period | `SD,TM,h,llll` | Self-timing period 0000–9999 ms |
| Offset | `SD,OF,h,mmmmmmmm` | Offset value (9-char signed) |
| Analog scaling | `SD,AU,h,nn` | Analog output scaling |
| Analog ref value | `SD,AO,h,mmmmmmmm,mmmmmmmm` | Analog reference values |
| Tolerance UPPER | `SD,UP,h,mmmmmmmm` | Upper tolerance |
| Tolerance STANDARD | `SD,SD,h,mmmmmmmm` | Standard/reference tolerance |
| Tolerance LOWER | `SD,LW,h,mmmmmmmm` | Lower tolerance |
| Tolerance HH | `SD,HH,h,mmmmmmmm` | HH threshold |
| Tolerance HI | `SD,HI,h,mmmmmmmm` | HI threshold |
| Tolerance LO | `SD,LO,h,mmmmmmmm` | LO threshold |
| Tolerance LL | `SD,LL,h,mmmmmmmm` | LL threshold |
| Error ON/OFF (HOLD-H) | `SD,EH,h,mmmmmmmm` | Abnormal value elimination high |
| Error ON/OFF (HOLD-L) | `SD,EL,h,mmmmmmmm` | Abnormal value elimination low |
| Logic calibration | `SD,CL,a,...` | Logic calibration T1-A, T1-B, T2-A, T2-B |
| Error output | `SD,JO,h,ww` | Error output ON/OFF |
| Statistics | `SD,ST,h,ooooooo` | Statistical processing setting |
| Group processing | `SD,GR,ppp` | Group processing |

### Setting Confirmation Commands (SC)

Read back the current value of any SD parameter. Replace `SD` with `SC`, omit the value:

```
SD,CA,1,03  →  set
SC,CA,1     →  read back current value
```

### Whole Settings Transfer

| Command | Description |
|---------|-------------|
| `SR` | Read all program settings (binary, 988 bytes + checksum) |
| `SW,data` | Write all program settings |
| `SA` | Read all environment settings (binary, 88 bytes + checksum) |
| `SB,data` | Write all environment settings |

---

## 10. Response Formats

### Measured Value Response

```
M0,+01.23450,GO,+02.45600,GO
│  │          │   │          └── OUT2 comparator
│  │          │   └── OUT2 measured value
│  │          └── OUT1 comparator
│  └── OUT1 measured value
└── Echo of command
```

Comparator codes: `HH`, `HI`, `GO`, `LO`, `LL`

Comparator fields are present only when `r=1` (Value+Comp) was requested.

### Setting Confirmation Response

```
SC,CA,1,03
│       └── current value
│    └── output/area number
│ └── parameter
└── SC echo
```

### Error Response

```
ER,cmd,nn
│      └── error code
│   └── command that caused the error
└── ER prefix
```

### Program Read Response

```
PR,7
│  └── current program number
└── PR echo
```

---

## 11. Error Codes

| Code | Meaning |
|------|---------|
| 00 | Command error (unrecognised command) |
| 01 | Command error due to operational problem (e.g. timing active) |
| 06 | Delimiter error at time of PLC mode selection |
| 20 | Data length error (wrong number of parameters) |
| 21 | Error in the number of data items |
| 22 | Data value out of range |
| 88 | Timeout error |
| 99 | Other error (device not ready, stats not complete, etc.) |

---

## 12. Measurement Value Format

Measured values are returned as a fixed 9-character string:

```
+01.23450
│ │      └── decimal block (position varies with unit/resolution)
│ └── integer block (total 8 chars fixed)
└── sign (+ or -)
```

Examples:

| Display | Wire format |
|---------|-------------|
| 1.23450 | `+01.23450` |
| –123.450 | `–0123.450` |
| –123.4 | `–00123.40` |

---

## 13. Environment Settings Reference

These settings are configured from the device front panel, not via RS-232C commands (except via binary SA/SB transfer). They must match the software connection settings.

| Item | Options | Notes |
|------|---------|-------|
| BAUDRATE | 1200/2400/4800/**9600**/19200/38400/57600/115200 | Must match software |
| PARITY | **NONE**/EVEN/ODD | Must match software |
| STOPBIT | **1**/2 | Must match software |
| D-LENGTH | 7/**8** | Must match software |
| D-MODE | **NORMAL**/PRINTER 1/PRINTER 2/PLC | Use NORMAL for this software |
| D-SEND | **OFF**/S1/S2 | Must be OFF for command mode |
| P-SELECT | AUTO/**PANEL** | Must be PANEL for PW/PR/PL commands |
| T-MODE | SYNC/ASYNC | Affects timing behaviour |

---

## 14. Troubleshooting

### Device not responding

- Verify `D-SEND=OFF` on the device.
- Confirm the baud rate, parity, and data bits match exactly.
- Check the cable wiring (TXD↔RXD crossover).
- Try lowering the baud rate to 9600.

### `ER,99` on statistics read

Statistics sampling must be completed before reading. Follow the sequence:
1. Configure with `SD,ST,h,setting`
2. Start sampling: `O h`
3. Let the device accumulate measurements
4. Stop sampling: `R h`
5. Wait for the device to finish processing (a few hundred milliseconds)
6. Read result: `M h,2`

### `ER,20` on `PL` (key lock)

Set `P-SELECT=PANEL` in the device environment settings via the front panel menu.

### `ER,20` on `PW` or `PR` (program commands)

Same as above — `P-SELECT=PANEL` required.

### Poll interval won't go below a certain value

The effective minimum is 0.1 s. At very high baud rates and short intervals, the actual rate may be limited by device response time (~17 ms per command per the timing chart). At 9600 baud, approximately 100 ms is a safe minimum.

### Live chart is empty

matplotlib must be installed: `pip install matplotlib`. The chart only updates during active polling.

### Settings tab appears blank

Scroll down — the settings panel is scrollable. Use the mouse wheel or the scrollbar on the right edge.

---

## 15. Code Structure

```
keyence-ls7601-gui.py
│
├── LS7601Serial                 Serial transport layer
│   ├── connect()                Open serial port
│   ├── disconnect()             Close serial port
│   └── send_command()           Thread-safe send + readline
│
├── LS7601Commands               Command builder and response parser
│   ├── measured_value()         Build M command
│   ├── timing_on/off()          Build H/U commands
│   ├── set_*()                  Build SD,* setting commands
│   ├── sc()                     Build SC,* confirmation commands
│   ├── parse_measured_value_response()   Parse M/L response
│   ├── parse_program_response()          Parse PR response
│   └── to_float()               Convert measurement string to float
│
└── LS7601App  (tk.Tk)           Main GUI application
    ├── _build_styles()          TTK style definitions (dark theme)
    ├── _build_ui()              Top-level layout
    ├── _build_connection_panel()
    ├── _build_quick_controls()
    ├── _build_tab_measurement()
    ├── _build_tab_live_chart()
    ├── _build_tab_settings()
    ├── _build_tab_statistics()
    ├── _build_tab_program()
    ├── _build_tab_console()
    ├── _poll_loop()             Background polling thread
    ├── _process_measurement()   Update UI with new reading
    └── _log()                   Append to console log
```

### Adding a New Command

1. Add a static method to `LS7601Commands` that returns the command string.
2. Add a handler method to `LS7601App` that calls `self.serial.send_command(cmd)`.
3. Call `self._log(f">> {cmd}  << {resp}")` for automatic console logging.

### Extending the Settings Tab

Each settings group is built with three helpers:

- `_lf(parent, title)` — creates a styled LabelFrame
- `_srow(lf, row, label, varname, default, choices)` — adds a label + entry/combobox row, stores the `tk.StringVar` as `self.<varname>`
- `_sbtn(lf, row, label, callback)` — adds a full-width Apply button

---

*This documentation covers software version consistent with the ls7601_controller.py file in this repository. For hardware-specific details, consult the official Keyence LS-7600 Series Instruction Manual, Chapter 8 (RS-232C).*
