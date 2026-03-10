"""
Design an ATM -- Interview-Feasible OOD Solution
=================================================

Assumptions / Reduced Scope:
  - Single ATM serving one customer at a time (no concurrency).
  - Bank is modeled as an in-memory account store (no network layer).
  - Cash dispenser tracks a single denomination ($20 bills) for simplicity.
  - PIN is stored as a plain string (no hashing -- interview shortcut).
  - Deposits are credited immediately (no hold / manual verification).
  - Each card maps to exactly one customer with one or more accounts.

Main Use Cases Implemented:
  1. Insert card -> authenticate with PIN
  2. Check balance (checking or savings)
  3. Withdraw cash (with dispenser and balance validation)
  4. Deposit cash (immediate credit)
  5. Eject card / end session

What Was Left Out:
  - Check deposit, fund transfers between accounts
  - Full bank network / inter-bank communication
  - Receipt printing, detailed transaction logging
  - Operator functions (refill cash, maintenance)
  - Complex error recovery, card retention after failed PINs
  - Multi-denomination cash dispensing
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ATMState(Enum):
    IDLE = auto()           # waiting for card
    CARD_INSERTED = auto()  # card in, awaiting PIN
    AUTHENTICATED = auto()  # PIN verified, selecting transaction
    TRANSACTION = auto()    # executing a transaction


class TransactionType(Enum):
    BALANCE_INQUIRY = auto()
    WITHDRAW = auto()
    DEPOSIT_CASH = auto()


class TransactionStatus(Enum):
    SUCCESS = auto()
    FAILURE = auto()


class AccountType(Enum):
    CHECKING = auto()
    SAVINGS = auto()


# ---------------------------------------------------------------------------
# Account hierarchy
# ---------------------------------------------------------------------------

class Account(ABC):
    """Base class for bank accounts."""

    def __init__(self, account_number: str, account_type: AccountType,
                 initial_balance: float = 0.0):
        self.account_number = account_number
        self.account_type = account_type
        self._balance: float = initial_balance

    @property
    def balance(self) -> float:
        return self._balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self._balance:
            raise ValueError("Insufficient funds")
        self._validate_withdrawal(amount)
        self._balance -= amount

    def _validate_withdrawal(self, amount: float) -> None:
        """Hook for subclass-specific withdrawal rules."""
        pass

    def __repr__(self) -> str:
        return f"{self.account_type.name}({self.account_number}) bal=${self._balance:.2f}"


class CheckingAccount(Account):
    def __init__(self, account_number: str, initial_balance: float = 0.0):
        super().__init__(account_number, AccountType.CHECKING, initial_balance)


class SavingsAccount(Account):
    DAILY_WITHDRAW_LIMIT = 1000.0

    def __init__(self, account_number: str, initial_balance: float = 0.0):
        super().__init__(account_number, AccountType.SAVINGS, initial_balance)

    def _validate_withdrawal(self, amount: float) -> None:
        if amount > self.DAILY_WITHDRAW_LIMIT:
            raise ValueError(
                f"Savings withdrawal exceeds daily limit "
                f"(${self.DAILY_WITHDRAW_LIMIT:.2f})"
            )


# ---------------------------------------------------------------------------
# Card & Customer
# ---------------------------------------------------------------------------

class Card:
    """Represents a physical ATM / debit card."""

    def __init__(self, card_number: str, pin: str, customer_id: str):
        self.card_number = card_number
        self._pin = pin
        self.customer_id = customer_id

    def verify_pin(self, entered_pin: str) -> bool:
        return self._pin == entered_pin


class Customer:
    """A bank customer who owns a card and one or more accounts."""

    def __init__(self, customer_id: str, name: str):
        self.customer_id = customer_id
        self.name = name
        self.accounts: dict[AccountType, Account] = {}

    def add_account(self, account: Account) -> None:
        self.accounts[account.account_type] = account

    def get_account(self, account_type: AccountType) -> Account:
        acct = self.accounts.get(account_type)
        if acct is None:
            raise ValueError(f"No {account_type.name} account on file")
        return acct


# ---------------------------------------------------------------------------
# Transaction hierarchy
# ---------------------------------------------------------------------------

class Transaction(ABC):
    """Abstract base for all ATM transactions."""

    def __init__(self, account: Account):
        self.transaction_id: str = uuid.uuid4().hex[:8]
        self.account = account
        self.created_at: datetime = datetime.now()
        self.status: TransactionStatus = TransactionStatus.FAILURE

    @abstractmethod
    def execute(self) -> str:
        """Run the transaction logic; return a human-readable result string."""
        ...


class BalanceInquiry(Transaction):
    def execute(self) -> str:
        self.status = TransactionStatus.SUCCESS
        return (
            f"Account {self.account.account_number} "
            f"({self.account.account_type.name}): "
            f"${self.account.balance:.2f}"
        )


class CashWithdrawal(Transaction):
    def __init__(self, account: Account, amount: float,
                 dispenser: CashDispenser):
        super().__init__(account)
        self.amount = amount
        self._dispenser = dispenser

    def execute(self) -> str:
        if not self._dispenser.can_dispense(self.amount):
            return "ATM has insufficient cash. Try a smaller amount."
        try:
            self.account.withdraw(self.amount)
        except ValueError as exc:
            return f"Withdrawal failed: {exc}"
        self._dispenser.dispense(self.amount)
        self.status = TransactionStatus.SUCCESS
        return (
            f"Dispensed ${self.amount:.2f}. "
            f"Remaining balance: ${self.account.balance:.2f}"
        )


class CashDeposit(Transaction):
    def __init__(self, account: Account, amount: float):
        super().__init__(account)
        self.amount = amount

    def execute(self) -> str:
        try:
            self.account.deposit(self.amount)
        except ValueError as exc:
            return f"Deposit failed: {exc}"
        self.status = TransactionStatus.SUCCESS
        return (
            f"Deposited ${self.amount:.2f}. "
            f"New balance: ${self.account.balance:.2f}"
        )


# ---------------------------------------------------------------------------
# ATM components
# ---------------------------------------------------------------------------

class CashDispenser:
    """Tracks available $20 bills and dispenses cash."""

    BILL_VALUE = 20

    def __init__(self, num_bills: int = 500):
        self._num_bills = num_bills

    @property
    def total_cash(self) -> float:
        return self._num_bills * self.BILL_VALUE

    def can_dispense(self, amount: float) -> bool:
        if amount % self.BILL_VALUE != 0:
            return False
        return amount <= self.total_cash

    def dispense(self, amount: float) -> int:
        """Dispense the given amount. Returns number of bills dispensed."""
        if not self.can_dispense(amount):
            raise ValueError("Cannot dispense requested amount")
        bills = int(amount // self.BILL_VALUE)
        self._num_bills -= bills
        return bills


# ---------------------------------------------------------------------------
# Bank (in-memory account store)
# ---------------------------------------------------------------------------

class Bank:
    """Simplified bank: stores customers, cards, and validates PINs."""

    def __init__(self, name: str):
        self.name = name
        self._customers: dict[str, Customer] = {}   # customer_id -> Customer
        self._cards: dict[str, Card] = {}            # card_number -> Card

    def add_customer(self, customer: Customer, card: Card) -> None:
        self._customers[customer.customer_id] = customer
        self._cards[card.card_number] = card

    def authenticate(self, card_number: str, pin: str) -> Optional[Customer]:
        """Return the Customer if card + PIN are valid, else None."""
        card = self._cards.get(card_number)
        if card is None or not card.verify_pin(pin):
            return None
        return self._customers.get(card.customer_id)


# ---------------------------------------------------------------------------
# ATM  (simplified state machine)
# ---------------------------------------------------------------------------

class ATM:
    """
    Core ATM class with a simple state machine:
        IDLE -> CARD_INSERTED -> AUTHENTICATED -> TRANSACTION -> AUTHENTICATED
                                                              -> IDLE (eject)
    """

    MAX_PIN_ATTEMPTS = 3

    def __init__(self, atm_id: str, bank: Bank,
                 dispenser: Optional[CashDispenser] = None):
        self.atm_id = atm_id
        self._bank = bank
        self._dispenser = dispenser or CashDispenser()
        self._state: ATMState = ATMState.IDLE

        # session-scoped fields
        self._current_card_number: Optional[str] = None
        self._current_customer: Optional[Customer] = None

    # -- helpers -------------------------------------------------------------

    @property
    def state(self) -> ATMState:
        return self._state

    def _require_state(self, *expected: ATMState) -> None:
        if self._state not in expected:
            raise RuntimeError(
                f"Invalid ATM state: expected one of "
                f"{[s.name for s in expected]}, got {self._state.name}"
            )

    def _reset_session(self) -> None:
        self._current_card_number = None
        self._current_customer = None
        self._state = ATMState.IDLE

    # -- public workflow -----------------------------------------------------

    def insert_card(self, card_number: str) -> str:
        self._require_state(ATMState.IDLE)
        self._current_card_number = card_number
        self._state = ATMState.CARD_INSERTED
        return "Card accepted. Please enter your PIN."

    def enter_pin(self, pin: str) -> str:
        self._require_state(ATMState.CARD_INSERTED)
        customer = self._bank.authenticate(self._current_card_number, pin)
        if customer is None:
            self._reset_session()
            return "Authentication failed. Card ejected."
        self._current_customer = customer
        self._state = ATMState.AUTHENTICATED
        return f"Welcome, {customer.name}. Select a transaction."

    def check_balance(self, account_type: AccountType) -> str:
        self._require_state(ATMState.AUTHENTICATED)
        self._state = ATMState.TRANSACTION
        try:
            account = self._current_customer.get_account(account_type)
            txn = BalanceInquiry(account)
            result = txn.execute()
        except ValueError as exc:
            result = str(exc)
        self._state = ATMState.AUTHENTICATED
        return result

    def withdraw(self, account_type: AccountType, amount: float) -> str:
        self._require_state(ATMState.AUTHENTICATED)
        self._state = ATMState.TRANSACTION
        try:
            account = self._current_customer.get_account(account_type)
            txn = CashWithdrawal(account, amount, self._dispenser)
            result = txn.execute()
        except ValueError as exc:
            result = str(exc)
        self._state = ATMState.AUTHENTICATED
        return result

    def deposit(self, account_type: AccountType, amount: float) -> str:
        self._require_state(ATMState.AUTHENTICATED)
        self._state = ATMState.TRANSACTION
        try:
            account = self._current_customer.get_account(account_type)
            txn = CashDeposit(account, amount)
            result = txn.execute()
        except ValueError as exc:
            result = str(exc)
        self._state = ATMState.AUTHENTICATED
        return result

    def eject_card(self) -> str:
        self._reset_session()
        return "Card ejected. Thank you."


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # --- Setup bank with one customer ---
    bank = Bank("DemoBank")

    customer = Customer("C001", "Alice Johnson")
    checking = CheckingAccount("ACC-100", initial_balance=2500.00)
    savings = SavingsAccount("ACC-200", initial_balance=10000.00)
    customer.add_account(checking)
    customer.add_account(savings)

    card = Card(card_number="4111-1111-1111-1111", pin="1234",
                customer_id="C001")
    bank.add_customer(customer, card)

    # --- Create ATM ---
    atm = ATM(atm_id="ATM-001", bank=bank,
              dispenser=CashDispenser(num_bills=100))  # $2000 in $20s

    # --- Simulate a session ---
    print("=== ATM Session ===\n")

    print(atm.insert_card("4111-1111-1111-1111"))
    print(atm.enter_pin("1234"))
    print()

    # Balance inquiries
    print("-- Balance Inquiry --")
    print(atm.check_balance(AccountType.CHECKING))
    print(atm.check_balance(AccountType.SAVINGS))
    print()

    # Withdraw from checking
    print("-- Withdraw $200 from Checking --")
    print(atm.withdraw(AccountType.CHECKING, 200))
    print()

    # Deposit to checking
    print("-- Deposit $500 to Checking --")
    print(atm.deposit(AccountType.CHECKING, 500))
    print()

    # Check updated balance
    print("-- Updated Balance --")
    print(atm.check_balance(AccountType.CHECKING))
    print()

    # Try to withdraw too much
    print("-- Attempt to withdraw $5000 from Checking --")
    print(atm.withdraw(AccountType.CHECKING, 5000))
    print()

    # Try to withdraw non-multiple of $20
    print("-- Attempt to withdraw $55 (not a multiple of $20) --")
    print(atm.withdraw(AccountType.CHECKING, 55))
    print()

    # Savings withdrawal limit
    print("-- Attempt to withdraw $1500 from Savings (exceeds daily limit) --")
    print(atm.withdraw(AccountType.SAVINGS, 1500))
    print()

    # End session
    print(atm.eject_card())

    # --- Demonstrate failed auth ---
    print("\n=== Failed Auth ===\n")
    print(atm.insert_card("4111-1111-1111-1111"))
    print(atm.enter_pin("0000"))  # wrong PIN
