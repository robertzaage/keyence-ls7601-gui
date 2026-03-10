#!/usr/bin/env python3
"""
LS-7601 Series Laser Micrometer - RS-232C Control Software
Full-featured GUI for measurement, settings, and monitoring.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import queue
import csv
import json
import os
from datetime import datetime
from collections import deque

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
CARD_BG   = "#313244"
ENTRY_BG  = "#45475a"
FG        = "#cdd6f4"
FG_DIM    = "#a6adc8"
ACCENT    = "#89b4fa"
GREEN     = "#a6e3a1"
RED       = "#f38ba8"
ORANGE    = "#fab387"
BORDER    = "#585b70"
HEADER_BG = "#181825"

# ─────────────────────────────────────────────────────────────────────────────
# Serial Communication Layer
# ─────────────────────────────────────────────────────────────────────────────

class LS7601Serial:
    def __init__(self):
        self.ser = None
        self.lock = threading.Lock()
        self.delimiter = "\r"
        self.timeout = 2.0

    def connect(self, port, baudrate=9600, parity="N", stopbits=1,
                bytesize=8, plc_mode=False):
        # PLC mode uses STX/ETX framing, but the serial delimiter is still CR
        self.delimiter = "\r"
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            parity={"N": serial.PARITY_NONE,
                    "E": serial.PARITY_EVEN,
                    "O": serial.PARITY_ODD}[parity],
            stopbits={1: serial.STOPBITS_ONE,
                      2: serial.STOPBITS_TWO}[stopbits],
            bytesize=bytesize,
            timeout=self.timeout,
        )
        return self.ser.is_open

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    @property
    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def send_command(self, cmd: str) -> str:
        if not self.is_connected:
            raise ConnectionError("Not connected to device.")
        with self.lock:
            full_cmd = (cmd + self.delimiter).encode("ascii")
            self.ser.reset_input_buffer()
            self.ser.write(full_cmd)
            raw = self.ser.readline()
            return raw.decode("ascii", errors="replace").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Command Builder / Parser
# ─────────────────────────────────────────────────────────────────────────────

class LS7601Commands:

    # ── Measurement ──────────────────────────────────────────────────────────
    @staticmethod
    def measured_value(output_num: int, output_type: int) -> str:
        return f"M{output_num},{output_type}"

    @staticmethod
    def re_output() -> str:
        return "MR"

    @staticmethod
    def timing_on(output_num: int) -> str:
        return f"H{output_num}"

    @staticmethod
    def timing_off(output_num: int) -> str:
        return f"U{output_num}"

    @staticmethod
    def reset(output_num: int) -> str:
        return f"Q{output_num}"

    @staticmethod
    def auto_zero_on(output_num: int) -> str:
        return f"V{output_num}"

    @staticmethod
    def auto_zero_off(output_num: int) -> str:
        return f"W{output_num}"

    @staticmethod
    def statistics_on(output_num: int) -> str:
        return f"O{output_num}"

    @staticmethod
    def statistics_off(output_num: int) -> str:
        return f"R{output_num}"

    # ── Program / KeyLock ─────────────────────────────────────────────────────
    @staticmethod
    def program_select(prog_num: str) -> str:
        # PW,v  – v is program number 0-9 or A-F
        return f"PW,{prog_num}"

    @staticmethod
    def program_read() -> str:
        return "PR"

    @staticmethod
    def key_lock(on: bool) -> str:
        # PL,w  – w: 0=OFF, 1=ON  (single digit, not two-digit!)
        return f"PL,{'1' if on else '0'}"

    # ── Setting Change (SD) ───────────────────────────────────────────────────
    @staticmethod
    def set_area(area_num: int, method: int) -> str:
        return f"SD,AR,{area_num},{method}"

    @staticmethod
    def set_level(area_num: int, level: int) -> str:
        return f"SD,LE,{area_num},{level:02d}"

    @staticmethod
    def set_calculation(output_num: int, calc_code: int) -> str:
        return f"SD,CA,{output_num},{calc_code:02d}"

    @staticmethod
    def set_average(output_num: int, avg_code: int) -> str:
        return f"SD,AV,{output_num},{avg_code:02d}"

    @staticmethod
    def set_measuring_mode(output_num: int, mode_code: int) -> str:
        return f"SD,ME,{output_num},{mode_code:02d}"

    @staticmethod
    def set_offset(output_num: int, value: str) -> str:
        return f"SD,OF,{output_num},{value}"

    @staticmethod
    def set_tolerance_upper(output_num: int, value: str) -> str:
        return f"SD,UP,{output_num},{value}"

    @staticmethod
    def set_tolerance_standard(output_num: int, value: str) -> str:
        return f"SD,SD,{output_num},{value}"

    @staticmethod
    def set_tolerance_lower(output_num: int, value: str) -> str:
        return f"SD,LW,{output_num},{value}"

    @staticmethod
    def set_tolerance_hh(output_num: int, value: str) -> str:
        return f"SD,HH,{output_num},{value}"

    @staticmethod
    def set_tolerance_hi(output_num: int, value: str) -> str:
        return f"SD,HI,{output_num},{value}"

    @staticmethod
    def set_tolerance_lo(output_num: int, value: str) -> str:
        return f"SD,LO,{output_num},{value}"

    @staticmethod
    def set_tolerance_ll(output_num: int, value: str) -> str:
        return f"SD,LL,{output_num},{value}"

    @staticmethod
    def set_statistics(output_num: int, setting: str) -> str:
        return f"SD,ST,{output_num},{setting}"

    # ── Setting Confirmation (SC) ──────────────────────────────────────────────
    @staticmethod
    def sc(param: str, output_or_area) -> str:
        return f"SC,{param},{output_or_area}"

    # ── Response Parsing ──────────────────────────────────────────────────────
    @staticmethod
    def parse_measured_value_response(response: str):
        result = {"raw": response, "out1": None, "out1_comp": None,
                  "out2": None, "out2_comp": None, "error": None}
        if not response:
            result["error"] = "No response"
            return result
        if "ER," in response:
            result["error"] = response
            return result
        parts = response.split(",")
        values = parts[1:]  # skip echo header like "M0"
        comp_codes = {"HH", "HI", "GO", "LO", "LL"}
        readings, comparators = [], []
        for p in values:
            p = p.strip()
            if p in comp_codes:
                comparators.append(p)
            elif p:
                readings.append(p)
        if readings:
            result["out1"] = readings[0]
        if len(readings) > 1:
            result["out2"] = readings[1]
        if comparators:
            result["out1_comp"] = comparators[0]
        if len(comparators) > 1:
            result["out2_comp"] = comparators[1]
        return result

    @staticmethod
    def parse_program_response(response: str) -> str:
        """PR,v  →  returns v"""
        parts = response.split(",")
        if len(parts) >= 2:
            return parts[1].strip()
        return response

    @staticmethod
    def to_float(value_str) -> float | None:
        try:
            return float(value_str)
        except (ValueError, TypeError):
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────

class LS7601App(tk.Tk):
    COMP_COLORS = {
        "HH": RED,
        "HI": ORANGE,
        "GO": GREEN,
        "LO": ORANGE,
        "LL": RED,
        None: BORDER,
    }

    def __init__(self):
        super().__init__()
        self.title("LS-7601 Series Control Software")
        self.geometry("1150x800")
        self.configure(bg=BG)
        self.resizable(True, True)

        self.serial    = LS7601Serial()
        self.commands  = LS7601Commands()
        self.polling_active = False
        self.poll_thread    = None

        self.data_log      = []
        self.out1_history  = deque(maxlen=300)
        self.out2_history  = deque(maxlen=300)
        self.time_history  = deque(maxlen=300)
        self.t0 = None

        self._build_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────────────────────
    # Styles
    # ─────────────────────────────────────────────────────────────────────────

    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".",              background=BG,      foreground=FG,
                                      font=("Segoe UI", 9))
        s.configure("TFrame",         background=BG)
        s.configure("Card.TFrame",    background=CARD_BG)
        s.configure("TLabel",         background=BG,      foreground=FG)
        s.configure("Card.TLabel",    background=CARD_BG, foreground=FG)
        s.configure("Dim.TLabel",     background=BG,      foreground=FG_DIM)
        s.configure("CardDim.TLabel", background=CARD_BG, foreground=FG_DIM)

        s.configure("TButton",
                    background=ACCENT, foreground=BG,
                    font=("Segoe UI", 9, "bold"),
                    relief="flat", borderwidth=0, focusthickness=0)
        s.map("TButton",
              background=[("active", "#b4befe"), ("disabled", BORDER)],
              foreground=[("disabled", FG_DIM)])
        s.configure("Red.TButton",   background=RED,    foreground=BG)
        s.map("Red.TButton",   background=[("active", "#eba0ac")])
        s.configure("Green.TButton", background=GREEN,  foreground=BG)
        s.map("Green.TButton", background=[("active", "#b9f0b5")])
        s.configure("Orange.TButton",background=ORANGE, foreground=BG)
        s.map("Orange.TButton",background=[("active", "#fdd8c2")])

        s.configure("TEntry",
                    fieldbackground=ENTRY_BG, foreground=FG,
                    insertcolor=FG, borderwidth=1,
                    selectbackground=ACCENT, selectforeground=BG)
        s.configure("TSpinbox",
                    fieldbackground=ENTRY_BG, foreground=FG,
                    insertcolor=FG, selectbackground=ACCENT,
                    selectforeground=BG, arrowcolor=FG,
                    background=ENTRY_BG, borderwidth=1)
        s.configure("TCombobox",
                    fieldbackground=ENTRY_BG, foreground=FG,
                    selectbackground=ACCENT, selectforeground=BG,
                    arrowcolor=FG)
        s.map("TCombobox",
              fieldbackground=[("readonly", ENTRY_BG)],
              foreground=[("readonly", FG)])

        s.configure("TNotebook",      background=BG, borderwidth=0)
        s.configure("TNotebook.Tab",  background=CARD_BG, foreground=FG,
                                      padding=[14, 5])
        s.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", BG)])

        s.configure("TLabelframe",       background=CARD_BG,
                                          bordercolor=BORDER)
        s.configure("TLabelframe.Label", background=CARD_BG,
                                          foreground=ACCENT,
                                          font=("Segoe UI", 9, "bold"))

        # Radio / Check on card backgrounds
        s.configure("Card.TRadiobutton",
                    background=CARD_BG, foreground=FG,
                    focuscolor=CARD_BG, indicatorcolor=ACCENT)
        s.map("Card.TRadiobutton",
              background=[("active", CARD_BG)],
              indicatorcolor=[("selected", ACCENT)])
        s.configure("Card.TCheckbutton",
                    background=CARD_BG, foreground=FG,
                    focuscolor=CARD_BG)
        s.map("Card.TCheckbutton",
              background=[("active", CARD_BG)])

        s.configure("Horizontal.TScale",
                    background=CARD_BG, troughcolor=ENTRY_BG,
                    sliderrelief="flat")
        s.configure("TScrollbar",
                    background=CARD_BG, troughcolor=BG,
                    bordercolor=BG, arrowcolor=FG_DIM,
                    relief="flat")
        s.configure("TSeparator", background=BORDER)

        # ── Treeview – fully dark ──────────────────────────────────────────
        s.configure("Treeview",
                    background=CARD_BG, foreground=FG,
                    fieldbackground=CARD_BG,
                    borderwidth=0, relief="flat",
                    rowheight=22)
        s.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", BG)])
        s.configure("Treeview.Heading",
                    background=HEADER_BG, foreground=ACCENT,
                    relief="flat", font=("Segoe UI", 9, "bold"))
        s.map("Treeview.Heading",
              background=[("active", BORDER)])

    # ─────────────────────────────────────────────────────────────────────────
    # Top-level layout
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header bar ──────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=HEADER_BG, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  LS-7601  Laser Micrometer Controller",
                 bg=HEADER_BG, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=12)
        self.conn_badge = tk.Label(hdr, text="● DISCONNECTED",
                                   bg=HEADER_BG, fg=RED,
                                   font=("Segoe UI", 9, "bold"))
        self.conn_badge.pack(side="right", padx=16)

        # ── Main body ────────────────────────────────────────────────────────
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        sidebar = ttk.Frame(body, style="Card.TFrame", width=215)
        sidebar.pack(side="left", fill="y", padx=(0, 5))
        sidebar.pack_propagate(False)
        self._build_connection_panel(sidebar)
        self._build_quick_controls(sidebar)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)

        self._build_tab_measurement()
        self._build_tab_live_chart()
        self._build_tab_settings()
        self._build_tab_statistics()
        self._build_tab_program()
        self._build_tab_console()

    # ─────────────────────────────────────────────────────────────────────────
    # Connection Panel
    # ─────────────────────────────────────────────────────────────────────────

    def _build_connection_panel(self, parent):
        lf = ttk.LabelFrame(parent, text="Connection", padding=8)
        lf.pack(fill="x", padx=6, pady=(8, 4))
        lf.columnconfigure(1, weight=1)

        def row(r, lbl, widget_fn):
            tk.Label(lf, text=lbl, bg=CARD_BG, fg=FG_DIM,
                     font=("Segoe UI", 8)).grid(row=r, column=0, sticky="w",
                                                pady=2, padx=(0, 4))
            w = widget_fn(lf)
            w.grid(row=r, column=1, columnspan=2, sticky="ew", pady=2)
            return w

        self.port_var = tk.StringVar()
        port_frame = tk.Frame(lf, bg=CARD_BG)
        port_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=2)
        port_frame.columnconfigure(0, weight=1)
        tk.Label(port_frame, text="Port", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(port_frame, textvariable=self.port_var, width=11)
        self.port_cb.grid(row=1, column=0, sticky="ew")
        ttk.Button(port_frame, text="⟳", width=3,
                   command=self._refresh_ports).grid(row=1, column=1, padx=(3, 0))

        def mkrow(lf, r, text, var, values, default):
            tk.Label(lf, text=text, bg=CARD_BG, fg=FG_DIM,
                     font=("Segoe UI", 8)).grid(row=r, column=0, sticky="w",
                                                pady=2, padx=(0, 4))
            v = tk.StringVar(value=default)
            cb = ttk.Combobox(lf, textvariable=v, values=values,
                              state="readonly", width=13)
            cb.grid(row=r, column=1, columnspan=2, sticky="ew", pady=2)
            return v

        self.baud_var   = mkrow(lf, 1, "Baud", None,
                                ["1200","2400","4800","9600",
                                 "19200","38400","57600","115200"], "9600")
        self.parity_var = mkrow(lf, 2, "Parity", None, ["N","E","O"], "N")
        self.stop_var   = mkrow(lf, 3, "Stop bits", None, ["1","2"], "1")
        self.data_var   = mkrow(lf, 4, "Data bits", None, ["7","8"], "8")
        self.dmode_var  = mkrow(lf, 5, "D-MODE", None, ["NORMAL","PLC"], "NORMAL")

        self.connect_btn = ttk.Button(lf, text="Connect",
                                      command=self._toggle_connect)
        self.connect_btn.grid(row=6, column=0, columnspan=3,
                              sticky="ew", pady=(8, 2))
        self._refresh_ports()

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        if ports:
            self.port_var.set(ports[0])

    def _toggle_connect(self):
        if self.serial.is_connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        try:
            self.serial.connect(
                port=self.port_var.get(),
                baudrate=int(self.baud_var.get()),
                parity=self.parity_var.get(),
                stopbits=int(self.stop_var.get()),
                bytesize=int(self.data_var.get()),
                plc_mode=(self.dmode_var.get() == "PLC"),
            )
            self.connect_btn.configure(text="Disconnect", style="Red.TButton")
            self.conn_badge.configure(text="● CONNECTED", fg=GREEN)
            self._log(f"Connected to {self.port_var.get()} "
                      f"@ {self.baud_var.get()} baud")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def _do_disconnect(self):
        self.polling_active = False
        self.serial.disconnect()
        self.connect_btn.configure(text="Connect", style="TButton")
        self.conn_badge.configure(text="● DISCONNECTED", fg=RED)
        self._log("Disconnected.")

    # ─────────────────────────────────────────────────────────────────────────
    # Quick Controls (sidebar)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_quick_controls(self, parent):
        lf = ttk.LabelFrame(parent, text="Quick Controls", padding=8)
        lf.pack(fill="x", padx=6, pady=4)

        # Output selector – single shared variable used by all quick cmds
        self.quick_out = tk.StringVar(value="0")
        sel_row = tk.Frame(lf, bg=CARD_BG)
        sel_row.pack(fill="x", pady=(0, 6))
        tk.Label(sel_row, text="Chan:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        for v, t in [("0", "Both"), ("1", "1"), ("2", "2")]:
            ttk.Radiobutton(sel_row, text=t, variable=self.quick_out, value=v,
                            style="Card.TRadiobutton").pack(side="left", padx=2)

        def qbtn(lbl, fn, style="TButton"):
            ttk.Button(lf, text=lbl, style=style,
                       command=fn).pack(fill="x", pady=2)

        def _q(fn): return lambda: self._send_quick(fn(int(self.quick_out.get())))

        qbtn("Timing ON",     _q(self.commands.timing_on))
        qbtn("Timing OFF",    _q(self.commands.timing_off))
        qbtn("Reset",         _q(self.commands.reset),         "Red.TButton")
        qbtn("Auto Zero ON",  _q(self.commands.auto_zero_on),  "Green.TButton")
        qbtn("Auto Zero OFF", _q(self.commands.auto_zero_off))
        qbtn("Stats Sampling ON",  _q(self.commands.statistics_on),  "Green.TButton")
        qbtn("Stats Sampling OFF", _q(self.commands.statistics_off))
        qbtn("Re-output",     lambda: self._send_quick(self.commands.re_output()))

        # Poll interval with a proper spinbox (supports fractional values)
        ttk.Separator(lf, orient="horizontal").pack(fill="x", pady=6)
        tk.Label(lf, text="Poll interval (s)", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w")
        self.poll_interval_var = tk.StringVar(value="0.50")
        sp = ttk.Spinbox(lf, from_=0.1, to=60.0, increment=0.1,
                         textvariable=self.poll_interval_var,
                         format="%.2f", width=8)
        sp.pack(fill="x", pady=(2, 0))

    def _get_poll_interval(self) -> float:
        try:
            v = float(self.poll_interval_var.get())
            return max(0.1, v)
        except ValueError:
            return 0.5

    def _send_quick(self, cmd):
        if not self.serial.is_connected:
            messagebox.showwarning("Not Connected", "Please connect first.")
            return
        try:
            resp = self.serial.send_command(cmd)
            self._log(f">> {cmd}  << {resp}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Measurement
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_measurement(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Measurement  ")
        tab.configure(style="TFrame")

        # ── Big value display ─────────────────────────────────────────────
        disp_outer = tk.Frame(tab, bg=CARD_BG)
        disp_outer.pack(fill="x", padx=6, pady=6)
        disp_outer.columnconfigure((0, 1), weight=1)

        for col, title, attr_val, attr_comp in [
            (0, "OUT 1", "out1_label", "out1_comp_label"),
            (1, "OUT 2", "out2_label", "out2_comp_label"),
        ]:
            card = tk.Frame(disp_outer, bg=CARD_BG)
            card.grid(row=0, column=col, padx=6, pady=6, sticky="ew")
            tk.Label(card, text=title, bg=CARD_BG, fg=ACCENT,
                     font=("Segoe UI", 10, "bold")).pack(pady=(4, 0))
            val_lbl = tk.Label(card, text="─────────", bg=CARD_BG, fg=FG,
                               font=("Courier New", 26, "bold"))
            val_lbl.pack()
            comp_lbl = tk.Label(card, text="", bg=CARD_BG, fg=BORDER,
                                font=("Segoe UI", 11, "bold"))
            comp_lbl.pack(pady=(0, 6))
            setattr(self, attr_val, val_lbl)
            setattr(self, attr_comp, comp_lbl)

        # ── Controls row ──────────────────────────────────────────────────
        ctrl = tk.Frame(tab, bg=CARD_BG)
        ctrl.pack(fill="x", padx=6, pady=(0, 4))

        tk.Label(ctrl, text="  Output:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        self.meas_out = tk.StringVar(value="0")
        for v, t in [("0","Both"), ("1","OUT1"), ("2","OUT2")]:
            ttk.Radiobutton(ctrl, text=t, variable=self.meas_out, value=v,
                            style="Card.TRadiobutton").pack(side="left", padx=3)

        tk.Label(ctrl, text="   Type:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        self.meas_type = tk.StringVar(value="1")
        for v, t in [("0","Value"), ("1","Value+Comp"), ("2","Stats result")]:
            ttk.Radiobutton(ctrl, text=t, variable=self.meas_type, value=v,
                            style="Card.TRadiobutton").pack(side="left", padx=3)

        tk.Frame(ctrl, bg=BORDER, width=1).pack(side="left",
                                                fill="y", padx=10, pady=4)

        ttk.Button(ctrl, text="Single Read",
                   command=self._single_read).pack(side="left", padx=4, pady=4)

        self.poll_btn = ttk.Button(ctrl, text="▶ Start Polling",
                                   command=self._toggle_polling,
                                   style="Green.TButton")
        self.poll_btn.pack(side="left", padx=4, pady=4)

        ttk.Button(ctrl, text="Export CSV",
                   command=self._export_csv).pack(side="right", padx=8, pady=4)

        # ── Data log table ────────────────────────────────────────────────
        tbl_frame = tk.Frame(tab, bg=BG)
        tbl_frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        cols = ("Time", "OUT1", "OUT1 Comp", "OUT2", "OUT2 Comp", "Raw")
        self.meas_tree = ttk.Treeview(tbl_frame, columns=cols,
                                      show="headings", height=12)
        widths = {"Time": 95, "OUT1": 100, "OUT1 Comp": 80,
                  "OUT2": 100, "OUT2 Comp": 80, "Raw": 260}
        for c in cols:
            self.meas_tree.heading(c, text=c)
            self.meas_tree.column(c, width=widths[c], anchor="center",
                                  minwidth=60)
        # Tag colours for comparator rows
        self.meas_tree.tag_configure("HH", foreground=RED)
        self.meas_tree.tag_configure("LL", foreground=RED)
        self.meas_tree.tag_configure("HI", foreground=ORANGE)
        self.meas_tree.tag_configure("LO", foreground=ORANGE)
        self.meas_tree.tag_configure("GO", foreground=GREEN)
        self.meas_tree.tag_configure("err", foreground=RED)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical",
                            command=self.meas_tree.yview)
        self.meas_tree.configure(yscrollcommand=vsb.set)
        self.meas_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(tab, textvariable=self.status_var,
                 bg=HEADER_BG, fg=FG_DIM,
                 font=("Segoe UI", 8), anchor="w").pack(
            fill="x", padx=0, pady=0)

    def _single_read(self):
        if not self._check_conn():
            return
        try:
            cmd = self.commands.measured_value(
                int(self.meas_out.get()), int(self.meas_type.get()))
            resp = self.serial.send_command(cmd)
            self._process_measurement(resp, cmd)
        except Exception as e:
            self._log(f"ERROR: {e}")
            self.status_var.set(f"Error: {e}")

    def _toggle_polling(self):
        if self.polling_active:
            self.polling_active = False
            self.poll_btn.configure(text="▶ Start Polling",
                                    style="Green.TButton")
        else:
            if not self._check_conn():
                return
            # Reset chart on every new polling session
            self._clear_chart()
            self.t0 = time.time()
            self.polling_active = True
            self.poll_btn.configure(text="■ Stop Polling",
                                    style="Red.TButton")
            self.poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True)
            self.poll_thread.start()

    def _poll_loop(self):
        while self.polling_active:
            try:
                cmd = self.commands.measured_value(
                    int(self.meas_out.get()), int(self.meas_type.get()))
                resp = self.serial.send_command(cmd)
                self.after(0, self._process_measurement, resp, cmd)
            except Exception as e:
                self.after(0, self._log, f"Poll error: {e}")
                self.polling_active = False
                self.after(0, self.poll_btn.configure,
                           {"text": "▶ Start Polling", "style": "Green.TButton"})
                break
            time.sleep(self._get_poll_interval())

    def _process_measurement(self, response: str, cmd: str):
        parsed = self.commands.parse_measured_value_response(response)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        t_elapsed = time.time() - (self.t0 or time.time())

        # Big displays
        for attr_val, attr_comp, key, comp_key in [
            ("out1_label", "out1_comp_label", "out1", "out1_comp"),
            ("out2_label", "out2_comp_label", "out2", "out2_comp"),
        ]:
            val  = parsed.get(key)
            comp = parsed.get(comp_key)
            getattr(self, attr_val).configure(
                text=val if val else "─────────",
                fg=FG if val else BORDER)
            getattr(self, attr_comp).configure(
                text=comp or ("ERR" if parsed.get("error") else ""),
                fg=self.COMP_COLORS.get(comp, RED if parsed.get("error") else BORDER))

        # Chart history
        v1 = self.commands.to_float(parsed.get("out1"))
        v2 = self.commands.to_float(parsed.get("out2"))
        if v1 is not None:
            self.out1_history.append(v1)
            self.time_history.append(t_elapsed)
        if v2 is not None:
            self.out2_history.append(v2)
        if MATPLOTLIB_AVAILABLE:
            self._update_chart()

        # Table row with colour tag
        comp = parsed.get("out1_comp") or parsed.get("out2_comp")
        tag  = comp if comp else ("err" if parsed.get("error") else "")
        row  = (ts,
                parsed.get("out1", ""),
                parsed.get("out1_comp", ""),
                parsed.get("out2", ""),
                parsed.get("out2_comp", ""),
                response[:80])
        self.meas_tree.insert("", 0, values=row,
                              tags=(tag,) if tag else ())
        children = self.meas_tree.get_children()
        if len(children) > 500:
            self.meas_tree.delete(children[-1])

        self.data_log.append({
            "time": ts, "out1": parsed.get("out1",""),
            "out1_comp": parsed.get("out1_comp",""),
            "out2": parsed.get("out2",""),
            "out2_comp": parsed.get("out2_comp",""),
            "raw": response,
        })
        self.status_var.set(
            f"Last: {ts}  OUT1={parsed.get('out1','–')}  "
            f"OUT2={parsed.get('out2','–')}"
            + (f"  [{parsed['error']}]" if parsed.get("error") else ""))
        self._log(f">> {cmd}  << {response}")

    def _export_csv(self):
        if not self.data_log:
            messagebox.showinfo("No Data", "No measurement data to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=f"ls7601_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["time","out1","out1_comp","out2","out2_comp","raw"])
            writer.writeheader()
            writer.writerows(self.data_log)
        messagebox.showinfo("Exported", f"Saved to:\n{path}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Live Chart
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_live_chart(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Live Chart  ")

        if not MATPLOTLIB_AVAILABLE:
            tk.Label(tab, text="matplotlib not installed.\npip install matplotlib",
                     bg=BG, fg=FG_DIM, font=("Segoe UI", 11)).pack(expand=True)
            self.chart_canvas = None
            return

        # ── Scale controls ────────────────────────────────────────────────
        sc_row = tk.Frame(tab, bg=CARD_BG)
        sc_row.pack(fill="x", padx=6, pady=(6, 2))

        tk.Label(sc_row, text="Y-axis:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4))

        self.chart_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sc_row, text="Auto scale",
                        variable=self.chart_auto_var,
                        style="Card.TCheckbutton",
                        command=self._on_autoscale_toggle).pack(side="left")

        tk.Label(sc_row, text="  Min:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self.chart_ymin_var = tk.StringVar(value="0.0")
        self.chart_ymin_entry = ttk.Entry(sc_row, textvariable=self.chart_ymin_var,
                                          width=8, state="disabled")
        self.chart_ymin_entry.pack(side="left")

        tk.Label(sc_row, text="  Max:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        self.chart_ymax_var = tk.StringVar(value="10.0")
        self.chart_ymax_entry = ttk.Entry(sc_row, textvariable=self.chart_ymax_var,
                                          width=8, state="disabled")
        self.chart_ymax_entry.pack(side="left")

        ttk.Button(sc_row, text="Apply",
                   command=self._apply_chart_scale).pack(side="left", padx=6)
        ttk.Button(sc_row, text="Clear Chart",
                   command=self._clear_chart).pack(side="right", padx=8)

        # ── Figure ────────────────────────────────────────────────────────
        fig = Figure(figsize=(8, 4.2), dpi=96, facecolor=BG)
        self.ax = fig.add_subplot(111)
        self._style_axes(self.ax)
        self.line1, = self.ax.plot([], [], color=ACCENT, lw=1.5, label="OUT1")
        self.line2, = self.ax.plot([], [], color=GREEN,  lw=1.5, label="OUT2")
        leg = self.ax.legend(facecolor=CARD_BG, labelcolor=FG,
                             edgecolor=BORDER)

        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.chart_canvas = canvas
        self.chart_fig    = fig

    def _style_axes(self, ax):
        ax.set_facecolor(CARD_BG)
        ax.tick_params(colors=FG_DIM, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.set_xlabel("Time (s)", color=FG_DIM, fontsize=9)
        ax.set_ylabel("Value",    color=FG_DIM, fontsize=9)
        ax.set_title("Live Measurement", color=ACCENT, fontsize=10)
        ax.grid(True, color=BORDER, alpha=0.4, linewidth=0.5)

    def _on_autoscale_toggle(self):
        state = "disabled" if self.chart_auto_var.get() else "normal"
        self.chart_ymin_entry.configure(state=state)
        self.chart_ymax_entry.configure(state=state)

    def _apply_chart_scale(self):
        if not MATPLOTLIB_AVAILABLE or self.chart_canvas is None:
            return
        if not self.chart_auto_var.get():
            try:
                ymin = float(self.chart_ymin_var.get())
                ymax = float(self.chart_ymax_var.get())
                self.ax.set_ylim(ymin, ymax)
                self.chart_canvas.draw_idle()
            except ValueError:
                messagebox.showerror("Invalid", "Y-axis min/max must be numbers.")

    def _update_chart(self):
        if not MATPLOTLIB_AVAILABLE or self.chart_canvas is None:
            return
        t  = list(self.time_history)
        v1 = list(self.out1_history)
        v2 = list(self.out2_history)
        if t and v1:
            self.line1.set_data(t[:len(v1)], v1)
        if t and v2:
            self.line2.set_data(t[:len(v2)], v2)
        if self.chart_auto_var.get():
            self.ax.relim()
            self.ax.autoscale_view()
        self.chart_canvas.draw_idle()

    def _clear_chart(self):
        self.out1_history.clear()
        self.out2_history.clear()
        self.time_history.clear()
        self.t0 = time.time()
        if MATPLOTLIB_AVAILABLE and self.chart_canvas:
            self.line1.set_data([], [])
            self.line2.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.chart_canvas.draw_idle()

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Settings
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_settings(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Settings  ")

        # Scrollable canvas
        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(evt=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_resize(evt):
            canvas.itemconfig(win_id, width=evt.width)

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        # Mouse-wheel scrolling
        def _on_wheel(evt):
            canvas.yview_scroll(int(-1 * (evt.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)

        col_l = tk.Frame(inner, bg=BG)
        col_l.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=4)
        col_r = tk.Frame(inner, bg=BG)
        col_r.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=4)

        # ── Area Settings ─────────────────────────────────────────────────
        self._settings_area(col_l)
        # ── Output / Calculation ──────────────────────────────────────────
        self._settings_output(col_l)
        # ── Reference Tolerances ─────────────────────────────────────────
        self._settings_ref_tolerance(col_r)
        # ── Threshold Tolerances ─────────────────────────────────────────
        self._settings_thr_tolerance(col_r)
        # ── Confirm (SC) ─────────────────────────────────────────────────
        self._settings_confirm(col_r)

    def _lf(self, parent, title):
        """Create a styled LabelFrame on a plain BG parent."""
        f = tk.LabelFrame(parent, text=f"  {title}  ",
                          bg=CARD_BG, fg=ACCENT,
                          font=("Segoe UI", 9, "bold"),
                          relief="flat", bd=1,
                          highlightbackground=BORDER,
                          highlightthickness=1)
        f.pack(fill="x", pady=(0, 8))
        return f

    def _srow(self, parent, row, label, varname, default, choices=None):
        tk.Label(parent, text=label, bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).grid(
            row=row, column=0, sticky="w", padx=(8, 4), pady=3)
        var = tk.StringVar(value=default)
        setattr(self, varname, var)
        if choices:
            cb = ttk.Combobox(parent, textvariable=var, values=choices,
                              state="readonly", width=16)
            cb.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=3)
        else:
            e = ttk.Entry(parent, textvariable=var, width=18)
            e.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=3)
        parent.columnconfigure(1, weight=1)

    def _sbtn(self, parent, row, label, cmd, style="TButton"):
        ttk.Button(parent, text=label, style=style,
                   command=cmd).grid(
            row=row, column=0, columnspan=2,
            sticky="ew", padx=8, pady=(4, 8))

    def _settings_area(self, parent):
        lf = self._lf(parent, "Area Settings")
        self._srow(lf, 0, "Area number", "s_area_num", "1", ["1","2"])
        self._srow(lf, 1, "Measuring method", "s_area_method", "0=DIA",
                   ["0=DIA","1=T-EDGE","2=B-EDGE","3=SEG"])
        self._srow(lf, 2, "Threshold level (10-99)", "s_area_level", "50")
        self._sbtn(lf, 3, "Apply Area Settings", self._apply_area)

    def _settings_output(self, parent):
        lf = self._lf(parent, "Output / Calculation")
        self._srow(lf, 0, "Output number", "s_out_num", "1=OUT1",
                   ["1=OUT1","2=OUT2"])
        self._srow(lf, 1, "Calculation code (00-xx)", "s_calc", "00")
        self._srow(lf, 2, "Averaging code (00-12)", "s_avg", "00")
        self._srow(lf, 3, "Measuring mode code", "s_me", "00")
        self._srow(lf, 4, "Offset value (e.g. +00000000)", "s_offset",
                   "+00000000")
        self._sbtn(lf, 5, "Apply Output Settings", self._apply_output)

    def _settings_ref_tolerance(self, parent):
        lf = self._lf(parent, "Tolerance – Reference Value Mode")
        self._srow(lf, 0, "Output number", "s_tol_out", "1=OUT1",
                   ["1=OUT1","2=OUT2"])
        self._srow(lf, 1, "Upper  (UP)",     "s_tol_upper", "+00000000")
        self._srow(lf, 2, "Standard (SD)",   "s_tol_std",   "+00000000")
        self._srow(lf, 3, "Lower  (LW)",     "s_tol_lower", "+00000000")
        self._sbtn(lf, 4, "Apply Reference Tolerances", self._apply_ref_tol)

    def _settings_thr_tolerance(self, parent):
        lf = self._lf(parent, "Tolerance – Threshold Mode")
        self._srow(lf, 0, "Output number", "s_thr_out", "1=OUT1",
                   ["1=OUT1","2=OUT2"])
        self._srow(lf, 1, "HH", "s_tol_hh", "+00000000")
        self._srow(lf, 2, "HI", "s_tol_hi", "+00000000")
        self._srow(lf, 3, "LO", "s_tol_lo", "+00000000")
        self._srow(lf, 4, "LL", "s_tol_ll", "+00000000")
        self._sbtn(lf, 5, "Apply Threshold Tolerances", self._apply_thr_tol)

    def _settings_confirm(self, parent):
        lf = self._lf(parent, "Confirm Current Setting (SC)")
        self._srow(lf, 0, "Param (CA/AV/ME/OF/UP/SD/LW…)", "s_sc_param", "CA")
        self._srow(lf, 1, "Output/Area number", "s_sc_out", "1")
        self._sbtn(lf, 2, "Read Setting (SC command)", self._read_setting)
        self.sc_result_var = tk.StringVar(value="–")
        tk.Label(lf, textvariable=self.sc_result_var,
                 bg=CARD_BG, fg=GREEN,
                 font=("Courier New", 9),
                 wraplength=260, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

    def _out_num(self, var):
        return int(getattr(self, var).get().split("=")[0])

    def _apply_area(self):
        if not self._check_conn(): return
        try:
            a = int(self.s_area_num.get().split("=")[0])
            m = int(self.s_area_method.get().split("=")[0])
            lv = int(self.s_area_level.get())
            for cmd in [self.commands.set_area(a, m),
                        self.commands.set_level(a, lv)]:
                r = self.serial.send_command(cmd)
                self._log(f">> {cmd}  << {r}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _apply_output(self):
        if not self._check_conn(): return
        try:
            h = self._out_num("s_out_num")
            for cmd in [
                self.commands.set_calculation(h, int(self.s_calc.get())),
                self.commands.set_average(h,     int(self.s_avg.get())),
                self.commands.set_measuring_mode(h, int(self.s_me.get())),
                self.commands.set_offset(h, self.s_offset.get()),
            ]:
                r = self.serial.send_command(cmd)
                self._log(f">> {cmd}  << {r}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _apply_ref_tol(self):
        if not self._check_conn(): return
        try:
            h = self._out_num("s_tol_out")
            for cmd in [
                self.commands.set_tolerance_upper(h,    self.s_tol_upper.get()),
                self.commands.set_tolerance_standard(h, self.s_tol_std.get()),
                self.commands.set_tolerance_lower(h,    self.s_tol_lower.get()),
            ]:
                r = self.serial.send_command(cmd)
                self._log(f">> {cmd}  << {r}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _apply_thr_tol(self):
        if not self._check_conn(): return
        try:
            h = self._out_num("s_thr_out")
            for cmd in [
                self.commands.set_tolerance_hh(h, self.s_tol_hh.get()),
                self.commands.set_tolerance_hi(h, self.s_tol_hi.get()),
                self.commands.set_tolerance_lo(h, self.s_tol_lo.get()),
                self.commands.set_tolerance_ll(h, self.s_tol_ll.get()),
            ]:
                r = self.serial.send_command(cmd)
                self._log(f">> {cmd}  << {r}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _read_setting(self):
        if not self._check_conn(): return
        try:
            cmd = self.commands.sc(self.s_sc_param.get(), self.s_sc_out.get())
            r = self.serial.send_command(cmd)
            self._log(f">> {cmd}  << {r}")
            self.sc_result_var.set(r)
        except Exception as e:
            self._log(f"ERROR: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Statistics
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_statistics(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Statistics  ")

        lf = tk.LabelFrame(tab, text="  Statistical Processing Setup  ",
                           bg=CARD_BG, fg=ACCENT,
                           font=("Segoe UI", 9, "bold"),
                           relief="flat", highlightbackground=BORDER,
                           highlightthickness=1)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(1, weight=1)

        tk.Label(lf, text="Output:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w",
                                            padx=8, pady=6)
        self.stat_out_var = tk.StringVar(value="1=OUT1")
        ttk.Combobox(lf, textvariable=self.stat_out_var,
                     values=["1=OUT1","2=OUT2"], state="readonly",
                     width=10).grid(row=0, column=1, sticky="w", padx=4)

        tk.Label(lf, text="Setting:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w",
                                            padx=8, pady=6)
        self.stat_setting_var = tk.StringVar(value="0000001")
        ttk.Entry(lf, textvariable=self.stat_setting_var,
                  width=14).grid(row=1, column=1, sticky="w", padx=4)
        tk.Label(lf, text="0000000=OFF  0000001=External  0000002-9999999=count",
                 bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 7)).grid(row=1, column=2, sticky="w", padx=4)

        btn_row = tk.Frame(lf, bg=CARD_BG)
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        for txt, fn, sty in [
            ("Apply SD,ST Setting",   self._apply_stats,     "TButton"),
            ("Stats Sampling ON",     self._stats_on,        "Green.TButton"),
            ("Stats Sampling OFF",    self._stats_off,       "Orange.TButton"),
            ("Read Result (M q,2)",   self._read_stats,      "TButton"),
        ]:
            ttk.Button(btn_row, text=txt, style=sty,
                       command=fn).pack(side="left", padx=4)

        tk.Label(lf,
                 text=(
                     "Note: ER,99 = timeout/not ready. Start sampling with "
                     "'Stats Sampling ON', wait for measurements,\n"
                     "then stop with 'Stats Sampling OFF' before reading result."
                 ),
                 bg=CARD_BG, fg=ORANGE, font=("Segoe UI", 8),
                 justify="left").grid(row=3, column=0, columnspan=3,
                                      sticky="w", padx=8, pady=(0, 8))

        # Result area
        res_lf = tk.LabelFrame(tab, text="  Statistical Result  ",
                               bg=CARD_BG, fg=ACCENT,
                               font=("Segoe UI", 9, "bold"),
                               relief="flat", highlightbackground=BORDER,
                               highlightthickness=1)
        res_lf.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.stats_text = tk.Text(
            res_lf, height=16,
            bg=BG, fg=FG,
            font=("Courier New", 9),
            insertbackground=FG,
            relief="flat", borderwidth=0,
            state="disabled")
        vsb = ttk.Scrollbar(res_lf, orient="vertical",
                            command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.stats_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _apply_stats(self):
        if not self._check_conn(): return
        try:
            out = int(self.stat_out_var.get().split("=")[0])
            cmd = self.commands.set_statistics(out, self.stat_setting_var.get())
            r = self.serial.send_command(cmd)
            self._log(f">> {cmd}  << {r}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _stats_on(self):
        if not self._check_conn(): return
        out = int(self.stat_out_var.get().split("=")[0])
        self._send_quick(self.commands.statistics_on(out))

    def _stats_off(self):
        if not self._check_conn(): return
        out = int(self.stat_out_var.get().split("=")[0])
        self._send_quick(self.commands.statistics_off(out))

    def _read_stats(self):
        if not self._check_conn(): return
        try:
            out = int(self.stat_out_var.get().split("=")[0])
            cmd = self.commands.measured_value(out, 2)
            r = self.serial.send_command(cmd)
            self._log(f">> {cmd}  << {r}")
            self.stats_text.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.stats_text.insert("end", f"[{ts}]  {r}\n")
            # Pretty-print known stats fields
            if r and "ER" not in r:
                parts = r.split(",")
                labels = ["header","MAX","MIN","AVE","PP","σ",
                          "N","N_HH","N_HI","N_GO","N_LO","N_LL"]
                for i, p in enumerate(parts):
                    lbl = labels[i] if i < len(labels) else f"[{i}]"
                    self.stats_text.insert("end", f"        {lbl:8s} = {p.strip()}\n")
            self.stats_text.insert("end", "\n")
            self.stats_text.see("end")
            self.stats_text.configure(state="disabled")
        except Exception as e:
            self._log(f"ERROR: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Program
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_program(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Program  ")

        # Program select / read
        lf1 = tk.LabelFrame(tab, text="  Program Number  ",
                            bg=CARD_BG, fg=ACCENT,
                            font=("Segoe UI", 9, "bold"),
                            relief="flat", highlightbackground=BORDER,
                            highlightthickness=1)
        lf1.pack(fill="x", padx=10, pady=10)

        row0 = tk.Frame(lf1, bg=CARD_BG)
        row0.pack(fill="x", padx=8, pady=8)
        tk.Label(row0, text="Program number (0-9 or A-F):",
                 bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        self.prog_var = tk.StringVar(value="0")
        ttk.Entry(row0, textvariable=self.prog_var, width=5).pack(
            side="left", padx=8)
        ttk.Button(row0, text="Select (PW)",
                   command=self._select_program).pack(side="left", padx=4)

        row1 = tk.Frame(lf1, bg=CARD_BG)
        row1.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row1, text="Read Current Program (PR)",
                   command=self._read_program_num).pack(side="left", padx=4)
        tk.Label(row1, text="Current:", bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        self.prog_result_var = tk.StringVar(value="–")
        tk.Label(row1, textvariable=self.prog_result_var,
                 bg=CARD_BG, fg=GREEN,
                 font=("Courier New", 11, "bold")).pack(side="left")

        # Key lock
        lf2 = tk.LabelFrame(tab, text="  Key Lock  ",
                            bg=CARD_BG, fg=ACCENT,
                            font=("Segoe UI", 9, "bold"),
                            relief="flat", highlightbackground=BORDER,
                            highlightthickness=1)
        lf2.pack(fill="x", padx=10, pady=(0, 8))
        row2 = tk.Frame(lf2, bg=CARD_BG)
        row2.pack(fill="x", padx=8, pady=8)
        self.key_lock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Key Lock ON",
                        variable=self.key_lock_var,
                        style="Card.TCheckbutton").pack(side="left")
        ttk.Button(row2, text="Apply (PL,1 / PL,0)",
                   command=self._apply_key_lock).pack(side="left", padx=12)
        tk.Label(lf2,
                 text="Note: Key lock requires P-SELECT=PANEL in environment settings.",
                 bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(0, 6))

        # Binary backup/restore
        lf3 = tk.LabelFrame(tab, text="  Whole Settings Backup / Restore  ",
                            bg=CARD_BG, fg=ACCENT,
                            font=("Segoe UI", 9, "bold"),
                            relief="flat", highlightbackground=BORDER,
                            highlightthickness=1)
        lf3.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(lf3, text="Binary SR/SA/SW/SB commands. NORMAL D-MODE required.",
                 bg=CARD_BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(6, 2))
        row3 = tk.Frame(lf3, bg=CARD_BG)
        row3.pack(fill="x", padx=8, pady=6)
        for txt, fn in [
            ("Read Program (SR)", self._sr_read),
            ("Read Env (SA)",     self._sa_read),
            ("Write Program (SW)", self._sw_write),
            ("Write Env (SB)",    self._sb_write),
        ]:
            ttk.Button(row3, text=txt, command=fn).pack(side="left", padx=4)
        self.backup_status = tk.Label(lf3, text="",
                                      bg=CARD_BG, fg=FG_DIM,
                                      font=("Segoe UI", 8))
        self.backup_status.pack(anchor="w", padx=8, pady=(0, 6))

    def _select_program(self):
        if not self._check_conn(): return
        cmd = self.commands.program_select(self.prog_var.get().strip().upper())
        r = self.serial.send_command(cmd)
        self._log(f">> {cmd}  << {r}")

    def _read_program_num(self):
        if not self._check_conn(): return
        cmd = self.commands.program_read()
        r = self.serial.send_command(cmd)
        self._log(f">> {cmd}  << {r}")
        # Parse PR,v response
        prog = self.commands.parse_program_response(r)
        self.prog_result_var.set(prog)

    def _apply_key_lock(self):
        if not self._check_conn(): return
        # PL,1 = ON, PL,0 = OFF  (single digit per manual)
        cmd = self.commands.key_lock(self.key_lock_var.get())
        r = self.serial.send_command(cmd)
        self._log(f">> {cmd}  << {r}")
        if "ER" in r:
            messagebox.showwarning(
                "Key Lock Error",
                f"Device returned: {r}\n\n"
                "Key lock requires P-SELECT=PANEL in the device's "
                "environment settings. Check the device front panel menu.\n\n"
                "Error 20 = data length error, which can also indicate\n"
                "the panel lock feature is not enabled on this unit.")

    def _sr_read(self):
        if not self._check_conn(): return
        try:
            r = self.serial.send_command("SR")
            self._log(f">> SR  (response length {len(r)} chars)")
            path = filedialog.asksaveasfilename(
                defaultextension=".bin",
                filetypes=[("Binary", "*.bin"), ("All", "*.*")])
            if path:
                with open(path, "wb") as f:
                    f.write(r.encode("ascii", errors="replace"))
                self.backup_status.configure(text=f"Program settings saved: {path}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _sa_read(self):
        if not self._check_conn(): return
        try:
            r = self.serial.send_command("SA")
            self._log(f">> SA  (response length {len(r)} chars)")
            path = filedialog.asksaveasfilename(
                defaultextension=".bin",
                filetypes=[("Binary", "*.bin"), ("All", "*.*")])
            if path:
                with open(path, "wb") as f:
                    f.write(r.encode("ascii", errors="replace"))
                self.backup_status.configure(text=f"Env settings saved: {path}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _sw_write(self):
        path = filedialog.askopenfilename(
            filetypes=[("Binary", "*.bin"), ("All", "*.*")])
        if not path or not self._check_conn(): return
        try:
            with open(path, "rb") as f:
                data = f.read()
            r = self.serial.send_command(
                "SW," + data.decode("ascii", errors="replace"))
            self._log(f">> SW,...  << {r}")
            self.backup_status.configure(text="Program settings written.")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _sb_write(self):
        path = filedialog.askopenfilename(
            filetypes=[("Binary", "*.bin"), ("All", "*.*")])
        if not path or not self._check_conn(): return
        try:
            with open(path, "rb") as f:
                data = f.read()
            r = self.serial.send_command(
                "SB," + data.decode("ascii", errors="replace"))
            self._log(f">> SB,...  << {r}")
            self.backup_status.configure(text="Env settings written.")
        except Exception as e:
            self._log(f"ERROR: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab: Console
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_console(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Console  ")

        self.console = tk.Text(
            tab, bg=BG, fg=FG,
            font=("Courier New", 9),
            insertbackground=FG,
            relief="flat", borderwidth=0,
            state="disabled")
        vsb = ttk.Scrollbar(tab, orient="vertical",
                            command=self.console.yview)
        self.console.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.console.pack(side="top", fill="both", expand=True,
                          padx=4, pady=(4, 0))

        # Command entry row
        cmd_frame = tk.Frame(tab, bg=CARD_BG)
        cmd_frame.pack(fill="x", padx=4, pady=4)
        tk.Label(cmd_frame, text="CMD>", bg=CARD_BG, fg=ACCENT,
                 font=("Courier New", 9, "bold")).pack(side="left", padx=6)
        self.cmd_entry = ttk.Entry(cmd_frame, font=("Courier New", 10))
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.cmd_entry.bind("<Return>", self._send_console_cmd)
        self.cmd_entry.bind("<Up>",     self._history_up)
        self.cmd_entry.bind("<Down>",   self._history_down)
        ttk.Button(cmd_frame, text="Send",
                   command=self._send_console_cmd).pack(side="left", padx=(0, 4))
        ttk.Button(cmd_frame, text="Clear",
                   command=self._clear_console).pack(side="left")

        self._cmd_history    = []
        self._cmd_history_idx = -1

        # Quick-reference
        ref = tk.LabelFrame(tab, text="  Command Reference  ",
                            bg=CARD_BG, fg=ACCENT,
                            font=("Segoe UI", 8, "bold"),
                            relief="flat", highlightbackground=BORDER,
                            highlightthickness=1)
        ref.pack(fill="x", padx=4, pady=(0, 4))
        ref_text = (
            "M q,r  Measured value (q=0/1/2 output, r=0/1/2 type)  |  MR  Re-output  |  L q,r  Timing read\n"
            "H q  Timing ON  |  U q  Timing OFF  |  Q q  Reset  |  V q  Auto Zero ON  |  W q  Auto Zero OFF\n"
            "O q  Stats sampling ON  |  R q  Stats sampling OFF\n"
            "SD,AR,a,c  Set area method  |  SD,LE,a,gg  Threshold level  |  SD,CA,h,ii  Calculation\n"
            "SD,AV,h,jj  Average  |  SD,ME,h,kk  Mode  |  SD,OF,h,value  Offset\n"
            "SD,UP/SD/LW/HH/HI/LO/LL,h,value  Tolerances  |  SD,ST,h,setting  Statistics\n"
            "SC,param,h  Confirm setting  |  PR  Read program  |  PW,v  Select program  |  PL,1/0  Key lock\n"
            "SR  Read program (binary)  |  SA  Read env (binary)"
        )
        tk.Label(ref, text=ref_text, bg=CARD_BG, fg=FG_DIM,
                 font=("Courier New", 7), justify="left").pack(
            anchor="w", padx=6, pady=4)

    def _send_console_cmd(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self._cmd_history.append(cmd)
        self._cmd_history_idx = len(self._cmd_history)
        self.cmd_entry.delete(0, "end")
        if not self.serial.is_connected:
            self._log("ERROR: Not connected.")
            return
        try:
            resp = self.serial.send_command(cmd)
            self._log(f">> {cmd}\n<< {resp}")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _history_up(self, event=None):
        if self._cmd_history and self._cmd_history_idx > 0:
            self._cmd_history_idx -= 1
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, self._cmd_history[self._cmd_history_idx])

    def _history_down(self, event=None):
        if self._cmd_history_idx < len(self._cmd_history) - 1:
            self._cmd_history_idx += 1
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, self._cmd_history[self._cmd_history_idx])
        else:
            self._cmd_history_idx = len(self._cmd_history)
            self.cmd_entry.delete(0, "end")

    def _clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {msg}\n"
        self.console.configure(state="normal")
        self.console.insert("end", line)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _check_conn(self) -> bool:
        if not self.serial.is_connected:
            messagebox.showwarning("Not Connected", "Please connect first.")
            return False
        return True

    def _on_close(self):
        self.polling_active = False
        self.serial.disconnect()
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = LS7601App()
    app.mainloop()


if __name__ == "__main__":
    main()
