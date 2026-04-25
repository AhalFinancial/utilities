"""Audio device enumeration and selection helpers."""

from typing import Callable, Dict, Iterable, List, Optional, Tuple


def _require_sounddevice(sd_module=None):
    if sd_module is not None:
        return sd_module
    try:
        import sounddevice as sd  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency check only
        raise RuntimeError(
            "sounddevice is required for live recording. Install with `pip install sounddevice`."
        ) from exc
    return sd


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def _score_device(dev: Dict) -> Tuple[int, int]:
    host = (dev.get("hostapi") or "").upper()
    score = 0
    if "WASAPI" in host:
        score += 3
    if "MME" in host:
        score += 1
    name = (dev.get("name") or "").lower()
    if "mapper" in name:
        score -= 2
    return score, dev.get("index", 0)


def _dedupe_devices(devices: Iterable[Dict]) -> List[Dict]:
    chosen: Dict[Tuple[str, bool], Dict] = {}
    for dev in devices:
        key = (dev["label"].lower(), bool(dev["loopback"]))
        if key not in chosen:
            chosen[key] = dev
            continue
        if _score_device(dev) > _score_device(chosen[key]):
            chosen[key] = dev
    return list(chosen.values())


def list_audio_devices(sd_module=None, exclude_hostapis: Optional[List[str]] = None) -> List[Dict]:
    sd = _require_sounddevice(sd_module)
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    excluded = [h.upper() for h in (exclude_hostapis or [])]

    results: List[Dict] = []
    for idx, dev in enumerate(devices):
        hostapi_name = None
        try:
            hostapi_name = hostapis[dev.get("hostapi", 0)].get("name")
        except Exception:
            hostapi_name = None
        if hostapi_name and hostapi_name.upper() in excluded:
            continue
        base = {
            "index": idx,
            "name": _normalize_name(dev.get("name", f"Device {idx}")),
            "hostapi": hostapi_name,
            "max_input_channels": dev.get("max_input_channels", 0),
            "max_output_channels": dev.get("max_output_channels", 0),
        }

        if base["max_input_channels"] > 0:
            results.append(
                {
                    **base,
                    "id": f"in-{idx}",
                    "loopback": False,
                    "label": base["name"],
                }
            )

        if base["max_output_channels"] > 0:
            results.append(
                {
                    **base,
                    "id": f"loop-{idx}",
                    "loopback": True,
                    "label": f"{base['name']} (loopback)",
                }
            )

    return _dedupe_devices(results)


def _default_prompt(prompt: str, choices: List[str]) -> str:
    try:
        import click  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency check only
        raise RuntimeError("click is required for device prompts.") from exc
    return click.prompt(prompt, type=click.Choice(choices), default=choices[0])


def select_default_devices(devices: Optional[List[Dict]] = None) -> Dict[str, Dict]:
    devices = devices or list_audio_devices(exclude_hostapis=["WDM-KS"])
    mic_choices = [d for d in devices if not d["loopback"] and d["max_input_channels"] > 0]
    loop_choices = [d for d in devices if d["loopback"] and d["max_output_channels"] > 0]

    if not mic_choices or not loop_choices:
        devices = list_audio_devices()
        mic_choices = [d for d in devices if not d["loopback"] and d["max_input_channels"] > 0]
        loop_choices = [d for d in devices if d["loopback"] and d["max_output_channels"] > 0]

    if not mic_choices:
        raise ValueError("No microphone input devices found.")
    if not loop_choices:
        raise ValueError("No loopback-capable output devices found.")

    mic = sorted(mic_choices, key=_score_device, reverse=True)[0]
    loop = sorted(loop_choices, key=_score_device, reverse=True)[0]
    return {"mic": mic, "loopback": loop}


def prompt_for_devices(
    devices: Optional[List[Dict]] = None,
    prompt_fn: Optional[Callable[[str, List[str]], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Dict]:
    devices = devices or list_audio_devices(exclude_hostapis=["WDM-KS"])
    if not devices:
        devices = list_audio_devices()
    prompt_fn = prompt_fn or _default_prompt
    output_fn = output_fn or (lambda _msg: None)

    mic_choices = [d for d in devices if not d["loopback"] and d["max_input_channels"] > 0]
    loop_choices = [d for d in devices if d["loopback"] and d["max_output_channels"] > 0]

    if not mic_choices:
        raise ValueError("No microphone input devices found.")
    if not loop_choices:
        raise ValueError("No loopback-capable output devices found.")

    def _emit_list(title: str, choices: List[Dict]) -> List[str]:
        labels = []
        output_fn(f"{title}:")
        for idx, dev in enumerate(choices, start=1):
            label = f"{idx}. {dev['label']}"
            output_fn(label)
            labels.append(str(idx))
        return labels

    mic_labels = _emit_list("Microphone devices", mic_choices)
    mic_sel = prompt_fn("Select microphone device", mic_labels)
    mic_device = mic_choices[int(mic_sel) - 1]

    loop_labels = _emit_list("Desktop audio devices", loop_choices)
    loop_sel = prompt_fn("Select desktop (loopback) device", loop_labels)
    loop_device = loop_choices[int(loop_sel) - 1]

    return {"mic": mic_device, "loopback": loop_device}
