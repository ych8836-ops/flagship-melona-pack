import math

import torch
import torch.nn.functional as F
import torchaudio


class H3DynamicResonanceSuppressor:
    """Reduce a resonant band only while that band becomes excessive."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "center_freq": (
                    "INT",
                    {"default": 320, "min": 120, "max": 1200, "step": 5},
                ),
                "q": (
                    "FLOAT",
                    {"default": 0.8, "min": 0.2, "max": 5.0, "step": 0.05},
                ),
                "threshold_db": (
                    "FLOAT",
                    {"default": -22.0, "min": -60.0, "max": 0.0, "step": 0.5},
                ),
                "ratio": (
                    "FLOAT",
                    {"default": 2.5, "min": 1.0, "max": 10.0, "step": 0.1},
                ),
                "max_reduction_db": (
                    "FLOAT",
                    {"default": 2.0, "min": 0.0, "max": 12.0, "step": 0.1},
                ),
                "attack_ms": (
                    "FLOAT",
                    {"default": 30.0, "min": 1.0, "max": 500.0, "step": 1.0},
                ),
                "release_ms": (
                    "FLOAT",
                    {"default": 180.0, "min": 10.0, "max": 2000.0, "step": 5.0},
                ),
                "mix": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "reduction_info")
    FUNCTION = "process"
    CATEGORY = "Flagship Melona/Audio"
    DESCRIPTION = (
        "Dynamically attenuates a low-mid resonance only when it becomes "
        "excessive. It does not normalize, hard-clip, or use an AI model."
    )

    @staticmethod
    def _smooth_reduction(values, attack_coeff, release_coeff):
        smoothed = torch.empty_like(values)
        previous = torch.zeros_like(values[:, 0])
        for index in range(values.shape[1]):
            target = values[:, index]
            coefficient = torch.where(
                target > previous,
                torch.full_like(previous, attack_coeff),
                torch.full_like(previous, release_coeff),
            )
            previous = coefficient * previous + (1.0 - coefficient) * target
            smoothed[:, index] = previous
        return smoothed

    def process(
        self,
        audio,
        center_freq,
        q,
        threshold_db,
        ratio,
        max_reduction_db,
        attack_ms,
        release_ms,
        mix,
    ):
        if audio is None:
            return (None, "No audio input")

        waveform = audio["waveform"]
        sample_rate = int(audio["sample_rate"])
        if waveform.shape[-1] == 0:
            return (audio, "Empty audio input")

        nyquist = sample_rate / 2.0
        frequency = min(float(center_freq), nyquist * 0.95)
        working = waveform.float()
        original_shape = working.shape

        if working.ndim == 1:
            working = working.reshape(1, 1, -1)
        elif working.ndim == 2:
            working = working.unsqueeze(0)
        elif working.ndim != 3:
            raise ValueError("AUDIO waveform must have 1, 2, or 3 dimensions")

        batch, channels, samples = working.shape
        flattened = working.reshape(batch * channels, samples)
        band = torchaudio.functional.bandpass_biquad(
            flattened,
            sample_rate,
            central_freq=frequency,
            Q=float(q),
        ).reshape(batch, channels, samples)

        hop = max(1, int(round(sample_rate * 0.010)))
        window = max(hop, int(round(sample_rate * 0.040)))
        detector = band.square().mean(dim=1)
        if samples < window:
            detector = F.pad(detector, (0, window - samples))
        frames = detector.unfold(-1, window, hop).mean(dim=-1)
        level_db = 10.0 * torch.log10(frames.clamp_min(1.0e-12))

        slope = 1.0 - (1.0 / max(float(ratio), 1.0))
        reduction = (level_db - float(threshold_db)).clamp_min(0.0) * slope
        reduction = reduction.clamp_max(float(max_reduction_db))

        hop_seconds = hop / float(sample_rate)
        attack_coeff = math.exp(-hop_seconds / max(float(attack_ms) / 1000.0, 1.0e-4))
        release_coeff = math.exp(-hop_seconds / max(float(release_ms) / 1000.0, 1.0e-4))
        reduction = self._smooth_reduction(reduction, attack_coeff, release_coeff)

        gain = torch.pow(10.0, -reduction / 20.0)
        gain = F.interpolate(
            gain.unsqueeze(1), size=samples, mode="linear", align_corners=False
        )

        processed = working - band * (1.0 - gain) * float(mix)
        processed = processed.to(dtype=waveform.dtype)
        if len(original_shape) == 1:
            processed = processed.reshape(-1)
        elif len(original_shape) == 2:
            processed = processed.squeeze(0)

        mean_reduction = float(reduction.mean().detach().cpu())
        peak_reduction = float(reduction.max().detach().cpu())
        info = (
            f"center={frequency:.0f}Hz, Q={float(q):.2f}, "
            f"mean reduction={mean_reduction:.2f}dB, "
            f"peak reduction={peak_reduction:.2f}dB"
        )
        return ({"waveform": processed, "sample_rate": sample_rate}, info)


NODE_CLASS_MAPPINGS = {
    "H3DynamicResonanceSuppressor": H3DynamicResonanceSuppressor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3DynamicResonanceSuppressor": "H3 Dynamic Resonance Suppressor",
}
