# Keyence LS-7601 GUI

> Python GUI for RS-232C control, live measurement, and configuration of the Keyence LS-7600 Series laser micrometer.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Interface](https://img.shields.io/badge/Interface-RS--232C-orange)

---

## Overview
This project is a full-featured desktop application for communicating with the **Keyence LS-7600 Series** laser micrometer (LS-7601, LS-7602, etc.) over an RS-232C serial connection.

It covers the entire RS-232C command set documented in **Chapter 8** of the LS-7600 Series manual - from live measurement polling and real-time charting through tolerance configuration, statistical processing, and binary program backup/restore.

---

## Features

| Category | Capabilities |
|----------|-------------|
| **Connection** | Auto port detection, configurable baud/parity/stop/data bits, NORMAL and PLC D-MODE |
| **Measurement** | Single read, continuous polling, OUT1/OUT2 simultaneous, comparator result display (HH/HI/GO/LO/LL) |
| **Live Chart** | Real-time strip chart with auto or manual Y-axis scaling, chart reset on new poll session |
| **Settings** | Area method, threshold level, calculation, averaging, measuring mode, offset, all tolerance modes |
| **Statistics** | Configure SD,ST, start/stop sampling, read and parse statistical result output |
| **Program** | Program number select/read, key lock, binary settings backup and restore (SR/SA/SW/SB) |
| **Console** | Raw RS-232C terminal with command history (↑/↓), full timestamped communication log |
| **Data Export** | CSV export of all measurement sessions |

---

## Screenshots

TODO

---

## Requirements

- Python **3.10** or newer
- A physical RS-232C port or USB-to-RS232 adapter
- LS-7600 Series device with RS-232C enabled (`D-SEND=OFF` for command mode)

### Python dependencies

```
pyserial>=3.5
matplotlib>=3.7   # optional – required for Live Chart tab
```

Install with:

```bash
pip install pyserial matplotlib
```

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourname/keyence-ls7601-gui.git
cd ls7601-controller

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python keyence-ls7601-gui.py
```

No build step required. The application uses Python's built-in `tkinter` for the GUI.

---

## Quick Start

1. Connect the LS-7601 to your PC with a **OP-35382** cable (9-pin D-sub) or **OP-25253** (25-pin).
2. On the device, set `D-SEND=OFF` so the device responds to commands rather than pushing data automatically.
3. Launch the application and select the correct **COM port** in the sidebar.
4. Set **Baud Rate** to match the device setting (default `9600`).
5. Click **Connect**.
6. Switch to the **Measurement** tab and click **Single Read** or **▶ Start Polling**.

---

## Device Cable Wiring

| LS-7601 Pin | Signal | PC (9-pin D-sub) |
|-------------|--------|------------------|
| 2 | SD (TXD) | Pin 2 (RXD) |
| 3 | RD (RXD) | Pin 3 (TXD) |
| 4 | SG (GND) | Pin 5 (GND) |

All other pins must be left **open**.

---

## Supported Commands

The application implements the full Chapter 8 command set:

`M` `MR` `L` `H` `U` `Q` `V` `W` `O` `R` `PR` `PW` `PL` `SD` `SC` `SR` `SA` `SW` `SB`

See [DOCS.md](DOCS.md) for full command reference and protocol details.

---

## Known Limitations

- **Key lock (`PL`)** requires `P-SELECT=PANEL` in the device environment settings. If the device returns `ER,20`, enable this setting from the front panel menu.
- **Statistics result (`M q,2`)** requires statistical sampling to have been started (`O q`), completed (`R q`), and fully processed before reading. `ER,99` means the device is not ready yet.
- **Binary backup/restore (SR/SA/SW/SB)** requires `D-MODE=NORMAL`. These commands transfer raw binary data; the application saves and loads them as binary files.
- **PLC mode** (STX+ETX framing) is selectable in the connection settings but full framing support for PLC-linked KV-series is not yet implemented.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

---

## Disclaimer

This software is an independent project and is **not affiliated with, endorsed by, or supported by Keyence Corporation**. Use at your own risk. Always verify critical measurement settings directly on the device.
