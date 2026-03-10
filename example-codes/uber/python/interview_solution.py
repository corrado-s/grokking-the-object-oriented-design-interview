"""
Design Uber -- Interview-Feasible OOD Solution
===============================================

Problem: Design a simplified ride-sharing system (Uber).

Assumptions / Reduced Scope:
  - Single city, no multi-region support.
  - Driver matching uses a naive nearest-available search (no spatial index).
  - Distance computed with the Haversine formula for realism, but the
    coordinate space is kept small for demo purposes.
  - Fare = base fare + per-km rate * distance.  No surge pricing, no
    per-minute component, no ride-type multipliers.
  - One active trip per rider at a time; one active trip per driver.
  - No authentication, payments, notifications, or persistent storage.

Main Use Cases Implemented:
  1. Rider requests a ride (pickup + dropoff locations).
  2. RideService finds the nearest available driver and creates a Trip.
  3. Driver accepts the trip  ->  status becomes MATCHED.
  4. Driver starts the trip   ->  status becomes IN_PROGRESS.
  5. Driver completes the trip -> fare is calculated, status becomes COMPLETED.
  6. Either party may cancel   -> status becomes CANCELLED.

What Was Left Out:
  - Account hierarchy / account-status management.
  - Payment processing and billing details.
  - Driver/rider rating system.
  - Surge / dynamic pricing.
  - Notification system (push, SMS, email).
  - Route optimization and ETA calculation.
  - Real-time GPS tracking stream.
  - Ride types (UberX, XL, Black, Pool).
  - Concurrency / thread safety.
"""

from __future__ import annotations

import math
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TripStatus(Enum):
    REQUESTED = auto()
    MATCHED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class DriverStatus(Enum):
    AVAILABLE = auto()
    ON_TRIP = auto()
    OFFLINE = auto()


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Location:
    """Immutable geographic coordinate."""
    latitude: float
    longitude: float

    def distance_km(self, other: Location) -> float:
        """Haversine distance in kilometres."""
        R = 6_371  # Earth radius in km
        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlon = math.radians(other.longitude - self.longitude)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def __str__(self) -> str:
        return f"({self.latitude:.4f}, {self.longitude:.4f})"


@dataclass
class Vehicle:
    license_plate: str
    make: str
    model: str


# ---------------------------------------------------------------------------
# Domain Entities
# ---------------------------------------------------------------------------

class Rider:
    def __init__(self, name: str) -> None:
        self.rider_id: str = uuid.uuid4().hex[:8]
        self.name = name

    def __repr__(self) -> str:
        return f"Rider({self.name!r})"


class Driver:
    def __init__(self, name: str, vehicle: Vehicle, location: Location) -> None:
        self.driver_id: str = uuid.uuid4().hex[:8]
        self.name = name
        self.vehicle = vehicle
        self.location = location
        self.status: DriverStatus = DriverStatus.AVAILABLE

    def go_online(self) -> None:
        self.status = DriverStatus.AVAILABLE

    def go_offline(self) -> None:
        self.status = DriverStatus.OFFLINE

    def update_location(self, location: Location) -> None:
        self.location = location

    def __repr__(self) -> str:
        return f"Driver({self.name!r}, status={self.status.name})"


@dataclass
class Trip:
    trip_id: str
    rider: Rider
    pickup: Location
    dropoff: Location
    status: TripStatus = TripStatus.REQUESTED
    driver: Optional[Driver] = None
    fare: Optional[float] = None

    # -- state transitions --------------------------------------------------

    def match_driver(self, driver: Driver) -> None:
        if self.status != TripStatus.REQUESTED:
            raise ValueError(f"Cannot match driver: trip is {self.status.name}")
        self.driver = driver
        self.status = TripStatus.MATCHED
        driver.status = DriverStatus.ON_TRIP

    def start(self) -> None:
        if self.status != TripStatus.MATCHED:
            raise ValueError(f"Cannot start: trip is {self.status.name}")
        self.status = TripStatus.IN_PROGRESS

    def complete(self, fare: float) -> None:
        if self.status != TripStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete: trip is {self.status.name}")
        self.fare = fare
        self.status = TripStatus.COMPLETED
        if self.driver:
            self.driver.status = DriverStatus.AVAILABLE

    def cancel(self) -> None:
        if self.status in (TripStatus.COMPLETED, TripStatus.CANCELLED):
            raise ValueError(f"Cannot cancel: trip is {self.status.name}")
        self.status = TripStatus.CANCELLED
        if self.driver:
            self.driver.status = DriverStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Service Layer
# ---------------------------------------------------------------------------

class RideService:
    """
    Central coordinator -- the 'system' that owns drivers, riders, and trips.
    In an interview this would be the Facade / Application Service.
    """

    BASE_FARE: float = 3.00  # dollars
    PER_KM_RATE: float = 1.50  # dollars per km

    def __init__(self) -> None:
        self._drivers: dict[str, Driver] = {}
        self._riders: dict[str, Rider] = {}
        self._trips: dict[str, Trip] = {}

    # -- registration -------------------------------------------------------

    def register_rider(self, rider: Rider) -> None:
        self._riders[rider.rider_id] = rider

    def register_driver(self, driver: Driver) -> None:
        self._drivers[driver.driver_id] = driver

    # -- core workflow ------------------------------------------------------

    def request_ride(self, rider: Rider, pickup: Location, dropoff: Location) -> Trip:
        """Rider requests a ride; system finds nearest driver and creates a Trip."""
        trip_id = uuid.uuid4().hex[:8]
        trip = Trip(trip_id=trip_id, rider=rider, pickup=pickup, dropoff=dropoff)
        self._trips[trip_id] = trip

        driver = self._find_nearest_driver(pickup)
        if driver is None:
            print(f"  [RideService] No available drivers for trip {trip_id}.")
            return trip

        trip.match_driver(driver)
        print(f"  [RideService] Trip {trip_id}: matched rider {rider.name} "
              f"with driver {driver.name}.")
        return trip

    def start_trip(self, trip: Trip) -> None:
        trip.start()
        print(f"  [RideService] Trip {trip.trip_id} is now in progress.")

    def complete_trip(self, trip: Trip) -> None:
        fare = self._calculate_fare(trip.pickup, trip.dropoff)
        trip.complete(fare)
        print(f"  [RideService] Trip {trip.trip_id} completed. "
              f"Fare: ${fare:.2f}")

    def cancel_trip(self, trip: Trip) -> None:
        trip.cancel()
        print(f"  [RideService] Trip {trip.trip_id} cancelled.")

    # -- internals ----------------------------------------------------------

    def _find_nearest_driver(self, pickup: Location) -> Optional[Driver]:
        available = [d for d in self._drivers.values()
                     if d.status == DriverStatus.AVAILABLE]
        if not available:
            return None
        return min(available, key=lambda d: d.location.distance_km(pickup))

    def _calculate_fare(self, pickup: Location, dropoff: Location) -> float:
        distance = pickup.distance_km(dropoff)
        return round(self.BASE_FARE + self.PER_KM_RATE * distance, 2)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    service = RideService()

    # -- create some drivers with vehicles and locations --------------------
    driver_alice = Driver(
        name="Alice",
        vehicle=Vehicle("ABC-1234", "Toyota", "Camry"),
        location=Location(40.7128, -74.0060),   # Manhattan
    )
    driver_bob = Driver(
        name="Bob",
        vehicle=Vehicle("XYZ-5678", "Honda", "Civic"),
        location=Location(40.7580, -73.9855),    # Midtown
    )
    service.register_driver(driver_alice)
    service.register_driver(driver_bob)

    # -- create a rider -----------------------------------------------------
    rider_carol = Rider(name="Carol")
    service.register_rider(rider_carol)

    # -- full happy-path workflow -------------------------------------------
    print("=== Ride Request ===")
    pickup = Location(40.7484, -73.9857)   # Empire State Building
    dropoff = Location(40.6892, -74.0445)  # Statue of Liberty
    trip = service.request_ride(rider_carol, pickup, dropoff)
    print(f"  Trip status: {trip.status.name}")

    print("\n=== Start Trip ===")
    service.start_trip(trip)
    print(f"  Trip status: {trip.status.name}")

    print("\n=== Complete Trip ===")
    service.complete_trip(trip)
    print(f"  Trip status: {trip.status.name}")
    print(f"  Fare charged: ${trip.fare:.2f}")
    print(f"  Driver {trip.driver.name} is now: {trip.driver.status.name}")

    # -- cancellation scenario ----------------------------------------------
    print("\n=== Cancellation Scenario ===")
    trip2 = service.request_ride(rider_carol, pickup, dropoff)
    print(f"  Trip status before cancel: {trip2.status.name}")
    service.cancel_trip(trip2)
    print(f"  Trip status after cancel: {trip2.status.name}")
    print(f"  Driver {trip2.driver.name} is now: {trip2.driver.status.name}")
