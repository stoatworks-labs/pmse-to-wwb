import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from show_generator import (
    MAX_CHANNELS_PER_RECEIVER,
    ReceiverConfigError,
    UnsupportedBandError,
    generate_show,
)


def make_channel(freq, name="Ch", band="G56"):
    return {"frequency_mhz": freq, "name": name, "band": band}


def make_receiver(name, channel_count, channels, ip_address=None):
    return {"name": name, "channel_count": channel_count, "ip_address": ip_address, "channels": channels}


def test_generate_show_is_well_formed_xml():
    receivers = [make_receiver("Rack 1", 4, [make_channel(471.0 + i * 0.5) for i in range(4)])]
    xml_str = generate_show(receivers, show_name="Test Show", customer="Test Co")
    root = ET.fromstring(xml_str)  # raises if malformed
    assert root.tag == "show"


def test_generate_show_full_receiver_has_no_filler():
    channels = [make_channel(471.0 + i * 0.5, name=f"Ch{i+1}") for i in range(4)]
    receivers = [make_receiver("Rack 1", 4, channels)]
    root = ET.fromstring(generate_show(receivers))

    devices = root.findall(".//inventory/device")
    assert len(devices) == 1
    names = [ch.findtext("channel_name") for ch in devices[0].findall("channel")]
    assert names == ["Ch1", "Ch2", "Ch3", "Ch4"]
    assert "Unused" not in names


def test_generate_show_pads_with_filler_channels():
    channels = [make_channel(471.0), make_channel(471.5)]
    receivers = [make_receiver("Rack 1", 4, channels)]  # capacity 4, only 2 real channels
    root = ET.fromstring(generate_show(receivers))

    device = root.find(".//inventory/device")
    all_channels = device.findall("channel")
    assert len(all_channels) == 4
    names = [ch.findtext("channel_name") for ch in all_channels]
    assert names.count("Unused") == 2

    ids = root.findall(".//coordination_info/channel_management/channels/id")
    active_flags = [i.get("active_channel") for i in ids]
    assert active_flags.count("false") == 2
    assert active_flags.count("true") == 2


def test_generate_show_supports_multiple_receivers_with_different_capacities():
    receivers = [
        make_receiver("Stage Left", 4, [make_channel(471.0 + i * 0.5) for i in range(4)]),
        make_receiver("IEM Rack", 2, [make_channel(500.0)]),
        make_receiver("Single Ch", 1, [make_channel(510.0)]),
    ]
    root = ET.fromstring(generate_show(receivers))
    devices = root.findall(".//inventory/device")
    assert len(devices) == 3
    assert [len(d.findall("channel")) for d in devices] == [4, 2, 1]


def test_generate_show_frequencies_match_input_in_khz():
    channels = [make_channel(471.375), make_channel(500.125)]
    receivers = [make_receiver("Rack 1", 2, channels)]
    root = ET.fromstring(generate_show(receivers))

    expected_khz = sorted(str(int(round(c["frequency_mhz"] * 1000))) for c in channels)
    actual_khz = sorted(
        ch.findtext("frequency")
        for d in root.findall(".//inventory/device")
        for ch in d.findall("channel")
    )
    assert actual_khz == expected_khz


def test_generate_show_ip_address_round_trips():
    receivers = [make_receiver("Rack 1", 1, [make_channel(471.0)], ip_address="192.168.1.101")]
    root = ET.fromstring(generate_show(receivers))
    device = root.find(".//inventory/device")
    assert device.findtext("ip_mode") == "1"

    import ipaddress
    decoded = ipaddress.IPv4Address(int(device.findtext("ip_address")))
    assert str(decoded) == "192.168.1.101"


def test_generate_show_no_ip_leaves_mode_unset():
    receivers = [make_receiver("Rack 1", 1, [make_channel(471.0)])]
    root = ET.fromstring(generate_show(receivers))
    device = root.find(".//inventory/device")
    assert device.findtext("ip_mode") == "0"
    assert device.findtext("ip_address") == "0"


def test_generate_show_rejects_invalid_ip():
    receivers = [make_receiver("Rack 1", 1, [make_channel(471.0)], ip_address="not-an-ip")]
    with pytest.raises(ReceiverConfigError, match="not-an-ip"):
        generate_show(receivers)


def test_generate_show_rejects_over_capacity_receiver():
    channels = [make_channel(471.0), make_channel(472.0), make_channel(473.0)]
    receivers = [make_receiver("Rack 1", 2, channels)]
    with pytest.raises(ReceiverConfigError, match="capacity for 2"):
        generate_show(receivers)


def test_generate_show_rejects_channel_count_out_of_range():
    receivers = [make_receiver("Rack 1", MAX_CHANNELS_PER_RECEIVER + 1, [])]
    with pytest.raises(ReceiverConfigError):
        generate_show(receivers)


def test_generate_show_mirror_sections_stay_consistent():
    receivers = [
        make_receiver("Rack 1", 4, [make_channel(471.0 + i * 0.5) for i in range(4)]),
        make_receiver("Rack 2", 8, [make_channel(500.0 + i) for i in range(5)]),  # partial
    ]
    root = ET.fromstring(generate_show(receivers))

    real_channel_count = 4 + 5

    mic_channels = root.find(".//coordinated_data_root/mic_channels")
    assert mic_channels.get("count") == str(real_channel_count)
    assert len(mic_channels.findall("freq_entry")) == real_channel_count

    profiles = root.find(".//coordinated_data_root/compatibility_profile_settings")
    n_devices = len(root.findall(".//inventory/device"))
    assert n_devices == 2
    assert profiles.get("count") == str(n_devices)
    assert len(profiles.findall("profile")) == n_devices

    incl_freqs = root.find(".//inclusion_group/freqs")
    assert incl_freqs.get("count") == str(real_channel_count)
    assert len(incl_freqs.findall("f")) == real_channel_count


def test_generate_show_rejects_unsupported_band():
    receivers = [
        make_receiver(
            "Rack 1",
            2,
            [make_channel(471.0, band="G56"), make_channel(600.0, band="H50")],
        )
    ]
    with pytest.raises(UnsupportedBandError, match="H50"):
        generate_show(receivers)


def test_generate_show_escapes_special_characters():
    receivers = [make_receiver("Rack <1> & \"stage\"", 1, [make_channel(471.0, name="O'Brien & Sons")])]
    xml_str = generate_show(
        receivers,
        show_name="Show <with> & \"quotes\"",
        customer="O'Brien & Sons",
    )
    ET.fromstring(xml_str)  # must still be well-formed after escaping
