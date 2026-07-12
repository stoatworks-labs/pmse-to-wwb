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
"""

import uuid
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

TEMPLATES_DIR = Path(__file__).parent / "templates"

_SKELETON = (TEMPLATES_DIR / "skeleton.xml.tpl").read_text()
_DEVICE_TPL = (TEMPLATES_DIR / "device_ad4q_a.xml.tpl").read_text()
_PROFILE_TPL = (TEMPLATES_DIR / "profile_ad4q_a.xml.tpl").read_text()
_FREQ_ENTRY_TPL = (TEMPLATES_DIR / "freq_entry_ad4q_a.xml.tpl").read_text()

CHANNELS_PER_DEVICE = 4
FILLER_NAME = "Unused"

_ORIG_DEVICE_ID = "83DD8AE3-F353-4378-B294-69C905285801"
_ORIG_ZONE = "Room 8/9"
_ORIG_CHANNEL_FREQS = ["550375", "551625", "551125", "554875"]
_ORIG_CHANNEL_NAME_TAG = '<channel_name type="10"><![CDATA[Shure]]></channel_name>'

_ORIG_FE_ID = f"{_ORIG_DEVICE_ID}-0"
_ORIG_FE_ZONE = "Room 8/9"
_ORIG_FE_VALUE = "578875"
_ORIG_FE_CHANN_NUM = "0"

_ORIG_PROFILE_ZONE = "Room 10"


def _cdata(text: str) -> str:
    safe = str(text).replace("]]>", "]] >")
    return f"<![CDATA[{safe}]]>"


def _new_id() -> str:
    return str(uuid.uuid4()).upper()


def _build_device(device_id: str, zone: str, freqs_khz: list, names: list) -> str:
    block = _DEVICE_TPL.replace(
        f'<id dcid="04DFAE08-FD5A-11E3-A18A-0015C5F3F612">{_ORIG_DEVICE_ID}</id>',
        f'<id dcid="04DFAE08-FD5A-11E3-A18A-0015C5F3F612">{device_id}</id>',
        1,
    )
    block = block.replace(
        f"<zone type=\"12\">{_ORIG_ZONE}</zone>",
        f'<zone type="12">{escape(zone)}</zone>',
        1,
    )

    parts = block.split(_ORIG_CHANNEL_NAME_TAG)
    if len(parts) != CHANNELS_PER_DEVICE + 1:
        raise RuntimeError("device template channel_name pattern not found as expected")
    rebuilt = parts[0]
    for i in range(CHANNELS_PER_DEVICE):
        name = names[i] if i < len(names) else FILLER_NAME
        rebuilt += f'<channel_name type="10">{_cdata(name)}</channel_name>'
        rebuilt += parts[i + 1]
    block = rebuilt

    for i, orig_freq in enumerate(_ORIG_CHANNEL_FREQS):
        freq = freqs_khz[i] if i < len(freqs_khz) else orig_freq
        block = block.replace(
            f'<frequency type="3">{orig_freq}</frequency>',
            f'<frequency type="3">{freq}</frequency>',
            1,
        )
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


def _chunk(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def generate_show(
    assignments,
    show_name: str = "PMSE Licence Import",
    customer: str = "",
    poc_name: str = "",
    venue_name: str = "",
    venue_address: str = "",
) -> str:
    """assignments: list of objects with .frequency_mhz (float) and a name
    (falls back to positional numbering if not present). Groups into
    simulated AD4Q-A quad receivers, 4 channels each."""

    now = datetime.now()
    chunks = list(_chunk(assignments, CHANNELS_PER_DEVICE))

    devices_xml = []
    channel_ids_xml = []
    freq_entries_xml = []
    profiles_xml = []
    all_freqs_khz = []

    for chunk_idx, chunk in enumerate(chunks):
        device_id = _new_id()
        start_n = chunk_idx * CHANNELS_PER_DEVICE + 1
        end_n = start_n + len(chunk) - 1
        zone = f"Ch {start_n}-{end_n}" if len(chunk) > 1 else f"Ch {start_n}"

        freqs_khz = [str(int(round(a.frequency_mhz * 1000))) for a in chunk]
        names = [getattr(a, "suggested_name", None) or f"Ch{start_n + i}" for i, a in enumerate(chunk)]

        devices_xml.append(_build_device(device_id, zone, freqs_khz, names))

        for i in range(CHANNELS_PER_DEVICE):
            active = i < len(chunk)
            channel_ids_xml.append(
                f'<id active_channel="{"true" if active else "false"}" '
                f'coordination_include="{"true" if active else "false"}">{device_id}-{i}</id>'
            )
            if active:
                freq_entries_xml.append(_build_freq_entry(device_id, i, freqs_khz[i], zone))
                all_freqs_khz.append(freqs_khz[i])

        profiles_xml.append(_build_profile(zone))

    total_channels = len(chunks) * CHANNELS_PER_DEVICE

    out = _SKELETON
    out = out.replace("{{SHOW_NAME}}", escape(show_name))
    out = out.replace("{{CUSTOMER}}", escape(customer))
    out = out.replace("{{POC_NAME}}", escape(poc_name))
    out = out.replace("{{VENUE_NAME}}", escape(venue_name))
    out = out.replace("{{VENUE_ADDRESS}}", escape(venue_address))
    out = out.replace("{{BAND_PLAN_NAME}}", escape(show_name)[:40] or "List 1")
    out = out.replace("{{GROUP_NAME}}", "Ofcom Licence")
    out = out.replace("{{DATE}}", now.strftime("%a %b %d %Y"))
    out = out.replace("{{TIME}}", now.strftime("%H:%M:%S"))
    out = out.replace("{{INVENTORY_DEVICES}}", "".join(devices_xml))
    out = out.replace("{{CHANNEL_IDS}}", "".join(channel_ids_xml))
    out = out.replace("{{MIC_CHANNEL_COUNT}}", str(total_channels))
    out = out.replace("{{FREQ_ENTRIES}}", "".join(freq_entries_xml))
    out = out.replace("{{PROFILE_COUNT}}", str(len(profiles_xml)))
    out = out.replace("{{COMPAT_PROFILES}}", "".join(profiles_xml))
    out = out.replace("{{INCL_FREQ_COUNT}}", str(len(all_freqs_khz)))
    out = out.replace("{{INCL_FREQS}}", "".join(f"<f>{f}</f>" for f in all_freqs_khz))

    return out
