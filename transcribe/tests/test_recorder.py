from transcribe.recorder.devices import list_audio_devices, prompt_for_devices, select_default_devices


class FakeSoundDevice:
    @staticmethod
    def query_devices():
        return [
            {"name": "Mic 1", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 0},
            {"name": "Speaker 1", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
        ]

    @staticmethod
    def query_hostapis():
        return [{"name": "WASAPI"}]


def test_list_audio_devices_normalizes_and_adds_loopback():
    devices = list_audio_devices(sd_module=FakeSoundDevice)
    labels = [d["label"] for d in devices]
    assert "Mic 1" in labels
    assert "Speaker 1 (loopback)" in labels
    assert any(d["loopback"] for d in devices)


def test_prompt_for_devices_selects_expected():
    devices = list_audio_devices(sd_module=FakeSoundDevice)
    prompts = []

    def fake_prompt(prompt, choices):
        prompts.append((prompt, choices))
        return "1"

    selected = prompt_for_devices(devices=devices, prompt_fn=fake_prompt, output_fn=lambda _msg: None)
    assert selected["mic"]["label"] == "Mic 1"
    assert selected["loopback"]["label"] == "Speaker 1 (loopback)"


def test_prompt_for_devices_requires_loopback():
    devices = [
        {"label": "Mic 1", "loopback": False, "max_input_channels": 1, "max_output_channels": 0}
    ]
    try:
        prompt_for_devices(devices=devices, prompt_fn=lambda _p, _c: "1", output_fn=lambda _m: None)
    except ValueError as exc:
        assert "loopback" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing loopback devices")


def test_select_default_devices_prefers_available():
    devices = list_audio_devices(sd_module=FakeSoundDevice)
    selected = select_default_devices(devices=devices)
    assert selected["mic"]["label"] == "Mic 1"
    assert selected["loopback"]["label"] == "Speaker 1 (loopback)"
