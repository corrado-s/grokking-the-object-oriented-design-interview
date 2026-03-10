"""
Design LinkedIn -- Interview-Feasible OOD Solution

Assumptions / Reduced Scope:
  - Single-process, in-memory system (no persistence, no concurrency).
  - Users are identified by a unique user_id string; no separate Account /
    Person / Admin hierarchy.
  - No messaging system, notification system, or recommendation engine.
  - No group management or company-page complexity (companies exist only as
    a name on a JobPosting).
  - No endorsements, skills, accomplishments, or profile-stat tracking.
  - Search is a simple case-insensitive substring match -- good enough to
    demonstrate the interface without an indexing discussion.

Main Use-Cases Implemented:
  1. Create a user with a profile containing experiences and education.
  2. Send, accept, and reject connection requests (full lifecycle).
  3. Create posts visible to connections.
  4. Create job postings and apply for jobs.

What Was Left Out:
  - Full account hierarchy (Account, Person, Admin)
  - Group management and company pages
  - Messaging and notification systems
  - Search ranking / recommendation engine
  - Endorsements, skills, accomplishments
  - Media attachments, comments, likes/shares counts
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConnectionStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EmploymentType(Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

class Experience:
    """A single work-experience entry on a user's profile."""

    def __init__(
        self,
        title: str,
        company: str,
        location: str,
        start_date: date,
        end_date: Optional[date] = None,
        description: str = "",
    ) -> None:
        self.title = title
        self.company = company
        self.location = location
        self.start_date = start_date
        self.end_date = end_date  # None means "present"
        self.description = description

    def __repr__(self) -> str:
        end = self.end_date or "present"
        return f"Experience({self.title} @ {self.company}, {self.start_date}-{end})"


class Education:
    """A single education entry on a user's profile."""

    def __init__(
        self,
        school: str,
        degree: str,
        field_of_study: str,
        start_year: int,
        end_year: Optional[int] = None,
    ) -> None:
        self.school = school
        self.degree = degree
        self.field_of_study = field_of_study
        self.start_year = start_year
        self.end_year = end_year

    def __repr__(self) -> str:
        end = self.end_year or "present"
        return f"Education({self.degree} in {self.field_of_study}, {self.school}, {self.start_year}-{end})"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class Profile:
    """Aggregates a user's headline, summary, experiences, and education."""

    def __init__(self, headline: str = "", summary: str = "") -> None:
        self.headline = headline
        self.summary = summary
        self.experiences: list[Experience] = []
        self.educations: list[Education] = []

    def add_experience(self, experience: Experience) -> None:
        self.experiences.append(experience)

    def add_education(self, education: Education) -> None:
        self.educations.append(education)

    def __repr__(self) -> str:
        return (
            f"Profile(headline={self.headline!r}, "
            f"experiences={len(self.experiences)}, "
            f"educations={len(self.educations)})"
        )


# ---------------------------------------------------------------------------
# Connection Request
# ---------------------------------------------------------------------------

class ConnectionRequest:
    """Represents a pending/accepted/rejected connection between two users."""

    def __init__(self, from_user: User, to_user: User) -> None:
        self.request_id: str = uuid.uuid4().hex[:8]
        self.from_user = from_user
        self.to_user = to_user
        self.status = ConnectionStatus.PENDING
        self.created_at = datetime.now()

    def accept(self) -> None:
        if self.status != ConnectionStatus.PENDING:
            raise ValueError(f"Cannot accept a request that is {self.status.value}")
        self.status = ConnectionStatus.ACCEPTED
        # Connections are bidirectional.
        self.from_user._connections.add(self.to_user.user_id)
        self.to_user._connections.add(self.from_user.user_id)

    def reject(self) -> None:
        if self.status != ConnectionStatus.PENDING:
            raise ValueError(f"Cannot reject a request that is {self.status.value}")
        self.status = ConnectionStatus.REJECTED

    def __repr__(self) -> str:
        return (
            f"ConnectionRequest({self.from_user.name} -> {self.to_user.name}, "
            f"status={self.status.value})"
        )


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class Post:
    """A text update shared with a user's connections."""

    def __init__(self, author: User, text: str) -> None:
        self.post_id: str = uuid.uuid4().hex[:8]
        self.author = author
        self.text = text
        self.created_at = datetime.now()

    def __repr__(self) -> str:
        snippet = self.text[:40] + ("..." if len(self.text) > 40 else "")
        return f"Post(by={self.author.name}, text={snippet!r})"


# ---------------------------------------------------------------------------
# Job Posting & Application
# ---------------------------------------------------------------------------

class JobPosting:
    """A job listing created by any user (acting as a hiring manager)."""

    def __init__(
        self,
        title: str,
        company: str,
        location: str,
        description: str = "",
        employment_type: EmploymentType = EmploymentType.FULL_TIME,
    ) -> None:
        self.posting_id: str = uuid.uuid4().hex[:8]
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.employment_type = employment_type
        self.created_at = datetime.now()
        self.is_active: bool = True
        self._applicants: list[User] = []

    def apply(self, user: User) -> None:
        if not self.is_active:
            raise ValueError("This job posting is no longer active.")
        if user in self._applicants:
            raise ValueError(f"{user.name} has already applied.")
        self._applicants.append(user)

    @property
    def applicants(self) -> list[User]:
        return list(self._applicants)

    def close(self) -> None:
        self.is_active = False

    def __repr__(self) -> str:
        return f"JobPosting({self.title} @ {self.company}, active={self.is_active})"


# ---------------------------------------------------------------------------
# User (core entity)
# ---------------------------------------------------------------------------

class User:
    """
    Central entity representing a LinkedIn member.

    Owns a Profile and manages connections, posts, and job applications.
    """

    def __init__(self, user_id: str, name: str, email: str) -> None:
        self.user_id = user_id
        self.name = name
        self.email = email
        self.profile = Profile()
        self.posts: list[Post] = []
        self.created_at = datetime.now()

        # Internal bookkeeping -- accessed by ConnectionRequest and LinkedIn.
        self._connections: set[str] = set()
        self._sent_requests: list[ConnectionRequest] = []
        self._received_requests: list[ConnectionRequest] = []

    # -- connections --------------------------------------------------------

    def send_connection_request(self, other: User) -> ConnectionRequest:
        if other.user_id == self.user_id:
            raise ValueError("Cannot connect with yourself.")
        if other.user_id in self._connections:
            raise ValueError(f"Already connected with {other.name}.")
        request = ConnectionRequest(from_user=self, to_user=other)
        self._sent_requests.append(request)
        other._received_requests.append(request)
        return request

    def get_pending_requests(self) -> list[ConnectionRequest]:
        return [
            r for r in self._received_requests
            if r.status == ConnectionStatus.PENDING
        ]

    @property
    def connections(self) -> set[str]:
        return set(self._connections)

    # -- posts --------------------------------------------------------------

    def create_post(self, text: str) -> Post:
        post = Post(author=self, text=text)
        self.posts.append(post)
        return post

    # -- jobs ---------------------------------------------------------------

    def apply_to_job(self, posting: JobPosting) -> None:
        posting.apply(self)

    def __repr__(self) -> str:
        return f"User(id={self.user_id}, name={self.name!r})"


# ---------------------------------------------------------------------------
# LinkedIn (system facade)
# ---------------------------------------------------------------------------

class LinkedIn:
    """
    Top-level facade that owns all users and job postings and exposes
    simple search helpers.
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._job_postings: list[JobPosting] = []

    # -- user management ----------------------------------------------------

    def register_user(self, user_id: str, name: str, email: str) -> User:
        if user_id in self._users:
            raise ValueError(f"User ID {user_id!r} already exists.")
        user = User(user_id=user_id, name=name, email=email)
        self._users[user_id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    # -- job postings -------------------------------------------------------

    def add_job_posting(self, posting: JobPosting) -> None:
        self._job_postings.append(posting)

    # -- search (simple substring match) ------------------------------------

    def search_users(self, query: str) -> list[User]:
        q = query.lower()
        return [u for u in self._users.values() if q in u.name.lower()]

    def search_jobs(self, query: str) -> list[JobPosting]:
        q = query.lower()
        return [
            j for j in self._job_postings
            if j.is_active and (q in j.title.lower() or q in j.company.lower())
        ]

    def get_feed(self, user: User) -> list[Post]:
        """Return posts from the user's connections, newest first."""
        feed: list[Post] = []
        for conn_id in user.connections:
            conn = self._users.get(conn_id)
            if conn:
                feed.extend(conn.posts)
        feed.sort(key=lambda p: p.created_at, reverse=True)
        return feed


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ln = LinkedIn()

    # 1. Register users
    alice = ln.register_user("alice01", "Alice Johnson", "alice@example.com")
    bob = ln.register_user("bob02", "Bob Smith", "bob@example.com")
    carol = ln.register_user("carol03", "Carol Lee", "carol@example.com")

    # 2. Build profiles
    alice.profile.headline = "Senior Software Engineer"
    alice.profile.summary = "10 years building distributed systems."
    alice.profile.add_experience(
        Experience("Staff Engineer", "BigTech Co", "San Francisco", date(2020, 1, 1))
    )
    alice.profile.add_education(
        Education("MIT", "B.S.", "Computer Science", 2010, 2014)
    )

    bob.profile.headline = "Product Manager"
    bob.profile.add_experience(
        Experience("Senior PM", "StartupX", "New York", date(2019, 6, 1))
    )

    print("=== Profiles ===")
    print(f"  {alice.name}: {alice.profile}")
    print(f"  {bob.name}:   {bob.profile}")

    # 3. Connection requests
    req1 = alice.send_connection_request(bob)
    req2 = carol.send_connection_request(alice)
    print(f"\n=== Connection Requests ===")
    print(f"  {req1}")
    print(f"  {req2}")

    # Bob accepts Alice's request
    req1.accept()
    print(f"  After accept: {req1}")
    print(f"  Alice connections: {alice.connections}")
    print(f"  Bob connections:   {bob.connections}")

    # Alice rejects Carol's request
    req2.reject()
    print(f"  After reject: {req2}")

    # 4. Posts and feed
    alice.create_post("Excited to share my new paper on distributed consensus!")
    bob.create_post("Looking for great engineers to join our team.")
    print(f"\n=== Feed for Bob (sees Alice's posts) ===")
    for post in ln.get_feed(bob):
        print(f"  {post}")

    print(f"\n=== Feed for Carol (no connections, empty) ===")
    for post in ln.get_feed(carol):
        print(f"  {post}")

    # 5. Job postings and applications
    job = JobPosting(
        title="Backend Engineer",
        company="BigTech Co",
        location="San Francisco",
        description="Work on large-scale backend systems.",
        employment_type=EmploymentType.FULL_TIME,
    )
    ln.add_job_posting(job)

    results = ln.search_jobs("backend")
    print(f"\n=== Job Search for 'backend' ===")
    for j in results:
        print(f"  {j}")

    bob.apply_to_job(job)
    print(f"\n=== Applicants for '{job.title}' ===")
    for applicant in job.applicants:
        print(f"  {applicant}")

    # 6. Search users
    print(f"\n=== User Search for 'alice' ===")
    for u in ln.search_users("alice"):
        print(f"  {u}")

    print("\nDone.")
