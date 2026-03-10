"""
Airline Management System -- Interview-Feasible OOD Solution
============================================================

Problem:
    Design an Airline Management System that supports flight scheduling,
    seat reservations, and booking management.

Assumptions / Reduced Scope:
    - Single airline operating out of known airports.
    - No crew/pilot assignment or staff management.
    - No complex multi-leg itineraries (one reservation = one flight instance).
    - No notification system (email, SMS, push).
    - Payment is modeled as a simple status transition, not a full gateway.
    - No airport-admin role; flights are added programmatically.
    - Aircraft have a fixed seat map created at construction time.

Main Use Cases Implemented:
    1. Search flights by date and origin/destination airport.
    2. View available seats (by class) on a specific flight instance.
    3. Book a seat for a passenger on a flight instance.
    4. Cancel an existing reservation (seat is freed).
    5. Basic flight lifecycle (scheduled -> departed -> arrived / cancelled).

What Was Left Out:
    - Crew management and pilot assignment.
    - Weekly/custom schedule objects (instances are created directly).
    - Multi-flight itineraries and connecting-flight logic.
    - Notification service (email, SMS).
    - Full payment processing / refund workflow.
    - Account authentication, customer profiles, frequent-flyer programs.
    - Airport admin use cases (add/remove aircraft, etc.).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FlightStatus(Enum):
    SCHEDULED = auto()
    ACTIVE = auto()
    DEPARTED = auto()
    ARRIVED = auto()
    CANCELLED = auto()


class ReservationStatus(Enum):
    CONFIRMED = auto()
    CANCELLED = auto()


class SeatClass(Enum):
    ECONOMY = auto()
    BUSINESS = auto()
    FIRST_CLASS = auto()


# ---------------------------------------------------------------------------
# Value / Entity Classes
# ---------------------------------------------------------------------------

class Airport:
    """Represents an airport identified by its IATA code (e.g. 'JFK')."""

    def __init__(self, code: str, name: str, city: str) -> None:
        self.code = code
        self.name = name
        self.city = city

    def __repr__(self) -> str:
        return f"Airport({self.code!r})"


class Seat:
    """A physical seat on an aircraft.  Immutable once created."""

    def __init__(self, number: str, seat_class: SeatClass) -> None:
        self.number = number          # e.g. "12A"
        self.seat_class = seat_class

    def __repr__(self) -> str:
        return f"Seat({self.number}, {self.seat_class.name})"


class Aircraft:
    """An aircraft with a fixed collection of seats."""

    def __init__(self, model: str, registration: str, seats: list[Seat]) -> None:
        self.model = model
        self.registration = registration
        self.seats: list[Seat] = seats

    def __repr__(self) -> str:
        return f"Aircraft({self.registration!r}, seats={len(self.seats)})"


class Passenger:
    """A person traveling on a flight."""

    def __init__(self, name: str, passport_number: str) -> None:
        self.name = name
        self.passport_number = passport_number

    def __repr__(self) -> str:
        return f"Passenger({self.name!r})"


# ---------------------------------------------------------------------------
# Flight & FlightInstance
# ---------------------------------------------------------------------------

class Flight:
    """
    A scheduled route between two airports (e.g. 'AA100 JFK->LAX').
    Acts as a template; actual occurrences are FlightInstance objects.
    """

    def __init__(
        self,
        flight_number: str,
        departure_airport: Airport,
        arrival_airport: Airport,
        duration_minutes: int,
    ) -> None:
        self.flight_number = flight_number
        self.departure_airport = departure_airport
        self.arrival_airport = arrival_airport
        self.duration_minutes = duration_minutes

    def __repr__(self) -> str:
        return (
            f"Flight({self.flight_number}, "
            f"{self.departure_airport.code}->{self.arrival_airport.code})"
        )


class FlightInstance:
    """
    A concrete occurrence of a Flight on a specific date/time, tied to a
    particular Aircraft.  Tracks per-seat availability and reservations.
    """

    def __init__(
        self,
        flight: Flight,
        departure_time: datetime,
        aircraft: Aircraft,
        gate: str = "",
    ) -> None:
        self.instance_id: str = uuid.uuid4().hex[:8]
        self.flight = flight
        self.departure_time = departure_time
        self.aircraft = aircraft
        self.gate = gate
        self.status: FlightStatus = FlightStatus.SCHEDULED

        # seat number -> Seat for quick lookup
        self._seat_map: dict[str, Seat] = {s.number: s for s in aircraft.seats}
        # seat number -> reservation that claimed it (None = available)
        self._reserved: dict[str, Optional[Reservation]] = {
            s.number: None for s in aircraft.seats
        }

    @property
    def arrival_time(self) -> datetime:
        return self.departure_time + timedelta(minutes=self.flight.duration_minutes)

    # -- Queries ------------------------------------------------------------

    def available_seats(self, seat_class: Optional[SeatClass] = None) -> list[Seat]:
        """Return seats that are not yet reserved, optionally filtered by class."""
        results = []
        for seat_num, reservation in self._reserved.items():
            if reservation is None:
                seat = self._seat_map[seat_num]
                if seat_class is None or seat.seat_class == seat_class:
                    results.append(seat)
        return results

    def is_seat_available(self, seat_number: str) -> bool:
        return (
            seat_number in self._reserved
            and self._reserved[seat_number] is None
        )

    # -- Mutations (called by BookingSystem) --------------------------------

    def _reserve_seat(self, seat_number: str, reservation: Reservation) -> None:
        if not self.is_seat_available(seat_number):
            raise ValueError(f"Seat {seat_number} is not available.")
        self._reserved[seat_number] = reservation

    def _release_seat(self, seat_number: str) -> None:
        if seat_number in self._reserved:
            self._reserved[seat_number] = None

    def cancel(self) -> None:
        """Cancel the entire flight instance."""
        self.status = FlightStatus.CANCELLED

    def __repr__(self) -> str:
        dep = self.departure_time.strftime("%Y-%m-%d %H:%M")
        return (
            f"FlightInstance({self.flight.flight_number}, {dep}, "
            f"status={self.status.name})"
        )


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------

class Reservation:
    """
    A confirmed booking linking a Passenger to a Seat on a FlightInstance.
    """

    def __init__(
        self,
        flight_instance: FlightInstance,
        passenger: Passenger,
        seat: Seat,
    ) -> None:
        self.confirmation_number: str = uuid.uuid4().hex[:8].upper()
        self.flight_instance = flight_instance
        self.passenger = passenger
        self.seat = seat
        self.status: ReservationStatus = ReservationStatus.CONFIRMED
        self.created_at: datetime = datetime.now()

    def cancel(self) -> None:
        """Cancel this reservation and free the seat."""
        if self.status == ReservationStatus.CANCELLED:
            raise ValueError("Reservation is already cancelled.")
        self.status = ReservationStatus.CANCELLED
        self.flight_instance._release_seat(self.seat.number)

    def __repr__(self) -> str:
        return (
            f"Reservation({self.confirmation_number}, "
            f"{self.passenger.name}, seat={self.seat.number}, "
            f"{self.status.name})"
        )


# ---------------------------------------------------------------------------
# Airline  (top-level aggregate / facade)
# ---------------------------------------------------------------------------

class Airline:
    """
    Central service that owns flights, instances, and reservations.
    Provides the main workflow: search -> select -> book -> cancel.
    """

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code
        self._flights: list[Flight] = []
        self._instances: list[FlightInstance] = []
        self._reservations: dict[str, Reservation] = {}   # confirmation# -> Reservation

    # -- Admin helpers (simplified) -----------------------------------------

    def add_flight(self, flight: Flight) -> None:
        self._flights.append(flight)

    def schedule_instance(
        self,
        flight: Flight,
        departure_time: datetime,
        aircraft: Aircraft,
        gate: str = "",
    ) -> FlightInstance:
        instance = FlightInstance(flight, departure_time, aircraft, gate)
        self._instances.append(instance)
        return instance

    # -- Search -------------------------------------------------------------

    def search_flights(
        self,
        date: datetime,
        origin: str,
        destination: str,
    ) -> list[FlightInstance]:
        """
        Return all FlightInstances on *date* flying from *origin* to
        *destination* (IATA codes) that are still SCHEDULED.
        """
        results: list[FlightInstance] = []
        for inst in self._instances:
            if inst.status != FlightStatus.SCHEDULED:
                continue
            if inst.departure_time.date() != date.date():
                continue
            if (
                inst.flight.departure_airport.code == origin
                and inst.flight.arrival_airport.code == destination
            ):
                results.append(inst)
        return results

    # -- Booking ------------------------------------------------------------

    def book_seat(
        self,
        flight_instance: FlightInstance,
        passenger: Passenger,
        seat_number: str,
    ) -> Reservation:
        """
        Reserve a specific seat for a passenger on a flight instance.
        Returns the Reservation with a unique confirmation number.
        Raises ValueError if the seat is unavailable or the flight is
        not in SCHEDULED status.
        """
        if flight_instance.status != FlightStatus.SCHEDULED:
            raise ValueError(
                f"Cannot book on flight with status {flight_instance.status.name}."
            )
        if not flight_instance.is_seat_available(seat_number):
            raise ValueError(f"Seat {seat_number} is not available.")

        seat = flight_instance._seat_map[seat_number]
        reservation = Reservation(flight_instance, passenger, seat)
        flight_instance._reserve_seat(seat_number, reservation)
        self._reservations[reservation.confirmation_number] = reservation
        return reservation

    # -- Cancel / Lookup ----------------------------------------------------

    def cancel_reservation(self, confirmation_number: str) -> Reservation:
        """Cancel a reservation by its confirmation number."""
        reservation = self._reservations.get(confirmation_number)
        if reservation is None:
            raise KeyError(f"No reservation found for {confirmation_number}.")
        reservation.cancel()
        return reservation

    def get_reservation(self, confirmation_number: str) -> Reservation:
        reservation = self._reservations.get(confirmation_number)
        if reservation is None:
            raise KeyError(f"No reservation found for {confirmation_number}.")
        return reservation


# ---------------------------------------------------------------------------
# Helper: build a simple aircraft with economy / business / first seats
# ---------------------------------------------------------------------------

def make_aircraft(
    model: str,
    registration: str,
    first: int = 4,
    business: int = 8,
    economy: int = 24,
) -> Aircraft:
    """Factory to create an Aircraft with a realistic seat layout."""
    seats: list[Seat] = []
    row = 1
    letters = "ABCDEF"

    for _ in range(first):
        seats.append(Seat(f"{row}{letters[len(seats) % 2]}", SeatClass.FIRST_CLASS))
        if len(seats) % 2 == 0:
            row += 1
    for _ in range(business):
        seats.append(Seat(f"{row}{letters[len(seats) % 4]}", SeatClass.BUSINESS))
        if len(seats) % 4 == 0:
            row += 1
    for _ in range(economy):
        seats.append(Seat(f"{row}{letters[len(seats) % 6]}", SeatClass.ECONOMY))
        if len(seats) % 6 == 0:
            row += 1

    return Aircraft(model, registration, seats)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # -- Setup airports & airline --
    jfk = Airport("JFK", "John F. Kennedy International", "New York")
    lax = Airport("LAX", "Los Angeles International", "Los Angeles")

    airline = Airline("SkyHigh Airlines", "SH")

    # -- Create a flight template and an aircraft --
    flight_aa100 = Flight("SH100", jfk, lax, duration_minutes=330)
    airline.add_flight(flight_aa100)

    aircraft = make_aircraft("Boeing 737", "N12345")
    print(f"Aircraft: {aircraft}  (seats: {[s.number for s in aircraft.seats]})\n")

    # -- Schedule a concrete instance for tomorrow --
    tomorrow_9am = datetime(2025, 7, 1, 9, 0)
    instance = airline.schedule_instance(flight_aa100, tomorrow_9am, aircraft, gate="B12")
    print(f"Scheduled: {instance}")
    print(f"  Departs : {instance.departure_time}")
    print(f"  Arrives : {instance.arrival_time}\n")

    # -- 1. Search flights --
    results = airline.search_flights(tomorrow_9am, "JFK", "LAX")
    print(f"Search results for JFK->LAX on {tomorrow_9am.date()}: {results}\n")

    # -- 2. Check available seats --
    economy_seats = instance.available_seats(SeatClass.ECONOMY)
    business_seats = instance.available_seats(SeatClass.BUSINESS)
    first_seats = instance.available_seats(SeatClass.FIRST_CLASS)
    print(f"Available -- Economy: {len(economy_seats)}, "
          f"Business: {len(business_seats)}, First: {len(first_seats)}")

    # -- 3. Book a seat --
    passenger_alice = Passenger("Alice Smith", "US12345678")
    chosen_seat = economy_seats[0]
    res = airline.book_seat(instance, passenger_alice, chosen_seat.number)
    print(f"\nBooked: {res}")
    print(f"  Confirmation #: {res.confirmation_number}")
    print(f"  Seat          : {res.seat}")
    print(f"  Economy left  : {len(instance.available_seats(SeatClass.ECONOMY))}")

    # -- 4. Look up reservation --
    looked_up = airline.get_reservation(res.confirmation_number)
    print(f"\nLooked up: {looked_up}")

    # -- 5. Cancel reservation --
    airline.cancel_reservation(res.confirmation_number)
    print(f"\nAfter cancel: {res}")
    print(f"  Economy left  : {len(instance.available_seats(SeatClass.ECONOMY))}")

    # -- 6. Try double-cancel (expect error) --
    try:
        airline.cancel_reservation(res.confirmation_number)
    except ValueError as e:
        print(f"\nExpected error on double cancel: {e}")

    # -- 7. Book a business seat for another passenger --
    passenger_bob = Passenger("Bob Jones", "UK87654321")
    biz_seat = business_seats[0]
    res2 = airline.book_seat(instance, passenger_bob, biz_seat.number)
    print(f"\nBooked business: {res2}")

    print("\n--- Demo complete ---")
