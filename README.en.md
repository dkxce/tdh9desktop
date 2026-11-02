# TIDRadio TD-H9 · APRS KISS TNC BLE

[RU](README.md) | [EN](README.en.md) | [Releases](https://github.com/dkxce/tdh9desktop/releases)

The program turns the radio **TIDRadio TD-H9** (and compatible firmware with BLE-service)
Odmaster) in **KISS-TNC modem over Bluetooth Low Energy**. The radio acts as
hardware TNC: it modulates / demodulates the AFSK signal 1200 baud, and the program
It exchanges ready-made KISS/AX.25 frames over BLE. On top of that, the program.
Elevates TCP servers for external APRS applications and built-in IGate.

-

##1. What is it and why?

TIDRadio TD-H9 radios do not emit sound (AFSK) outwards like conventional TNC radios.
Instead, a built-in **TNC** that communicates with the outside is running inside.
Bluetooth device. This allows the PC to go to APRS air without
audio cables and a separate TNC device.

The task of the program is to make such a radio a full-fledged TNC modem with which
**Any** APRS applications (maps, UI clients, digiters/igate) can work.

``
APRS text frame (SRC>DST,PATH:info)
Encode ax25
¶
Binary AX.25 frame (addresses of 7 bytes, control, PID, info)
Kiss escape + FEND
¶
KISS frame: [0xC0][port:cmd][escape(AX.25)][0xC0]
BLE GATT write/notify
¶
TIDRadio radio (AFSK 1200 baud and back)
``

-

##2. Opportunities

**BLE radio connection** as KISS-TNC (scanning, device history)
Auto-connection via MAC from memory.
- **KISS-protocol exchange** (borders `0xC0`, escape `0xDB`/`0xDC`/`0xDD`).
**Binary AX.25** ный text APRS: reception and transmission, neat parsing without
"Cracofish."
**Three TCP servers are selected simultaneously by:
**Binary KISS** (Port 8023) is a raw KISS stream for TNC clients.
**AGWPE** (port 8000) – 36-byte headers, Dire Wolf format
**APRS-IS** (port 14580) is a text protocol with passcode verification.
* Built-in IGate** – radio щий APRS-IS (incoming and outgoing gateways)
Filtering rules, autosave settings).
**Sending APRS** from GUI: From/To/Comment fields or raw frame, history (MRU).
**RX/TX log** with highlighting and copying, vertical scrolling.
**List of connected clients** Scrollable TCP servers.
**Received/sent packet logs** in JSON (`packet log`), device history
and messages ("mru store").

-

##3. Requirements

Python **3.10+** (GUI on tkinter) or 3.11+
The **bleak** library for BLE ('pip install bleak').
TIDRadio TD-H9 (or firmware with APRS **0000af00**)
Windows / macOS / Linux (tested on Windows)

-

##4. Quick start.

*
pip install bleak
Python main. py
``

1. Launch 'python main.py'.
2. In the tab **"TNC & TX"** click **Scan** - select the radio from the list,
Press **Connect.
3. Connect and make sure there are services (Write/Notify) in the log.
4. In the tab **"Server & IGate"** select server mode and port, click
**Start server**.
5. Connect an external APRS application (see Compatibility section).
6. To transfer the packet, fill in the Transmit fields and press **Send**, or
Send it through a connected application.

-

##5. Structure of the project

| File | Role |
|---|---|
| `main.py' | GUI (Tk), orchestration, two tabs, log RX/TX |
| `ble radio.py` | BLE transport (bleak, asyncio in flow), performance resolution |
| `gatt info.py` | service description/characteristics of BLE GATT |
| `kiss.py' | KISS protocol (packaging/unpacking) |
| `ax25.py' | binary AX.25   readable APRS text |
| `aprs parser.py` | analysis of the contents of the APRS package (position, message, etc.)
| `kiss tcp server.py' | Binary KISS TCP server (8023) |
| `agw server.py' | AGWPE / Dire Wolf (8000) TCP server
| `aprsis server.py' | APRS-IS TCP server (14580)
| `igate.py` | built-in IGate (radio о APRS-IS), settings |
| `mru store.py' | history of devices and messages
| `packet log.py` | accepted/sent packet logs |
| `aprsis test.py`, `igate test.py` | test clients (listener/IGate sender) |
| `settings.json` | IGate settings (in the module folder) |

-

#6. BLE (Services and Specifications)

The program uses the APRS service from the Odmaster application:

| Appointment | UUID |
|---|---|
| APRS service | `0000af00-0000-1000-8000-00805f9b34fb' |
| TX (write) | `0000af01-0000-1000-8000-00805f9b34fb' (write-without-response) |
| RX (notify) | `0000af02-0000-1000-8000-00805f9b34fb' |

There are backup candidates for other firmware ('ff02'/'ffe2' for recording).
'ff01'/'ffe1' for notify. The resolution of characteristics occurs automatically when
connection; the found set is stored in `devcfg <address>. json for speed
reconnection.

-

##7. TCP servers

You can run a single server at the same time. The mode is selected in the GUI and through
presets:

| Default Port mode | Protocol | What is useful |
|---|---|---|----|
| `Binary KISS` | 8023 | raw KISS frames | hardware/software TNC clients |
| `AGW (AGWPE)` | 8000 | 36-byte AGW headers, Dire Wolf format | UISS, UI-View32, AGW clients |
| `APRS-IS` | 14580 | text APRS + login/passcode | network APRS clients and tests |

Incoming radio packets are sent to all connected customers in their
format (KISS bytes / AGW monitor / APRS-IS strings). Outgoing client staff
They are encoded in AX.25 and sent to the BLE radio.

## Binary KISS (kiss tcp server.py)

The client sends and receives raw KISS frames just like a serial TNC over the network.
No login. All customers can transfer.

### AGWPE (agw server.py)

Compatible with AGWPE TCP/IP and **Dire Wolf** (36-byte)
headline. Supports typical AGW requests:
- `R` version (AGWPE 2005/127);
G`/`g` - information about the port and its facilities;
"X" - registration of the call sign;
- `m`/`k` - inclusion of monitoring/raw personnel;
- `V`/`M` - transmission of UI-frame (with / without diga); `K` - raw AX.25.

Reception: Sends 'U' monitor frames in Dire Wolf format
1:Fm SRC to DST Via ... <UI pid=. Len=.. >[HH:MM:SS]"". It's tested with
UISS clients and AGW clients.

### APRS-IS (aprsis server.py)

The APRS-IS text protocol. Client logs in line
'user Callsign pass Passcode vers ... filter ...'. ** Passcode is mandatory** and
is verified by the standard APRS-IS algorithm; an incorrect passcode gives only
Reading the ether (unverified). "#" comments are not broadcast on the radio.

-

##8. Built-in IGate

`igate.py` is an independent bridge between APRS radio and APRS-IS:

**Network → radio:** The packet only goes on the air if there is one in its path.
<IGATE NAME> and it passes flags (Reject qAR/qAO, Require TCPIP).
- **Radio → Network:** Adds `,qAR, <IGATE NAME> to the path and the packet goes to
APRS-IS.
- Customer login:
`user <APRSIS CLIENT> pass <PASSCODE> vers TDH9KissIGate v1.0 filter <FILTER>`
The default filter is `d/<IGATE NAME>*' (without SSID).
Flags are applied **on-the-fly** (without restart) thanks to live-getter.
- The settings are stored in 'settings'. json′ near the module and are stored at
Press **Start** and close the window.
In the GUI, one button is **Start/Stop**.

-

##9. Compatibility with APRS applications

The program transmits the radio through the **three** interface, so it works with it.
A wide range of desktop APRS applications.

###UISS

- Connects to the program as a **AGW engine (AGWPE TCP/IP)**.
- In UISS, select TNC/communication: **AGW Packet Engine, TCP/IP**, specify port **8000**
(AGW (AGWPE) server).
UISS uses AGW version requests, port and monitoring; transmission is supported
and receiving packets, positions and messages.

###UI-View32

Connection via **AGWPE TCP/IP** (port 8000)
In the UI-View32 settings, specify the interface **AGWPE**/**AGW TCP/IP**, host
`127.0.0.1' (or where the program is running), port `8000'.
- Receive all ether through the AGW-monitor and transmission through digpiters.

##APRSIS32

- Connects via **TCP/IP** either as **AGW** (port 8000), or (in some cases)
assemblies) as KISS-TNC.
Specify **AGW connection type and server address; APRSIS32 will send AGW frames
and take monitoring.
It can also operate via **Binary KISS** (port 8023) as a conventional TCP-TNC.

## KMZViewer (https://github.com/dkxce/KMZViewer)

- Map Viewer App/KMZ of the author of the project; receives APRS stream
The interface the program provides (KISS/AGW/APRS-IS).
Configure the APRS source in KMZViewer to the local program server
(e.g. APRS-IS `127.0.0.1:14580' or KISS).

##APRSWin (https://github.com/dkxce/APRSWin)

Windows-APRS client; connects to the program as a TNC over **TCP** in mode
**Binary KISS** (port 8023) or **AGW** (port 8000).
- Uses reading of the entire ether through the KISS/AGW monitor and transmission from the map.

### APRSAir (https://github.com/dkxce/APRSAIR)

APRS-client / author's program; also works through local KISS / AGW / APRS-IS
program interface.

**Short:** All listed programs connect externally via TCP.
>> If they can **AGWPE**, use AGW (AGWPE) mode (port 8000).
> if you are waiting for **KISS-TNC over TCP** - "Binary KISS" mode (port 8023);
> and any APRS-IS-compatible mode is 'APRS-IS' (port 14580).

-

##10. Data flow principle

``
TIDRadio TD-H9 (TNC + AFSK 1200)
BLE GATT 0000af00 (write af01 / notify af02)
ble radio.py (bleak, asyncio)
KISS frames
kiss.py . ax25.py . aprs parser. py
¶
main. py
─ ─ ─ ─ ─   ─ ─ ─ ─ ─   ─ ─ ─ ─ ─  
KISS(8023) AGW(8000) APRS-IS(14580) IGate(APRS-IS radio)
─ ─ ─ ─ ─   ─ ─ ─ ─ ─   ─ ─ ─ ─ ─  
External APRS clients / APRS-IS network
``

-

#11. KISS and AX.25 format (short reference)

- **KISS:** `FEND=0xC0`, `FESC=0xDB`, `TFEND=0xDC`, `TFESC=0xDD`;
0x01 TXDELAY, 0x02 PERSIST, 0x03 SLOTTIME, 0x04 TXTAIL,
`0x05 FULLDUPLEX', `0x06 SETHARDWARE', `0xFF RETURN'.
**AX.25 UI:** control `0x03', PID `0xF0'; addresses 7 bytes (6 characters)
shifted to the left + SSID / flag), the call sign in the upper / Latin register.
The program itself encodes the text in binary AX.25 and back, so customers
There's a lot of APRS text.

-

##12. License and authorship

Program - **authored project dkxce** (c) https://github.com/dkxce.
Written for compatibility with TIDRadio TD-H9.

-

##13. Screenshots

<img src="images/screen1.png"/>
<img src="images/screen2.png"/>

-

**Author**: [dkxce](https://github.com/dkxce)
**Android**: [dkxce/tdh9android](https://github.com/dkxce/tdh9android)
**Desktop**: [dkxce/tdh9desktop](https://github.com/dkxce/tdh9desktop)
**Manual**: [dkxce/Tidradio-TD-H9](https://github.com/dkxce/Tidradio-TD-H9)