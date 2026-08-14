from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch


@dataclass
class CubeLUT:
    """Parsed Adobe/CapCut-compatible .cube LUT."""

    table: torch.Tensor
    size: int
    is_1d: bool
    domain_min: Tuple[float, float, float]
    domain_max: Tuple[float, float, float]

    def apply(self, image: torch.Tensor) -> torch.Tensor:
        """Apply the LUT to an RGB tensor shaped (..., 3), returning float32 RGB."""
        if image.shape[-1] != 3:
            raise ValueError("LUT application requires an RGB tensor with 3 channels")

        original_shape = image.shape
        rgb = image.to(dtype=torch.float32)
        domain_min = torch.tensor(self.domain_min, device=rgb.device, dtype=rgb.dtype)
        domain_max = torch.tensor(self.domain_max, device=rgb.device, dtype=rgb.dtype)
        span = torch.where((domain_max - domain_min).abs() < 1e-12, 1.0, domain_max - domain_min)
        normalized = ((rgb - domain_min) / span).clamp(0.0, 1.0)

        table = self.table.to(device=rgb.device, dtype=rgb.dtype)
        if self.is_1d:
            positions = normalized * float(self.size - 1)
            low = positions.floor().to(torch.long)
            high = (low + 1).clamp(max=self.size - 1)
            fraction = positions - low.to(dtype=positions.dtype)
            channels = []
            for channel in range(3):
                values = table[:, channel]
                low_values = values[low[..., channel]]
                high_values = values[high[..., channel]]
                channels.append(low_values + (high_values - low_values) * fraction[..., channel])
            return torch.stack(channels, dim=-1).reshape(original_shape).clamp(0.0, 1.0)

        positions = normalized * float(self.size - 1)
        low = positions.floor().to(torch.long)
        high = (low + 1).clamp(max=self.size - 1)
        fraction = positions - low.to(dtype=positions.dtype)

        r0, g0, b0 = low.unbind(dim=-1)
        r1, g1, b1 = high.unbind(dim=-1)
        fr, fg, fb = fraction.unbind(dim=-1)

        flat_table = table.reshape(self.size * self.size * self.size, 3)

        def lookup(r: torch.Tensor, g: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
            index = ((r * self.size) + g) * self.size + b
            return flat_table[index.reshape(-1)].reshape(*index.shape, 3)

        c000 = lookup(r0, g0, b0)
        c001 = lookup(r0, g0, b1)
        c010 = lookup(r0, g1, b0)
        c011 = lookup(r0, g1, b1)
        c100 = lookup(r1, g0, b0)
        c101 = lookup(r1, g0, b1)
        c110 = lookup(r1, g1, b0)
        c111 = lookup(r1, g1, b1)

        fr = fr.unsqueeze(-1)
        fg = fg.unsqueeze(-1)
        fb = fb.unsqueeze(-1)
        c00 = c000 * (1.0 - fb) + c001 * fb
        c01 = c010 * (1.0 - fb) + c011 * fb
        c10 = c100 * (1.0 - fb) + c101 * fb
        c11 = c110 * (1.0 - fb) + c111 * fb
        c0 = c00 * (1.0 - fg) + c01 * fg
        c1 = c10 * (1.0 - fg) + c11 * fg
        return (c0 * (1.0 - fr) + c1 * fr).reshape(original_shape).clamp(0.0, 1.0)


def _parse_vector(parts: List[str], line_number: int) -> Tuple[float, float, float]:
    if len(parts) != 3:
        raise ValueError(f"Invalid .cube vector on line {line_number}")
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError as exc:
        raise ValueError(f"Invalid .cube number on line {line_number}") from exc


def load_cube(path: str) -> CubeLUT:
    """Load a .cube file with 1D or 3D RGB data."""
    lut_1d_size: Optional[int] = None
    lut_3d_size: Optional[int] = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    values: List[Tuple[float, float, float]] = []

    with open(path, "r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            keyword = parts[0].upper()
            if keyword in {"TITLE", "LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE"}:
                continue
            if keyword == "LUT_1D_SIZE":
                if len(parts) != 2:
                    raise ValueError(f"Invalid LUT_1D_SIZE on line {line_number}")
                lut_1d_size = int(parts[1])
                continue
            if keyword == "LUT_3D_SIZE":
                if len(parts) != 2:
                    raise ValueError(f"Invalid LUT_3D_SIZE on line {line_number}")
                lut_3d_size = int(parts[1])
                continue
            if keyword == "DOMAIN_MIN":
                domain_min = _parse_vector(parts[1:], line_number)
                continue
            if keyword == "DOMAIN_MAX":
                domain_max = _parse_vector(parts[1:], line_number)
                continue
            if keyword in {"LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE"}:
                continue
            values.append(_parse_vector(parts, line_number))

    if lut_3d_size is not None and lut_1d_size is not None:
        raise ValueError("A .cube file cannot define both LUT_1D_SIZE and LUT_3D_SIZE")
    if lut_3d_size is not None:
        expected = lut_3d_size ** 3
        if lut_3d_size < 2 or len(values) != expected:
            raise ValueError(f"Expected {expected} 3D LUT entries, found {len(values)}")
        # .cube stores blue as the fastest-changing axis. Keep the runtime
        # lookup order as RGB by reversing the first three axes after reshape.
        table = torch.tensor(values, dtype=torch.float32).reshape(lut_3d_size, lut_3d_size, lut_3d_size, 3)
        table = table.permute(2, 1, 0, 3).contiguous()
        return CubeLUT(table, lut_3d_size, False, domain_min, domain_max)
    if lut_1d_size is not None:
        if lut_1d_size < 2 or len(values) != lut_1d_size:
            raise ValueError(f"Expected {lut_1d_size} 1D LUT entries, found {len(values)}")
        table = torch.tensor(values, dtype=torch.float32).reshape(lut_1d_size, 3)
        return CubeLUT(table, lut_1d_size, True, domain_min, domain_max)
    raise ValueError(".cube file is missing LUT_1D_SIZE or LUT_3D_SIZE")
