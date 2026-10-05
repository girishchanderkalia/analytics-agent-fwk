"""Synthetic overlay measurements for the v3 mock scopes.

Stands in for measured wafer overlay until real data is connected. Points are
regenerated deterministically from lot and wafer identifiers, so the trend
KPIs in ``trend_rows_v3.json`` and the TDBB runs in ``tdbb_runs_v3.json`` see
the same wafers. Values are in nm; positions in mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random
from statistics import mean, stdev

WAFER_RADIUS_MM = 150.0
FIELD_HALF_WIDTH_MM = 13.0
FIELD_HALF_HEIGHT_MM = 16.5
# Grid anchored on a field center of the real LotOV9 exposure layout.
FIELD_CENTERS = tuple(
    (round(44.0 + 26.0 * i, 3), round(-56.763 + 33.0 * j, 3))
    for i in range(-7, 5)
    for j in range(-3, 5)
    if math.hypot(44.0 + 26.0 * i, -56.763 + 33.0 * j) <= 135.0
)
INTRAFIELD_POSITIONS = ((0.0, 0.0), (-10.5, -13.5), (10.5, -13.5), (-10.5, 13.5), (10.5, 13.5))

# TDBB level 1 (average/common): a wafer-translation + magnification + rotation
# fingerprint shared by the whole population, not specific to one chuck, lot, or wafer.
TRANSLATION_BASE_NM = (0.55, 0.45)
MAG_BASE_NM = (0.3, 0.25)
ROTATION_BASE_NM = 0.15

# TDBB level 2 (chuck-to-chuck): the two wafer chucks shift in opposite directions.
CHUCK_OFFSETS_NM = {
    "Waferstage chuck ID 1": (0.32, -0.27, -0.045),
    "Waferstage chuck ID 2": (-0.32, 0.27, 0.045),
}

# TDBB level 3 (lot-to-lot): correctable (translation/mag/rotation) spread between lots is
# kept small, while each lot gets its own non-correctable (NCE) fingerprint offset, so most
# lot-to-lot variation shows up as NCE rather than CE.
LOT_TRANSLATION_SIGMA = 0.12
LOT_MAG_SIGMA = 0.08
LOT_ROTATION_SIGMA = 0.05
LOT_NCE_BIAS_NM = 0.15


@dataclass(frozen=True)
class OverlayProfile:
    nce_sigma_nm: float
    nce_edge_nm: float
    change_date: str | None = None
    nce_sigma_after_nm: float | None = None
    nce_edge_after_nm: float | None = None
    ce_shift_x_nm: float = 0.0
    ce_shift_y_nm: float = 0.0
    ce_noise_after_multiplier: float = 1.0

    def nce(self, lot_start: str) -> tuple[float, float]:
        if self.change_date and lot_start[:10] >= self.change_date:
            return self.nce_sigma_after_nm or self.nce_sigma_nm, self.nce_edge_after_nm or self.nce_edge_nm
        return self.nce_sigma_nm, self.nce_edge_nm

    def ce_shift(self, lot_start: str) -> tuple[float, float]:
        # Correctable (translation) step applied from change_date onward, alongside the NCE step.
        if self.change_date and lot_start[:10] >= self.change_date:
            return self.ce_shift_x_nm, self.ce_shift_y_nm
        return 0.0, 0.0

    def ce_noise_multiplier(self, lot_start: str) -> float:
        # Widens CE lot-to-lot/wafer-to-wafer spread from change_date onward, so those
        # context levels rise too (not just the Average fingerprint from ce_shift).
        if self.change_date and lot_start[:10] >= self.change_date:
            return self.ce_noise_after_multiplier
        return 1.0


# (product, layer, scanner) -> profile. Only the first scope has the September step.
PROFILES = {
    ("AAA2", "OV_NO_ID2", "GW021"): OverlayProfile(
        0.62, 0.45, "2026-09-01", 0.92, 1.6, ce_shift_x_nm=0.6, ce_shift_y_nm=0.5, ce_noise_after_multiplier=1.8,
    ),
    ("AAA2", "OV_KTDB2", "GW021"): OverlayProfile(0.6, 0.45),
    ("AAA2", "OV_NO_ID2", "GW022"): OverlayProfile(0.58, 0.4),
}


def profile_for(product: str | None, layer: str | None, scanner: str | None) -> OverlayProfile | None:
    return PROFILES.get((str(product), str(layer), str(scanner)))


def wafer_points(
    lot_id: str,
    wafer_id: str,
    chuck_id: str | None,
    lot_start: str,
    profile: OverlayProfile,
) -> list[dict[str, float]]:
    """Return overlay components per measured point of one wafer."""

    lot = Random(f"lot|{lot_id}")
    wafer = Random(f"wafer|{lot_id}|{wafer_id}")
    chuck_x, chuck_y, chuck_rot = CHUCK_OFFSETS_NM.get(str(chuck_id), (0.0, 0.0, 0.0))
    shift_x, shift_y = profile.ce_shift(lot_start)
    noise = profile.ce_noise_multiplier(lot_start)
    tx = TRANSLATION_BASE_NM[0] + shift_x + lot.gauss(0, LOT_TRANSLATION_SIGMA * noise) + chuck_x + wafer.gauss(0, 0.12 * noise)
    ty = TRANSLATION_BASE_NM[1] + shift_y + lot.gauss(0, LOT_TRANSLATION_SIGMA * noise) + chuck_y + wafer.gauss(0, 0.12 * noise)
    mag_x = MAG_BASE_NM[0] + lot.gauss(0, LOT_MAG_SIGMA * noise) + wafer.gauss(0, 0.08 * noise)
    mag_y = MAG_BASE_NM[1] + lot.gauss(0, LOT_MAG_SIGMA * noise) + wafer.gauss(0, 0.08 * noise)
    rotation = ROTATION_BASE_NM + chuck_rot + lot.gauss(0, LOT_ROTATION_SIGMA * noise) + wafer.gauss(0, 0.06 * noise)
    field_mag_x = 0.35 + lot.gauss(0, 0.05) + wafer.gauss(0, 0.02)
    field_mag_y = 0.45 + lot.gauss(0, 0.05) + wafer.gauss(0, 0.02)
    field_rotation = 0.2 + lot.gauss(0, 0.04) + wafer.gauss(0, 0.015)
    nce_sigma, nce_edge = profile.nce(lot_start)
    edge = nce_edge * lot.uniform(0.85, 1.15)
    # Level 3 (lot-to-lot): a per-lot non-correctable fingerprint shared by every wafer in the lot.
    lot_nce_bias_x = lot.gauss(0, LOT_NCE_BIAS_NM)
    lot_nce_bias_y = lot.gauss(0, LOT_NCE_BIAS_NM)

    points = []
    for center_x, center_y in FIELD_CENTERS:
        for intra_x, intra_y in INTRAFIELD_POSITIONS:
            x, y = center_x + intra_x, center_y + intra_y
            radius = math.hypot(x, y)
            ce_wafer_x = tx + mag_x * x / WAFER_RADIUS_MM - rotation * y / WAFER_RADIUS_MM
            ce_wafer_y = ty + mag_y * y / WAFER_RADIUS_MM + rotation * x / WAFER_RADIUS_MM
            ce_field_x = field_mag_x * intra_x / FIELD_HALF_WIDTH_MM - field_rotation * intra_y / FIELD_HALF_HEIGHT_MM
            ce_field_y = field_mag_y * intra_y / FIELD_HALF_HEIGHT_MM + field_rotation * intra_x / FIELD_HALF_WIDTH_MM
            roll_off = edge * (radius / WAFER_RADIUS_MM) ** 4
            nce_x = roll_off * (x / radius if radius else 0.0) + lot_nce_bias_x + wafer.gauss(0, nce_sigma)
            nce_y = roll_off * (y / radius if radius else 0.0) + lot_nce_bias_y + wafer.gauss(0, nce_sigma)
            points.append({
                "field_center_x": center_x,
                "field_center_y": center_y,
                "intrafield_position_x": intra_x,
                "intrafield_position_y": intra_y,
                "ce_translation_x": tx,
                "ce_translation_y": ty,
                "ce_wafer_x": ce_wafer_x,
                "ce_wafer_y": ce_wafer_y,
                "ce_field_x": ce_field_x,
                "ce_field_y": ce_field_y,
                "nce_x": nce_x,
                "nce_y": nce_y,
                "overlay_x": ce_wafer_x + ce_field_x + nce_x,
                "overlay_y": ce_wafer_y + ce_field_y + nce_y,
            })
    return points


def m3s(values: list[float]) -> float | None:
    """Overlay KPI: |mean| + 3 sigma, as in the raw-data conversion."""

    if len(values) < 2:
        return None
    return round(abs(mean(values)) + 3 * stdev(values), 3)
