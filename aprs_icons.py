# -*- coding: utf-8 -*-
"""
aprs_icons.py -- APRS symbol picker widget for the TD-H9 settings tab.

Author:  dkxce (c)  https://github.com/dkxce/Tidradio-TD-H9
Version: v1.0.0.0

Russian:  Диалог выбора иконки APRS (двух таблиц: Primary "/" и
          Secondary "\\"), с предпросмотром картинки из встроенной
          base64-базы (aprs_icons_data.py). Используется для поля
          "Icon Settings" (байт символа 0x30D6, номер 0-93).
English:  APRS icon picker dialog (Primary "/" and Secondary "\\"
          symbol tables) with image preview from the embedded base64
          database (aprs_icons_data.py). Used by the "Icon Settings"
          field (symbol byte 0x30D6, index 0-93).
"""

from __future__ import annotations

import base64
import io
import tkinter as tk
from tkinter import ttk

from aprs_icons_data import PRIMARY_ICONS, SECONDARY_ICONS

__author__ = "dkxce (c) https://github.com/dkxce/Tidradio-TD-H9"
__version__ = "v1.0.0.0"


class AprsIcon:
    """One icon entry: index, symbol string, description, PNG bytes."""
    __slots__ = ("n", "sym", "name", "png")

    def __init__(self, n: int, sym: str, name: str, b64: str):
        self.n = n
        self.sym = sym
        self.name = name
        try:
            self.png = base64.b64decode(b64)
        except Exception:
            self.png = b""

    @property
    def label(self) -> str:
        """Dropdown/clipboard label: "№: symbol (description)"."""
        base = "%d: %s" % (self.n, self.sym)
        if self.name:
            base += "  %s" % self.name
        return base


def load_icons():
    """Return (primary_list, secondary_list) of AprsIcon objects."""
    primary = [AprsIcon(e["n"], e["sym"], e.get("name", ""), e.get("b64", ""))
               for e in PRIMARY_ICONS]
    secondary = [AprsIcon(e["n"], e["sym"], e.get("name", ""), e.get("b64", ""))
                 for e in SECONDARY_ICONS]
    return primary, secondary


class APRSIconSelector(tk.Toplevel):
    """Modal dialog: pick an APRS icon and store the result in ``result``.

    Russian:  Модальный диалог выбора иконки APRS. После выбора
              ``selector.result`` = (index, symbol, description, png_bytes).
    """

    def __init__(self, master, initial_index: int = 0, table_id: str = "primary"):
        super().__init__(master)
        self.title("APRS Icon Settings / Выбор иконки APRS")
        self.geometry("640x520")
        self.transient(master)
        self.grab_set()

        self.result = None
        self._table = "primary" if table_id != "secondary" else "secondary"
        self._primary, self._secondary = load_icons()
        self._set_icons = {"primary": self._primary, "secondary": self._secondary}
        self._selected_index = initial_index if 0 <= initial_index < 94 else 0

        self._build_ui()
        self._refresh_preview()
        self._refresh_list()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Table / Таблица:").pack(side="left")
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(
            top, textvariable=self.table_var, state="readonly", width=14,
            values=("Primary /", "Secondary \\"))
        self.table_combo.set("Primary /" if self._table == "primary" else "Secondary \\")
        self.table_combo.pack(side="left", padx=6)
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_change)

        # search box
        ttk.Label(top, text="Filter / Поиск:").pack(side="left", padx=(18, 4))
        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=22).pack(side="left")
        self.search_var.trace_add("write", lambda *a: self._refresh_list())

        # preview on the right
        preview = ttk.LabelFrame(self, text="Preview / Предпросмотр")
        preview.pack(side="right", fill="y", padx=8, pady=6)
        self.preview_label = ttk.Label(preview, text="", anchor="center")
        self.preview_label.pack(padx=10, pady=10)
        self.preview_text = ttk.Label(preview, text="", anchor="center",
                                      foreground="gray")
        self.preview_text.pack(padx=10, pady=(0, 8))

        # listbox on the left
        list_frame = ttk.Frame(self)
        list_frame.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        self.listbox = tk.Listbox(list_frame, height=18, activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical",
                               command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", lambda e: self._on_ok())

        # buttons
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="OK", command=self._on_ok).pack(side="right", padx=4)
        ttk.Button(btns, text="Cancel / Отмена", command=self.destroy).pack(side="right")

    # ------------------------------------------------------------- helpers
    def _current_icons(self):
        return self._set_icons[self._table]

    def _refresh_kind(self):
        if self._table == "secondary":
            self.table_combo.set("Secondary \\")
        else:
            self.table_combo.set("Primary /")

    def _on_table_change(self, _e=None):
        if self.table_var.get().startswith("Secondary"):
            self._table = "secondary"
        else:
            self._table = "primary"
        self._refresh_list()

    def _filtered(self):
        q = self.search_var.get().strip().lower()
        icons = self._current_icons()
        if not q:
            return icons
        return [ic for ic in icons
                if q in ic.sym.lower() or q in ic.name.lower()
                or str(ic.n) == q]

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        items = self._filtered()
        for ic in items:
            self.listbox.insert(tk.END, "(#%02d) %s  %s" % (ic.n, ic.sym, ic.name))
        # preselect the current one
        for i, ic in enumerate(items):
            if ic.n == self._selected_index:
                self.listbox.selection_set(i)
                self.listbox.see(i)
                break

    def _on_select(self, _e=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        icons = self._filtered()
        ic = icons[sel[0]]
        self._selected_index = ic.n
        self._refresh_preview()

    def _refresh_preview(self):
        ic = self._current_icons()[self._selected_index]
        if ic.png:
            try:
                img = tk.PhotoImage(data=ic.png)
                self.preview_label.configure(image=img)
                self.preview_label.image = img
            except Exception:
                self.preview_label.configure(image="")
        self.preview_text.configure(
            text="%d  %s\n%s" % (ic.n, ic.sym, ic.name or "—"))

    def _on_ok(self):
        ic = self._current_icons()[self._selected_index]
        self.result = (ic.n, ic.sym, ic.name, ic.png)
        self.destroy()


def choose_icon(master, index: int = 0, table: str = "primary"):
    """Open the modal icon picker; return (index, symbol, name, png) or None."""
    dlg = APRSIconSelector(master, initial_index=index, table_id=table)
    master.wait_window(dlg)
    return dlg.result