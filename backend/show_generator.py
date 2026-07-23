"""Generates a Shure Wireless Workbench 7 .shw show file.

EXPERIMENTAL: WWB's native show-file format is undocumented. This module
works by cloning real, structurally-verified XML fragments (extracted from
a working WWB7 7.8.1 show file) for a Shure AD4Q-A quad receiver in the
G56 band, and substituting only frequency/name/identity fields. Everything
else is copied verbatim from a real working file, on the theory that
unedited boilerplate is far less likely to break WWB's parser than a
hand-built equivalent.

This has not been validated by Shure and should be treated as best-effort:
open the generated file in WWB and check it before relying on it for a show.

Receivers are user-defined (name, channel capacity, optional IP address) --
see generate_show()'s docstring for the exact shape. The IP address fields
in particular are UNVERIFIED: the real sample file this was reverse
engineered from never had a device with a real IP configured, so the
ip_mode/ip_address encoding here is a best-effort guess (packed 32-bit
IPv4 address, ip_mode=1 for static), not something we've seen WWB actually
accept. Treat any IP baked into a generated show file as a starting point
to verify/correct inside WWB, not a guarantee.
"""

import ipaddress
import uuid
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

TEMPLATES_DIR = Path(__file__).parent / "templates"

_SKELETON = (TEMPLATES_DIR / "skeleton.xml.tpl").read_text()
_DEVICE_SHELL_TPL = (TEMPLATES_DIR / "device_shell_ad4q_a.xml.tpl").read_text()
_CHANNEL_TPL = (TEMPLATES_DIR / "channel_ad4q_a.xml.tpl").read_text()
_PROFILE_TPL = (TEMPLATES_DIR / "profile_ad4q_a.xml.tpl").read_text()
_FREQ_ENTRY_TPL = (TEMPLATES_DIR / "freq_entry_ad4q_a.xml.tpl").read_text()

FILLER_NAME = "Unused"
FILLER_FREQ_KHZ = "470100"  # low edge of the G56 range; channel is marked inactive regardless.
MAX_CHANNELS_PER_RECEIVER = 8  # matches the template's regtx1..8 slots; a sanity ceiling, not a real hardware limit we've verified.

# The only band/receiver combination we have a real, structurally-verified
# template for. Ofcom licences can cover other Shure bands (e.g. G50, H50,
# K3E) that use different receiver hardware and compat profiles -- silently
# labelling those as AD4Q-A/G56 would misrepresent real RF equipment, so we
# refuse instead of guessing.
SUPPORTED_BAND = "G56"

_ORIG_FE_ID = "83DD8AE3-F353-4378-B294-69C905285801-0"
_ORIG_FE_ZONE = "Room 8/9"
_ORIG_FE_VALUE = "578875"
_ORIG_FE_CHANN_NUM = "0"

_ORIG_PROFILE_ZONE = "Room 10"


class UnsupportedBandError(ValueError):
    """Raised when a channel uses a band/model this generator has no
    verified template for."""


class ReceiverConfigError(ValueError):
    """Raised for invalid receiver configuration: too many channels for the
    receiver's declared capacity, or an unparseable IP address."""


def _cdata(text: str) -> str:
    safe = str(text).replace("]]>", "]] >")
    return f"<![CDATA[{safe}]]>"


def _attr_escape(text: str) -> str:
    """escape() only handles &, <, > -- also escape quotes since this is
    used inside a double-quoted XML attribute value."""
    return escape(text, {'"': "&quot;", "'": "&apos;"})


def _new_id() -> str:
    return str(uuid.uuid4()).upper()


def _ip_to_int(ip_str: str) -> int:
    try:
        return int(ipaddress.IPv4Address(ip_str.strip()))
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ReceiverConfigError(f"'{ip_str}' is not a valid IPv4 address.") from exc


def _build_channel(number: int, freq_khz: str, name: str) -> str:
    block = _CHANNEL_TPL
    block = block.replace("{{CHANNEL_NUMBER}}", str(number))
    block = block.replace("{{CHANNEL_NAME}}", _cdata(name))
    block = block.replace("{{FREQUENCY_KHZ}}", str(freq_khz))
    block = block.replace("{{REMOTE_NAME}}", escape(f"RemChannel{number}"))
    return block


def _build_device(
    device_id: str, device_name: str, zone: str, ip_address: str, channels_xml: str
) -> str:
    ip_mode = "0"
    ip_address_int = "0"
    if ip_address:
        ip_address_int = str(_ip_to_int(ip_address))
        ip_mode = "1"  # best guess for "static" -- unverified, see module docstring.

    block = _DEVICE_SHELL_TPL
    block = block.replace("{{DEVICE_ID}}", device_id)
    block = block.replace("{{DEVICE_NAME}}", _cdata(device_name))
    block = block.replace("{{ZONE}}", escape(zone))
    block = block.replace("{{IP_MODE}}", ip_mode)
    block = block.replace("{{IP_ADDRESS}}", ip_address_int)
    block = block.replace("{{CHANNELS}}", channels_xml)
    return block


def _build_freq_entry(device_id: str, index: int, freq_khz: str, zone: str) -> str:
    fe_id = f"{device_id}-{index}"
    block = _FREQ_ENTRY_TPL.replace(f'id="{_ORIG_FE_ID}"', f'id="{fe_id}"', 1)
    block = block.replace(f"<zone>{_ORIG_FE_ZONE}</zone>", f"<zone>{escape(zone)}</zone>", 1)
    block = block.replace(f"<value>{_ORIG_FE_VALUE}</value>", f"<value>{freq_khz}</value>", 1)
    block = block.replace(
        f"<chann_num>{_ORIG_FE_CHANN_NUM}</chann_num>", f"<chann_num>{index}</chann_num>", 1
    )
    block = block.replace(
        f"<source_id>{_ORIG_FE_ID}</source_id>", f"<source_id>{fe_id}</source_id>", 1
    )
    return block


def _build_profile(zone: str) -> str:
    return _PROFILE_TPL.replace(
        f"<zone>{_ORIG_PROFILE_ZONE}</zone>", f"<zone>{escape(zone)}</zone>", 1
    )


def generate_show(
    receivers,
    show_name: str = "PMSE Licence Import",
    customer: str = "",
    poc_name: str = "",
    venue_name: str = "",
    venue_address: str = "",
) -> str:
    """receivers: list of dicts, each describing one simulated AD4Q-A-style
    receiver:
        {
            "name": str,               # zone/label; auto-generated if blank
            "channel_count": int,      # receiver's channel capacity (1-8)
            "ip_address": str | None,  # optional dotted-quad; see module docstring
            "channels": [
                {"frequency_mhz": float, "name": str, "band": str},
                ...  # up to channel_count entries; remaining slots become
                     # inactive "Unused" filler channels
            ],
        }

    Raises UnsupportedBandError if any channel's band isn't G56 (the only
    band/receiver this generator has a verified template for), or
    ReceiverConfigError for an over-capacity receiver or an unparseable IP.
    """
    unsupported = sorted(
        {
            (ch.get("band") or "").strip()
            for r in receivers
            for ch in r["channels"]
            if (ch.get("band") or "").strip().upper() != SUPPORTED_BAND
        }
    )
    if unsupported:
        raise UnsupportedBandError(
            f"Show-file generation only supports the {SUPPORTED_BAND} band (Shure AD4Q-A "
            f"template). This licence includes band(s) {', '.join(unsupported)}, which have "
            "no verified template, so no .shw file was generated for it."
        )

    for r in receivers:
        count = r.get("channel_count", 0)
        if not (1 <= count <= MAX_CHANNELS_PER_RECEIVER):
            raise ReceiverConfigError(
                f"Receiver '{r.get('name', '?')}' has channel_count={count}; "
                f"must be between 1 and {MAX_CHANNELS_PER_RECEIVER}."
            )
        if len(r["channels"]) > count:
            raise ReceiverConfigError(
                f"Receiver '{r.get('name', '?')}' was given {len(r['channels'])} channel(s) "
                f"but only has capacity for {count}."
            )

    now = datetime.now()

    devices_xml = []
    channel_ids_xml = []
    freq_entries_xml = []
    profiles_xml = []
    all_freqs_khz = []

    for r_index, r in enumerate(receivers, start=1):
        device_id = _new_id()
        channel_count = r["channel_count"]
        zone = r.get("name") or f"Receiver {r_index}"

        channels_xml_parts = []
        for i in range(channel_count):
            if i < len(r["channels"]):
                ch = r["channels"][i]
                freq_khz = str(int(round(ch["frequency_mhz"] * 1000)))
                name = ch.get("name") or f"Ch{i + 1}"
                active = True
            else:
                freq_khz = FILLER_FREQ_KHZ
                name = FILLER_NAME
                active = False

            channels_xml_parts.append(_build_channel(i + 1, freq_khz, name))

            channel_ids_xml.append(
                f'<id active_channel="{"true" if active else "false"}" '
                f'coordination_include="{"true" if active else "false"}">{device_id}-{i}</id>'
            )
            if active:
                freq_entries_xml.append(_build_freq_entry(device_id, i, freq_khz, zone))
                all_freqs_khz.append(freq_khz)

        devices_xml.append(
            _build_device(
                device_id,
                device_name=zone,
                zone=zone,
                ip_address=(r.get("ip_address") or "").strip(),
                channels_xml="".join(channels_xml_parts),
            )
        )
        profiles_xml.append(_build_profile(zone))

    out = _SKELETON
    out = out.replace("{{SHOW_NAME}}", escape(show_name))
    out = out.replace("{{CUSTOMER}}", escape(customer))
    out = out.replace("{{POC_NAME}}", escape(poc_name))
    out = out.replace("{{VENUE_NAME}}", escape(venue_name))
    out = out.replace("{{VENUE_ADDRESS}}", escape(venue_address))
    out = out.replace("{{BAND_PLAN_NAME}}", _attr_escape(show_name[:40]) or "List 1")
    out = out.replace("{{GROUP_NAME}}", "Ofcom Licence")
    out = out.replace("{{DATE}}", now.strftime("%a %b %d %Y"))
    out = out.replace("{{TIME}}", now.strftime("%H:%M:%S"))
    out = out.replace("{{INVENTORY_DEVICES}}", "".join(devices_xml))
    out = out.replace("{{CHANNEL_IDS}}", "".join(channel_ids_xml))
    out = out.replace("{{MIC_CHANNEL_COUNT}}", str(len(all_freqs_khz)))
    out = out.replace("{{FREQ_ENTRIES}}", "".join(freq_entries_xml))
    out = out.replace("{{PROFILE_COUNT}}", str(len(profiles_xml)))
    out = out.replace("{{COMPAT_PROFILES}}", "".join(profiles_xml))
    out = out.replace("{{INCL_FREQ_COUNT}}", str(len(all_freqs_khz)))
    out = out.replace("{{INCL_FREQS}}", "".join(f"<f>{f}</f>" for f in all_freqs_khz))

    return out
