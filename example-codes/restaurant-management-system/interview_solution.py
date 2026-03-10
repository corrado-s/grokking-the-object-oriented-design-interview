"""
Restaurant Management System -- Interview-Feasible OOD Solution
===============================================================

Assumptions / Reduced Scope
---------------------------
- Single restaurant, single branch (no Branch or multi-location logic).
- No employee account hierarchy (Account, Person, Employee, Receptionist, etc.).
  We model actors implicitly through the Restaurant facade methods.
- No Kitchen / Chef / TableChart management -- orders simply transition through
  statuses (RECEIVED -> PREPARING -> COMPLETED).
- No notification system for upcoming reservations.
- Payment is modeled as a simple enum on the Bill; no gateway integration.
- TableSeat is omitted; a Meal is tied to a seat *number* (int) within a Table.

Main Use Cases Implemented
--------------------------
1. Browse the menu (menu sections and items).
2. Search for available tables by party size and datetime.
3. Make a reservation for a future time slot.
4. Cancel a reservation.
5. Check in a reservation (seat guests, table becomes OCCUPIED).
6. Place an order with meals per seat, each meal having meal items.
7. Mark an order as preparing, then completed (kitchen lifecycle).
8. Generate a bill from a completed order.
9. Pay the bill (cash / card / check).

What Was Left Out
-----------------
- Full account/employee class hierarchy and authentication.
- Branch & multi-restaurant management.
- Kitchen internals, chef assignment, table charts / seating layout images.
- Notification system (SMS/email reminders).
- Complex payment processing (gateway calls, refunds, splitting bills).
- Persistent storage -- everything lives in memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TableStatus(Enum):
    FREE = auto()
    RESERVED = auto()
    OCCUPIED = auto()


class ReservationStatus(Enum):
    CONFIRMED = auto()
    CHECKED_IN = auto()
    CANCELED = auto()


class OrderStatus(Enum):
    RECEIVED = auto()
    PREPARING = auto()
    COMPLETED = auto()
    CANCELED = auto()


class PaymentMethod(Enum):
    CASH = auto()
    CREDIT_CARD = auto()
    CHECK = auto()


class PaymentStatus(Enum):
    UNPAID = auto()
    COMPLETED = auto()


# ---------------------------------------------------------------------------
# Menu domain
# ---------------------------------------------------------------------------

@dataclass
class MenuItem:
    item_id: int
    title: str
    description: str
    price: float


@dataclass
class MenuSection:
    section_id: int
    title: str
    description: str
    items: list[MenuItem] = field(default_factory=list)

    def add_item(self, item: MenuItem) -> None:
        self.items.append(item)


@dataclass
class Menu:
    menu_id: int
    title: str
    sections: list[MenuSection] = field(default_factory=list)

    def add_section(self, section: MenuSection) -> None:
        self.sections.append(section)

    def display(self) -> str:
        lines: list[str] = [f"=== {self.title} ==="]
        for sec in self.sections:
            lines.append(f"\n-- {sec.title} --")
            for item in sec.items:
                lines.append(f"  [{item.item_id}] {item.title:.<30} ${item.price:.2f}")
                lines.append(f"       {item.description}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table & Reservation
# ---------------------------------------------------------------------------

@dataclass
class Table:
    table_id: int
    max_capacity: int
    status: TableStatus = TableStatus.FREE

    def is_free(self) -> bool:
        return self.status == TableStatus.FREE

    def __repr__(self) -> str:
        return f"Table(id={self.table_id}, capacity={self.max_capacity}, status={self.status.name})"


@dataclass
class Reservation:
    reservation_id: int
    table: Table
    customer_name: str
    party_size: int
    time: datetime
    status: ReservationStatus = ReservationStatus.CONFIRMED
    notes: str = ""

    def cancel(self) -> None:
        if self.status == ReservationStatus.CONFIRMED:
            self.status = ReservationStatus.CANCELED
            self.table.status = TableStatus.FREE

    def check_in(self) -> None:
        if self.status == ReservationStatus.CONFIRMED:
            self.status = ReservationStatus.CHECKED_IN
            self.table.status = TableStatus.OCCUPIED


# ---------------------------------------------------------------------------
# Order, Meal, Bill
# ---------------------------------------------------------------------------

@dataclass
class MealItem:
    menu_item: MenuItem
    quantity: int = 1

    @property
    def subtotal(self) -> float:
        return self.menu_item.price * self.quantity


@dataclass
class Meal:
    seat_number: int
    items: list[MealItem] = field(default_factory=list)

    def add_item(self, menu_item: MenuItem, quantity: int = 1) -> None:
        self.items.append(MealItem(menu_item=menu_item, quantity=quantity))

    @property
    def subtotal(self) -> float:
        return sum(mi.subtotal for mi in self.items)


@dataclass
class Bill:
    order_id: int
    amount: float
    tax: float
    total: float
    payment_status: PaymentStatus = PaymentStatus.UNPAID
    payment_method: Optional[PaymentMethod] = None

    def pay(self, method: PaymentMethod) -> None:
        self.payment_method = method
        self.payment_status = PaymentStatus.COMPLETED

    def display(self) -> str:
        lines = [
            f"--- Bill for Order #{self.order_id} ---",
            f"  Subtotal : ${self.amount:.2f}",
            f"  Tax      : ${self.tax:.2f}",
            f"  Total    : ${self.total:.2f}",
            f"  Status   : {self.payment_status.name}",
        ]
        if self.payment_method:
            lines.append(f"  Paid via : {self.payment_method.name}")
        return "\n".join(lines)


@dataclass
class Order:
    order_id: int
    table: Table
    meals: list[Meal] = field(default_factory=list)
    status: OrderStatus = OrderStatus.RECEIVED
    created_at: datetime = field(default_factory=datetime.now)
    bill: Optional[Bill] = None

    def add_meal(self, meal: Meal) -> None:
        self.meals.append(meal)

    def remove_meal(self, seat_number: int) -> None:
        self.meals = [m for m in self.meals if m.seat_number != seat_number]

    def mark_preparing(self) -> None:
        if self.status == OrderStatus.RECEIVED:
            self.status = OrderStatus.PREPARING

    def mark_completed(self) -> None:
        if self.status == OrderStatus.PREPARING:
            self.status = OrderStatus.COMPLETED

    def cancel(self) -> None:
        if self.status in (OrderStatus.RECEIVED, OrderStatus.PREPARING):
            self.status = OrderStatus.CANCELED

    def generate_bill(self, tax_rate: float = 0.08) -> Bill:
        """Create a Bill from the meals on this order."""
        amount = sum(meal.subtotal for meal in self.meals)
        tax = round(amount * tax_rate, 2)
        total = round(amount + tax, 2)
        self.bill = Bill(order_id=self.order_id, amount=amount, tax=tax, total=total)
        return self.bill


# ---------------------------------------------------------------------------
# Restaurant  (top-level facade / service layer)
# ---------------------------------------------------------------------------

class Restaurant:
    """
    Single-branch restaurant that owns tables, a menu, reservations, and orders.
    Acts as the central facade for all use cases.
    """

    def __init__(self, name: str):
        self.name = name
        self.menu = Menu(menu_id=1, title=f"{name} Menu")
        self._tables: dict[int, Table] = {}
        self._reservations: dict[int, Reservation] = {}
        self._orders: dict[int, Order] = {}
        self._next_reservation_id = 1
        self._next_order_id = 1

    # -- Table management ---------------------------------------------------

    def add_table(self, table_id: int, capacity: int) -> Table:
        table = Table(table_id=table_id, max_capacity=capacity)
        self._tables[table_id] = table
        return table

    def search_available_tables(self, party_size: int) -> list[Table]:
        """Return free tables that can seat the requested party size."""
        return [
            t for t in self._tables.values()
            if t.is_free() and t.max_capacity >= party_size
        ]

    # -- Reservation management ---------------------------------------------

    def make_reservation(
        self,
        customer_name: str,
        party_size: int,
        time: datetime,
        notes: str = "",
    ) -> Optional[Reservation]:
        """Reserve the smallest available table that fits the party."""
        candidates = sorted(self.search_available_tables(party_size), key=lambda t: t.max_capacity)
        if not candidates:
            return None
        table = candidates[0]
        table.status = TableStatus.RESERVED
        res = Reservation(
            reservation_id=self._next_reservation_id,
            table=table,
            customer_name=customer_name,
            party_size=party_size,
            time=time,
            notes=notes,
        )
        self._reservations[res.reservation_id] = res
        self._next_reservation_id += 1
        return res

    def cancel_reservation(self, reservation_id: int) -> bool:
        res = self._reservations.get(reservation_id)
        if res and res.status == ReservationStatus.CONFIRMED:
            res.cancel()
            return True
        return False

    def check_in_reservation(self, reservation_id: int) -> bool:
        res = self._reservations.get(reservation_id)
        if res and res.status == ReservationStatus.CONFIRMED:
            res.check_in()
            return True
        return False

    # -- Order management ---------------------------------------------------

    def create_order(self, table_id: int) -> Optional[Order]:
        table = self._tables.get(table_id)
        if table is None or table.status != TableStatus.OCCUPIED:
            return None
        order = Order(order_id=self._next_order_id, table=table)
        self._orders[order.order_id] = order
        self._next_order_id += 1
        return order

    def get_order(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    # -- Bill & Payment -----------------------------------------------------

    def generate_bill(self, order_id: int, tax_rate: float = 0.08) -> Optional[Bill]:
        order = self._orders.get(order_id)
        if order is None:
            return None
        return order.generate_bill(tax_rate)

    def pay_bill(self, order_id: int, method: PaymentMethod) -> bool:
        order = self._orders.get(order_id)
        if order is None or order.bill is None:
            return False
        order.bill.pay(method)
        # Free the table after payment.
        order.table.status = TableStatus.FREE
        return True


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Bootstrap the restaurant and its menu.
    restaurant = Restaurant("The Grokking Grill")

    appetizers = MenuSection(section_id=1, title="Appetizers", description="Start your meal right")
    appetizers.add_item(MenuItem(1, "Spring Rolls", "Crispy veggie rolls", 6.50))
    appetizers.add_item(MenuItem(2, "Soup of the Day", "Chef's daily pick", 5.00))

    mains = MenuSection(section_id=2, title="Main Courses", description="Hearty entrees")
    mains.add_item(MenuItem(3, "Grilled Salmon", "Atlantic salmon, lemon butter", 18.00))
    mains.add_item(MenuItem(4, "Ribeye Steak", "12 oz, herb-crusted", 24.00))
    mains.add_item(MenuItem(5, "Pasta Primavera", "Seasonal vegetables, penne", 14.00))

    restaurant.menu.add_section(appetizers)
    restaurant.menu.add_section(mains)
    print(restaurant.menu.display())

    # 2. Set up tables.
    restaurant.add_table(table_id=1, capacity=2)
    restaurant.add_table(table_id=2, capacity=4)
    restaurant.add_table(table_id=3, capacity=6)
    restaurant.add_table(table_id=4, capacity=4)

    # 3. Search for a table for a party of 3.
    available = restaurant.search_available_tables(party_size=3)
    print(f"\nAvailable tables for party of 3: {available}")

    # 4. Make a reservation.
    reservation = restaurant.make_reservation(
        customer_name="Alice",
        party_size=3,
        time=datetime.now() + timedelta(hours=2),
        notes="Window seat preferred",
    )
    assert reservation is not None
    print(f"\nReservation created: #{reservation.reservation_id} "
          f"for {reservation.customer_name} at Table {reservation.table.table_id} "
          f"(status={reservation.status.name})")

    # 5. Check in the reservation (guests arrive).
    restaurant.check_in_reservation(reservation.reservation_id)
    print(f"After check-in: Table {reservation.table.table_id} is {reservation.table.status.name}")

    # 6. Create an order for the now-occupied table.
    order = restaurant.create_order(table_id=reservation.table.table_id)
    assert order is not None

    # Seat 1 orders spring rolls + salmon.
    meal1 = Meal(seat_number=1)
    meal1.add_item(appetizers.items[0], quantity=1)  # Spring Rolls
    meal1.add_item(mains.items[0], quantity=1)        # Grilled Salmon

    # Seat 2 orders soup + steak.
    meal2 = Meal(seat_number=2)
    meal2.add_item(appetizers.items[1], quantity=1)  # Soup of the Day
    meal2.add_item(mains.items[1], quantity=1)        # Ribeye Steak

    # Seat 3 orders pasta.
    meal3 = Meal(seat_number=3)
    meal3.add_item(mains.items[2], quantity=1)        # Pasta Primavera

    order.add_meal(meal1)
    order.add_meal(meal2)
    order.add_meal(meal3)

    print(f"\nOrder #{order.order_id} placed with {len(order.meals)} meals "
          f"(status={order.status.name})")

    # 7. Kitchen workflow.
    order.mark_preparing()
    print(f"Order status -> {order.status.name}")
    order.mark_completed()
    print(f"Order status -> {order.status.name}")

    # 8. Generate and display the bill.
    bill = restaurant.generate_bill(order.order_id)
    assert bill is not None
    print(f"\n{bill.display()}")

    # 9. Pay the bill.
    restaurant.pay_bill(order.order_id, PaymentMethod.CREDIT_CARD)
    print(f"\n{bill.display()}")
    print(f"Table {reservation.table.table_id} is now {reservation.table.status.name}")

    # 10. Show that a reservation can be canceled.
    res2 = restaurant.make_reservation("Bob", party_size=2, time=datetime.now() + timedelta(hours=3))
    assert res2 is not None
    print(f"\nBob's reservation #{res2.reservation_id} at Table {res2.table.table_id} "
          f"(status={res2.status.name})")
    restaurant.cancel_reservation(res2.reservation_id)
    print(f"After cancel: status={res2.status.name}, "
          f"Table {res2.table.table_id} is {res2.table.status.name}")
