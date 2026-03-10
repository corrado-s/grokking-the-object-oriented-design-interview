"""
Movie Ticket Booking System -- Interview-Feasible OOD Solution

Assumptions / Reduced Scope:
    - Single cinema with multiple halls (no multi-cinema / city management).
    - No admin flows (add/remove movies, block users). Movies and shows are
      pre-populated directly.
    - No notification system (email, SMS, push).
    - No coupon / discount logic.
    - No search catalog -- customers browse a flat movie list and pick shows.
    - Payment is modeled but not integrated with a real gateway.
    - Concurrency is handled with a threading.Lock per show (seat-level
      locking). In production this would be a DB-level transaction with
      SERIALIZABLE isolation, but a lock demonstrates the concept in-process.

Main Use-Cases Implemented:
    1. Browse movies currently showing at the cinema.
    2. Select a movie and view its available shows.
    3. View the seating chart for a show and pick seats.
    4. Book the selected seats (with seat locking to prevent double-booking).
    5. Make a payment for the booking.
    6. Cancel a booking and release the seats.

Left Out (would mention in interview):
    - Full search/catalog system (search by genre, language, city, etc.).
    - Admin / FrontDeskOfficer roles and their workflows.
    - Notification service.
    - Coupon and discount engine.
    - Multi-cinema and city-level management.
    - Guest registration flow.
    - Refund processing.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SeatType(Enum):
    REGULAR = auto()
    PREMIUM = auto()
    ACCESSIBLE = auto()


class SeatStatus(Enum):
    AVAILABLE = auto()
    LOCKED = auto()      # temporarily held during booking
    BOOKED = auto()


class BookingStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    CANCELED = auto()


class PaymentStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    REFUNDED = auto()


class PaymentMethod(Enum):
    CREDIT_CARD = auto()
    CASH = auto()


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------

class Movie:
    """Represents a film that can be shown in one or more halls."""

    def __init__(self, title: str, duration_mins: int, genre: str, language: str = "English"):
        self.movie_id: str = str(uuid.uuid4())[:8]
        self.title = title
        self.duration_mins = duration_mins
        self.genre = genre
        self.language = language
        self._shows: list[Show] = []

    def add_show(self, show: Show) -> None:
        self._shows.append(show)

    def get_shows(self) -> list[Show]:
        return list(self._shows)

    def __repr__(self) -> str:
        return f"Movie('{self.title}', {self.duration_mins}min, {self.genre})"


class Seat:
    """A physical seat inside a cinema hall. Immutable across shows."""

    def __init__(self, row: str, number: int, seat_type: SeatType = SeatType.REGULAR):
        self.seat_id: str = f"{row}{number}"
        self.row = row
        self.number = number
        self.seat_type = seat_type

    def __repr__(self) -> str:
        return f"Seat({self.seat_id}, {self.seat_type.name})"


class CinemaHall:
    """A screening room with a fixed layout of seats."""

    def __init__(self, name: str, seats: list[Seat]):
        self.name = name
        self.seats = seats

    def __repr__(self) -> str:
        return f"CinemaHall('{self.name}', {len(self.seats)} seats)"


class Cinema:
    """A single cinema venue containing multiple halls."""

    def __init__(self, name: str, halls: list[CinemaHall]):
        self.name = name
        self.halls = halls
        self._movies: list[Movie] = []

    def add_movie(self, movie: Movie) -> None:
        self._movies.append(movie)

    def get_movies(self) -> list[Movie]:
        return list(self._movies)


# ---------------------------------------------------------------------------
# Show & Show-Seat (per-show seat state)
# ---------------------------------------------------------------------------

class ShowSeat:
    """Tracks the booking state of a physical Seat for a specific Show."""

    def __init__(self, seat: Seat, price: float):
        self.seat = seat
        self.price = price
        self.status: SeatStatus = SeatStatus.AVAILABLE
        self._locked_by: Optional[str] = None  # booking_id that holds the lock

    @property
    def is_available(self) -> bool:
        return self.status == SeatStatus.AVAILABLE

    def __repr__(self) -> str:
        return f"ShowSeat({self.seat.seat_id}, {self.status.name}, ${self.price})"


class Show:
    """A screening of a Movie in a CinemaHall at a specific time.

    Owns a Lock to serialize seat-reservation attempts and prevent
    double-booking.
    """

    def __init__(self, movie: Movie, hall: CinemaHall, start_time: datetime,
                 base_price: float = 10.0, premium_surcharge: float = 5.0):
        self.show_id: str = str(uuid.uuid4())[:8]
        self.movie = movie
        self.hall = hall
        self.start_time = start_time
        self.end_time = start_time + timedelta(minutes=movie.duration_mins)

        # Build per-show seat state
        self._show_seats: dict[str, ShowSeat] = {}
        for seat in hall.seats:
            price = base_price + (premium_surcharge if seat.seat_type == SeatType.PREMIUM else 0)
            self._show_seats[seat.seat_id] = ShowSeat(seat, price)

        self._lock = threading.Lock()

    # -- Queries ---------------------------------------------------------------

    def get_available_seats(self) -> list[ShowSeat]:
        return [ss for ss in self._show_seats.values() if ss.is_available]

    def get_all_show_seats(self) -> list[ShowSeat]:
        return list(self._show_seats.values())

    def get_show_seat(self, seat_id: str) -> Optional[ShowSeat]:
        return self._show_seats.get(seat_id)

    # -- Seat Locking (concurrency) --------------------------------------------

    def lock_seats(self, seat_ids: list[str], booking_id: str) -> bool:
        """Atomically lock the requested seats for a booking.

        Returns True if ALL seats were available and are now locked.
        Returns False (and locks nothing) if any seat is unavailable.
        In a real system this would be a DB transaction with
        SERIALIZABLE isolation level.
        """
        with self._lock:
            # Validate all seats exist and are available
            targets: list[ShowSeat] = []
            for sid in seat_ids:
                ss = self._show_seats.get(sid)
                if ss is None or not ss.is_available:
                    return False
                targets.append(ss)

            # All good -- lock them
            for ss in targets:
                ss.status = SeatStatus.LOCKED
                ss._locked_by = booking_id
            return True

    def confirm_seats(self, seat_ids: list[str], booking_id: str) -> None:
        """Move locked seats to BOOKED after successful payment."""
        with self._lock:
            for sid in seat_ids:
                ss = self._show_seats[sid]
                if ss._locked_by == booking_id:
                    ss.status = SeatStatus.BOOKED

    def release_seats(self, seat_ids: list[str], booking_id: str) -> None:
        """Release seats back to AVAILABLE (on cancel or timeout)."""
        with self._lock:
            for sid in seat_ids:
                ss = self._show_seats.get(sid)
                if ss and ss._locked_by == booking_id:
                    ss.status = SeatStatus.AVAILABLE
                    ss._locked_by = None

    def __repr__(self) -> str:
        avail = len(self.get_available_seats())
        return (f"Show('{self.movie.title}' @ {self.hall.name}, "
                f"{self.start_time:%H:%M}, {avail}/{len(self._show_seats)} avail)")


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class Payment:
    """Represents a payment transaction for a booking."""

    def __init__(self, amount: float, method: PaymentMethod):
        self.transaction_id: str = str(uuid.uuid4())[:8]
        self.amount = amount
        self.method = method
        self.status: PaymentStatus = PaymentStatus.PENDING
        self.created_at: datetime = datetime.now()

    def complete(self) -> bool:
        """Simulate payment processing. Always succeeds for demo purposes."""
        self.status = PaymentStatus.COMPLETED
        return True

    def refund(self) -> bool:
        if self.status == PaymentStatus.COMPLETED:
            self.status = PaymentStatus.REFUNDED
            return True
        return False

    def __repr__(self) -> str:
        return f"Payment(${self.amount}, {self.method.name}, {self.status.name})"


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

class Booking:
    """Ties together a Customer, a Show, selected seats, and a Payment."""

    def __init__(self, customer: Customer, show: Show, seat_ids: list[str]):
        self.booking_id: str = str(uuid.uuid4())[:8]
        self.customer = customer
        self.show = show
        self.seat_ids = seat_ids
        self.status: BookingStatus = BookingStatus.PENDING
        self.payment: Optional[Payment] = None
        self.created_at: datetime = datetime.now()

        # Calculate total
        self.total_amount: float = sum(
            show.get_show_seat(sid).price for sid in seat_ids  # type: ignore[union-attr]
        )

    def make_payment(self, method: PaymentMethod) -> bool:
        """Process payment and confirm the booking."""
        if self.status != BookingStatus.PENDING:
            print(f"  [!] Booking {self.booking_id} is not in PENDING state.")
            return False

        payment = Payment(self.total_amount, method)
        if payment.complete():
            self.payment = payment
            self.status = BookingStatus.CONFIRMED
            self.show.confirm_seats(self.seat_ids, self.booking_id)
            return True

        # Payment failed -- release seats
        self.show.release_seats(self.seat_ids, self.booking_id)
        return False

    def cancel(self) -> bool:
        """Cancel the booking and free the seats."""
        if self.status == BookingStatus.CANCELED:
            print(f"  [!] Booking {self.booking_id} already canceled.")
            return False

        self.show.release_seats(self.seat_ids, self.booking_id)
        if self.payment:
            self.payment.refund()
        self.status = BookingStatus.CANCELED
        return True

    def __repr__(self) -> str:
        return (f"Booking({self.booking_id}, {self.status.name}, "
                f"{len(self.seat_ids)} seats, ${self.total_amount})")


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class Customer:
    """A registered user who can browse movies and make bookings."""

    def __init__(self, name: str, email: str):
        self.customer_id: str = str(uuid.uuid4())[:8]
        self.name = name
        self.email = email
        self._bookings: list[Booking] = []

    def book_seats(self, show: Show, seat_ids: list[str]) -> Optional[Booking]:
        """Attempt to lock seats and create a pending booking."""
        booking_id_placeholder = str(uuid.uuid4())[:8]

        # Try to lock -- this is where concurrency protection kicks in
        if not show.lock_seats(seat_ids, booking_id_placeholder):
            print(f"  [!] Could not lock seats {seat_ids} -- one or more unavailable.")
            return None

        booking = Booking(self, show, seat_ids)
        # Patch the booking_id into the locks so confirm/release works correctly
        booking.booking_id = booking_id_placeholder
        self._bookings.append(booking)
        return booking

    def get_bookings(self) -> list[Booking]:
        return list(self._bookings)

    def __repr__(self) -> str:
        return f"Customer('{self.name}', {self.email})"


# ---------------------------------------------------------------------------
# Booking System (thin orchestrator / facade)
# ---------------------------------------------------------------------------

class MovieTicketBookingSystem:
    """Facade that ties together the cinema, movies, and booking workflow."""

    def __init__(self, cinema: Cinema):
        self.cinema = cinema

    def get_movies(self) -> list[Movie]:
        return self.cinema.get_movies()

    def get_shows_for_movie(self, movie: Movie) -> list[Show]:
        return movie.get_shows()

    def get_available_seats(self, show: Show) -> list[ShowSeat]:
        return show.get_available_seats()

    def create_booking(self, customer: Customer, show: Show,
                       seat_ids: list[str]) -> Optional[Booking]:
        return customer.book_seats(show, seat_ids)

    def confirm_booking(self, booking: Booking,
                        method: PaymentMethod = PaymentMethod.CREDIT_CARD) -> bool:
        return booking.make_payment(method)

    def cancel_booking(self, booking: Booking) -> bool:
        return booking.cancel()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _build_sample_cinema() -> Cinema:
    """Set up a small cinema with one hall and a handful of seats."""
    seats = []
    for row in ["A", "B", "C"]:
        for num in range(1, 6):
            stype = SeatType.PREMIUM if row == "A" else SeatType.REGULAR
            seats.append(Seat(row, num, stype))
    hall = CinemaHall("Hall 1", seats)
    return Cinema("Downtown Cinema", [hall])


def main() -> None:
    # --- Setup ----------------------------------------------------------------
    cinema = _build_sample_cinema()
    hall = cinema.halls[0]

    movie1 = Movie("Inception", 148, "Sci-Fi")
    movie2 = Movie("The Grand Budapest Hotel", 99, "Comedy")
    cinema.add_movie(movie1)
    cinema.add_movie(movie2)

    show1 = Show(movie1, hall, datetime(2026, 3, 15, 19, 0), base_price=12.0, premium_surcharge=5.0)
    show2 = Show(movie2, hall, datetime(2026, 3, 15, 21, 0), base_price=10.0, premium_surcharge=4.0)
    movie1.add_show(show1)
    movie2.add_show(show2)

    system = MovieTicketBookingSystem(cinema)
    alice = Customer("Alice", "alice@example.com")
    bob = Customer("Bob", "bob@example.com")

    # --- Workflow: browse movies ----------------------------------------------
    print("=== Movies Now Showing ===")
    for m in system.get_movies():
        print(f"  {m}")

    # --- Workflow: pick a show ------------------------------------------------
    print(f"\n=== Shows for '{movie1.title}' ===")
    for s in system.get_shows_for_movie(movie1):
        print(f"  {s}")

    # --- Workflow: view available seats ----------------------------------------
    print(f"\n=== Available Seats for Show {show1.show_id} ===")
    for ss in system.get_available_seats(show1):
        print(f"  {ss}")

    # --- Workflow: Alice books A1, A2 -----------------------------------------
    print("\n--- Alice books seats A1, A2 ---")
    booking_a = system.create_booking(alice, show1, ["A1", "A2"])
    if booking_a:
        print(f"  Booking created: {booking_a}")
        ok = system.confirm_booking(booking_a, PaymentMethod.CREDIT_CARD)
        print(f"  Payment confirmed: {ok}  |  {booking_a}")

    # --- Workflow: Bob tries the same seats (should fail) ----------------------
    print("\n--- Bob tries to book A1, A2 (already booked) ---")
    booking_b = system.create_booking(bob, show1, ["A1", "A2"])
    print(f"  Result: {booking_b}")  # None

    # --- Workflow: Bob books B3, B4 instead -----------------------------------
    print("\n--- Bob books seats B3, B4 ---")
    booking_b2 = system.create_booking(bob, show1, ["B3", "B4"])
    if booking_b2:
        ok = system.confirm_booking(booking_b2, PaymentMethod.CASH)
        print(f"  {booking_b2}")

    # --- Workflow: Alice cancels her booking -----------------------------------
    print("\n--- Alice cancels her booking ---")
    if booking_a:
        system.cancel_booking(booking_a)
        print(f"  {booking_a}")
        if booking_a.payment:
            print(f"  Payment status: {booking_a.payment.status.name}")

    # --- A1, A2 are available again -------------------------------------------
    print(f"\n=== Available seats after cancellation ===")
    for ss in system.get_available_seats(show1):
        print(f"  {ss}")

    # --- Show customer booking history ----------------------------------------
    print(f"\n=== Alice's Bookings ===")
    for b in alice.get_bookings():
        print(f"  {b}")
    print(f"\n=== Bob's Bookings ===")
    for b in bob.get_bookings():
        print(f"  {b}")


if __name__ == "__main__":
    main()
