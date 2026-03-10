"""
Design a Library Management System
===================================

Assumptions / Reduced Scope:
  - Single library instance (no multi-branch support).
  - Members only (no librarian/admin account hierarchy).
  - Books are identified by ISBN; physical copies (BookItem) by barcode.
  - In-memory data storage (dicts) instead of a database layer.
  - No notification system, no rack/location tracking, no barcode scanning HW.
  - Simplified search: title and author substring matching on the catalog.

Main Use Cases Implemented:
  1. Add books (with multiple physical copies) to the library.
  2. Register members.
  3. Search the catalog by title or author.
  4. Member checks out a book item  (respects max-book limit, reference-only flag,
     and existing reservations by other members).
  5. Member returns a book item     (auto-calculates overdue fine).
  6. Member reserves a currently-unavailable book item.

What Was Left Out:
  - Librarian class and admin workflows (add/remove books, block members).
  - Full Account base class and AccountStatus lifecycle.
  - Notification system (email/SMS on overdue or reservation ready).
  - Rack / physical-location tracking.
  - Catalog as a separate class with multiple index structures.
  - BookFormat enum, publication-date search, renew-book flow.
  - Persistent storage / database integration.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BookStatus(Enum):
    AVAILABLE = auto()
    RESERVED = auto()
    LOANED = auto()
    LOST = auto()


class ReservationStatus(Enum):
    WAITING = auto()
    COMPLETED = auto()
    CANCELED = auto()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BOOKS_PER_MEMBER = 5
MAX_LENDING_DAYS = 10
FINE_PER_DAY = 1.00  # dollars


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

class Book:
    """Represents the *title-level* concept (ISBN, title, authors, subject)."""

    def __init__(self, isbn: str, title: str, authors: list[str], subject: str):
        self.isbn = isbn
        self.title = title
        self.authors = authors
        self.subject = subject


class BookItem:
    """A single physical copy of a Book, identified by a unique barcode."""

    def __init__(self, barcode: str, book: Book, is_reference_only: bool = False):
        self.barcode = barcode
        self.book = book
        self.is_reference_only = is_reference_only
        self.status: BookStatus = BookStatus.AVAILABLE
        self.borrowed_by: Optional[str] = None  # member_id
        self.due_date: Optional[datetime] = None


class Member:
    """A library member who can search, checkout, return, and reserve books."""

    def __init__(self, member_id: str, name: str):
        self.member_id = member_id
        self.name = name
        self.books_checked_out: int = 0


class BookLending:
    """Records a single checkout transaction."""

    def __init__(self, barcode: str, member_id: str, due_date: datetime):
        self.barcode = barcode
        self.member_id = member_id
        self.creation_date: datetime = datetime.now()
        self.due_date = due_date
        self.return_date: Optional[datetime] = None


class BookReservation:
    """Records a reservation when a book item is not currently available."""

    def __init__(self, barcode: str, member_id: str):
        self.barcode = barcode
        self.member_id = member_id
        self.creation_date: datetime = datetime.now()
        self.status: ReservationStatus = ReservationStatus.WAITING


# ---------------------------------------------------------------------------
# Library  (the main system / facade)
# ---------------------------------------------------------------------------

class Library:
    """
    Central facade that owns all data and exposes the core use-case methods.

    In a production system each dict would be backed by a database table.
    """

    def __init__(self, name: str):
        self.name = name
        self._books: dict[str, Book] = {}                  # isbn  -> Book
        self._items: dict[str, BookItem] = {}               # barcode -> BookItem
        self._members: dict[str, Member] = {}               # member_id -> Member
        self._lendings: dict[str, BookLending] = {}         # barcode -> active lending
        self._reservations: dict[str, BookReservation] = {} # barcode -> reservation

    # ---- catalog management ------------------------------------------------

    def add_book(self, book: Book) -> None:
        self._books[book.isbn] = book

    def add_book_item(self, item: BookItem) -> None:
        # Ensure the parent Book is registered as well.
        if item.book.isbn not in self._books:
            self.add_book(item.book)
        self._items[item.barcode] = item

    def register_member(self, member: Member) -> None:
        self._members[member.member_id] = member

    # ---- search -------------------------------------------------------------

    def search_by_title(self, query: str) -> list[BookItem]:
        q = query.lower()
        return [it for it in self._items.values()
                if q in it.book.title.lower()]

    def search_by_author(self, query: str) -> list[BookItem]:
        q = query.lower()
        return [it for it in self._items.values()
                if any(q in a.lower() for a in it.book.authors)]

    # ---- checkout -----------------------------------------------------------

    def checkout(self, barcode: str, member_id: str) -> bool:
        item = self._items.get(barcode)
        member = self._members.get(member_id)

        if item is None or member is None:
            print("Book item or member not found.")
            return False

        if item.is_reference_only:
            print(f"'{item.book.title}' is reference-only and cannot be checked out.")
            return False

        if item.status != BookStatus.AVAILABLE:
            print(f"'{item.book.title}' is not available (status: {item.status.name}).")
            return False

        if member.books_checked_out >= MAX_BOOKS_PER_MEMBER:
            print(f"{member.name} has already checked out {MAX_BOOKS_PER_MEMBER} books.")
            return False

        # If another member has a reservation, block this checkout.
        reservation = self._reservations.get(barcode)
        if reservation and reservation.member_id != member_id:
            print(f"'{item.book.title}' is reserved by another member.")
            return False

        # If *this* member had the reservation, complete it.
        if reservation and reservation.member_id == member_id:
            reservation.status = ReservationStatus.COMPLETED
            del self._reservations[barcode]

        # Create lending record and update state.
        due_date = datetime.now() + timedelta(days=MAX_LENDING_DAYS)
        self._lendings[barcode] = BookLending(barcode, member_id, due_date)

        item.status = BookStatus.LOANED
        item.borrowed_by = member_id
        item.due_date = due_date
        member.books_checked_out += 1

        print(f"Checked out '{item.book.title}' to {member.name}. "
              f"Due: {due_date.strftime('%Y-%m-%d')}")
        return True

    # ---- return -------------------------------------------------------------

    def return_book(self, barcode: str, member_id: str) -> float:
        """Return a book. Returns the fine amount (0.0 if on time)."""
        lending = self._lendings.get(barcode)
        if lending is None or lending.member_id != member_id:
            print("No active lending found for this member/barcode.")
            return 0.0

        item = self._items[barcode]
        member = self._members[member_id]

        lending.return_date = datetime.now()
        fine = self._calculate_fine(lending)

        # If someone reserved this item while it was loaned, mark RESERVED.
        reservation = self._reservations.get(barcode)
        if reservation:
            item.status = BookStatus.RESERVED
            print(f"'{item.book.title}' is now held for member "
                  f"{reservation.member_id}'s reservation.")
        else:
            item.status = BookStatus.AVAILABLE

        item.borrowed_by = None
        item.due_date = None
        member.books_checked_out -= 1
        del self._lendings[barcode]

        if fine > 0:
            print(f"'{item.book.title}' returned late. Fine: ${fine:.2f}")
        else:
            print(f"'{item.book.title}' returned on time.")
        return fine

    # ---- reserve ------------------------------------------------------------

    def reserve(self, barcode: str, member_id: str) -> bool:
        item = self._items.get(barcode)
        member = self._members.get(member_id)

        if item is None or member is None:
            print("Book item or member not found.")
            return False

        if item.status == BookStatus.AVAILABLE:
            print("Book is available -- checkout instead of reserving.")
            return False

        if barcode in self._reservations:
            print("A reservation already exists for this copy.")
            return False

        self._reservations[barcode] = BookReservation(barcode, member_id)
        print(f"'{item.book.title}' reserved for {member.name}.")
        return True

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _calculate_fine(lending: BookLending) -> float:
        if lending.return_date and lending.return_date > lending.due_date:
            overdue_days = (lending.return_date - lending.due_date).days
            return overdue_days * FINE_PER_DAY
        return 0.0


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    lib = Library("City Central Library")

    # --- set up catalog ---
    clean_code = Book("978-0-13-468599-1", "Clean Code",
                      ["Robert C. Martin"], "Software Engineering")
    design_patterns = Book("978-0-201-63361-0", "Design Patterns",
                           ["Erich Gamma", "Richard Helm",
                            "Ralph Johnson", "John Vlissides"],
                           "Software Engineering")

    cc_copy1 = BookItem("BC-001", clean_code)
    cc_copy2 = BookItem("BC-002", clean_code)
    dp_copy1 = BookItem("BC-003", design_patterns)
    ref_only = BookItem("BC-004", design_patterns, is_reference_only=True)

    for item in [cc_copy1, cc_copy2, dp_copy1, ref_only]:
        lib.add_book_item(item)

    # --- register members ---
    alice = Member("M-001", "Alice")
    bob   = Member("M-002", "Bob")
    lib.register_member(alice)
    lib.register_member(bob)

    print("=" * 60)
    print("Search")
    print("=" * 60)
    results = lib.search_by_title("clean")
    for r in results:
        print(f"  Found: '{r.book.title}' [barcode {r.barcode}]")

    print()
    results = lib.search_by_author("gamma")
    for r in results:
        print(f"  Found: '{r.book.title}' [barcode {r.barcode}]")

    print()
    print("=" * 60)
    print("Checkout / Return / Reserve flow")
    print("=" * 60)

    # Alice checks out Clean Code copy 1
    lib.checkout("BC-001", "M-001")

    # Bob tries to check out the reference-only copy
    lib.checkout("BC-004", "M-002")

    # Bob checks out Design Patterns copy 1
    lib.checkout("BC-003", "M-002")

    # Alice tries to reserve Design Patterns (already loaned to Bob)
    lib.reserve("BC-003", "M-001")

    # Bob returns Design Patterns -- Alice's reservation kicks in
    lib.return_book("BC-003", "M-002")

    # Now Alice can check out Design Patterns via her reservation
    # The item is RESERVED for her, so we mark it AVAILABLE to allow checkout.
    # (In a richer system a background job would flip status; here we do it inline.)
    dp_copy1.status = BookStatus.AVAILABLE
    lib.checkout("BC-003", "M-001")

    print()
    print("=" * 60)
    print("Overdue fine simulation")
    print("=" * 60)

    # Simulate an overdue return by back-dating the lending record.
    lending = lib._lendings.get("BC-001")
    if lending:
        lending.due_date = datetime.now() - timedelta(days=3)  # 3 days overdue
    fine = lib.return_book("BC-001", "M-001")
    print(f"  Total fine collected: ${fine:.2f}")
