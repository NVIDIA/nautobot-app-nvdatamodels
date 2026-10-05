"""Pure coordinate policies for LPU C2C topologies."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from nautobot_nvdatamodels.choices import LPUC2CTopologyChoices


@dataclass(frozen=True, order=True)
class LocalCoordinate:
    """Topology-local location of an LPU C2C member."""

    tray_slot: int | None = None

    def sort_key(self):
        """Return a stable topology-aware coordinate sort key."""
        return (0, self.tray_slot or 0)


class CoordinatePolicyError(ValueError):
    """A coordinate policy validation error with a stable machine code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _invalid_native_position(native_position):
    raise CoordinatePolicyError(
        "INVALID_NATIVE_POSITION", f"Native position {native_position!r} is not valid for this topology."
    )


def _parse_native_position(native_position):
    if native_position is None or isinstance(native_position, bool):
        _invalid_native_position(native_position)
    if isinstance(native_position, int):
        return native_position
    if isinstance(native_position, Decimal):
        try:
            if not native_position.is_finite() or native_position != native_position.to_integral_value():
                _invalid_native_position(native_position)
        except InvalidOperation:
            _invalid_native_position(native_position)
        return int(native_position)
    _invalid_native_position(native_position)


def derive_local_coordinate(topology, native_position):
    """Derive a topology-local coordinate from a native rack position."""
    position = _parse_native_position(native_position)

    if topology == LPUC2CTopologyChoices.LP30_C2C:
        if position < 8 or position > 38 or (position - 8) % 2:
            _invalid_native_position(native_position)
        index = (position - 8) // 2
        return LocalCoordinate(tray_slot=index + 1)

    _invalid_native_position(native_position)


def _invalid_coordinate_override():
    raise CoordinatePolicyError(
        "INVALID_COORDINATE_OVERRIDE", "Coordinate override is not valid for this topology."
    )


def _is_coordinate_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def resolve_local_coordinate(topology, native_position, tray_slot=None):
    """Resolve an explicit valid override or derive the native coordinate."""
    if tray_slot is None:
        return derive_local_coordinate(topology, native_position)

    if topology == LPUC2CTopologyChoices.LP30_C2C:
        if _is_coordinate_integer(tray_slot) and tray_slot in range(1, 17):
            return LocalCoordinate(tray_slot=tray_slot)
        _invalid_coordinate_override()

    _invalid_coordinate_override()
