"""
==============================================================================
  APRS/GNSS settings parser for the TD-H9 clone image
  Author:  dkxce (c)  https://github.com/dkxce/Tidradio-TD-H9
  Version: v1.0.0.0

  Russian:  Разбор настроек APRS и GNSS из полного образа рации (0x3148
            байт, из них 8 байт — идентификация + 0x3140 байт памяти).
            Оффсеты взяты из собственного дизассемблерного анализа
            Customer Programming Software (Disasm/aprs.md, gnss.md) и
            согласованы с melidosian/h9toolbox settings.mjs. Только чтение.
  English:  Parse APRS and GNSS settings out of the full TD-H9 radio image
            (0x3148 bytes = 8-byte identity + 0x3140 bytes of memory).
            Offsets come from our own disassembly of the Customer Programming
            Software (Disasm/aprs.md, gnss.md) and are aligned with
            melidosian/h9toolbox settings.mjs. Read-only.
==============================================================================
"""

from __future__ import annotations

import json
import struct
from typing import Any, Dict, List, Optional

# td9_aprs has the writable-field table (offsets + encoders); importing it here
# is safe: bleak is only imported lazily inside td9_aprs functions.
from td9_aprs import WRITABLE, encode_setting

__author__ = "dkxce (c) https://github.com/dkxce/Tidradio-TD-H9"
__version__ = "v1.0.0.0"

MEM_SIZE = 0x3140
IDENT_SIZE = 8
IMAGE_SIZE = MEM_SIZE + IDENT_SIZE

# The clone image carries a small 0x3000-area header; the memory map here
# indexes into the MEMORY portion (offset = abs_image - 8). For read offsets
# our parser below is given the full image and internally subtracts 8.

SSID_CHOICES = {i: str(i) for i in range(16)}
ICON_TABLE_CHOICES = {0x2F: "Primary /", 0x5C: "Alternate \\"}
MIC_TYPES = ["M0: Off duty", "M1: En route", "M2: In service", "M3: Returning",
             "M4: Committed", "M5: Special", "M6: Priority", "M7: Emergency"]
TX_CHANNEL_CHOICES = {0: "CH-A Locked", 1: "CH-B Locked", 2: "CH-A Auto",
                      3: "CH-B Auto", 4: "CH-A + CH-B"}
RX_CHANNEL_CHOICES = {0: "Off", 1: "CH-A", 2: "CH-B"}
DIGI_FWD_CHOICES = {0: "CH-A", 1: "CH-B", 2: "CH-A + CH-B"}
POS_SOURCE_CHOICES = {0: "Fixed coordinates", 1: "GNSS (GPS)"}
FORMAT_CHOICES = {0: "Degrees", 1: "Degrees + minutes",
                  2: "Degrees + minutes + seconds"}
SPEED_CHOICES = {0: "km/h", 1: "knots", 2: "m/s"}
DIST_CHOICES = {0: "km", 1: "nautical miles", 2: "miles"}
ALT_CHOICES = {0: "meters", 1: "feet"}


def _opt_label(mapping, key):
    """Return mapping[key] label, or 'Unknown (key)' when missing."""
    return mapping.get(key, f"Unknown ({key})")


def _text(data: bytes) -> str:
    """Decode a fixed-size printable-ASCII field (0x00/0xFF terminated).

    Returns an empty string for an empty/uninitialized (all 0x00 or all 0xFF)
    field; returns the printable text when present; otherwise falls back to a
    compact raw-hex hint so non-ASCII bytes are never silently dropped.
    """
    raw = data
    end = -1
    for i, b in enumerate(raw):
        if b == 0 or b == 0xFF:
            end = i
            break
    if end < 0:
        end = len(raw)
    chars = raw[:end]
    if not chars:
        return ""
    if all(32 <= b <= 126 for b in chars):
        return chars.decode("ascii", errors="replace")
    # Non-printable non-empty data: show a hex hint instead of guessing.
    return f"Raw: {' '.join(f'{b:02x}' for b in raw)}"


def _trimmed_chars(image, off: int, length: int) -> str:
    """Read a fixed-size printable-ASCII field, returning only the text.

    Unlike chars(), which shows a hex hint for non-ASCII content, this
    returns the trimmed decoded string (empty when the field is empty).
    """
    raw = image._mem[off:off + length]
    end = -1
    for i, b in enumerate(raw):
        if b == 0 or b == 0xFF:
            end = i
            break
    if end < 0:
        end = len(raw)
    chars = raw[:end]
    if chars:
        return chars.decode("ascii", errors="ignore")
    return ""


def _field_labels():
    """Return the ordered list of APRS+GNSS field names for export."""
    return [
        "aprs_on", "callsign", "ssid", "icon_table", "comment",
        "icon_symbol", "mic_e_start", "mic_e_type",
        "route1_name", "route1_count", "route2_name", "route2_count",
        "report_voltage", "report_sats", "report_mileage",
        "ptt_link", "timed_beacon", "beacon_interval",
        "digi_fwd_channel", "digi1_enabled", "digi1_name",
        "digi2_enabled", "digi2_name", "forward_wait", "remote_password",
        "rx_channel", "tx_channel", "ptt_priority", "rx_popup",
        "gps_on", "position_format", "time_zone", "speed_unit",
        "dist_unit", "alt_unit", "fixed_position",
        "station_type",
    ]


class AprsSettings:
    """Parsed APRS + GNSS settings with human-friendly values."""

    def __init__(self) -> None:
        # A container of raw values keyed by field name (ints / strings).
        self.values: Dict[str, Any] = {}
        self.labels: Dict[str, Any] = {}

    def set(self, key: str, raw, label) -> None:
        self.values[key] = raw
        self.labels[key] = label

    def as_dict(self) -> Dict[str, Any]:
        """Return an ordered dict of human-readable label values."""
        d: Dict[str, Any] = {}
        for k in _field_labels():
            if k in self.labels:
                d[k] = self.labels[k]
        return d

    def as_json(self, pretty: bool = True) -> str:
        doc = {
            "aprs_settings": self.as_dict(),
            "raw": {k: self.values[k] for k in _field_labels()
                    if k in self.values},
        }
        return json.dumps(doc, ensure_ascii=False, indent=2 if pretty else None)


class TDH9Image:
    """Wrap a full clone image and expose read-offset helpers.

    A field's memory offset (as documented) is its position in the memory
    portion; index = offset + IDENT_SIZE into the full image.
    """

    def __init__(self, image: bytes) -> None:
        if len(image) != IMAGE_SIZE:
            raise ValueError(
                f"Expected {IMAGE_SIZE} bytes, got {len(image)}.")
        self._image = image
        self._mem = image[IDENT_SIZE:]

    @property
    def identity(self) -> bytes:
        return self._image[:IDENT_SIZE]

    @property
    def mode(self) -> str:
        # Russian: 0x4E Normal, 0x48 HAM, 0x47 GMRS — режим прошивки рации.
        return {0x4E: "Normal", 0x48: "HAM", 0x47: "GMRS"}.get(
            self._image[7] if len(self._image) > 7 else 0xFF, "Unknown")

    def byte(self, off: int) -> int:
        return self._mem[off]

    def u16le(self, off: int) -> int:
        return self._mem[off] | (self._mem[off + 1] << 8)

    def u32be(self, off: int) -> int:
        return struct.unpack(">I", self._mem[off:off + 4])[0]

    def i32be(self, off: int) -> int:
        return struct.unpack(">i", self._mem[off:off + 4])[0]

    def chars(self, off: int, length: int) -> str:
        return _text(self._mem[off:off + length])

    def is_all_ff(self, off: int, length: int) -> bool:
        return all(b == 0xFF for b in self._mem[off:off + length])


def parse_aprs(image: TDH9Image) -> AprsSettings:
    """Parse APRS (0x307c..) and GNSS (0x3066..) settings from the image.

    Offsets are ABSOLUTE memory offsets from our Disasm (aprs.md): the
    identity header (8 bytes) is already accounted for by the byte()/chars()
    helpers on the memory portion, so these addresses index the actual
    radio memory directly.
    """
    s = AprsSettings()
    # ----- APRS identity / beacon -------------------------------------------
    s.set("aprs_on", image.byte(0x307c),
          "On" if image.byte(0x307c) == 1 else "Off")
    s.set("callsign", image.chars(0x307d, 6),
          image.chars(0x307d, 6))
    ssid = image.byte(0x3083)
    s.set("ssid", ssid, _opt_label(SSID_CHOICES, ssid))
    icon_table = image.byte(0x3084)
    s.set("icon_table", icon_table, _opt_label(ICON_TABLE_CHOICES, icon_table))
    s.set("comment", _trimmed_chars(image, 0x3095, 64),
          _trimmed_chars(image, 0x3095, 64))
    symbol = image.byte(0x30d6)
    s.set("icon_symbol", symbol, str(symbol))
    mic_e = image.byte(0x30d7)
    s.set("mic_e_start", mic_e, "On" if mic_e == 1 else "Off")
    mic_t = image.byte(0x30d8)
    s.set("mic_e_type", mic_t, _opt_label(
        {i: MIC_TYPES[i] for i in range(len(MIC_TYPES))}, mic_t))

    # ----- Routes -----------------------------------------------------------
    # aprs.md: Route-1 Name 0x30d9, Count 0x30e1; Route-2 Name 0x30e2,
    # Count 0x30ea. Count always sits +8 relative to the route name.
    for prefix, base in (("route1", 0x30d9), ("route2", 0x30e2)):
        name = image.chars(base, 8)
        count = image.byte(base + 8)
        s.set(f"{prefix}_name", name, name if name else "—")
        s.set(f"{prefix}_count", count, str(count))

    # ----- Reports & beacon -------------------------------------------------
    for key, off in (("report_voltage", 0x30eb),
                     ("report_sats", 0x30ec),
                     ("report_mileage", 0x30ed),
                     ("ptt_link", 0x30ee),
                     ("timed_beacon", 0x30ef)):
        v = image.byte(off)
        s.set(key, v, "On" if v == 1 else "Off")
    interval = image.u16le(0x30f0)
    s.set("beacon_interval", interval,
          f"{interval} s" if interval else "—")

    # ----- Relay / routing ---------------------------------------------------
    fwd = image.byte(0x30f2)
    s.set("digi_fwd_channel", fwd, _opt_label(DIGI_FWD_CHOICES, fwd))
    d1 = image.byte(0x30f3)
    s.set("digi1_enabled", d1, "On" if d1 == 1 else "Off")
    s.set("digi1_name", image.chars(0x30f4, 8), image.chars(0x30f4, 8))
    d2 = image.byte(0x30fc)
    s.set("digi2_enabled", d2, "On" if d2 == 1 else "Off")
    s.set("digi2_name", image.chars(0x30fd, 8), image.chars(0x30fd, 8))
    wait = image.byte(0x3105)
    s.set("forward_wait", wait, f"{wait} s")
    s.set("remote_password", image.chars(0x3106, 8),
          image.chars(0x3106, 8))
    rxch = image.byte(0x310e)
    s.set("rx_channel", rxch, _opt_label(RX_CHANNEL_CHOICES, rxch))
    txch = image.byte(0x310f)
    s.set("tx_channel", txch, _opt_label(TX_CHANNEL_CHOICES, txch))
    prio = image.byte(0x3110)
    s.set("ptt_priority", prio,
          "APRS" if prio == 1 else "Call")
    pop = image.byte(0x3113)
    s.set("rx_popup", pop, "On" if pop == 1 else "Off")

    # ----- GNSS block (0x3066..0x307b) --------------------------------------
    gps = image.byte(0x3066)
    s.set("gps_on", gps, "On" if gps == 1 else "Off")
    fmt = image.byte(0x3067)
    s.set("position_format", fmt, _opt_label(FORMAT_CHOICES, fmt))
    tz = image.byte(0x3068)
    s.set("time_zone", tz, _opt_label(
        {i: f"UTC{i - 12:+d}" for i in range(25)}, tz))
    sp = image.byte(0x3069)
    s.set("speed_unit", sp, _opt_label(SPEED_CHOICES, sp))
    du = image.byte(0x306a)
    s.set("dist_unit", du, _opt_label(DIST_CHOICES, du))
    au = image.byte(0x306b)
    s.set("alt_unit", au, _opt_label(ALT_CHOICES, au))
    s.set("fixed_position", _format_fixed_position(image),
          _format_fixed_position(image))
    st = image.byte(0x307b)
    s.set("station_type", st, _opt_label(POS_SOURCE_CHOICES, st))

    return s


def _format_fixed_position(image: TDH9Image) -> str:
    """Render the fixed GNSS position (0x306c..0x3076) as human text."""
    raw = image.identity  # placeholder to satisfy linters; not used
    del raw
    # Longitude (BE u32) @ 0x306c, E/W @ 0x3070, Latitude @ 0x3071,
    # N/S @ 0x3075, Altitude (BE i32) @ 0x3076.
    if image.is_all_ff(0x306c, 0x76 - 0x6c) and image.i32be(0x3076) == 0xFFFFFFFF:
        # 0x306c..0x3075 all ff, altitude all-ff -> not configured
        pass
    # is_all_ff over the whole block:
    if image.is_all_ff(0x306c, 0x307b - 0x306c + 1):
        return "Not configured"
    lon = image.u32be(0x306c) / 1_000_000.0
    lat = image.u32be(0x3071) / 1_000_000.0
    alt = image.i32be(0x3076) / 1_000_000.0
    ew = chr(image.byte(0x3070)) if image.byte(0x3070) in (ord('E'), ord('W')) else '?'
    ns = chr(image.byte(0x3075)) if image.byte(0x3075) in (ord('N'), ord('S')) else '?'
    if lon > 180 or lat > 90:
        return "Stored bytes are not a valid fixed position"
    return f"{lat:.6f}{ns}, {lon:.6f}{ew}, {alt:.1f}m"


def build_report(image: TDH9Image, settings: AprsSettings) -> str:
    """Return a compact multi-line human-readable report of the settings."""
    A = settings.labels
    lines = [
        f"TD-H9 mode:      {image.mode}",
        f"APRS:            {A.get('aprs_on')}",
        f"Callsign:        {A.get('callsign')}-{A.get('ssid')}",
        f"Icon table:      {A.get('icon_table')}  (symbol {A.get('icon_symbol')})",
        f"Comment:         {A.get('comment')}",
        f"Route 1:         {A.get('route1_name')}-{A.get('route1_count')}",
        f"Route 2:         {A.get('route2_name')}-{A.get('route2_count')}",
        f"Mic-E:           {A.get('mic_e_start')}  {A.get('mic_e_type')}",
        f"Reports:         volt={A.get('report_voltage')} "
        f"sats={A.get('report_sats')} mil={A.get('report_mileage')}",
        f"PTT beacon:      {A.get('ptt_link')}",
        f"Timed beacon:    {A.get('timed_beacon')}  ({A.get('beacon_interval')})",
        f"RX channel:      {A.get('rx_channel')}",
        f"TX channel:      {A.get('tx_channel')}",
        f"PTT priority:    {A.get('ptt_priority')}",
        f"RX popup:        {A.get('rx_popup')}",
        "",
        "GNSS:",
        f"  GPS:           {A.get('gps_on')}",
        f"  Format:        {A.get('position_format')}",
        f"  Time zone:     {A.get('time_zone')}",
        f"  Units:         {A.get('speed_unit')} / {A.get('dist_unit')} / {A.get('alt_unit')}",
        f"  Fixed point:   {A.get('fixed_position')}",
        f"  Station type:  {A.get('station_type')}",
        "",
        "APRS relay / routing:",
        f"  Forward ch:    {A.get('digi_fwd_channel')}",
        f"  DIGI1:         {A.get('digi1_enabled')}  {A.get('digi1_name')}",
        f"  DIGI2:         {A.get('digi2_enabled')}  {A.get('digi2_name')}",
        f"  Fwd wait:      {A.get('forward_wait')}",
        f"  Remote pwd:    {A.get('remote_password') or '—'}",
    ]
    return "\n".join(lines)


def patch_image(image: bytes, changes: Dict[str, Any]) -> bytes:
    """Apply field changes to a full TD-H9 image (8-byte identity + 0x3140
    memory).  `changes` maps writable field names to new human values, e.g.
    {"callsign": "R2AKA", "beacon_interval": "600", "ssid": "7"}.

    Returns a new image bytes object with the patched fields.  Raises
    KeyError for unknown fields and ValueError for bad values.

    The values are encoded with the same rules as td9_aprs.py ``set``
    (encode_setting): texts, numbers, on/off and choice labels are accepted.
    """
    if len(image) != IMAGE_SIZE:
        raise ValueError(
            f"Expected {IMAGE_SIZE} bytes, got {len(image)}.")
    data = bytearray(image)
    # memory portion starts at offset 8 (identity header)
    mem = data[IDENT_SIZE:]
    for key, value in changes.items():
        off, enc = encode_setting(key, value)
        mem[off:off + len(enc)] = enc
    data[IDENT_SIZE:] = mem
    return bytes(data)


def changed_fields(current: bytes, patched: bytes) -> Dict[str, Any]:
    """Return the list of writable fields whose bytes differ between two
    images (used to report which fields were actually changed)."""
    if len(current) != IMAGE_SIZE or len(patched) != IMAGE_SIZE:
        raise ValueError("Both images must be full TD-H9 images.")
    mem_c = current[IDENT_SIZE:]
    mem_p = patched[IDENT_SIZE:]
    out = []
    for key, (off, kind) in WRITABLE.items():
        length = {"byte": 1, "yesno": 1, "u16le": 2,
                  "text6": 6, "text8": 8, "text64": 64,
                  "coord5": 5, "coord4": 4}.get(kind, 1)
        if mem_c[off:off + length] != mem_p[off:off + length]:
            out.append(key)
    return out