"""
Design a Parking Lot -- Interview-Feasible Solution
====================================================

Assumptions / Reduced Scope:
  - Single parking lot (singleton), multiple floors, each floor has spots.
  - Four spot types: COMPACT, LARGE, HANDICAPPED, MOTORCYCLE.
  - Four vehicle types: CAR, TRUCK, VAN, MOTORCYCLE.
  - Vehicles are mapped to compatible spot types (e.g. trucks -> LARGE only).
  - Hourly rate model: $4 first hour, $3.50 hours 2-3, $2.50 thereafter.
  - No concurrency / thread-safety (interview simplification).

Main Use Cases Implemented:
  1. Vehicle enters the lot and receives a ticket with an assigned spot.
  2. Vehicle is parked in the first available compatible spot (floor-by-floor).
  3. Vehicle pays (fee computed from entry time) and exits, freeing the spot.
  4. Lot reports when full (per vehicle type).

What Was Left Out:
  - Display boards, electric panel / electric spot type.
  - Admin CRUD flows (add/remove floors, spots, panels).
  - Account system (Admin, ParkingAttendant, Customer accounts).
  - Entrance / exit panel objects, customer info portals.
  - Payment gateway integration (cash vs. credit card distinction).
  - Thread-safe locking (trivial to add with threading.Lock).
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VehicleType(Enum):
    CAR = auto()
    TRUCK = auto()
    VAN = auto()
    MOTORCYCLE = auto()


class SpotType(Enum):
    COMPACT = auto()
    LARGE = auto()
    HANDICAPPED = auto()
    MOTORCYCLE = auto()


class TicketStatus(Enum):
    ACTIVE = auto()
    PAID = auto()


# Maps each vehicle type to the spot types it may occupy, in preference order.
VEHICLE_SPOT_COMPATIBILITY: dict[VehicleType, list[SpotType]] = {
    VehicleType.CAR:        [SpotType.COMPACT, SpotType.LARGE],
    VehicleType.TRUCK:      [SpotType.LARGE],
    VehicleType.VAN:        [SpotType.LARGE],
    VehicleType.MOTORCYCLE: [SpotType.MOTORCYCLE],
}


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

class Vehicle:
    def __init__(self, license_plate: str, vehicle_type: VehicleType) -> None:
        self.license_plate = license_plate
        self.vehicle_type = vehicle_type
        self.ticket: Optional[ParkingTicket] = None

    def __repr__(self) -> str:
        return f"Vehicle({self.vehicle_type.name}, {self.license_plate!r})"


# ---------------------------------------------------------------------------
# ParkingSpot
# ---------------------------------------------------------------------------

class ParkingSpot:
    def __init__(self, spot_id: str, spot_type: SpotType, floor: int) -> None:
        self.spot_id = spot_id
        self.spot_type = spot_type
        self.floor = floor
        self.vehicle: Optional[Vehicle] = None

    @property
    def is_free(self) -> bool:
        return self.vehicle is None

    def assign_vehicle(self, vehicle: Vehicle) -> None:
        if not self.is_free:
            raise ValueError(f"Spot {self.spot_id} is already occupied.")
        self.vehicle = vehicle

    def remove_vehicle(self) -> Optional[Vehicle]:
        v = self.vehicle
        self.vehicle = None
        return v

    def __repr__(self) -> str:
        status = "free" if self.is_free else f"occupied by {self.vehicle}"
        return f"ParkingSpot({self.spot_id}, {self.spot_type.name}, floor={self.floor}, {status})"


# ---------------------------------------------------------------------------
# ParkingTicket
# ---------------------------------------------------------------------------

class ParkingTicket:
    def __init__(self, vehicle: Vehicle, spot: ParkingSpot, entry_time: Optional[datetime] = None) -> None:
        self.ticket_id: str = uuid.uuid4().hex[:8].upper()
        self.vehicle = vehicle
        self.spot = spot
        self.entry_time: datetime = entry_time or datetime.now()
        self.exit_time: Optional[datetime] = None
        self.amount_paid: float = 0.0
        self.status: TicketStatus = TicketStatus.ACTIVE

    def __repr__(self) -> str:
        return (
            f"ParkingTicket(id={self.ticket_id}, vehicle={self.vehicle.license_plate}, "
            f"spot={self.spot.spot_id}, status={self.status.name})"
        )


# ---------------------------------------------------------------------------
# ParkingRate  (per-hour tiered pricing)
# ---------------------------------------------------------------------------

class ParkingRate:
    """$4.00 first hour, $3.50 hours 2-3, $2.50 each additional hour."""

    def calculate_fee(self, hours: float) -> float:
        full_hours = max(1, math.ceil(hours))  # minimum charge = 1 hour
        total = 0.0
        for h in range(1, full_hours + 1):
            if h == 1:
                total += 4.0
            elif h <= 3:
                total += 3.5
            else:
                total += 2.5
        return total


# ---------------------------------------------------------------------------
# ParkingFloor
# ---------------------------------------------------------------------------

class ParkingFloor:
    def __init__(self, floor_number: int) -> None:
        self.floor_number = floor_number
        self.spots: list[ParkingSpot] = []

    def add_spot(self, spot: ParkingSpot) -> None:
        self.spots.append(spot)

    def find_available_spot(self, spot_types: list[SpotType]) -> Optional[ParkingSpot]:
        """Return the first free spot whose type is in *spot_types*, or None."""
        for spot in self.spots:
            if spot.is_free and spot.spot_type in spot_types:
                return spot
        return None

    def free_spot_count(self, spot_type: Optional[SpotType] = None) -> int:
        return sum(
            1 for s in self.spots
            if s.is_free and (spot_type is None or s.spot_type == spot_type)
        )

    def __repr__(self) -> str:
        return f"ParkingFloor({self.floor_number}, spots={len(self.spots)}, free={self.free_spot_count()})"


# ---------------------------------------------------------------------------
# ParkingLot  (singleton)
# ---------------------------------------------------------------------------

class ParkingLot:
    _instance: Optional[ParkingLot] = None

    def __new__(cls, *args, **kwargs) -> ParkingLot:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str = "Default Lot") -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.name = name
        self.floors: list[ParkingFloor] = []
        self.active_tickets: dict[str, ParkingTicket] = {}
        self.rate = ParkingRate()

    # -- Setup helpers -------------------------------------------------------

    def add_floor(self, floor: ParkingFloor) -> None:
        self.floors.append(floor)

    # -- Core workflow -------------------------------------------------------

    def enter(self, vehicle: Vehicle, entry_time: Optional[datetime] = None) -> ParkingTicket:
        """Assign a spot and issue a ticket, or raise if lot is full for this vehicle type."""
        spot = self._find_spot(vehicle.vehicle_type)
        if spot is None:
            raise Exception(
                f"No available spot for {vehicle.vehicle_type.name} ({vehicle.license_plate})."
            )

        spot.assign_vehicle(vehicle)
        ticket = ParkingTicket(vehicle, spot, entry_time=entry_time)
        ticket.vehicle = vehicle
        vehicle.ticket = ticket
        self.active_tickets[ticket.ticket_id] = ticket
        return ticket

    def exit(self, ticket: ParkingTicket, exit_time: Optional[datetime] = None) -> float:
        """Calculate fee, mark ticket paid, free the spot, and return amount."""
        if ticket.status != TicketStatus.ACTIVE:
            raise ValueError("Ticket already paid / inactive.")

        ticket.exit_time = exit_time or datetime.now()
        hours = (ticket.exit_time - ticket.entry_time).total_seconds() / 3600.0
        fee = self.rate.calculate_fee(hours)

        ticket.amount_paid = fee
        ticket.status = TicketStatus.PAID
        ticket.spot.remove_vehicle()
        self.active_tickets.pop(ticket.ticket_id, None)
        return fee

    # -- Queries -------------------------------------------------------------

    def is_full(self, vehicle_type: Optional[VehicleType] = None) -> bool:
        """Check if the lot is full overall, or for a specific vehicle type."""
        if vehicle_type is None:
            return all(f.free_spot_count() == 0 for f in self.floors)
        return self._find_spot(vehicle_type) is None

    def available_spots(self) -> dict[SpotType, int]:
        counts: dict[SpotType, int] = {st: 0 for st in SpotType}
        for floor in self.floors:
            for st in SpotType:
                counts[st] += floor.free_spot_count(st)
        return counts

    # -- Internals -----------------------------------------------------------

    def _find_spot(self, vehicle_type: VehicleType) -> Optional[ParkingSpot]:
        compatible = VEHICLE_SPOT_COMPATIBILITY[vehicle_type]
        for floor in self.floors:
            spot = floor.find_available_spot(compatible)
            if spot is not None:
                return spot
        return None

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing / demo reruns)."""
        cls._instance = None

    def __repr__(self) -> str:
        total = sum(len(f.spots) for f in self.floors)
        free = sum(f.free_spot_count() for f in self.floors)
        return f"ParkingLot({self.name!r}, floors={len(self.floors)}, total_spots={total}, free={free})"


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Reset singleton in case module is re-run
    ParkingLot.reset()

    # -- Build the lot -------------------------------------------------------
    lot = ParkingLot("Downtown Garage")

    floor1 = ParkingFloor(floor_number=1)
    for i in range(1, 6):
        floor1.add_spot(ParkingSpot(f"1-C{i}", SpotType.COMPACT, floor=1))
    for i in range(1, 4):
        floor1.add_spot(ParkingSpot(f"1-L{i}", SpotType.LARGE, floor=1))
    floor1.add_spot(ParkingSpot("1-H1", SpotType.HANDICAPPED, floor=1))
    floor1.add_spot(ParkingSpot("1-M1", SpotType.MOTORCYCLE, floor=1))

    floor2 = ParkingFloor(floor_number=2)
    for i in range(1, 4):
        floor2.add_spot(ParkingSpot(f"2-C{i}", SpotType.COMPACT, floor=2))
    for i in range(1, 3):
        floor2.add_spot(ParkingSpot(f"2-L{i}", SpotType.LARGE, floor=2))
    floor2.add_spot(ParkingSpot("2-M1", SpotType.MOTORCYCLE, floor=2))

    lot.add_floor(floor1)
    lot.add_floor(floor2)

    print(lot)
    print(f"Available spots: {lot.available_spots()}\n")

    # -- Simulate vehicles entering ------------------------------------------
    now = datetime.now()

    car = Vehicle("ABC-1234", VehicleType.CAR)
    truck = Vehicle("TRK-9999", VehicleType.TRUCK)
    moto = Vehicle("MOTO-42", VehicleType.MOTORCYCLE)

    t1 = lot.enter(car, entry_time=now - timedelta(hours=2, minutes=30))
    t2 = lot.enter(truck, entry_time=now - timedelta(hours=5))
    t3 = lot.enter(moto, entry_time=now - timedelta(minutes=45))

    print(f"Issued: {t1}")
    print(f"Issued: {t2}")
    print(f"Issued: {t3}")
    print(f"\n{lot}")
    print(f"Available spots: {lot.available_spots()}\n")

    # -- Vehicles pay and exit -----------------------------------------------
    fee1 = lot.exit(t1, exit_time=now)
    print(f"{car.license_plate} parked ~2.5 hrs -> fee: ${fee1:.2f}")

    fee2 = lot.exit(t2, exit_time=now)
    print(f"{truck.license_plate} parked ~5 hrs -> fee: ${fee2:.2f}")

    fee3 = lot.exit(t3, exit_time=now)
    print(f"{moto.license_plate} parked ~45 min -> fee: ${fee3:.2f}")

    print(f"\n{lot}")
    print(f"Available spots: {lot.available_spots()}")

    # -- Edge case: lot full -------------------------------------------------
    print(f"\nIs lot full for TRUCK? {lot.is_full(VehicleType.TRUCK)}")
    print(f"Is lot full overall? {lot.is_full()}")
