"""
Design a Car Rental System
==========================

Assumptions / Reduced Scope:
  - Single rental location (multi-location is a straightforward extension).
  - Members are the only actors; no receptionist/worker role hierarchy.
  - Flat daily rate per vehicle type (no sub-types like economy/luxury car).
  - Late returns incur a per-day surcharge (simple late fee model).
  - A vehicle can only be part of one active reservation at a time.

Main Use Cases Implemented:
  1. Add vehicles to the system inventory.
  2. Search available vehicles by type.
  3. Member makes a reservation (date range + vehicle).
  4. Member picks up a reserved vehicle.
  5. Member returns a vehicle; bill is computed (including late fees).
  6. Member cancels a reservation.

What Was Left Out:
  - Full account hierarchy (Receptionist, Worker, AdditionalDriver).
  - Equipment rental, insurance, and additional services.
  - Complex billing (itemized bill, tax, payment gateway integration).
  - Notification system (approaching pickup / overdue alerts).
  - Barcode scanning and vehicle logs.
  - Multi-location drop-off logic.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VehicleType(Enum):
    CAR = auto()
    VAN = auto()
    SUV = auto()
    TRUCK = auto()


class VehicleStatus(Enum):
    AVAILABLE = auto()
    RESERVED = auto()
    LOANED = auto()


class ReservationStatus(Enum):
    PENDING = auto()    # reservation created, not yet picked up
    ACTIVE = auto()     # vehicle has been picked up
    COMPLETED = auto()  # vehicle returned
    CANCELLED = auto()


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------

class Vehicle:
    """Represents a rentable vehicle in the fleet."""

    # Daily rates by vehicle type (dollars).
    DAILY_RATES: dict[VehicleType, float] = {
        VehicleType.CAR: 50.0,
        VehicleType.VAN: 70.0,
        VehicleType.SUV: 80.0,
        VehicleType.TRUCK: 100.0,
    }

    def __init__(
        self,
        vehicle_id: str,
        license_plate: str,
        vehicle_type: VehicleType,
        make: str,
        model: str,
        year: int,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.vehicle_type = vehicle_type
        self.make = make
        self.model = model
        self.year = year
        self.status = VehicleStatus.AVAILABLE

    @property
    def daily_rate(self) -> float:
        return self.DAILY_RATES[self.vehicle_type]

    def __repr__(self) -> str:
        return (
            f"Vehicle({self.vehicle_type.name}, {self.make} {self.model} "
            f"{self.year}, plate={self.license_plate}, "
            f"status={self.status.name})"
        )


class Member:
    """A registered member who can search, reserve, and rent vehicles."""

    def __init__(self, member_id: str, name: str, email: str) -> None:
        self.member_id = member_id
        self.name = name
        self.email = email

    def __repr__(self) -> str:
        return f"Member({self.name}, {self.email})"


class VehicleReservation:
    """Tracks the lifecycle of a single vehicle rental."""

    LATE_FEE_PER_DAY: float = 30.0

    def __init__(
        self,
        member: Member,
        vehicle: Vehicle,
        start_date: date,
        end_date: date,
    ) -> None:
        self.reservation_id: str = uuid.uuid4().hex[:8]
        self.member = member
        self.vehicle = vehicle
        self.start_date = start_date
        self.end_date = end_date
        self.status = ReservationStatus.PENDING
        self.return_date: Optional[date] = None
        self.total_bill: float = 0.0

    # -- lifecycle ----------------------------------------------------------

    def pick_up(self) -> None:
        """Member picks up the vehicle."""
        if self.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot pick up: reservation is {self.status.name}"
            )
        self.status = ReservationStatus.ACTIVE
        self.vehicle.status = VehicleStatus.LOANED

    def return_vehicle(self, return_date: date) -> float:
        """Member returns the vehicle; computes and returns the total bill."""
        if self.status != ReservationStatus.ACTIVE:
            raise ValueError(
                f"Cannot return: reservation is {self.status.name}"
            )
        self.return_date = return_date
        self.total_bill = self._compute_bill()
        self.status = ReservationStatus.COMPLETED
        self.vehicle.status = VehicleStatus.AVAILABLE
        return self.total_bill

    def cancel(self) -> None:
        """Cancel a pending reservation."""
        if self.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot cancel: reservation is {self.status.name}"
            )
        self.status = ReservationStatus.CANCELLED
        self.vehicle.status = VehicleStatus.AVAILABLE

    # -- billing ------------------------------------------------------------

    def _compute_bill(self) -> float:
        rental_days = max((self.end_date - self.start_date).days, 1)
        base_charge = rental_days * self.vehicle.daily_rate

        late_fee = 0.0
        if self.return_date and self.return_date > self.end_date:
            late_days = (self.return_date - self.end_date).days
            late_fee = late_days * self.LATE_FEE_PER_DAY

        return base_charge + late_fee

    def __repr__(self) -> str:
        return (
            f"Reservation({self.reservation_id}, "
            f"{self.member.name}, "
            f"{self.vehicle.make} {self.vehicle.model}, "
            f"{self.status.name})"
        )


# ---------------------------------------------------------------------------
# Car Rental System (Facade / Service Layer)
# ---------------------------------------------------------------------------

class CarRentalSystem:
    """
    Top-level facade that manages vehicles, members, and reservations.

    In a real system this would delegate to repositories / databases;
    here we keep in-memory collections for interview clarity.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._vehicles: dict[str, Vehicle] = {}              # vehicle_id -> Vehicle
        self._members: dict[str, Member] = {}                # member_id -> Member
        self._reservations: dict[str, VehicleReservation] = {}  # res_id -> Reservation

    # -- inventory management -----------------------------------------------

    def add_vehicle(self, vehicle: Vehicle) -> None:
        if vehicle.vehicle_id in self._vehicles:
            raise ValueError(f"Vehicle {vehicle.vehicle_id} already exists")
        self._vehicles[vehicle.vehicle_id] = vehicle

    def register_member(self, member: Member) -> None:
        if member.member_id in self._members:
            raise ValueError(f"Member {member.member_id} already exists")
        self._members[member.member_id] = member

    # -- search -------------------------------------------------------------

    def search_available(
        self,
        vehicle_type: Optional[VehicleType] = None,
    ) -> list[Vehicle]:
        """Return available vehicles, optionally filtered by type."""
        results = [
            v for v in self._vehicles.values()
            if v.status == VehicleStatus.AVAILABLE
        ]
        if vehicle_type is not None:
            results = [v for v in results if v.vehicle_type == vehicle_type]
        return results

    # -- reservation workflow -----------------------------------------------

    def make_reservation(
        self,
        member_id: str,
        vehicle_id: str,
        start_date: date,
        end_date: date,
    ) -> VehicleReservation:
        """Create a reservation (vehicle becomes RESERVED immediately)."""
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"Unknown member: {member_id}")

        vehicle = self._vehicles.get(vehicle_id)
        if vehicle is None:
            raise ValueError(f"Unknown vehicle: {vehicle_id}")
        if vehicle.status != VehicleStatus.AVAILABLE:
            raise ValueError(
                f"Vehicle {vehicle_id} is not available "
                f"(status={vehicle.status.name})"
            )
        if end_date <= start_date:
            raise ValueError("end_date must be after start_date")

        vehicle.status = VehicleStatus.RESERVED
        reservation = VehicleReservation(member, vehicle, start_date, end_date)
        self._reservations[reservation.reservation_id] = reservation
        return reservation

    def pick_up_vehicle(self, reservation_id: str) -> None:
        """Member picks up a reserved vehicle."""
        res = self._get_reservation(reservation_id)
        res.pick_up()

    def return_vehicle(
        self,
        reservation_id: str,
        return_date: date,
    ) -> float:
        """Return a vehicle and get the total bill amount."""
        res = self._get_reservation(reservation_id)
        return res.return_vehicle(return_date)

    def cancel_reservation(self, reservation_id: str) -> None:
        """Cancel a pending reservation."""
        res = self._get_reservation(reservation_id)
        res.cancel()

    # -- queries ------------------------------------------------------------

    def get_member_reservations(
        self, member_id: str
    ) -> list[VehicleReservation]:
        return [
            r for r in self._reservations.values()
            if r.member.member_id == member_id
        ]

    # -- helpers ------------------------------------------------------------

    def _get_reservation(self, reservation_id: str) -> VehicleReservation:
        res = self._reservations.get(reservation_id)
        if res is None:
            raise ValueError(f"Unknown reservation: {reservation_id}")
        return res


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    system = CarRentalSystem("Metro Car Rentals")

    # --- Set up inventory ---
    vehicles = [
        Vehicle("V1", "ABC-1234", VehicleType.CAR, "Toyota", "Camry", 2023),
        Vehicle("V2", "DEF-5678", VehicleType.SUV, "Ford", "Explorer", 2022),
        Vehicle("V3", "GHI-9012", VehicleType.VAN, "Honda", "Odyssey", 2024),
        Vehicle("V4", "JKL-3456", VehicleType.TRUCK, "Ram", "1500", 2023),
    ]
    for v in vehicles:
        system.add_vehicle(v)

    # --- Register a member ---
    alice = Member("M1", "Alice Johnson", "alice@example.com")
    system.register_member(alice)

    # --- Search for available SUVs ---
    print("Available SUVs:")
    for v in system.search_available(VehicleType.SUV):
        print(f"  {v}")

    # --- Make a reservation ---
    res = system.make_reservation(
        "M1", "V2",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 5),
    )
    print(f"\nReservation created: {res}")

    # --- Pick up the vehicle ---
    system.pick_up_vehicle(res.reservation_id)
    print(f"After pickup: {res}")

    # --- Return the vehicle (on time) ---
    bill = system.return_vehicle(res.reservation_id, return_date=date(2026, 4, 5))
    print(f"Returned on time. Bill: ${bill:.2f}")

    # --- Another reservation with a late return ---
    res2 = system.make_reservation(
        "M1", "V1",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 4),
    )
    system.pick_up_vehicle(res2.reservation_id)
    late_bill = system.return_vehicle(
        res2.reservation_id, return_date=date(2026, 5, 6)
    )
    print(f"\nReturned late (2 days over). Bill: ${late_bill:.2f}")
    print(f"  Base: 3 days x ${Vehicle.DAILY_RATES[VehicleType.CAR]:.2f} "
          f"= ${3 * Vehicle.DAILY_RATES[VehicleType.CAR]:.2f}")
    print(f"  Late fee: 2 days x ${VehicleReservation.LATE_FEE_PER_DAY:.2f} "
          f"= ${2 * VehicleReservation.LATE_FEE_PER_DAY:.2f}")

    # --- Cancel a reservation ---
    res3 = system.make_reservation(
        "M1", "V3",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
    )
    system.cancel_reservation(res3.reservation_id)
    print(f"\nCancelled reservation: {res3}")

    # --- Show member history ---
    print(f"\nAll reservations for {alice.name}:")
    for r in system.get_member_reservations("M1"):
        print(f"  {r} | bill=${r.total_bill:.2f}")
