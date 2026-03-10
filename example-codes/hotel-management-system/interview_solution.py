"""
Hotel Management System -- Interview-Feasible OOD Solution
==========================================================

Assumptions / reduced scope:
  - Single hotel location (no multi-location hierarchy).
  - No full account system (no login, password, roles beyond Guest).
  - Housekeeping, room service, kitchen service, and amenities are omitted.
  - Room key management is omitted.
  - Notification system is omitted.
  - Invoice / complex billing is simplified to a single payment step at checkout.
  - Cancellation refund logic is simplified (full refund if > 24 h before check-in).
  - No persistence layer; all state lives in memory.

Main use cases implemented:
  1. Add rooms to a hotel.
  2. Guest searches for available rooms by style and date range.
  3. Guest books a room.
  4. Guest cancels a booking (with refund policy).
  5. Guest checks in.
  6. Guest checks out and pays.

What was left out:
  - Receptionist / Manager / Server / Housekeeper actor classes.
  - RoomKey, RoomHouseKeeping, RoomCharge hierarchy.
  - Notification engine, Invoice line-items, complex payment processing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoomStyle(Enum):
    STANDARD = auto()
    DELUXE = auto()
    FAMILY_SUITE = auto()
    BUSINESS_SUITE = auto()


class RoomStatus(Enum):
    AVAILABLE = auto()
    RESERVED = auto()
    OCCUPIED = auto()
    NOT_AVAILABLE = auto()


class BookingStatus(Enum):
    CONFIRMED = auto()
    CHECKED_IN = auto()
    CHECKED_OUT = auto()
    CANCELLED = auto()


class PaymentMethod(Enum):
    CREDIT_CARD = auto()
    CASH = auto()
    CHECK = auto()


# ---------------------------------------------------------------------------
# Guest
# ---------------------------------------------------------------------------

class Guest:
    """A hotel guest.  Keeps a lightweight profile and a history of bookings."""

    def __init__(self, name: str, email: str, phone: str) -> None:
        self.name = name
        self.email = email
        self.phone = phone
        self.bookings: list[RoomBooking] = []

    def __repr__(self) -> str:
        return f"Guest({self.name!r})"


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

class Room:
    """Represents a single hotel room."""

    def __init__(
        self,
        room_number: str,
        style: RoomStyle,
        price_per_night: float,
        is_smoking: bool = False,
    ) -> None:
        self.room_number = room_number
        self.style = style
        self.price_per_night = price_per_night
        self.is_smoking = is_smoking
        self.status = RoomStatus.AVAILABLE
        self.bookings: list[RoomBooking] = []  # history of bookings

    # --- availability check against a date range ---
    def is_available(self, check_in: date, check_out: date) -> bool:
        """Return True if the room has no overlapping CONFIRMED / CHECKED_IN booking."""
        for b in self.bookings:
            if b.status in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN):
                if b.check_in < check_out and b.check_out > check_in:
                    return False
        return True

    def __repr__(self) -> str:
        return (
            f"Room({self.room_number}, {self.style.name}, "
            f"${self.price_per_night}/night, {self.status.name})"
        )


# ---------------------------------------------------------------------------
# RoomBooking
# ---------------------------------------------------------------------------

class RoomBooking:
    """Ties a Guest to a Room for a specific date range."""

    def __init__(
        self,
        guest: Guest,
        room: Room,
        check_in: date,
        check_out: date,
    ) -> None:
        if check_out <= check_in:
            raise ValueError("check_out must be after check_in")

        self.reservation_id: str = uuid.uuid4().hex[:8].upper()
        self.guest = guest
        self.room = room
        self.check_in = check_in
        self.check_out = check_out
        self.status = BookingStatus.CONFIRMED
        self.created_at = datetime.now()

        # derived
        self.nights: int = (check_out - check_in).days
        self.total_charge: float = self.nights * room.price_per_night

    # --- lifecycle transitions ---

    def cancel(self) -> float:
        """Cancel the booking.  Returns the refund amount.
        Full refund if cancelled more than 24 hours before check-in; else no refund.
        """
        if self.status != BookingStatus.CONFIRMED:
            raise InvalidStateError(
                f"Cannot cancel booking in {self.status.name} state"
            )
        self.status = BookingStatus.CANCELLED
        self.room.status = RoomStatus.AVAILABLE

        hours_until_checkin = (
            datetime.combine(self.check_in, datetime.min.time()) - datetime.now()
        ).total_seconds() / 3600
        return self.total_charge if hours_until_checkin > 24 else 0.0

    def do_check_in(self) -> None:
        if self.status != BookingStatus.CONFIRMED:
            raise InvalidStateError(
                f"Cannot check in from {self.status.name} state"
            )
        self.status = BookingStatus.CHECKED_IN
        self.room.status = RoomStatus.OCCUPIED

    def do_check_out(self, method: PaymentMethod) -> float:
        """Check out and pay.  Returns the amount charged."""
        if self.status != BookingStatus.CHECKED_IN:
            raise InvalidStateError(
                f"Cannot check out from {self.status.name} state"
            )
        self.status = BookingStatus.CHECKED_OUT
        self.room.status = RoomStatus.AVAILABLE
        # In a real system, we would process `method` through a payment gateway.
        return self.total_charge

    def __repr__(self) -> str:
        return (
            f"Booking({self.reservation_id}, {self.room.room_number}, "
            f"{self.check_in}..{self.check_out}, {self.status.name})"
        )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class InvalidStateError(Exception):
    """Raised when a booking lifecycle transition is invalid."""


# ---------------------------------------------------------------------------
# Hotel  (the central facade / service)
# ---------------------------------------------------------------------------

class Hotel:
    """
    Central class that owns rooms and orchestrates searching, booking,
    check-in, and check-out.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.rooms: list[Room] = []
        self.bookings: list[RoomBooking] = []

    # --- room management ---

    def add_room(self, room: Room) -> None:
        self.rooms.append(room)

    # --- search ---

    def search_rooms(
        self,
        style: Optional[RoomStyle] = None,
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
    ) -> list[Room]:
        """Return rooms matching the optional style filter that are available
        for the requested date range."""
        results: list[Room] = []
        for room in self.rooms:
            if style and room.style != style:
                continue
            if check_in and check_out and not room.is_available(check_in, check_out):
                continue
            results.append(room)
        return results

    # --- booking workflow ---

    def book_room(
        self,
        guest: Guest,
        room: Room,
        check_in: date,
        check_out: date,
    ) -> RoomBooking:
        """Create a confirmed booking if the room is available."""
        if not room.is_available(check_in, check_out):
            raise ValueError(
                f"Room {room.room_number} is not available for the requested dates"
            )

        booking = RoomBooking(guest, room, check_in, check_out)
        room.bookings.append(booking)
        room.status = RoomStatus.RESERVED
        guest.bookings.append(booking)
        self.bookings.append(booking)
        return booking

    def cancel_booking(self, booking: RoomBooking) -> float:
        """Cancel a booking and return the refund amount."""
        return booking.cancel()

    def check_in(self, booking: RoomBooking) -> None:
        booking.do_check_in()

    def check_out(
        self, booking: RoomBooking, method: PaymentMethod = PaymentMethod.CREDIT_CARD
    ) -> float:
        """Check out and process payment.  Returns amount charged."""
        return booking.do_check_out(method)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Set up hotel with rooms
    hotel = Hotel("Grand Plaza")

    hotel.add_room(Room("101", RoomStyle.STANDARD, 100.0))
    hotel.add_room(Room("102", RoomStyle.STANDARD, 100.0))
    hotel.add_room(Room("201", RoomStyle.DELUXE, 200.0))
    hotel.add_room(Room("301", RoomStyle.FAMILY_SUITE, 350.0))
    hotel.add_room(Room("401", RoomStyle.BUSINESS_SUITE, 500.0, is_smoking=False))

    print(f"Hotel: {hotel.name}")
    print(f"Total rooms: {len(hotel.rooms)}\n")

    # 2. Guest searches for available deluxe rooms
    guest = Guest("Alice Johnson", "alice@example.com", "555-0101")
    ci = date.today() + timedelta(days=7)
    co = ci + timedelta(days=3)

    available = hotel.search_rooms(style=RoomStyle.DELUXE, check_in=ci, check_out=co)
    print(f"Available DELUXE rooms ({ci} to {co}): {available}\n")

    # 3. Book a room
    booking = hotel.book_room(guest, available[0], ci, co)
    print(f"Booking created: {booking}")
    print(f"  Total charge: ${booking.total_charge:.2f}")
    print(f"  Room status:  {booking.room.status.name}\n")

    # 4. Check in
    hotel.check_in(booking)
    print(f"After check-in:  {booking}")
    print(f"  Room status:   {booking.room.status.name}\n")

    # 5. Check out & pay
    charged = hotel.check_out(booking, PaymentMethod.CREDIT_CARD)
    print(f"After check-out: {booking}")
    print(f"  Amount charged: ${charged:.2f}")
    print(f"  Room status:    {booking.room.status.name}\n")

    # 6. Demonstrate cancellation with a second booking
    guest2 = Guest("Bob Smith", "bob@example.com", "555-0202")
    ci2 = date.today() + timedelta(days=14)
    co2 = ci2 + timedelta(days=2)
    booking2 = hotel.book_room(guest2, hotel.rooms[0], ci2, co2)
    print(f"Second booking: {booking2}")

    refund = hotel.cancel_booking(booking2)
    print(f"Cancelled. Refund: ${refund:.2f}")
    print(f"  Booking status: {booking2.status.name}")
    print(f"  Room status:    {booking2.room.status.name}\n")

    # 7. Show that the cancelled room is searchable again
    available_again = hotel.search_rooms(
        style=RoomStyle.STANDARD, check_in=ci2, check_out=co2
    )
    print(f"Available STANDARD rooms after cancellation: {available_again}")
