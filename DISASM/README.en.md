# APRS via BLE: analysis of the Odmaster application and implementation of the TNC modem in Python

[RU](README.md) | [EN](README.en.md)

**APK:** `Odmaster_2.6.4.apk`   
**APK decompilation:** `Ajadx-gui`   
**APRS package in APK:** `com.tid.aprs`

This document contains a complete description of how the TNC modem works through
Bluetooth: First – as it is done in a stock app**Odmaster**down
Decompiled APK, then how to implement it**Python**.
At the end is a comparison, a data flow chart, and a table of key constants.

---

## 0. What is a TNC modem via BLE?

On the radio.**TIDRadio TD-H9**hardware**TNC**(Terminal Node Controller):
It modulates / demodulates the AFSK signal 1200 baud and exchanges with the external
device (telephone/PC)**ready-made**protocolly**KISS**.

The order of the data is always this:

```
текстовый APRS-кадр (SRC>DST,PATH:info)
        │  encode_ax25
        ▼
бинарный AX.25-кадр (адреса выровнены по 7 байт, control, PID, info)
        │  kiss_escape + FEND
        ▼
KISS-фрейм:  [0xC0][port:cmd][escape(ax25)][0xC0]
        │  BLE GATT write / notify
        ▼
рация TIDRadio (AFSK в эфир и обратно)
```

BLE-exchange is just a transport for KISS-frames: write-characteristics for
Transmission to the radio (TX), notify-characteristics for reception from the radio (RX).

---

## 1. As done in APK Odmaster

Odmaster uses the module`com.tid.aprs`.   
Talk to the radio via Bluetooth.  
Data is KISS on top of AX.25.  
If necessary, IGate relay over TCP.

### 1.1 Two independent Bluetooth paths

| Way | Mechanism | Key APK classes |
| --- | --- | --- |
| 1. Classic Bluetooth | SPP RFCOMM, UUID`00001101-0000-1000-8000-00805F9B34FB` | `BluetoothTnc.java`, `AprsBlueActivity.java` |
| 2. BLE GATT. | library`cn.com.heaton.blelibrary`service`0000af00-0000-1000-8000-00805f9b34fb` | `AprsSendMessageNetworkVM.java`, `AprsVM.java` |
| 3. Radio (AFSK) | AFSK sound modulation/demodulation | `AprsAfskSendFragment.java`, `AprsAfskListFragment.java`, `afsk/*` |
| 4. Internet (IGate) | TCP + EasySocket | `AprsNetworkTranFragment.java`, `MessageProtocol.java` |

### 1.2 Classic Bluetooth (SPP RFCOMM)

Background flow`BtSocketThread`connected via SPP:

```
private UUID SPP = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
...
BluetoothSocket s = tnc.createRfcommSocketToServiceRecord(SPP);
s.connect();  // BluetoothTnc.java:133-135
```

Sending a packet to the radio:

```
OutputStream out = socket.getOutputStream();
out.write(Kiss.FEND);          // 0xC0
out.write(Kiss.CMD_DATA);      // 0x00
out.write(aPRSPacket.toAX25Frame());  // бинарный AX.25
out.write(Kiss.FEND);          // 0xC0
out.flush();
```

Reception - analysis of the KISS stream:

`FEND=0xC0`border,`FESC=0xDB`escape, escape  
`TFEND=0xDC`/`TFESC=0xDD`; FEND is called`Parser.parseAX25(...)` и   
`Parser.parse(...)`(lines)`BluetoothTnc.java:209-247`).

### 1.3 BLE GATT

Library`cn.com.heaton.blelibrary`   
(classes)`Ble`, `BleDevice`, `BleWriteCallback`, `BleNotifyCallback`), wrapper`BluUtils`.

**UUID for APRS (BLE GATT):**

| Appointment | UUID |
| --- | --- |
| Service APRS | `0000af00-0000-1000-8000-00805f9b34fb` |
| Characteristic TX (write) | `0000af01-0000-1000-8000-00805f9b34fb` |
| Characteristic RX (notify) | `0000af02-0000-1000-8000-00805f9b34fb` |

Sending:

```
ByteArrayOutputStream baos = new ByteArrayOutputStream();
baos.write(BluetoothTnc.Kiss.FEND);
baos.write(BluetoothTnc.Kiss.CMD_DATA);
baos.write(bArr);                                  // AX.25-фрейм
baos.write(BluetoothTnc.Kiss.FEND);
BluUtils.getInstance().getmBle().writeByUuid(
    device, baos.toByteArray(),
    UUID.fromString("0000af00-0000-1000-8000-00805f9b34fb"),  // service
    UUID.fromString("0000af01-0000-1000-8000-00805f9b34fb"),  // write char
    callback);
```

Reception (notify):

```
BluUtils.getInstance().getmBle().enableNotifyByUuid(
    device, true,
    UUID.fromString("0000af00-0000-1000-8000-00805f9b34fb"),
    UUID.fromString("0000af02-0000-1000-8000-00805f9b34fb"),
    new BleNotifyCallback<BleDevice>() {
        void onChanged(BleDevice d, BluetoothGattCharacteristic c) {
            String s = AprsByteProcessor.getKissString(c.getValue()).trim();
            if (TextUtils.isEmpty(s) || !s.contains(">")) return;
            APRSPacket packet = Parser.parse(s);
            AprsStringUtil.addKiss(packet);     // список до 50 пакетов
            handler.sendMessage(...);          // обновление UI
        }
    });
```

### 1.4 Common (not APRS) UUID radios`BluUtils.java`

| Appointment | UUID |
| --- | --- |
| Service radios | `0000ff00-0000-1000-8000-00805f9b34fb` |
| Write (teams) | `0000ff02-0000-1000-8000-00805f9b34fb` |
| Read more | `0000ff01-0000-1000-8000-00805f9b34fb` |
| Notify (DX) | `0000ff21-0000-1000-8000-00805f9b34fb` |
| Write (DX) | `0000ff22-0000-1000-8000-00805f9b34fb` |

`BluUtils.init`:

```
Ble.options()
  .setUuidService ("0000ff00-...")
  .setUuidWriteCha("0000ff02-...")
  .setUuidReadCha ("0000ff01-...")
  .create(context, ...);
```

### 1.5 Internet / IGate in APK

Prix`isRadioToNet() && isAutoConnect()`The received package is published in RxBus
?`BluetoothTnc.java:35`, `AprsMainActivity.java:210-216`) and goes to the network through
TCP + EasySocket. The network is used**textual**APRS.`AprsPacket.formatLogin`+ position) on TCP with 1024-byte read protocol.

---

## 2. How it is implemented in Python (TDH9KISS)

TDH9KISS Repeats the BLE GATT Path`af00`write`af01`notify`af02`), but adds on top of mini servers (KISS/AGW/APRS-IS) and built-in IGate,
So that the radio can work with external APRS applications and the network.

### 2.1 Modules

| Module | Role |
| --- | --- |
| `main.py` | GUI (Tk), orchestration, two tabs, RX/TX log |
| `ble_radio.py` | BLE-transport: scanning, connecting, reading GATT-services, sending / receiving personnel |
| `gatt_info.py` | human-readable descriptions of services / characteristics of GATT |
| `kiss.py` | KISS protocol: escape/unescape, frame parser |
| `ax25.py` | Encoding/decoding binary AX.25 text APRS |
| `aprs_parser.py` | Analysis of APRS packet content (position, message, etc.) |
| `kiss_tcp_server.py` | KISS TNC over TCP (port 8023) |
| `agw_server.py` | AGWPE-compatible server (port 8000, 36-byte headers) |
| `aprsis_server.py` | APRS-IS-compatible server (port 14580), passcode server verification |
| `igate.py` | IGate-client (radio а APRS-IS), gateway rules, settings.json |
| `mru_store.py`, `packet_log.py` | Device/message history and reception/transmission logs |
| `aprsis_test.py`, `igate_test.py` | Test scripts (listener / IGate sender) |

### 2.2 BLE transport`ble radio. py`)

The library is used**bleak**(asyncio) All Asyncio is performed separately.
background flow`ble-loop`), and results come to the GUI through colbacks and queues.

Key UUIDs:

```
SERVICE_APRS = "0000af00-0000-1000-8000-00805f9b34fb"  # Service APRS
CHAR_WRITE   = "0000af01-0000-1000-8000-00805f9b34fb"  # TX, write-without-response
CHAR_NOTIFY  = "0000af02-0000-1000-8000-00805f9b34fb"  # RX, notify
```

There are reserve candidates for other TNC firmware:

```
FALLBACK_WRITE  = [af01, ff02, ffe2]
FALLBACK_NOTIFY = [af02, ff01, ffe1]
```

**Resolution of characteristics** (`_resolve_chars`:

After connecting, the program lists all the services / characteristics of the device, looking for:  
- characterization writing (`write`or`write-without-response`)  
- notify characteristics`notify`)

prioritize familiar UUIDs`af01`/`af02`APRS-based`af00`Otherwise, first.
suitable from other services (for compatibility with firmware TD-H9 / SPP-versions).
Each feature found is recorded in per-device configuration  
`devcfg_<address>.json`(through)`mru_store`) with a human-readable description of  
`gatt_info` (`used_in_app`Notes the channels used).

**Transfer** (`_write_async`:

selects the response mode according to the characteristics:

```
if "write-without-response" in props and "write" not in props:
    use_response = False      # af01 — без ответа
else:
    use_response = "write" in props
```

writer`bytearray(data)`(KISS frame ready).

**Reception.** (`start_notify` → `_on_notify`) gives raw bytes to colback`on_rx`.

### 2.3 KISS protocol`kiss.py`)

Fully complies with the specification and APK:

| Name. | byte | Appointment |
| --- | --- | --- |
| `FEND` | `0xC0` | frame-line |
| `FESC` | `0xDB` | escape-prefix |
| `TFEND` | `0xDC` | screened |
| `TFESC` | `0xDD` | screened FESC |

**Frame assembly** `frame_kiss(ax25, port=0, cmd=CMD_DATA)`:

```
cmd_byte = ((port & 0x0F) << 4) | (command & 0x0F)
body = bytes([cmd_byte]) + kiss_escape(ax25)
return bytes([FEND]) + body + bytes([FEND])
```

**Parser** `KISSParser`incremental, processes bytes one by one
?`feed`) correctly experiences an escape sequence gap between TCP/BLE
In portions. On the completed frame, calls`on_frame(port, command, payload)`.
where`payload`De-escaped bytes AX.25.

### 2.4 AX.25 APRS (APRS)`ax25. py`)

**AX.25 address**- 7 bytes:

* `decode_ax25(data)`- analysis of the binary UI frame.
* `encode_ax25_text(text)`assembling a binary UI frame from text.
* `to_aprs_text(data)`If the binary frame decodes the`SRC>DST,..:info`;
  Otherwise returns raw bytes as ASCII (the case of “the radio has already given the text”).

The result: any received byte stream is reliably converted into readable
APRS-text without Krakozabra (`\ufffd`).

### 2.5 Incoming stream (radio → PC)

```
BLE notify (af02) → _on_ble_rx → KISSParser.feed
    → _on_kiss_frame(port, cmd, payload)
        → to_aprs_text(payload)  -> читаемый APRS-текст
        → parse_aprs → to_multiline() -> [RX] ... (лог)
        → broadcast(raw) на все TCP-серверы (KISS/AGW/APRS-IS)
        → _igate_radio_rx(text) — IGate, правило (b), радио → сеть
```

Each received package is logged into`rx_<addr>_<date>.json`and sent out
Connected clients of TCP servers, each of which packs it in its own way
Protocol (KISS-bytes / AGW 36-byte header / text APRS).

### Outbound stream (PC → radio)

Three sources, one way to the BLE radio:

| Source | Processing |
| --- | --- |
| Send button (From/To/Comment or Raw) | `_build_frame()` → `encode_ax25_text` → `frame_kiss` → `ble.send_raw` |
| KISS TCP client | `_client_tx(ax25)` → `frame_kiss` → `ble.send_raw` |
| AGW TCP client | `_client_tx(ax25)`(extract from 36-byte header) |
| APRS-IS client | `_client_tx_aprs(text)` → `encode_ax25_text` → `frame_kiss` → `ble.send_raw` |
| IGate (network → radio) | `_igate_to_radio(bytes)` → `frame_kiss` → `ble.send_raw` |

All paths eventually do`frame_kiss(ax25) и`ble.send raw (kiss frame)`. Каждый
уходящий кадр пишется в`Journal and History (MRU).

### 2.7 TCP servers (external APRS applications)

In the GUI tab "Server & IGate" you can select the mode:

* **Binary Kiss** (`kiss_tcp_server.py`Port 8023: Customer exchanges raw materials
  KISS frames, as with serial TNC over the network. Incoming radio packets
  wrap`frame_kiss`and sent to all customers (`broadcast`).
* **AGW (AGWPE)** (`agw_server.py`Port 8000 is compatible with Dire Wolf. 36-byte
  headline:`portx(1) res(3) datakind(1) res(1) pid(1) res(1) from(10) to(10)
  len(4 LE) reserved(4)`. Processing TX.`V`/`M`(UI frames, 1 byte number)
  DJ + 10 bytes per DJ + info,`K`(raw AX.25) and monitor`U`for RX.
* **APRS-IS** (`aprsis_server.py`Port 14580: Text protocol. Login.`user CALL pass PASSCODE vers ... filter ...`It is necessary to check passcode.
  by algorithm`compute_passcode`Unauthorized - read-only, lines`#`They don't go to the radio. Incoming text from the client is encoded in AX.25 and goes into the
  radio.

### 2.8 IGate (radio и APRS-IS) and settings.json

`igate.py`Independent IGate module:

* **Network → radio (rule a)** (`_should_gate_to_radio`): the package is on the radio,
  only if:
* callsign`<IGATE_NAME>`present on the way (`path`and
* contains`qAR`/`qAO`(if the respective flags)`check_no_qar`/
  `check_no_qao`included, and
* contains`TCPIP`if the flag`check_tcpip`on.
  Not past - logged as`net --skip-> radio`.
* **Radio → Network (rule b)** (`radio_rx`): added to the path`,qAR,<IGATE_NAME>`.

IGate client login:

```
user <APRSIS_CLIENT> pass <PASSCODE> vers TDH9KissIGate v1.0 filter <FILTER>
```

The default filter is`d/<IGATE_NAME>*`(to the addressee, without SSID). If the paragraph`Filter`No filter is given - it is substituted`d/<без SSID>*`for example`DKXCE-11` → `d/DKXCE*`).

**Live application of settings:**Each packet reads the current flag through`settings_getter` (`_igate_live_settings`), therefore switching checkboxes
(Require TCPIP / Reject qAR / Reject qAO) applies instantly, without restarting.

**`settings.json`**stored in the module folder`tidradio_kiss/settings.json`. Contains.`aprsis_client`, `igate_name`, `passcode`, `server`, `port`, `filter`, `enabled`,
`check_tcpip`, `check_no_qar`, `check_no_qao`. It is saved automatically when
push**Start.**When the window is closed (the Save button is no longer available).

Example:

```
{
  "aprsis_client": "DKXCE-10",
  "igate_name": "DKXCE-11",
  "passcode": 10986,
  "server": "localhost",
  "port": 12012,
  "filter": "d/DKXCE*",
  "enabled": true,
  "check_tcpip": false,
  "check_no_qar": true,
  "check_no_qao": false
}
```

**GUI IGATE:**button**Start/stop**(toggle), no separate Stop and Save.
At the start, the current shape values are applied and stored. IGate's log is spelled
common-window`RX/TX Log`.

### Interface (GUI)

* `main.py`builder`ttk.Notebook`with two tabs:
* tab**"TNC & TX"**Select the device (Scan/Connect/Disconnect)
  History, status, Transmit block (From/To/Comment + Send + Raw frame)
* tab**"Server & IGate"**Server (Port/Mode/Start/Preset)
  IGate form (APRSIS CLIENT / IGATE NAME / Passcode / Server)
  Port / Filter / Flags / Start-Stop
* bottom, under the tabs - a common window**"RX/TX Log"**(emphasis + copying)
  Ctrl+C, Clear button.

All logging (`[RX]`, `[TCP <- client]`, `[IGate ...]`, `[BLE]`) goes into this
window.

---

## 4. Outline data flow pattern

```
                ┌─────────────────────────────────────────────┐
                │  TIDRadio TD-H9  (встроенный TNC + AFSK)     │
                │            эфир 1200 бод ⇄ AX.25             │
                └──────────────────────┬──────────────────────┘
                     BLE GATT service 0000af00
                TX write af01  │  RX notify af02 (KISS)
                ┌──────────────▼──────────────┐
                │        ble_radio (bleak)     │
                │   asyncio-loop в потоке      │
                └──────────────┬──────────────┘
                 send_raw(kiss)││on_rx(kiss bytes)
             ┌─────────────────▼│──────────────────┐
             │               kiss.py               │
             │  frame_kiss (FEND+FEND) / KISSParser│
             └─────────────────┬──────────────────┘
             ┌─────────────────▼──────────────────────────────┐
             │                     main.py                    │
             │  ax25.encode/decode → to_aprs_text             │
             └───────────┬──────────┬───────────┬─────────────┘
        KISS TCP 8023    │ AGW 8000 │ APRS-IS   │  IGate (radio⇄APRS-IS)
        (клиент KISS)    │ (YaAC…)  │ 14580     │  net⇄radio rules a/b
        └────────────────┴────┬─────┴─────┬─────┘
                    внешние APRS-приложения / APRS-IS сеть
```

---

## 5. Key constants in one table

| Parameter | Meaning. |
| --- | --- |
| SPP UUID (classic, in APK) | `00001101-0000-1000-8000-00805F9B34FB` |
| APRS BLESS service | `0000af00-0000-1000-8000-00805f9b34fb` |
| APRS BLE write (TX) | `0000af01-0000-1000-8000-00805f9b34fb` |
| APRS BLE notify (RX) | `0000af02-0000-1000-8000-00805f9b34fb` |
| Fallback write | `0000af01`, `0000ff02`, `0000ffe2` |
| Fallback notify | `0000af02`, `0000ff01`, `0000ffe1` |
| General (not APRS) service (APK) | `0000ff00-...` |
| KISS FEND | `0xC0` |
| KISS CMD DATA | `0x00` |
| KISS FESC/TFEND/TFESC | `0xDB` / `0xDC` / `0xDD` |
| KISS team classes | `0x01 TXDELAY, 0x02 PERSIST, 0x03 SLOTTIME, 0x04 TXTAIL, 0x05 FULLDUPLEX, 0x06 SETHARDWARE, 0xFF RETURN` |
| AX.25 UI control/PID | `0x03` / `0xF0` |
| TCP server ports | KISS 8023 · AGW 8000 · APRS-IS 14580 |
| IGate-client | APRS-IS (default)`d/<IGATE_NAME>*`), settings. json in the module folder |

---