import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from show_generator import CHANNELS_PER_DEVICE, UnsupportedBandError, generate_show


@dataclass
class FakeAssignment:
    frequency_mhz: float
    model: str = "G56"
    suggested_name: str = field(default="")


def make_assignments(n, model="G56"):
    return [
        FakeAssignment(471.0 + i * 0.5, model=model, suggested_name=f"Ch{i + 1}")
        for i in range(n)
    ]


def test_generate_show_is_well_formed_xml():
    xml_str = generate_show(make_assignments(5), show_name="Test Show", customer="Test Co")
    root = ET.fromstring(xml_str)  # raises if malformed
    assert root.tag == "show"


def test_generate_show_device_and_channel_counts_exact_multiple():
    assignments = make_assignments(8)  # exactly 2 quad devices, no filler
    root = ET.fromstring(generate_show(assignments))

    devices = root.findall(".//inventory/device")
    assert len(devices) == 2
    total_channels = sum(len(d.findall("channel")) for d in devices)
    assert total_channels == 8

    names = [ch.findtext("channel_name") for d in devices for ch in d.findall("channel")]
    assert "Unused" not in names


def test_generate_show_pads_with_filler_channels():
    assignments = make_assignments(5)  # 1 full device + 1 device with 3 filler channels
    root = ET.fromstring(generate_show(assignments))

    devices = root.findall(".//inventory/device")
    assert len(devices) == 2

    all_channels = [ch for d in devices for ch in d.findall("channel")]
    assert len(all_channels) == 2 * CHANNELS_PER_DEVICE

    names = [ch.findtext("channel_name") for ch in all_channels]
    assert names.count("Unused") == 3

    # channel_management should mark filler channels inactive
    ids = root.findall(".//coordination_info/channel_management/channels/id")
    active_flags = [i.get("active_channel") for i in ids]
    assert active_flags.count("false") == 3
    assert active_flags.count("true") == 5


def test_generate_show_frequencies_match_input_in_khz():
    assignments = make_assignments(4)
    root = ET.fromstring(generate_show(assignments))

    expected_khz = sorted(str(int(round(a.frequency_mhz * 1000))) for a in assignments)
    actual_khz = sorted(
        ch.findtext("frequency")
        for d in root.findall(".//inventory/device")
        for ch in d.findall("channel")
    )
    assert actual_khz == expected_khz


def test_generate_show_mirror_sections_stay_consistent():
    assignments = make_assignments(9)  # forces a partially-filled device
    root = ET.fromstring(generate_show(assignments))

    mic_channels = root.find(".//coordinated_data_root/mic_channels")
    assert mic_channels.get("count") == "9"
    assert len(mic_channels.findall("freq_entry")) == 9

    profiles = root.find(".//coordinated_data_root/compatibility_profile_settings")
    n_devices = len(root.findall(".//inventory/device"))
    assert profiles.get("count") == str(n_devices)
    assert len(profiles.findall("profile")) == n_devices

    incl_freqs = root.find(".//inclusion_group/freqs")
    assert incl_freqs.get("count") == "9"
    assert len(incl_freqs.findall("f")) == 9


def test_generate_show_rejects_unsupported_band():
    assignments = make_assignments(2, model="G56") + make_assignments(1, model="H50")
    with pytest.raises(UnsupportedBandError, match="H50"):
        generate_show(assignments)


def test_generate_show_escapes_special_characters():
    xml_str = generate_show(
        make_assignments(1),
        show_name="Show <with> & \"quotes\"",
        customer="O'Brien & Sons",
    )
    # Must still be well-formed after escaping.
    ET.fromstring(xml_str)
