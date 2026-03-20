from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
import torch as th


def _convert_audio_channels(wav: th.Tensor, channels: int) -> th.Tensor:
    src_channels = wav.shape[-2]
    if src_channels == channels:
        return wav
    if channels == 1:
        return wav.mean(dim=-2, keepdim=True)
    if src_channels == 1:
        return wav.expand(channels, wav.shape[-1])
    if src_channels >= channels:
        return wav[:channels]
    raise ValueError("Unsupported channel conversion for Demucs input.")


def _load_wav_audio(path: Path, audio_channels: int, samplerate: int) -> th.Tensor:
    import julius

    with wave.open(str(path), "rb") as wav_file:
        src_channels = wav_file.getnchannels()
        src_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    dtype_map = {
        1: np.uint8,
        2: np.int16,
        4: np.int32,
    }
    if sample_width not in dtype_map:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    data = np.frombuffer(raw, dtype=dtype_map[sample_width])
    if src_channels > 1:
        data = data.reshape(-1, src_channels)
    else:
        data = data.reshape(-1, 1)

    if sample_width == 1:
        audio = (data.astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        audio = data.astype(np.float32) / 32768.0
    else:
        audio = data.astype(np.float32) / 2147483648.0

    tensor = th.from_numpy(audio.T.copy())
    tensor = _convert_audio_channels(tensor, audio_channels)
    if src_rate != samplerate:
        tensor = julius.resample_frac(tensor, src_rate, samplerate)
    return tensor


def _save_wav_audio(wav: th.Tensor, path: Path, samplerate: int) -> None:
    tensor = wav.detach().cpu().float().clamp(-1.0, 1.0)
    pcm = (tensor * 32767.0).round().short().transpose(0, 1).contiguous().numpy()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(int(tensor.shape[0]))
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(pcm.tobytes())


def _load_model(model_name: str, repo_dir: Path):
    from demucs.pretrained import get_model

    original_load = th.load

    def _compat_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    th.load = _compat_load
    try:
        return get_model(name=model_name, repo=repo_dir)
    finally:
        th.load = original_load


def _resolve_segment(model, requested_segment: int | None) -> int | None:
    # Hybrid transformer bags behave best with their native segmentation.
    if hasattr(model, "models"):
        return None
    return requested_segment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--model", default="htdemucs")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    repo_dir = Path(args.repo)

    from demucs.apply import apply_model

    model = _load_model(args.model, repo_dir)
    model.cpu()
    model.eval()
    segment = _resolve_segment(model, 8)

    wav = _load_wav_audio(input_path, model.audio_channels, model.samplerate)
    ref = wav.mean(0)
    wav = wav - ref.mean()
    std = ref.std()
    scale = std.item() if hasattr(std, "item") else float(std)
    if scale > 1e-8:
        wav = wav / std
    else:
        scale = 1.0

    with th.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device="cpu",
            shifts=1,
            split=True,
            overlap=0.25,
            progress=False,
            num_workers=0,
            segment=segment,
        )[0]
    sources = sources * scale
    sources = sources + ref.mean()

    vocals_index = list(model.sources).index("vocals")
    _save_wav_audio(sources[vocals_index].cpu(), output_path, model.samplerate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
