"""
Online Stock Brokerage System -- Interview-Feasible OOD Solution
================================================================

Problem: Design a system that lets members buy and sell stocks online,
track their portfolios, and manage different order types.

Assumptions / Reduced Scope:
  - Single stock exchange (singleton) with a simple simulated price fill.
  - No real market matching engine; orders fill immediately at current price
    (market) or at limit price if the market price is favorable.
  - No account hierarchy (Admin vs Member) -- just Member.
  - No watchlists, notifications, deposit/withdrawal, or reporting.
  - No order-part splitting; an order fills fully or is rejected.
  - No persistent storage; everything is in-memory.

Main Use Cases Implemented:
  1. Member views their portfolio (positions + cash balance).
  2. Member places a BUY order (market or limit).
  3. Member places a SELL order (market or limit).
  4. Order executes against the exchange and portfolio is updated.
  5. Member cancels an open (unfilled) order.

Left Out (would mention in interview):
  - Full Account base class, Admin role, account-status lifecycle.
  - Watchlists and stock search/inventory browsing.
  - Complex order types (stop-loss, stop-limit) and time-enforcement policies.
  - Order partial fills / order-part tracking.
  - Notification system, reporting / statements.
  - Deposit / withdrawal / money-transfer flows.
  - Thread safety / locking around balance and position mutations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderStatus(Enum):
    OPEN = auto()
    FILLED = auto()
    CANCELLED = auto()
    FAILED = auto()


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()


class OrderSide(Enum):
    BUY = auto()
    SELL = auto()


class ReturnStatus(Enum):
    SUCCESS = auto()
    INSUFFICIENT_FUNDS = auto()
    INSUFFICIENT_QUANTITY = auto()
    NO_STOCK_POSITION = auto()
    ORDER_NOT_FOUND = auto()
    ALREADY_FILLED = auto()
    LIMIT_PRICE_NOT_MET = auto()


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

class Stock:
    """Represents a tradeable stock with a symbol and a current market price."""

    def __init__(self, symbol: str, price: float) -> None:
        self.symbol = symbol
        self.price = price  # current market price

    def __repr__(self) -> str:
        return f"Stock({self.symbol}, ${self.price:.2f})"


# ---------------------------------------------------------------------------
# StockPosition
# ---------------------------------------------------------------------------

class StockPosition:
    """Tracks how many shares of a single stock a member owns and at what
    average cost basis."""

    def __init__(self, stock: Stock, quantity: int, avg_cost: float) -> None:
        self.stock = stock
        self.quantity = quantity
        self.avg_cost = avg_cost

    @property
    def market_value(self) -> float:
        return self.quantity * self.stock.price

    def __repr__(self) -> str:
        return (
            f"  {self.stock.symbol}: {self.quantity} shares "
            f"@ avg ${self.avg_cost:.2f}  "
            f"(mkt ${self.stock.price:.2f}, "
            f"value ${self.market_value:,.2f})"
        )


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order:
    """A buy or sell order placed by a member."""

    def __init__(
        self,
        order_side: OrderSide,
        order_type: OrderType,
        stock: Stock,
        quantity: int,
        limit_price: Optional[float] = None,
    ) -> None:
        self.order_id: str = str(uuid.uuid4())[:8]
        self.side = order_side
        self.type = order_type
        self.stock = stock
        self.quantity = quantity
        self.limit_price = limit_price  # only meaningful for LIMIT orders
        self.status = OrderStatus.OPEN
        self.filled_price: Optional[float] = None
        self.created_at: datetime = datetime.now()

    def __repr__(self) -> str:
        price_info = (
            f"limit=${self.limit_price:.2f}"
            if self.type == OrderType.LIMIT
            else "market"
        )
        filled = (
            f", filled@${self.filled_price:.2f}"
            if self.filled_price is not None
            else ""
        )
        return (
            f"Order({self.order_id} {self.side.name} {self.quantity}x"
            f"{self.stock.symbol} {price_info} "
            f"[{self.status.name}]{filled})"
        )


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class Portfolio:
    """Holds a member's cash balance and stock positions."""

    def __init__(self, cash_balance: float = 0.0) -> None:
        self.cash_balance = cash_balance
        self._positions: Dict[str, StockPosition] = {}

    def get_position(self, symbol: str) -> Optional[StockPosition]:
        return self._positions.get(symbol)

    def get_all_positions(self) -> List[StockPosition]:
        return list(self._positions.values())

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self._positions.values())

    @property
    def total_value(self) -> float:
        return self.cash_balance + self.total_market_value

    # -- mutators called after order execution --

    def add_shares(self, stock: Stock, quantity: int, price: float) -> None:
        """Add shares after a buy fill."""
        pos = self._positions.get(stock.symbol)
        if pos:
            total_cost = pos.avg_cost * pos.quantity + price * quantity
            pos.quantity += quantity
            pos.avg_cost = total_cost / pos.quantity
        else:
            self._positions[stock.symbol] = StockPosition(stock, quantity, price)
        self.cash_balance -= price * quantity

    def remove_shares(self, symbol: str, quantity: int, price: float) -> None:
        """Remove shares after a sell fill."""
        pos = self._positions[symbol]
        pos.quantity -= quantity
        if pos.quantity == 0:
            del self._positions[symbol]
        self.cash_balance += price * quantity

    def display(self) -> None:
        print(f"  Cash balance: ${self.cash_balance:,.2f}")
        if self._positions:
            print("  Positions:")
            for pos in self._positions.values():
                print(f"  {pos}")
        else:
            print("  Positions: (none)")
        print(f"  Total portfolio value: ${self.total_value:,.2f}")


# ---------------------------------------------------------------------------
# StockExchange (Singleton)
# ---------------------------------------------------------------------------

class StockExchange:
    """Singleton that holds listed stocks and executes orders.

    In a real system this would connect to an external exchange.  Here we
    simulate immediate fills for simplicity.
    """

    _instance: Optional[StockExchange] = None

    def __new__(cls) -> StockExchange:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._stocks: Dict[str, Stock] = {}
        return cls._instance

    # -- stock registry --

    def register_stock(self, stock: Stock) -> None:
        self._stocks[stock.symbol] = stock

    def get_stock(self, symbol: str) -> Optional[Stock]:
        return self._stocks.get(symbol)

    def update_price(self, symbol: str, new_price: float) -> None:
        stock = self._stocks.get(symbol)
        if stock:
            stock.price = new_price

    # -- order execution --

    def execute_order(self, order: Order) -> ReturnStatus:
        """Try to fill an order at current market price.

        - MARKET orders always fill at the current price.
        - LIMIT BUY fills only if market price <= limit.
        - LIMIT SELL fills only if market price >= limit.
        """
        current_price = order.stock.price

        if order.type == OrderType.LIMIT:
            assert order.limit_price is not None
            if order.side == OrderSide.BUY and current_price > order.limit_price:
                order.status = OrderStatus.FAILED
                return ReturnStatus.LIMIT_PRICE_NOT_MET
            if order.side == OrderSide.SELL and current_price < order.limit_price:
                order.status = OrderStatus.FAILED
                return ReturnStatus.LIMIT_PRICE_NOT_MET

        fill_price = (
            order.limit_price
            if order.type == OrderType.LIMIT
            else current_price
        )
        order.filled_price = fill_price
        order.status = OrderStatus.FILLED
        return ReturnStatus.SUCCESS


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------

class Member:
    """A brokerage member who can view their portfolio and place orders."""

    def __init__(self, name: str, initial_cash: float = 0.0) -> None:
        self.member_id: str = str(uuid.uuid4())[:8]
        self.name = name
        self.portfolio = Portfolio(cash_balance=initial_cash)
        self._orders: Dict[str, Order] = {}

    # -- read operations --

    def view_portfolio(self) -> None:
        print(f"\nPortfolio for {self.name}:")
        self.portfolio.display()

    def get_order_history(self) -> List[Order]:
        return list(self._orders.values())

    # -- place orders --

    def place_order(
        self,
        side: OrderSide,
        order_type: OrderType,
        stock: Stock,
        quantity: int,
        limit_price: Optional[float] = None,
    ) -> ReturnStatus:
        """Validate, create, execute, and settle an order."""

        # --- pre-validation ---
        if side == OrderSide.BUY:
            effective_price = (
                limit_price if order_type == OrderType.LIMIT else stock.price
            )
            if self.portfolio.cash_balance < quantity * effective_price:
                return ReturnStatus.INSUFFICIENT_FUNDS

        if side == OrderSide.SELL:
            pos = self.portfolio.get_position(stock.symbol)
            if pos is None:
                return ReturnStatus.NO_STOCK_POSITION
            if pos.quantity < quantity:
                return ReturnStatus.INSUFFICIENT_QUANTITY

        # --- create order ---
        order = Order(side, order_type, stock, quantity, limit_price)
        self._orders[order.order_id] = order

        # --- send to exchange ---
        exchange = StockExchange()
        result = exchange.execute_order(order)

        # --- settle if filled ---
        if result == ReturnStatus.SUCCESS:
            if side == OrderSide.BUY:
                assert order.filled_price is not None
                self.portfolio.add_shares(stock, quantity, order.filled_price)
            else:
                assert order.filled_price is not None
                self.portfolio.remove_shares(
                    stock.symbol, quantity, order.filled_price
                )

        return result

    def cancel_order(self, order_id: str) -> ReturnStatus:
        order = self._orders.get(order_id)
        if order is None:
            return ReturnStatus.ORDER_NOT_FOUND
        if order.status != OrderStatus.OPEN:
            return ReturnStatus.ALREADY_FILLED
        order.status = OrderStatus.CANCELLED
        return ReturnStatus.SUCCESS


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # --- bootstrap exchange with some stocks ---
    exchange = StockExchange()
    aapl = Stock("AAPL", 182.50)
    googl = Stock("GOOGL", 141.25)
    exchange.register_stock(aapl)
    exchange.register_stock(googl)

    # --- create a member with $50,000 cash ---
    alice = Member("Alice", initial_cash=50_000.00)
    alice.view_portfolio()

    # --- buy 100 shares of AAPL at market ---
    print("\n--- Buying 100 AAPL at market ---")
    result = alice.place_order(OrderSide.BUY, OrderType.MARKET, aapl, 100)
    print(f"Result: {result.name}")
    alice.view_portfolio()

    # --- buy 50 shares of GOOGL with a limit order ---
    print("\n--- Buying 50 GOOGL limit @ $140.00 ---")
    result = alice.place_order(
        OrderSide.BUY, OrderType.LIMIT, googl, 50, limit_price=140.00
    )
    print(f"Result: {result.name}  (price was ${googl.price:.2f}, limit $140)")

    # --- price drops, try again ---
    exchange.update_price("GOOGL", 139.50)
    print("\n--- GOOGL price dropped to $139.50, retrying limit buy ---")
    result = alice.place_order(
        OrderSide.BUY, OrderType.LIMIT, googl, 50, limit_price=140.00
    )
    print(f"Result: {result.name}")
    alice.view_portfolio()

    # --- sell 40 shares of AAPL at market ---
    print("\n--- Selling 40 AAPL at market ---")
    exchange.update_price("AAPL", 190.00)  # price went up
    result = alice.place_order(OrderSide.SELL, OrderType.MARKET, aapl, 40)
    print(f"Result: {result.name}")
    alice.view_portfolio()

    # --- try to sell more than owned ---
    print("\n--- Attempting to sell 200 AAPL (should fail) ---")
    result = alice.place_order(OrderSide.SELL, OrderType.MARKET, aapl, 200)
    print(f"Result: {result.name}")

    # --- try to buy with insufficient funds ---
    print("\n--- Attempting to buy 1000 GOOGL (should fail) ---")
    result = alice.place_order(OrderSide.BUY, OrderType.MARKET, googl, 1000)
    print(f"Result: {result.name}")

    # --- order history ---
    print("\n--- Order History ---")
    for o in alice.get_order_history():
        print(f"  {o}")
