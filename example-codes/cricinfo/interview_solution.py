"""
Design Cricinfo -- Interview-Feasible Solution
================================================

Problem: Model a cricket match scoring system (like Cricinfo/ESPNcricinfo)
that tracks ball-by-ball progress, runs, wickets, and generates a scorecard.

Assumptions / Reduced Scope:
  - Single match focus (no tournament/league management).
  - Limited-overs format only (e.g., T20/ODI). No multi-innings Test logic.
  - Each team has a playing XI; no squad/tournament-squad hierarchy.
  - No commentary, news, or notification subsystems.
  - No stadium/venue, umpire, or referee entities.
  - No admin/auth flows; direct API-style method calls.
  - Player statistics are per-innings only (no career aggregation).

Main Use Cases Implemented:
  1. Create a match between two teams of players.
  2. Start the match and play innings (team bats, opponent bowls).
  3. Record overs and individual balls (runs scored, extras, wickets).
  4. Track innings totals (runs, wickets, overs bowled).
  5. Generate a simple scorecard at the end.

Left Out:
  - Full tournament brackets and points tables.
  - Commentary / commentator system.
  - Stadium, umpire, referee modeling.
  - Admin and notification workflows.
  - Career-level player statistics and stat queries.
  - News and article management.
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MatchFormat(Enum):
    ODI = auto()
    T20 = auto()
    TEST = auto()


class MatchStatus(Enum):
    SCHEDULED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()


class BallType(Enum):
    NORMAL = auto()
    WIDE = auto()
    NO_BALL = auto()


class WicketType(Enum):
    BOWLED = auto()
    CAUGHT = auto()
    LBW = auto()
    RUN_OUT = auto()
    STUMPED = auto()
    HIT_WICKET = auto()


class RunType(Enum):
    NORMAL = auto()
    FOUR = auto()
    SIX = auto()
    BYE = auto()
    LEG_BYE = auto()


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------

@dataclass
class Player:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class Team:
    name: str
    players: list[Player] = field(default_factory=list)

    def add_player(self, player: Player) -> None:
        self.players.append(player)

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Ball-by-Ball Scoring
# ---------------------------------------------------------------------------

@dataclass
class Wicket:
    wicket_type: WicketType
    player_out: Player
    fielder: Optional[Player] = None  # catcher / run-out fielder

    def __str__(self) -> str:
        desc = f"{self.player_out.name} - {self.wicket_type.name}"
        if self.fielder:
            desc += f" (fielder: {self.fielder.name})"
        return desc


@dataclass
class Ball:
    """A single delivery in an over."""
    bowler: Player
    batsman: Player
    runs: int = 0
    run_type: RunType = RunType.NORMAL
    ball_type: BallType = BallType.NORMAL
    wicket: Optional[Wicket] = None

    @property
    def is_extra(self) -> bool:
        return self.ball_type in (BallType.WIDE, BallType.NO_BALL)

    @property
    def total_runs(self) -> int:
        """Runs charged to the batting side for this delivery."""
        extra = 1 if self.is_extra else 0
        return self.runs + extra

    def __str__(self) -> str:
        parts: list[str] = []
        if self.ball_type == BallType.WIDE:
            parts.append("Wide")
        elif self.ball_type == BallType.NO_BALL:
            parts.append("No-ball")
        if self.wicket:
            parts.append(f"WICKET ({self.wicket})")
        if self.runs:
            label = self.run_type.name if self.run_type != RunType.NORMAL else ""
            parts.append(f"{self.runs} run{'s' if self.runs != 1 else ''}" +
                         (f" ({label})" if label else ""))
        return f"{self.bowler.name} to {self.batsman.name}: " + (", ".join(parts) or "dot ball")


class Over:
    """An over consisting of (up to 6 legal) deliveries."""

    def __init__(self, number: int, bowler: Player) -> None:
        self.number = number
        self.bowler = bowler
        self.balls: list[Ball] = []

    def add_ball(self, ball: Ball) -> None:
        self.balls.append(ball)

    @property
    def legal_deliveries(self) -> int:
        return sum(1 for b in self.balls if not b.is_extra)

    @property
    def is_complete(self) -> bool:
        return self.legal_deliveries >= 6

    @property
    def runs_conceded(self) -> int:
        return sum(b.total_runs for b in self.balls)

    @property
    def wickets(self) -> int:
        return sum(1 for b in self.balls if b.wicket is not None)


# ---------------------------------------------------------------------------
# Innings & Scorecard
# ---------------------------------------------------------------------------

class Innings:
    """One team's turn to bat."""

    def __init__(self, number: int, batting_team: Team, bowling_team: Team) -> None:
        self.number = number
        self.batting_team = batting_team
        self.bowling_team = bowling_team
        self.overs: list[Over] = []

    def add_over(self, over: Over) -> None:
        self.overs.append(over)

    @property
    def total_runs(self) -> int:
        return sum(o.runs_conceded for o in self.overs)

    @property
    def total_wickets(self) -> int:
        return sum(o.wickets for o in self.overs)

    @property
    def overs_bowled(self) -> str:
        """Display as '5.3' meaning 5 complete overs + 3 balls."""
        if not self.overs:
            return "0.0"
        complete = sum(1 for o in self.overs if o.is_complete)
        partial = 0
        for o in self.overs:
            if not o.is_complete:
                partial = o.legal_deliveries
        return f"{complete}.{partial}"

    def scorecard(self) -> str:
        lines: list[str] = [
            f"--- {self.batting_team.name} Innings ---",
            f"Total: {self.total_runs}/{self.total_wickets} "
            f"({self.overs_bowled} overs)",
        ]

        # Batsman summary
        batsman_runs: dict[str, int] = {}
        batsman_balls: dict[str, int] = {}
        for over in self.overs:
            for ball in over.balls:
                name = ball.batsman.name
                batsman_runs.setdefault(name, 0)
                batsman_balls.setdefault(name, 0)
                if ball.run_type in (RunType.NORMAL, RunType.FOUR, RunType.SIX):
                    batsman_runs[name] += ball.runs
                if not ball.is_extra:
                    batsman_balls[name] += 1

        dismissals: dict[str, str] = {}
        for over in self.overs:
            for ball in over.balls:
                if ball.wicket:
                    dismissals[ball.wicket.player_out.name] = str(ball.wicket.wicket_type.name)

        lines.append("  Batting:")
        for name in batsman_runs:
            status = dismissals.get(name, "not out")
            lines.append(f"    {name}: {batsman_runs[name]} ({batsman_balls[name]} balls) [{status}]")

        # Bowler summary
        bowler_overs: dict[str, list[Over]] = {}
        for over in self.overs:
            bowler_overs.setdefault(over.bowler.name, []).append(over)

        lines.append("  Bowling:")
        for bname, overs in bowler_overs.items():
            runs = sum(o.runs_conceded for o in overs)
            wkts = sum(o.wickets for o in overs)
            count = len(overs)
            lines.append(f"    {bname}: {count} ov, {runs} runs, {wkts} wkt(s)")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class Match:
    def __init__(
        self,
        team_a: Team,
        team_b: Team,
        match_format: MatchFormat = MatchFormat.T20,
    ) -> None:
        self.team_a = team_a
        self.team_b = team_b
        self.match_format = match_format
        self.status: MatchStatus = MatchStatus.SCHEDULED
        self.innings: list[Innings] = []
        self._max_overs = 20 if match_format == MatchFormat.T20 else 50

    def start(self) -> None:
        if self.status != MatchStatus.SCHEDULED:
            raise RuntimeError("Match has already started or is completed.")
        self.status = MatchStatus.IN_PROGRESS

    def add_innings(self, batting_team: Team, bowling_team: Team) -> Innings:
        if self.status != MatchStatus.IN_PROGRESS:
            raise RuntimeError("Match is not in progress.")
        inning = Innings(len(self.innings) + 1, batting_team, bowling_team)
        self.innings.append(inning)
        return inning

    def complete(self) -> None:
        self.status = MatchStatus.COMPLETED

    def result_summary(self) -> str:
        if len(self.innings) < 2:
            return "Match not yet decided."
        first = self.innings[0]
        second = self.innings[1]
        if second.total_runs > first.total_runs:
            wickets_left = 10 - second.total_wickets
            return (f"{second.batting_team.name} won by "
                    f"{wickets_left} wicket(s)")
        elif first.total_runs > second.total_runs:
            run_diff = first.total_runs - second.total_runs
            return (f"{first.batting_team.name} won by "
                    f"{run_diff} run(s)")
        else:
            return "Match tied"

    def scorecard(self) -> str:
        sections = [
            f"=== {self.team_a.name} vs {self.team_b.name} "
            f"({self.match_format.name}) ===",
            f"Status: {self.status.name}",
        ]
        for inn in self.innings:
            sections.append(inn.scorecard())
        if self.status == MatchStatus.COMPLETED:
            sections.append(f"Result: {self.result_summary()}")
        return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _build_demo_teams() -> tuple[Team, Team]:
    """Create two small teams for demonstration."""
    india = Team("India")
    for name in ["Rohit", "Virat", "Pant", "Hardik", "Jadeja",
                  "Bumrah", "Shami", "Siraj", "Ashwin", "Rahul", "Gill"]:
        india.add_player(Player(name))

    australia = Team("Australia")
    for name in ["Warner", "Smith", "Labuschagne", "Head", "Maxwell",
                  "Cummins", "Starc", "Hazlewood", "Lyon", "Carey", "Green"]:
        australia.add_player(Player(name))

    return india, australia


def _simulate_over(
    innings: Innings,
    over_num: int,
    bowler: Player,
    batsman: Player,
    ball_specs: list[tuple[int, RunType, BallType, Optional[Wicket]]],
) -> Over:
    """Helper to add an over with specified ball outcomes."""
    over = Over(over_num, bowler)
    for runs, run_type, ball_type, wicket in ball_specs:
        ball = Ball(
            bowler=bowler,
            batsman=batsman,
            runs=runs,
            run_type=run_type,
            ball_type=ball_type,
            wicket=wicket,
        )
        over.add_ball(ball)
    innings.add_over(over)
    return over


if __name__ == "__main__":
    india, australia = _build_demo_teams()

    match = Match(india, australia, MatchFormat.T20)
    match.start()

    # ---- First Innings: India bats ----
    inn1 = match.add_innings(batting_team=india, bowling_team=australia)

    _simulate_over(inn1, 1, australia.players[5], india.players[0], [
        (0, RunType.NORMAL, BallType.NORMAL, None),
        (4, RunType.FOUR,   BallType.NORMAL, None),
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NORMAL, None),
        (6, RunType.SIX,    BallType.NORMAL, None),
        (2, RunType.NORMAL, BallType.NORMAL, None),
    ])

    _simulate_over(inn1, 2, australia.players[6], india.players[1], [
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.WIDE,   None),  # wide
        (0, RunType.NORMAL, BallType.NORMAL,
         Wicket(WicketType.CAUGHT, india.players[1], fielder=australia.players[1])),
        (4, RunType.FOUR,   BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NORMAL, None),
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (2, RunType.NORMAL, BallType.NORMAL, None),
    ])

    # ---- Second Innings: Australia bats ----
    inn2 = match.add_innings(batting_team=australia, bowling_team=india)

    _simulate_over(inn2, 1, india.players[5], australia.players[0], [
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NORMAL, None),
        (4, RunType.FOUR,   BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NORMAL,
         Wicket(WicketType.BOWLED, australia.players[0])),
        (6, RunType.SIX,    BallType.NORMAL, None),
        (1, RunType.NORMAL, BallType.NORMAL, None),
    ])

    _simulate_over(inn2, 2, india.players[6], australia.players[1], [
        (0, RunType.NORMAL, BallType.NORMAL, None),
        (2, RunType.NORMAL, BallType.NORMAL, None),
        (4, RunType.FOUR,   BallType.NORMAL, None),
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NO_BALL, None),
        (1, RunType.NORMAL, BallType.NORMAL, None),
        (0, RunType.NORMAL, BallType.NORMAL, None),
    ])

    match.complete()

    # ---- Print full scorecard ----
    print(match.scorecard())
