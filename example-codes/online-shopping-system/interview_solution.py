"""
Design Amazon Online Shopping System -- Interview-Feasible Solution

Assumptions / Reduced Scope:
    - Single-seller marketplace: products exist in a global catalog; no seller
      accounts or admin roles.
    - No product categories, reviews, ratings, or wishlists.
    - No shipping/tracking subsystem or shipment logs.
    - No notification system.
    - Payments are modeled but always succeed (no real gateway integration).
    - Inventory is tracked as a simple count on Product (no separate Item/SKU).

Main Use Cases Implemented:
    1. Browse / search products by name keyword.
    2. Add products to a shopping cart (with quantity).
    3. Update or remove items in the cart.
    4. Checkout: create an Order from the cart, process Payment.
    5. Cancel an order (if not yet shipped).
    6. Track order status transitions.

What Was Left Out:
    - Account hierarchy (Admin, Guest vs. Member), account status management
    - Seller flows, product CRUD by sellers
    - Product categories and catalog indexing by category
    - Review / rating system
    - Complex shipping, shipment logs, delivery tracking
    - Notification system (email, SMS, push)
    - Wishlist
    - Multiple payment methods with real validation
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    SHIPPED = auto()
    COMPLETED = auto()
    CANCELED = auto()


class PaymentMethod(Enum):
    CREDIT_CARD = auto()
    BANK_TRANSFER = auto()


class PaymentStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    DECLINED = auto()
    REFUNDED = auto()


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------

class Address:
    """Minimal shipping address value object."""

    def __init__(self, street: str, city: str, state: str, zip_code: str, country: str):
        self.street = street
        self.city = city
        self.state = state
        self.zip_code = zip_code
        self.country = country

    def __repr__(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}, {self.country}"


class Product:
    """A product available for purchase."""

    def __init__(self, name: str, description: str, price: float, stock: int = 0):
        self.product_id: str = uuid.uuid4().hex[:8]
        self.name = name
        self.description = description
        self.price = price
        self.stock = stock

    def is_in_stock(self, quantity: int = 1) -> bool:
        return self.stock >= quantity

    def reserve(self, quantity: int) -> None:
        if not self.is_in_stock(quantity):
            raise ValueError(f"Insufficient stock for '{self.name}' "
                             f"(requested {quantity}, available {self.stock})")
        self.stock -= quantity

    def release(self, quantity: int) -> None:
        """Return stock when an order is canceled."""
        self.stock += quantity

    def __repr__(self) -> str:
        return f"Product({self.name!r}, ${self.price:.2f}, stock={self.stock})"


class CartItem:
    """An entry inside a shopping cart linking a Product to a desired quantity."""

    def __init__(self, product: Product, quantity: int = 1):
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        self.product = product
        self.quantity = quantity

    @property
    def subtotal(self) -> float:
        return self.product.price * self.quantity

    def __repr__(self) -> str:
        return f"CartItem({self.product.name!r}, qty={self.quantity}, subtotal=${self.subtotal:.2f})"


class ShoppingCart:
    """Holds CartItems for a customer before checkout."""

    def __init__(self):
        self._items: dict[str, CartItem] = {}  # product_id -> CartItem

    def add_item(self, product: Product, quantity: int = 1) -> None:
        if product.product_id in self._items:
            self._items[product.product_id].quantity += quantity
        else:
            self._items[product.product_id] = CartItem(product, quantity)

    def remove_item(self, product_id: str) -> None:
        if product_id not in self._items:
            raise KeyError(f"Product {product_id} not in cart")
        del self._items[product_id]

    def update_quantity(self, product_id: str, quantity: int) -> None:
        if product_id not in self._items:
            raise KeyError(f"Product {product_id} not in cart")
        if quantity <= 0:
            self.remove_item(product_id)
        else:
            self._items[product_id].quantity = quantity

    def get_items(self) -> list[CartItem]:
        return list(self._items.values())

    @property
    def total(self) -> float:
        return sum(item.subtotal for item in self._items.values())

    @property
    def is_empty(self) -> bool:
        return len(self._items) == 0

    def clear(self) -> None:
        self._items.clear()

    def __repr__(self) -> str:
        return f"ShoppingCart({len(self._items)} items, total=${self.total:.2f})"


class Payment:
    """Records a payment attempt against an order."""

    def __init__(self, amount: float, method: PaymentMethod):
        self.payment_id: str = uuid.uuid4().hex[:8]
        self.amount = amount
        self.method = method
        self.status = PaymentStatus.PENDING
        self.paid_at: Optional[datetime] = None

    def execute(self) -> bool:
        """Simulate payment processing. Always succeeds in this demo."""
        self.status = PaymentStatus.COMPLETED
        self.paid_at = datetime.now()
        return True

    def refund(self) -> None:
        self.status = PaymentStatus.REFUNDED

    def __repr__(self) -> str:
        return (f"Payment(${self.amount:.2f}, {self.method.name}, "
                f"status={self.status.name})")


class Order:
    """Represents a customer's purchase. Created at checkout from cart contents."""

    def __init__(self, items: list[CartItem], shipping_address: Address):
        self.order_id: str = uuid.uuid4().hex[:8]
        self.items = list(items)  # snapshot
        self.shipping_address = shipping_address
        self.status = OrderStatus.PENDING
        self.payment: Optional[Payment] = None
        self.created_at: datetime = datetime.now()
        self._status_log: list[tuple[OrderStatus, datetime]] = [
            (OrderStatus.PENDING, self.created_at)
        ]

    @property
    def total(self) -> float:
        return sum(item.subtotal for item in self.items)

    # -- Status transitions --------------------------------------------------

    def _change_status(self, new_status: OrderStatus) -> None:
        self._status_log.append((new_status, datetime.now()))
        self.status = new_status

    def confirm(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise RuntimeError(f"Cannot confirm order in {self.status.name} state")
        self._change_status(OrderStatus.CONFIRMED)

    def ship(self) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise RuntimeError(f"Cannot ship order in {self.status.name} state")
        self._change_status(OrderStatus.SHIPPED)

    def complete(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise RuntimeError(f"Cannot complete order in {self.status.name} state")
        self._change_status(OrderStatus.COMPLETED)

    def cancel(self) -> None:
        if self.status in (OrderStatus.SHIPPED, OrderStatus.COMPLETED):
            raise RuntimeError("Cannot cancel an order that has already shipped")
        # Release reserved inventory
        for item in self.items:
            item.product.release(item.quantity)
        self._change_status(OrderStatus.CANCELED)
        if self.payment and self.payment.status == PaymentStatus.COMPLETED:
            self.payment.refund()

    def get_status_history(self) -> list[tuple[OrderStatus, datetime]]:
        return list(self._status_log)

    def __repr__(self) -> str:
        return (f"Order({self.order_id}, {len(self.items)} items, "
                f"${self.total:.2f}, {self.status.name})")


class Customer:
    """A registered customer who can browse, shop, and place orders."""

    def __init__(self, name: str, email: str, shipping_address: Address):
        self.customer_id: str = uuid.uuid4().hex[:8]
        self.name = name
        self.email = email
        self.shipping_address = shipping_address
        self.cart = ShoppingCart()
        self.orders: list[Order] = []

    def add_to_cart(self, product: Product, quantity: int = 1) -> None:
        if not product.is_in_stock(quantity):
            raise ValueError(f"'{product.name}' does not have enough stock")
        self.cart.add_item(product, quantity)

    def remove_from_cart(self, product_id: str) -> None:
        self.cart.remove_item(product_id)

    def checkout(self, payment_method: PaymentMethod = PaymentMethod.CREDIT_CARD) -> Order:
        """Create an Order from the current cart, process payment, and return it."""
        if self.cart.is_empty:
            raise RuntimeError("Cannot checkout with an empty cart")

        # Reserve inventory for each item
        reserved: list[CartItem] = []
        try:
            for item in self.cart.get_items():
                item.product.reserve(item.quantity)
                reserved.append(item)
        except ValueError:
            # Roll back any already-reserved stock
            for r in reserved:
                r.product.release(r.quantity)
            raise

        order = Order(self.cart.get_items(), self.shipping_address)

        # Process payment
        payment = Payment(order.total, payment_method)
        if not payment.execute():
            # Payment failed -- release inventory
            for item in order.items:
                item.product.release(item.quantity)
            raise RuntimeError("Payment failed")

        order.payment = payment
        order.confirm()
        self.orders.append(order)
        self.cart.clear()
        return order

    def cancel_order(self, order_id: str) -> None:
        order = next((o for o in self.orders if o.order_id == order_id), None)
        if order is None:
            raise KeyError(f"Order {order_id} not found")
        order.cancel()

    def __repr__(self) -> str:
        return f"Customer({self.name!r}, orders={len(self.orders)})"


# ---------------------------------------------------------------------------
# Product Catalog (simple search)
# ---------------------------------------------------------------------------

class ProductCatalog:
    """Global store of products with basic keyword search."""

    def __init__(self):
        self._products: dict[str, Product] = {}

    def add_product(self, product: Product) -> None:
        self._products[product.product_id] = product

    def search(self, keyword: str) -> list[Product]:
        """Case-insensitive substring search across product name and description."""
        keyword_lower = keyword.lower()
        return [
            p for p in self._products.values()
            if keyword_lower in p.name.lower()
            or keyword_lower in p.description.lower()
        ]

    def get_product(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)

    def list_all(self) -> list[Product]:
        return list(self._products.values())


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # -- Set up catalog with sample products ----------------------------------
    catalog = ProductCatalog()
    laptop = Product("Laptop", "15-inch, 16GB RAM, 512GB SSD", 1299.99, stock=10)
    headphones = Product("Wireless Headphones", "Noise-cancelling, Bluetooth 5.0", 199.99, stock=25)
    book = Product("Design Patterns", "Gang of Four classic textbook", 49.99, stock=50)

    catalog.add_product(laptop)
    catalog.add_product(headphones)
    catalog.add_product(book)

    # -- Create a customer ----------------------------------------------------
    address = Address("123 Main St", "Seattle", "WA", "98101", "US")
    alice = Customer("Alice", "alice@example.com", address)

    # -- Browse / search products ---------------------------------------------
    print("=== Search results for 'laptop' ===")
    for p in catalog.search("laptop"):
        print(f"  {p}")

    print("\n=== All products ===")
    for p in catalog.list_all():
        print(f"  {p}")

    # -- Add items to cart ----------------------------------------------------
    alice.add_to_cart(laptop, quantity=1)
    alice.add_to_cart(headphones, quantity=2)
    alice.add_to_cart(book, quantity=1)
    print(f"\n=== Cart: {alice.cart} ===")
    for item in alice.cart.get_items():
        print(f"  {item}")

    # -- Update cart (change headphone qty, remove book) ----------------------
    alice.cart.update_quantity(headphones.product_id, 1)
    alice.remove_from_cart(book.product_id)
    print(f"\n=== Updated cart: {alice.cart} ===")
    for item in alice.cart.get_items():
        print(f"  {item}")

    # -- Checkout (place order + pay) -----------------------------------------
    order = alice.checkout(PaymentMethod.CREDIT_CARD)
    print(f"\n=== Order placed: {order} ===")
    print(f"  Payment: {order.payment}")
    print(f"  Laptop stock after order: {laptop.stock}")

    # -- Progress the order through statuses ----------------------------------
    order.ship()
    order.complete()
    print(f"\n=== Order status history ===")
    for status, ts in order.get_status_history():
        print(f"  {status.name:12s} at {ts:%Y-%m-%d %H:%M:%S}")

    # -- Place a second order and cancel it -----------------------------------
    alice.add_to_cart(book, quantity=3)
    order2 = alice.checkout()
    print(f"\n=== Second order placed: {order2} ===")
    print(f"  Book stock before cancel: {book.stock}")
    alice.cancel_order(order2.order_id)
    print(f"  Canceled order status: {order2.status.name}")
    print(f"  Book stock after cancel:  {book.stock}")
    print(f"  Payment after cancel:     {order2.payment}")
