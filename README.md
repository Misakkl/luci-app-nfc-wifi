# luci-app-nfc-wifi

<p align="center">
  <img src="https://img.shields.io/badge/Hardware-Xiaomi%20AX3000T%20(RD03%20%2F%20AN8855)-blue" alt="Hardware">
  <img src="https://img.shields.io/badge/NFC%20Chip-FM11NT082C-00A6A6" alt="NFC Chip">
  <img src="https://img.shields.io/badge/Interface-I2C%200x57-4B8BBE" alt="Interface">
  <img src="https://img.shields.io/badge/Firmware-OpenWrt%20%7C%20LuCI-34A853" alt="Firmware">
  <img src="https://img.shields.io/badge/License-MIT-EA7E20" alt="License">
</p>

<p align="center">
  <a href="https://github.com/Misakkl/luci-app-nfc-wifi/releases"><img src="https://img.shields.io/github/v/release/Misakkl/luci-app-nfc-wifi?label=release&color=blue" alt="Release"></a>
  <a href="https://github.com/Misakkl/luci-app-nfc-wifi/stargazers"><img src="https://img.shields.io/github/stars/Misakkl/luci-app-nfc-wifi?style=social" alt="Stars"></a>
</p>

<p align="center"><b>English</b> | <a href="README.zh-CN.md">简体中文</a></p>

Automatically write your router's WiFi name and password to its built-in NFC tag.
Tap the router with your phone and you're connected.

Built for the **Xiaomi AX3000T** (RD03 / AN8855, Fudan Microelectronics FM11NT082C NFC chip).
Other devices using the same chip only need a different I2C bus and address.

```
Change WiFi in LuCI  ──►  Router rewrites the NFC tag  ──►  Phone taps to join
```

---

## Table of Contents

- [Why this exists](#why-this-exists)
- [Supported hardware](#supported-hardware)
- [Installation](#installation)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Protocol details](#protocol-details)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Development](#development)
- [License](#license)

---

## Why this exists

The Xiaomi AX3000T ships with an NFC tag on top of the case, pre-programmed with a
"tap to join WiFi" payload.

The problem: **the phone can't rewrite it, and neither can Xiaomi's own app.**

The reason is that the factory burns **RF-side static lock bits**
(EEPROM `0x0A/0x0B` = `FF FF`), permanently locking the NDEF area. Any write attempt
over the NFC radio path is rejected by the chip — the app reporting the tag as
"writable" is simply wrong.

But the **I2C (contact) side is a separate permission domain**, governed by the
`CT Lock Bits` (EEPROM block `0xF0/0xF1`) — and those are **not** locked:

| Path | Can it write? |
|---|---|
| Phone (RF side) | ❌ blocked by static lock bits |
| Router CPU (I2C side) | ✅ works |

This is by design: only the device itself is allowed to update the tag payload.

This plugin uses that I2C channel to keep the tag in sync with the WiFi configuration.

---

## Supported hardware

| Device | Status | Notes |
|---|---|---|
| Xiaomi AX3000T (RD03 / AN8855) | ✅ verified | works out of the box |
| Other FM11NT082C devices | ⚠️ needs tuning | adjust `bus` / `address` in `/etc/config/nfc_wifi` |

**Requirements**

- NFC chip **FM11NT082C** (Fudan Microelectronics)
- Chip attached to the CPU's I2C bus (bus 0, address `0x57` on the AX3000T)
- `i2ctransfer` available on the system

> ⚠️ **Version warning**: the AX3000T comes in several revisions. The RD03V2/V3 uses a
> **Qualcomm IPQ5018** and has nothing in common with the MediaTek variant. Do not treat
> this project as a universal solution. Only the community-designated "V2"
> (MediaTek MT7981B + Airoha AN8855 switch) matches.

---

## Installation

### Option 1: install the ipk (recommended)

```sh
scp luci-app-nfc-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 'opkg install /tmp/luci-app-nfc-wifi_1.0.0-1_all.ipk'
```

If dependencies are missing:

```sh
opkg update
opkg install luci-base i2c-tools
```

### Option 2: build from source

```sh
git clone https://github.com/<your-name>/luci-app-nfc-wifi.git
cd luci-app-nfc-wifi

python3 build-ipk.py          # produces dist/*.ipk, no SDK required
scp dist/luci-app-nfc-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 'opkg install /tmp/luci-app-nfc-wifi_1.0.0-1_all.ipk'
```

### Option 3: OpenWrt SDK

```sh
cp -r luci-app-nfc-wifi ~/openwrt-sdk/package/
cd ~/openwrt-sdk
make package/luci-app-nfc-wifi/compile V=s
```

The resulting package lands in `bin/packages/*/base/`.

### After installation

- A new menu entry appears under **System → NFC 标签同步**
- Boot-time sync is enabled automatically
- The tag is written once immediately

---

## Usage

### LuCI

**System → NFC 标签同步**

| Option | Description |
|---|---|
| Enable auto sync | Master switch. When off, automatic sync stops but "Sync now" still works |
| I2C bus | Leave empty for the default `0` |
| Tag address | Leave empty for the default `0x57` |
| Sync now | Force one write, ignoring the master switch |

After changing the WiFi SSID or password, hit **Save & Apply** — the tag follows.

### Command line

```sh
/usr/sbin/nfc-wifi-sync            # respects the master switch
/usr/sbin/nfc-wifi-sync --force    # ignore the master switch
/etc/init.d/nfc-wifi-sync reload   # same, via init

logread | grep nfc-wifi-sync       # check the result
```

### Verify the tag contents

```sh
# NDEF header — expect 03 55 d2 17
i2ctransfer -y 0 w2@0x57 0x00 0x10 r16@0x57

# SSID area
i2ctransfer -y 0 w2@0x57 0x00 0x39 r16@0x57
```

Tap the router with an Android phone — it should offer to join the network.

### When sync runs

1. **Boot** — `/etc/init.d/nfc-wifi-sync` (`S95`)
2. **WiFi interface up** — `/etc/hotplug.d/iface/99-nfc-wifi`, deduplicated via a
   fingerprint in `/tmp/nfc-wifi.fp` (no rewrite if the config hasn't changed, which
   saves EEPROM wear)
3. **Manual** — LuCI button or CLI

---

## How it works

```
┌──────────────┐
│  UCI config  │  wireless.<section>.ssid / .key
└──────┬───────┘
       │  read
       ▼
┌──────────────┐
│ Build NDEF   │  WSC Credential → byte sequence
└──────┬───────┘
       │  16 bytes per page
       ▼
┌──────────────┐
│ I2C write    │  i2ctransfer → FM11NT082C EEPROM
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ NFC tag      │  read by the phone
└──────────────┘
```

---

## Protocol details

Everything here was learned the hard way. Documenting it so nobody has to repeat it.

### ⚠️ The main trap: EEPROM needs two-byte big-endian addressing

```
write page: i2ctransfer -y 0 w18@0x57 0x00 <addrH> <addrL> <16 data bytes>
read  page: i2ctransfer -y 0 w2@0x57  0x00 <addrH> <addrL> r16@0x57
```

**Why it is easy to get wrong**: `i2ctransfer -y 0 w1@0x57 0x10` looks like
"read address 0x10", but it actually enters the **internal register space**, which has
only an 8-register window and behaves nothing like the EEPROM.

Symptoms of getting this wrong (all encountered during development):

| Symptom | Cause |
|---|---|
| Reading `0x00` returns data, `0x10`/`0x20` return zeros | you are in register space, not EEPROM |
| Writes are ACKed but nothing changes | same |
| Write target jumps around between runs | register `0x03` (read pointer) mistaken for the EEPROM address |
| **Concluding "OTP-locked, impossible"** | the worst trap — nearly gave up here |

### Internal registers (only visible when using one-byte addressing)

| Register | Purpose |
|---|---|
| `0x00` | data port |
| `0x03` | read pointer (auto-clears after use) |
| `0x08` and above | invalid (NAK) |

### EEPROM layout

```
0x0000  UID (7 bytes) + BCC
0x0008  lock bits (measured 6F B0 FF FF on the AX3000T)
0x000C  CC = E1 10 6D 00      ← capacity 880 bytes, read/write
0x0010  start of NDEF
```

### Page write rules

- The EEPROM is organised in **16-byte pages**
- A single write **must not cross a page boundary** (it gets NAKed or wraps to the page start)
- Align the address to a page boundary before writing

### NDEF / WSC format

The payload is standard **WSC (WiFi Simple Configuration)**, understood by both
iOS and Android:

```
03 <TLV length>                       NDEF TLV
  d2 17 <payload length>              MIME record, type is 23 bytes
  "application/vnd.wfa.wsc"
  10 0e <Cred length>                 Credential
    10 26 00 01 01                    Network Index
    10 45 <SSID length> <SSID>        SSID
    10 03 00 02 00 20                 WPA2-PSK
    10 0f 00 02 00 08                 AES
    10 27 <key length> <key>          Network Key
    10 20 00 06 ff ff ff ff ff fe     MAC (wildcard)
```

**Length math** (with `s` = SSID length, `k` = password length):

```
Cred    = 35 + s + k
payload = 4 + Cred
TLV     = 3 + 23 + payload
```

### WPA2 vs WPA3

The WSC specification has **no WPA3 field** — WPA3's SAE does not belong to this older
standard. So even if the AP runs WPA2/WPA3 mixed mode, the tag must advertise
**WPA2-PSK / AES**.

That is the correct and most compatible choice: a mixed-mode AP accepts WPA2 clients.
The tag only fails if the AP is reconfigured to **WPA3-only**.

---

## Troubleshooting

### Sync fails, log shows "write failed"

```sh
logread | grep nfc-wifi-sync
```

| Log line | Cause | Fix |
|---|---|---|
| `i2ctransfer missing` | i2c-tools not installed | `opkg install i2c-tools` |
| `no enabled AP with ssid found` | no enabled AP | check `/etc/config/wireless` |
| `write failed at addr 0x0010` | I2C communication failed | see below |
| `verify mismatch` | read-back differs | see below |
| `record too large` | SSID + password too long | keep under 42 characters |

### I2C communication failures

```sh
# 1. Is the chip on the bus?
i2cdetect -y 0
# expect an address at 0x57

# 2. Can we read the UID?
i2ctransfer -y 0 w2@0x57 0x00 0x00 r8@0x57
# expect 8 non-zero bytes

# 3. Is the I2C controller loaded?
ls /sys/bus/i2c/devices/
```

If `i2cdetect` does not show `0x57`:

- confirm the chip is really an FM11NT082C
- confirm the NFC chip is not disabled in hardware
- some builds do not load the I2C controller driver by default; install `kmod-i2c-*`

### The phone does nothing when tapped

| Platform | Behaviour |
|---|---|
| **Android** | should offer to join the network. If not, the NDEF is malformed |
| **iOS** | ⚠️ **system NFC only handles URL records** — WiFi records never prompt |

**This is a hard iOS limitation**, not a bug in this plugin. Alternatives:

1. read the tag with an app like "NFC Tools" and connect manually
2. **use a WiFi QR code** (the iPhone camera joins networks natively from a QR code)
3. use Apple's "share password" between Apple devices

A practical setup: print a QR code next to the router — Android taps the NFC tag,
iPhone scans the QR code.

### Write succeeds but the phone sees old data

- LuCI caches aggressively — force a reload (`Ctrl+Shift+R`)
- make sure you edited an **enabled** AP section (the script only reads sections with
  `mode='ap'` and `disabled!='1'`)

---

## Known limitations

| Limitation | Notes |
|---|---|
| **ASCII only** | non-ASCII SSIDs produce wrong lengths. Extending to byte-wise UTF-8 is straightforward |
| **SSID + password ≤ 42 chars** | the TLV length is a single byte and is bounded by the capacity in CC |
| **only the first enabled AP** | multi-SSID setups sync the first match only |
| **iOS does not prompt** | system limitation, see above |
| **write endurance** | EEPROM rated ~1M cycles; the hotplug hook deduplicates, so normal use is fine |

---

## Development

### Layout

```
luci-app-nfc-wifi/
├── build-ipk.py                          # standalone packager (no SDK needed)
├── Makefile                              # for the OpenWrt SDK
├── README.md                             # English
├── README.zh-CN.md                       # Chinese
├── LICENSE
├── root/                                 # installed at the router's filesystem root
│   ├── etc/
│   │   ├── config/nfc_wifi               # UCI config (conffile)
│   │   ├── init.d/nfc-wifi-sync          # boot sync
│   │   ├── hotplug.d/iface/99-nfc-wifi   # triggered on interface up
│   │   └── uci-defaults/90-nfc-wifi      # enable the service on first install
│   └── usr/
│       ├── sbin/nfc-wifi-sync            # the main script
│       └── share/
│           ├── luci/menu.d/              # menu entry
│           └── rpcd/acl.d/               # ACL
└── htdocs/                               # web assets
    └── luci-static/resources/view/nfc-wifi/nfc-wifi.js
```

### Porting to another device

Edit `/etc/config/nfc_wifi`:

```uci
config nfc_wifi 'main'
	option enabled '1'
	option bus '1'        # your I2C bus number
	option address '0x57' # your chip address
```

If the NDEF offset or CC capacity differs, adjust the `BASE` and `END` constants in
`root/usr/sbin/nfc-wifi-sync`.

### Packaging

```sh
python3 build-ipk.py            # 1.0.0-1
python3 build-ipk.py 1.1.0      # explicit version
```

Output goes to `dist/`. Builds are reproducible (fixed mtime, fixed gzip OS byte).

> Note: `build-ipk.py` emits a `gzip(tar(...))` archive. That is the format the target
> opkg actually parses — the traditional `ar` container is rejected by some newer opkg
> builds with `Malformed package file`.

---

## License

[MIT](LICENSE)

---

## Credits

- Fudan Microelectronics FM11NT082C datasheet (`XCY2020_1656501739000.pdf`)
- The OpenWrt and LuCI projects
- The ENshan forum community for AX3000T flashing documentation
