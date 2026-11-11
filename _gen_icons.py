# -*- coding: utf-8 -*-
"""Generate aprs_icons_data.py with base64-encoded APRS icons."""
import base64
import os

here = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.join(here, "td9_aprs_icons")

primary = {}
secondary = {}
for i in range(94):
    with open(os.path.join(base_dir, "primary_%03d.png" % i), "rb") as f:
        primary[i] = base64.b64encode(f.read()).decode("ascii")
    with open(os.path.join(base_dir, "secondary_%03d.png" % i), "rb") as f:
        secondary[i] = base64.b64encode(f.read()).decode("ascii")

primary_names = [
    "Police, Sheriff", "", "Digi", "Phone", "DX Cluster", "HF Gateway",
    "Small Aircraft", "Mobile Satellite Ground Station", "Wheelchair",
    "Snowmobile", "Red Cross", "Boy Scouts", "House QTH (VHF)", "X",
    "Red Dot", "0 Circle", "1 Circle", "2 Circle", "3 Circle", "4 Circle",
    "5 Circle", "6 Circle", "7 Circle", "8 Circle", "9 Circle", "Fire",
    "Campground", "Motorcycle", "Railroad Engine", "Car", "File Server",
    "Hurricane Future Prediction", "Aid Station", "BBS or PBBS", "Canoe",
    "", "Eyeball", "Farm Vehicle (Tractor)", "Grid Square (6-char)",
    "Hotel", "TCP/IP on air network station", "", "School", "PC user",
    "MacAPRS", "NTS Station", "Balloon", "Police", "TBD",
    "Recreational Vehicle", "Space Shuttle", "SSTV", "Bus", "Amateur TV",
    "NWS Site", "Helicopter", "Yacht", "WinAPRS", "Jogger",
    "Triangle (DF)", "Mail/Post Office", "Large Aircraft",
    "Weather Station", "Dish Antenna", "Ambulance", "Bicycle",
    "Incident Command Post", "Fire Department", "Horse (equestrian)",
    "Fire Truck", "Glider", "Hospital", "IOTA", "Jeep", "Truck",
    "Laptop", "Mic-E Repeater", "Node", "Emergency Ops Center",
    "Rover (puppy dog)", "Grid Square >128m", "Repeater", "Ship",
    "Truck Stop", "Truck (18-wheeler)", "Van", "Water Station",
    "X-APRS", "Yagi at QTH", "TBD", "", "", "", "",
]
secondary_names = [
    "Emergency", "", "Digi (green star)", "Bank or ATM", "Power Plant",
    "IGate (I=In, R=RX, T=1hopTX, 2=2hopTX)", "Crash & incident sites",
    "Cloudy", "Firenet MEO", "Snow", "Church", "Girl Scouts",
    "House (H=HF, O=Op Present)", "Ambiguous (Question Mark)",
    "Waypoint Destination", "Circle (E/I/W = IRLP/EchoLink/WIRES)", "",
    "", "", "", "", "", "", "802.11 or other network node", "Gas Station",
    "Hail", "Park/Picnic Area", "Advisory (one WX flag)",
    "APRStt Touchtone (DTMF)", "Cars & Vehicles", "Information Kiosk",
    "Hurricane/Tropical Storm", "Box: DTMF, RFID, XO", "Blowing Snow",
    "Coast Guard", "Drizzle", "Smoke", "Freezing Rain", "Snow Shower",
    "Haze", "Rain Shower", "Lightning", "Kenwood HT (w)", "Lighthouse",
    "MARS (A=Army, N=Navy, F=AF)", "Navigation Buoy", "Rocket",
    "Parking", "Earthquake", "Restaurant", "Satellite", "Thunderstorm",
    "Sunny", "VORTAC Nav Aid", "NWS Site", "Pharmacy Rx",
    "Radios and devices", "", "Wall Cloud", "", "", "Aircraft (Shows Heading)",
    "WX Station with Digi", "Rain", "ARRL, ARES, WinLINK, Dstar, LoRa, etc",
    "Blowing Dust/Sand", "CD triangle RACES/SATERN", "DX Spot", "Sleet",
    "Funnel Cloud", "Gale Flags", "Store or Hamfest",
    "BOX or points of Interest", "Work Zone (steam shovel)",
    "Special Vehicle SUV, ATV, 4x4", "Area Symbols", "Value Sign",
    "Triangle", "Small Circle", "Partly Cloudy", "", "Restrooms",
    "Ship/Boat (top view)", "Tornado", "Truck", "Van",
    "Flooding (Avalanches)", "Wreck or Obstruction", "Skywarn",
    "Overlayed Shelter", "Fog", "", "", "",
]

# APRS symbol table characters (index 0..93) - position 94/95 unused
TABLE_CHARS = '!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'


def primary_char(i):
    return "/" + TABLE_CHARS[i]


def secondary_char(i):
    return "\\" + TABLE_CHARS[i]


out = {}
out["_doc"] = ("APRS symbol tables with embedded base64 PNG icons "
               "(primary/secondary, indexes 0-93).")
out["primary"] = []
out["secondary"] = []
for i in range(94):
    out["primary"].append({
        "n": i, "sym": primary_char(i), "name": primary_names[i],
        "b64": primary[i],
    })
    out["secondary"].append({
        "n": i, "sym": secondary_char(i), "name": secondary_names[i],
        "b64": secondary[i],
    })

out_path = os.path.join(here, "aprs_icons_data.py")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("# -*- coding: utf-8 -*-\n")
    f.write("# APRS icon tables with embedded base64 PNG icons.\n")
    f.write("# Generated from https://github.com/dkxce/Tidradio-TD-H9/blob/main/"
            "Customer%20Programming%20Software/Disasm/APRS_symbols.md\n")
    f.write("PRIMARY_ICONS = ")
    f.write(repr(out["primary"]))
    f.write("\n\nSECONDARY_ICONS = ")
    f.write(repr(out["secondary"]))
    f.write("\n")

print("written %s" % out_path)
print("primary entries: %d, secondary entries: %d"
      % (len(out["primary"]), len(out["secondary"])))