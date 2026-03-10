"""
Design Blackjack and a Deck of Cards
=====================================

Assumptions / Reduced Scope:
    - Single standard 52-card deck (no multi-deck shoe).
    - One player versus one dealer.
    - No betting, insurance, split, or double-down mechanics.
    - Player decisions are limited to HIT or STAND.
    - Dealer follows standard house rule: hits on 16 or less, stands on 17+.

Main Use Cases Implemented:
    1. Build and shuffle a deck of cards.
    2. Deal two cards each to player and dealer (dealer's hole card hidden).
    3. Player takes turns hitting or standing.
    4. Dealer reveals hole card and plays according to house rules.
    5. Determine winner based on hand values (bust detection, blackjack).
    6. Ace counted as 1 or 11 (best non-busting value chosen automatically).

What Was Left Out:
    - Betting system (ante, pot, payouts).
    - Shoe (multi-deck dealing device).
    - Player account system (balance, authentication).
    - Insurance, split hands, double-down.
    - Multiple players at the table.
"""

from __future__ import annotations

import random
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Suit(Enum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"


class Rank(Enum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class Card:
    """A single playing card with a suit and rank."""

    def __init__(self, suit: Suit, rank: Rank) -> None:
        self.suit = suit
        self.rank = rank

    @property
    def value(self) -> int:
        """Blackjack point value (face cards = 10, ace = 11 by default).

        Ace flexibility (1 vs 11) is handled at the Hand level.
        """
        if self.rank == Rank.ACE:
            return 11
        if self.rank.value >= 10:  # JACK, QUEEN, KING
            return 10
        return self.rank.value

    @property
    def is_ace(self) -> bool:
        return self.rank == Rank.ACE

    def __repr__(self) -> str:
        return f"{self.rank.name.title()} of {self.suit.value}"


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------

class Deck:
    """Standard 52-card deck with shuffle and deal operations."""

    def __init__(self) -> None:
        self._cards: list[Card] = [
            Card(suit, rank) for suit in Suit for rank in Rank
        ]
        self.shuffle()

    def shuffle(self) -> None:
        random.shuffle(self._cards)

    def deal_card(self) -> Card:
        if not self._cards:
            raise ValueError("Deck is empty")
        return self._cards.pop()

    def __len__(self) -> int:
        return len(self._cards)


# ---------------------------------------------------------------------------
# Hand
# ---------------------------------------------------------------------------

class Hand:
    """A collection of cards with blackjack value calculation.

    Handles ace flexibility: each ace can count as 1 or 11 to produce the
    best (highest non-busting) total.
    """

    BLACKJACK = 21

    def __init__(self) -> None:
        self.cards: list[Card] = []

    def add_card(self, card: Card) -> None:
        self.cards.append(card)

    @property
    def value(self) -> int:
        """Best hand value: highest total that does not exceed 21.

        Strategy: start by counting every ace as 11, then downgrade aces
        to 1 (subtract 10) one at a time while the total exceeds 21.
        """
        total = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.is_ace)
        while total > self.BLACKJACK and aces > 0:
            total -= 10
            aces -= 1
        return total

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.value == self.BLACKJACK

    @property
    def is_bust(self) -> bool:
        return self.value > self.BLACKJACK

    def __repr__(self) -> str:
        cards_str = ", ".join(str(c) for c in self.cards)
        return f"[{cards_str}] (value: {self.value})"


# ---------------------------------------------------------------------------
# Player & Dealer
# ---------------------------------------------------------------------------

class Player:
    """A human player who can decide to hit or stand."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.hand = Hand()

    def wants_hit(self) -> bool:
        """Prompt the player for a decision. Returns True for HIT."""
        while True:
            choice = input(f"{self.name}, hit or stand? (h/s): ").strip().lower()
            if choice in ("h", "hit"):
                return True
            if choice in ("s", "stand"):
                return False
            print("  Please enter 'h' to hit or 's' to stand.")

    def __repr__(self) -> str:
        return f"{self.name}: {self.hand}"


class Dealer:
    """The dealer follows fixed house rules (hit on <= 16, stand on >= 17)."""

    STAND_THRESHOLD = 17

    def __init__(self) -> None:
        self.name = "Dealer"
        self.hand = Hand()

    def should_hit(self) -> bool:
        return self.hand.value < self.STAND_THRESHOLD

    def show_partial(self) -> str:
        """Show only the first card (up card); hide the hole card."""
        if len(self.hand.cards) < 2:
            return str(self.hand)
        return f"[{self.hand.cards[0]}, <hidden>]"

    def __repr__(self) -> str:
        return f"{self.name}: {self.hand}"


# ---------------------------------------------------------------------------
# BlackjackGame
# ---------------------------------------------------------------------------

class BlackjackGame:
    """Orchestrates a single round of blackjack between one player and a dealer.

    Flow:  deal -> player's turn -> dealer's turn -> determine winner.
    """

    def __init__(self, player_name: str = "Player") -> None:
        self.deck = Deck()
        self.player = Player(player_name)
        self.dealer = Dealer()

    # -- Setup --------------------------------------------------------------

    def deal_initial_cards(self) -> None:
        """Deal two cards each, alternating player-dealer as in a real game."""
        for _ in range(2):
            self.player.hand.add_card(self.deck.deal_card())
            self.dealer.hand.add_card(self.deck.deal_card())

    # -- Turns --------------------------------------------------------------

    def player_turn(self) -> None:
        """Let the player hit until they stand or bust."""
        while not self.player.hand.is_bust:
            print(f"\n  {self.player}")
            print(f"  {self.dealer.name}: {self.dealer.show_partial()}")
            if not self.player.wants_hit():
                break
            card = self.deck.deal_card()
            self.player.hand.add_card(card)
            print(f"  -> Dealt {card}")

        if self.player.hand.is_bust:
            print(f"\n  {self.player}  *** BUST ***")

    def dealer_turn(self) -> None:
        """Dealer reveals hole card and hits according to house rules."""
        print(f"\n  Dealer reveals: {self.dealer}")
        while self.dealer.should_hit():
            card = self.deck.deal_card()
            self.dealer.hand.add_card(card)
            print(f"  -> Dealer draws {card}  ({self.dealer.hand.value})")

        if self.dealer.hand.is_bust:
            print(f"  {self.dealer}  *** BUST ***")

    # -- Resolution ---------------------------------------------------------

    def determine_winner(self) -> str:
        """Compare hands and return a result message."""
        p_val = self.player.hand.value
        d_val = self.dealer.hand.value
        p_bj = self.player.hand.is_blackjack
        d_bj = self.dealer.hand.is_blackjack

        if self.player.hand.is_bust:
            return f"{self.dealer.name} wins! ({self.player.name} busted with {p_val})"
        if self.dealer.hand.is_bust:
            return f"{self.player.name} wins! ({self.dealer.name} busted with {d_val})"
        if p_bj and d_bj:
            return "Push! Both have blackjack."
        if p_bj:
            return f"{self.player.name} wins with BLACKJACK!"
        if d_bj:
            return f"{self.dealer.name} wins with BLACKJACK."
        if p_val > d_val:
            return f"{self.player.name} wins! ({p_val} vs {d_val})"
        if d_val > p_val:
            return f"{self.dealer.name} wins. ({d_val} vs {p_val})"
        return f"Push! Both have {p_val}."

    # -- Main loop ----------------------------------------------------------

    def play(self) -> None:
        """Run one complete round of blackjack."""
        print("=== Blackjack ===\n")
        self.deal_initial_cards()

        # Check for natural blackjacks before player acts
        if self.player.hand.is_blackjack or self.dealer.hand.is_blackjack:
            print(f"  {self.player}")
            print(f"  {self.dealer}")
        else:
            self.player_turn()
            if not self.player.hand.is_bust:
                self.dealer_turn()

        result = self.determine_winner()
        print(f"\n  Final -> {self.player}")
        print(f"  Final -> {self.dealer}")
        print(f"\n  Result: {result}\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    game = BlackjackGame(player_name="Alice")
    game.play()
