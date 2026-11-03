APRS via BLE: analysis of the Odmaster application and implementation of the TNC modem in Python

[RU](README.md) | [EN](README.en). md)

**APK:** `Odmaster 2.6.4.apk'
** Decompilation APK:** `Ajadx-gui`
** APRS package at APK:** `com.tid.aprs'

This document contains a complete description of how the TNC modem works through
Bluetooth: First – as done in the **Odmaster** stock app
decompiled APK), then how it is implemented in Python**.
At the end is a comparison, a data flow chart, and a table of key constants.

-

##0. What is a TNC modem via BLE?

On the radio **TIDRadio TD-H9** running hardware **TNC** (Terminal Node Controller):
It modulates / demodulates the AFSK signal 1200 baud and exchanges with the external
device (phone/PC) ** ready frames** according to the protocol **KISS**.

The order of the data is always this:

``
APRS text frame (SRC>DST,PATH:info)
Encode ax25
¶
Binary AX.25 frame (addresses aligned with 7 bytes, control, PID, info)
Kiss escape + FEND
¶
KISS frame: [0xC0][port:cmd][escape(ax25)][0xC0]
BLE GATT write/notify
¶
TIDRadio radio (AFSK on air and back)
``

BLE-exchange is just a transport for KISS-frames: write-characteristics for
Transmission to the radio (TX), notify-characteristics for reception from the radio (RX).

-

##1. As done in APK Odmaster

Odmaster uses the 'com.tid.aprs' module.
Talk to the radio via Bluetooth.
Data is KISS on top of AX.25.
If necessary, IGate relay over TCP.

1.1 Two independent Bluetooth tracks

| Path | Mechanism | Key classes APK |
|---|---|---|
| 1. Classic Bluetooth | SPP RFCOMM, UUID `00001101-0000-1000-8000-00805F9B34FB` | `BluetoothTnc.java`, `AprsBlueActivity.java` |
BLE GATT | library `cn.com.heaton.blelibrary`, service `0000af00-0000-1000-8000-00805f9b34fb` | `AprsSendMessageNetworkVM.java`, `AprsVM.java` |
| 3. Radio (AFSK) | AFSK sound modulation/demodulation | `AprsAfskSendFragment.java`, `AprsAfskListFragment.java`, `afsk/*` |
| 4. Internet (IGate) | TCP + EasySocket | `AprsNetworkTranFragment.java', `MessageProtocol.java'

##1.2 Classic Bluetooth (SPP RFCOMM)

Background stream `BtSocketThread` is connected via SPP:

Java
private UUID SPP = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
...
BluetoothSocket s = tnc.createRfcommSocketToServiceRecord(SPP)
s.connect(); // BluetoothTnc.java:133-135
``

Sending a packet to the radio:

Java
OutputStream out = socket.getOutputStream()
out.write(Kiss.FEND); // 0xC0
out.write(Kiss.CMD DATA); // 0x00
out.write(aPRSPacket.toAX25Frame()); // Binary AX. 25.
out.write(Kiss.FEND); // 0xC0
out.flush();
``

Reception - analysis of the KISS stream:

`FEND=0xC0' boundary, `FESC=0xDB' escape,
`TFEND=0xDC`/`TFESC=0xDD`; FEND calls `Parser.parseAX25(...) and
`Parser.parse(...)' (line `BluetoothTnc.java:209-247').

### 1.3 BLE GATT

Library `cn.com.heaton.blelibrary`
(classes `Ble`, `BleDevice`, `BleWriteCallback`, `BleNotifyCallback`), wrapper `BluUtils`.

**UUID for APRS (BLE GATT):**

| Appointment | UUID |
|---|---|
| Service APRS | `0000af00-0000-1000-8000-00805f9b34fb' |
| Characteristic TX (write) | `0000af01-0000-1000-8000-00805f9b34fb' |
| Characteristic RX (notify) | `0000af02-0000-1000-8000-00805f9b34fb' |

Sending:

Java
ByteArrayOutputStream baos = new ByteArrayOutputStream();
baos.write (BluetoothTnc.Kiss.FEND)
baos.write (BluetoothTnc.Kiss.CMD DATA)
baos.write(bArr); // AX.25-frame
baos.write (BluetoothTnc.Kiss.FEND)
BluUtils.getInstance().getmBle().writeByUuid()
device, baos.toByteArray(),
UUID.fromString("0000af00-0000-1000-8000-00805f9b34fb")
UUID.fromString("0000af01-0000-1000-8000-00805f9b34fb"), // write char
callback);
``

Reception (notify):

Java
BluUtils.getInstance().getmBle().enableNotifyByUuid().
device, true,
UUID.fromString ("0000af00-0000-1000-8000-00805f9b34fb"),
UUID.fromString ("0000af02-0000-1000-8000-00805f9b34fb"),
new BleNotifyCallback<BleDevice>()
void onChanged(BleDevice d, BluetoothGattCharacteristic c)
String s = AprsByteProcessor.getKissString(c.getValue()).trim();
if (TextUtils.isEmpty(s)| !s.contains(">")) return;
APRSPacket packet = Parser.parse(s)
AprsStringUtil.addKiss(packet); // list of up to 50 packages
handler.sendMessage(...)
}
}
``

###1.4 Common (not APRS) UUID radios 'BluUtils.java'

| Appointment | UUID |
|---|---|
| Service radios | `0000ff00-0000-1000-8000-00805f9b34fb' |
| Write (commands) | `0000ff02-0000-1000-8000-00805f9b34fb' |
| Read | `0000ff01-0000-1000-8000-00805f9b34fb' |
| Notify (DX) | `0000ff21-0000-1000-8000-00805f9b34fb' |
| Write (DX) | `0000ff22-0000-1000-8000-00805f9b34fb' |

`BluUtils.init':

Java
Ble.options()
.setUuidService ("0000ff00-...")
.setUuidWriteCha("0000ff02-...")
.setUuidReadCha ("0000ff01-...")
.create(context, ...);
``

### 1.5 Internet / IGate in APK

When `isRadioToNet() && isAutoConnect()' the received packet is published in RxBus
(‘BluetoothTnc.java:35’, ‘AprsMainActivity.java:210-216’) and goes online via
TCP + EasySocket. The network uses **text** APRS (`AprsPacket.formatLogin')
+ position) on TCP with 1024-byte read protocol.

-

##2. How it is implemented in Python (TDH9KISS)

TDH9KISS repeats the BLE GATT path (service 'af00', write 'af01', notify)
`af02`), but adds on top of the mini servers (KISS/AGW/APRS-IS) and the built-in IGate,
So that the radio can work with external APRS applications and the network.

###2.1 Modules

| Module | Role |
|---|---|
| `main.py' | GUI (Tk), orchestration, two tabs, log RX/TX |
| `ble radio.py` | BLE transport: scanning, connecting, reading GATT services, sending/receiving personnel |
| `gatt info.py` | human-readable service descriptions/GATT characteristics |
| `kiss.py` | KISS protocol: escape/unescape, frame parser |
| `ax25.py' | encoding/decoding binary AX.25   text APRS |
| `aprs parser.py` | analysis of the contents of the APRS package (position, message, etc.)
| `kiss tcp server.py' | KISS TNC over TCP (port 8023) |
| `agw server.py` | AGWPE-compatible server (port 8000, 36-byte headers) |
| `aprsis server.py` | APRS-IS-compatible server (port 14580), passcode server verification |
| `igate.py` | IGate client (radio а APRS-IS), gateway rules, settings. json |
| `mru store.py`, `packet log.py` | device/message history and reception/transmission logs |
| `aprsis test.py`, `igate test.py` | Test scripts (listener/IGate sender) |

### 2.2 BLE transport ('ble radio.py')

The library **bleak** (asyncio) is used. All Asyncio is performed separately.
background flow ("ble-loop"), and results come to the GUI through colbacks and queues.

Key UUIDs:

Python
SERVICE APRS = "0000af00-0000-1000-8000-00805f9b34fb" # Service APRS
CHAR WRITE = "0000af01-0000-1000-8000-00805f9b34fb" # TX, write-without-response
CHAR NOTIFY = "0000af02-0000-1000-8000-00805f9b34fb" # RX, notify
``

There are reserve candidates for other TNC firmware:

Python
FALLBACK WRITE = [af01, ff02, ffe2]
FALLBACK NOTIFY = [af02, ff01, ffe1]
``

**Performance resolution** (` resolve chars'):

After connecting, the program lists all the services / characteristics of the device, looking for:
Write-without-response ("write")
- notify-characteristics ("notify"),

with the priority of familiar UUID `af01`/`af02` in APRS-service `af00`, otherwise - the first
suitable from other services (for compatibility with firmware TD-H9 / SPP-versions).
Each feature found is recorded in per-device configuration
`devcfg <address>.json` (via `mru store`) with human-readable description
`gatt info` (`used in app` marks the channels used).

**Transmission** (' write async'):

selects the response mode according to the characteristics:

Python
if "write-without-response" in props and "write" not in props:
use response = False # af01
else:
use response = "write" in props
``

Writes 'bytearray(data)' (ready KISS frame).

** Reception (‘start notify’ → ‘ on notify’) gives raw bytes to the colback ‘on rx’.

### 2.3 KISS protocol (`kiss.py')

Fully complies with the specification and APK:

| Name | Byte | Purpose |
|---|---|---|
| `FEND' | `0xC0' | Frame |
| `FESC' | `0xDB' | escape prefix |
| `TFEND' | `0xDC' | screened FEND |
| `TFESC' | `0xDD' | screened by FESC |

**Frame kiss (ax25, port=0, cmd=CMD DATA)

Python
cmd byte = ((port & 0x0F) << 4) | (command & 0x0F)
body = bytes([cmd byte]) + kiss escape(ax25)
return bytes([FEND]) + body + bytes([FEND])
``

** Parser** 'KISSParser' - incremental, processes bytes one by one
("feed") correctly experiences escape sequence gap between TCP/BLE
In portions. On the completed frame, calls "on frame" (port, command, payload).
where ‘payload’ is de-escaped bytes AX.25.

### 2.4 AX.25 APRS ('ax25.py')

**AX.25 address** - 7 bytes:

Decode ax25(data) is a binary UI frame.
* encode ax25 text(text) assembling a binary UI frame from text.
- `to aprs text(data)` - if the binary frame - decodes in `SRC>DST, ...:info`;
Otherwise returns raw bytes as ASCII (the case of “the radio has already given the text”).

The result: any received byte stream is reliably converted into readable
APRS text without Krakozabra (`\ufffd`).

### 2.5 Incoming stream (radio → PC)

``
BLE notify (af02) →  on ble rx → KISSParser.feed
on kiss frame(port, cmd, payload)
to aprs text(payload) -> APRS-readable text
parse aprs → to multiline() -> [RX] ... (log)
broadcast(raw) to all TCP servers (KISS/AGW/APRS-IS)
igate radio rx(text) – IGate, rule (b), radio → network
``

Each received packet is logged in `rx <addr> <date>. json and sent to all
Connected clients of TCP servers, each of which packs it in its own way
Protocol (KISS-bytes / AGW 36-byte header / text APRS).

### 2.6 Outbound stream (PC → radio)

Three sources, one way to the BLE radio:

| Source | Processing |
|---|---|
| Send button (From/To/Comment or Raw fields) | ` build frame()` → `encode ax25 text` → `frame kiss` → `ble.send raw` |
| KISS TCP client | ` client tx(ax25)' → `frame kiss' → `ble.send raw' |
| AGW TCP client | ` client tx(ax25)' (extract from 36-byte header) |
| APRS-IS client | ` client tx aprs(text)' → `encode ax25 text' → `frame kiss' → `ble.send raw' |
| IGate (network → radio) | ` igate to radio(bytes)` → `frame kiss` → `ble.send raw` |

All paths are frame kiss(ax25) and ble.send raw(kiss frame). Everyone.
The outgoing frame is written in a 'tx ...' journal and in history (MRU).

### 2.7 TCP servers (external APRS applications)

In the GUI tab "Server & IGate" you can select the mode:

- **Binary KISS** (`kiss tcp server.py`, port 8023): customer exchanges raw
KISS frames, as with serial TNC over the network. Incoming radio packets
They wrap 'frame kiss' and send it to all customers ('broadcast').
**AGW (AGWPE)** (‘agw server.py’ port 8000): compatible with Dire Wolf. 36-byte
Title: `portx(1) res(3) datakind(1) res(1) pid(1) res(1) from(10) to(10)
len(4 LE) reserved(4)'. Processes TX `V`/`M` (UI frames, 1 byte number)
Dji + 10 bytes per Dji + info, 'K' (raw AX.25) and 'U' monitor for RX.
**APRS-IS** (`aprsis server.py` port 14580): text protocol. Login.
'user call pass pass passcode vers ... filter ...', must check passcode
by algorithm ("compute passcode"), unauthorized - read-only, strings "#"
They don't go to the radio. Incoming text from the client is encoded in AX.25 and goes into the
radio.

### 2.8 IGate (radio ) APRS-IS) and settings.json

`igate.py' is an independent IGate module:

- **Network → radio (rule a)** (' should gate to radio'): packet is streamed into radio
only if:
1. the call sign <IGATE NAME> is present in the path (`path`), and
2. does not contain `qAR`/`qAO` (if the corresponding flags `check no qar`/)
`check no qao' is included, and
3. contains `TCPIP' (if the `check tcpip' flag is enabled).
Not past - logged as "net -skip-> radio".
- **Radio → Network (rule b)** ('radio rx'): to the path added ',qAR, <IGATE NAME>'.

IGate client login:

``
user <APRSIS CLIENT> pass <PASSCODE> vers TDH9KissIGate v1.0 filter <FILTER> >>
``

The default filter is `d/<IGATE NAME>*' (without SSID). If the paragraph
`Filter` is not specified filter - is substituted `d/< without SSID>*` (e.g.
`DKXCE-11` → `d/DKXCE*`.

**Live application settings:** Each packet reads the current flags through
`settings getter` (` igate live settings`), so switching checkboxes
(Require TCPIP / Reject qAR / Reject qAO) applies instantly, without restarting.

**'settings. json`** is stored in the folder of the module `tidradio kiss/settings. json. Contains.
`aprsis client`, `igate name`, `passcode`, `server`, `port`, `filter`, `enabled`,
`check tcpip', `check no qar', `check no qao'. It is saved automatically when
Press **Start** and close the window (the Save button is no longer available).

Example:

"Json"
{
"aprsis client": "DKXCE-10",
"igate name": "DKXCE-11",
"passcode": 10986 .
"server": "localhost",
"port": 12012 .
"filter": "d/DKXCE*",
"enabled": true,
"check tcpip": false,
"check no qar": true,
"check no qao": false
}
``

**GUI IGate:** One button **Start/Stop** (toggle), no separate Stop and Save.
At the start, the current shape values are applied and stored. IGate's log is spelled
In the general window "RX / TX Log".

### 2.9 Interface (GUI)

Main.py builds ttk.Notebook with two tabs:
- tab **"TNC & TX"** - device selection (Scan/Connect/Disconnect,
History, status, Transmit block (From/To/Comment + Send + Raw frame)
- tab **"Server & IGate"** - server (Port/Mode/Start/Presets, list)
IGate form (APRSIS CLIENT / IGATE NAME / Passcode / Server)
Port / Filter / Flags / Start-Stop
- at the bottom, under tabs - a common window ** "RX / TX Log"** (allocation + copying)
Ctrl+C, Clear button.

All logging ("[RX]", "[TCP <- client]", "[IGate ...]", "[BLE]") goes into this.
window.

-

##4. Outline data flow pattern

``
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ?
TIDRadio TD-H9 (built-in TNC + AFSK)
versus ether 1200 bod   AX.25
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  
BLE GATT service 0000af00
TX write af01 versus RX notify af02 (KISS)
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  
versus ble radio (bleak) versus
Asyncio-loop in the stream
─ ─ ─ ─ ─ ─ ─   ─ ─ ─ ─ ─ ─  
send raw(kiss) ♥on rx(kiss bytes)
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  
versus kiss.py versus
versus frame kiss (FEND+FEND) / KISSParser→
─ ─ ─ ─ ─ ─ ─ ─ ─   ─ ─ ─ ─ ─ ─ ─ ─  
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  
versus main.py versus
ax25.encode/decode → to aprs text
─ ─ ─ ─ ─ ─   ─ ─ ─ ─ ─   ─ ─ ─ ─ ─   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  
KISS TCP 8023 versus AGW 8000 versus APRS-IS versus IGate (radio)APRS-IS)
(KISS client) versus (YaAC...) versus 14580 versus net rulesradio rules a/b
─ ─ ─ ─ ─ ─ ─ ─   ─   ─ ─   ─ ─   ─ ─   ─ ─  
External APRS applications / APRS-IS network
``

-

##5. Key constants in one table

| Parameter | Value |
|---|---|
| SPP UUID (classic, in APK) | `00001101-0000-1000-8000-00805F9B34FB' |
| APRS BLE service | `0000af00-0000-1000-8000-00805f9b34fb' |
| APRS BLE write (TX) | `0000af01-0000-1000-8000-00805f9b34fb' |
| APRS BLE notify (RX) | `0000af02-0000-1000-8000-00805f9b34fb' |
| Fallback write | `0000af01', `0000ff02', `0000ffe2' |
| Fallback notify | `0000af02', `0000ff01', `0000ffe1' |
| General (not APRS) service (APK) | `0000ff00-...' |
| KISS FEND | `0xC0' |
| KISS CMD DATA | `0x00' |
| KISS FESC / TFEND / TFESC | `0xDB` / `0xDC` / `0xDD' |
| KISS team classes | `0x01 TXDELAY, 0x02 PERSIST, 0x03 SLOTTIME, 0x04 TXTAIL, 0x05 FULLDUPLEX, 0x06 SETHARDWARE, 0xFF RETURN' |
| AX.25 UI control / PID | `0x03' / `0xF0' |
| TCP server ports | KISS 8023 · AGW 8000 · APRS-IS 14580 |
| IGate client | APRS-IS (default `d/<IGATE NAME>*), settings. json in the folder of the module |

-
