"""
Design Stack Overflow -- Interview-Feasible Solution
=====================================================

Assumptions / Reduced Scope:
    - Single-process, in-memory system (no database or API layer).
    - One user role: Member.  Admin, Moderator, and Guest hierarchies omitted.
    - No badge system, bounty system, notification system, or photo/media.
    - No complex search, flagging, or moderation tools.
    - Reputation is tracked with a simple integer on Member.

Main Use Cases Implemented:
    1. Register members.
    2. Post a question with tags.
    3. Post answers to a question.
    4. Vote (upvote / downvote) on questions and answers.
    5. Accept an answer (only by the question author).
    6. Add comments to questions and answers.
    7. Close / reopen a question.
    8. Reputation adjustments on votes and accepted answers.

What Was Left Out:
    - Full account hierarchy (Guest, Admin, Moderator).
    - Badge and bounty systems.
    - Notification system.
    - Photo / media attachments.
    - Flag / moderation workflows.
    - Persistent storage and search indexing.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QuestionStatus(Enum):
    OPEN = auto()
    CLOSED = auto()
    DELETED = auto()


class VoteType(Enum):
    UPVOTE = auto()
    DOWNVOTE = auto()


# Reputation deltas -- easy to tweak in one place.
class Rep:
    QUESTION_UPVOTE = 5
    QUESTION_DOWNVOTE = -2
    ANSWER_UPVOTE = 10
    ANSWER_DOWNVOTE = -2
    ANSWER_ACCEPTED = 15


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------

class Tag:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Tag({self.name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tag):
            return self.name == other.name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.name)


# ---------------------------------------------------------------------------
# Vote
# ---------------------------------------------------------------------------

class Vote:
    def __init__(self, voter: Member, vote_type: VoteType) -> None:
        self.voter = voter
        self.vote_type = vote_type
        self.created_at = datetime.now()


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class Comment:
    def __init__(self, text: str, author: Member) -> None:
        self.text = text
        self.author = author
        self.created_at = datetime.now()

    def __repr__(self) -> str:
        return f"Comment(by={self.author.name!r}, text={self.text[:40]!r})"


# ---------------------------------------------------------------------------
# Answer
# ---------------------------------------------------------------------------

class Answer:
    def __init__(self, text: str, author: Member, question: Question) -> None:
        self.text = text
        self.author = author
        self.question = question
        self.is_accepted: bool = False
        self.created_at = datetime.now()
        self.votes: list[Vote] = []
        self.comments: list[Comment] = []

    # -- voting -------------------------------------------------------------

    @property
    def vote_count(self) -> int:
        return sum(
            1 if v.vote_type == VoteType.UPVOTE else -1 for v in self.votes
        )

    def vote(self, voter: Member, vote_type: VoteType) -> None:
        """Cast or update a vote.  A member may only vote once per answer."""
        if voter is self.author:
            raise ValueError("Cannot vote on your own answer.")
        for existing in self.votes:
            if existing.voter is voter:
                existing.vote_type = vote_type
                return
        self.votes.append(Vote(voter, vote_type))
        # Adjust reputation of the *answer author*.
        delta = Rep.ANSWER_UPVOTE if vote_type == VoteType.UPVOTE else Rep.ANSWER_DOWNVOTE
        self.author.reputation += delta

    # -- comments -----------------------------------------------------------

    def add_comment(self, text: str, author: Member) -> Comment:
        comment = Comment(text, author)
        self.comments.append(comment)
        return comment

    # -- accept -------------------------------------------------------------

    def accept(self, accepted_by: Member) -> None:
        if accepted_by is not self.question.author:
            raise PermissionError("Only the question author can accept an answer.")
        if self.question.accepted_answer is not None:
            self.question.accepted_answer.is_accepted = False
        self.is_accepted = True
        self.question.accepted_answer = self
        self.author.reputation += Rep.ANSWER_ACCEPTED

    def __repr__(self) -> str:
        accepted_marker = " [accepted]" if self.is_accepted else ""
        return (
            f"Answer(by={self.author.name!r}, "
            f"votes={self.vote_count}{accepted_marker})"
        )


# ---------------------------------------------------------------------------
# Question
# ---------------------------------------------------------------------------

class Question:
    def __init__(self, title: str, description: str, author: Member) -> None:
        self.title = title
        self.description = description
        self.author = author
        self.status: QuestionStatus = QuestionStatus.OPEN
        self.created_at = datetime.now()
        self.tags: list[Tag] = []
        self.answers: list[Answer] = []
        self.comments: list[Comment] = []
        self.votes: list[Vote] = []
        self.accepted_answer: Optional[Answer] = None
        self.view_count: int = 0

    # -- tags ---------------------------------------------------------------

    def add_tag(self, tag: Tag) -> None:
        if tag not in self.tags:
            self.tags.append(tag)

    # -- answers ------------------------------------------------------------

    def add_answer(self, text: str, author: Member) -> Answer:
        if self.status != QuestionStatus.OPEN:
            raise ValueError("Cannot answer a closed or deleted question.")
        answer = Answer(text, author, question=self)
        self.answers.append(answer)
        return answer

    # -- voting -------------------------------------------------------------

    @property
    def vote_count(self) -> int:
        return sum(
            1 if v.vote_type == VoteType.UPVOTE else -1 for v in self.votes
        )

    def vote(self, voter: Member, vote_type: VoteType) -> None:
        if voter is self.author:
            raise ValueError("Cannot vote on your own question.")
        for existing in self.votes:
            if existing.voter is voter:
                existing.vote_type = vote_type
                return
        self.votes.append(Vote(voter, vote_type))
        delta = Rep.QUESTION_UPVOTE if vote_type == VoteType.UPVOTE else Rep.QUESTION_DOWNVOTE
        self.author.reputation += delta

    # -- comments -----------------------------------------------------------

    def add_comment(self, text: str, author: Member) -> Comment:
        comment = Comment(text, author)
        self.comments.append(comment)
        return comment

    # -- status management --------------------------------------------------

    def close(self) -> None:
        self.status = QuestionStatus.CLOSED

    def reopen(self) -> None:
        self.status = QuestionStatus.OPEN

    def delete(self) -> None:
        self.status = QuestionStatus.DELETED

    def __repr__(self) -> str:
        return (
            f"Question({self.title!r}, status={self.status.name}, "
            f"votes={self.vote_count}, answers={len(self.answers)})"
        )


# ---------------------------------------------------------------------------
# Member (User)
# ---------------------------------------------------------------------------

class Member:
    def __init__(self, member_id: int, name: str, email: str) -> None:
        self.member_id = member_id
        self.name = name
        self.email = email
        self.reputation: int = 0
        self.questions: list[Question] = []
        self.answers: list[Answer] = []

    def post_question(self, title: str, description: str) -> Question:
        question = Question(title, description, author=self)
        self.questions.append(question)
        return question

    def answer_question(self, question: Question, text: str) -> Answer:
        answer = question.add_answer(text, author=self)
        self.answers.append(answer)
        return answer

    def __repr__(self) -> str:
        return f"Member({self.name!r}, rep={self.reputation})"


# ---------------------------------------------------------------------------
# StackOverflow  --  top-level system / facade
# ---------------------------------------------------------------------------

class StackOverflow:
    """Central registry that owns all members and questions."""

    def __init__(self) -> None:
        self._members: dict[int, Member] = {}
        self._questions: list[Question] = []
        self._tag_pool: dict[str, Tag] = {}
        self._next_member_id: int = 1

    # -- member management --------------------------------------------------

    def register_member(self, name: str, email: str) -> Member:
        member = Member(self._next_member_id, name, email)
        self._members[member.member_id] = member
        self._next_member_id += 1
        return member

    # -- tag management -----------------------------------------------------

    def get_or_create_tag(self, name: str) -> Tag:
        name_lower = name.lower()
        if name_lower not in self._tag_pool:
            self._tag_pool[name_lower] = Tag(name_lower)
        return self._tag_pool[name_lower]

    # -- question management ------------------------------------------------

    def post_question(
        self,
        member: Member,
        title: str,
        description: str,
        tag_names: Optional[list[str]] = None,
    ) -> Question:
        question = member.post_question(title, description)
        self._questions.append(question)
        for tn in (tag_names or []):
            question.add_tag(self.get_or_create_tag(tn))
        return question

    # -- simple search ------------------------------------------------------

    def search(self, query: str) -> list[Question]:
        query_lower = query.lower()
        return [
            q
            for q in self._questions
            if query_lower in q.title.lower()
            or query_lower in q.description.lower()
            or any(query_lower == t.name for t in q.tags)
        ]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    so = StackOverflow()

    # 1. Register members
    alice = so.register_member("Alice", "alice@example.com")
    bob = so.register_member("Bob", "bob@example.com")
    carol = so.register_member("Carol", "carol@example.com")
    print(f"Registered: {alice}, {bob}, {carol}\n")

    # 2. Alice posts a question with tags
    q = so.post_question(
        alice,
        title="How do Python decorators work?",
        description="I understand functions are first-class objects, but I am "
        "confused by the @syntax for decorators. Can someone explain?",
        tag_names=["python", "decorators"],
    )
    print(f"Posted: {q}")
    print(f"  Tags: {q.tags}\n")

    # 3. Bob and Carol answer the question
    a1 = bob.answer_question(q, "Decorators are syntactic sugar for wrapping functions...")
    a2 = carol.answer_question(q, "Think of @decorator as func = decorator(func)...")
    print(f"Answers: {a1}, {a2}\n")

    # 4. Voting on the question and answers
    bob.reputation = 0  # reset for demo clarity
    carol.reputation = 0

    q.vote(bob, VoteType.UPVOTE)      # Alice gets +5 rep
    q.vote(carol, VoteType.UPVOTE)    # Alice gets +5 rep
    a2.vote(alice, VoteType.UPVOTE)   # Carol gets +10 rep
    a1.vote(alice, VoteType.UPVOTE)   # Bob gets +10 rep
    a1.vote(carol, VoteType.UPVOTE)   # Bob gets +10 rep

    print(f"After voting:")
    print(f"  {q}")
    print(f"  {a1}")
    print(f"  {a2}")
    print(f"  Alice rep={alice.reputation}, Bob rep={bob.reputation}, Carol rep={carol.reputation}\n")

    # 5. Alice accepts Carol's answer
    a2.accept(accepted_by=alice)       # Carol gets +15 rep
    print(f"Accepted answer: {a2}")
    print(f"  Carol rep now: {carol.reputation}\n")

    # 6. Add comments
    c1 = q.add_comment("Great question, I had the same confusion!", carol)
    c2 = a2.add_comment("Thanks, this one-liner really clarified things.", alice)
    print(f"Comments: {c1}, {c2}\n")

    # 7. Search
    results = so.search("decorators")
    print(f"Search 'decorators': {results}\n")

    # 8. Close and reopen
    q.close()
    print(f"After close: {q}")
    q.reopen()
    print(f"After reopen: {q}")
