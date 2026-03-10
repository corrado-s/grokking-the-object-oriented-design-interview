"""
Design Facebook (Social Network) -- Interview-Feasible Solution

Assumptions / Reduced Scope:
    - Single-process, in-memory system (no database, no distributed concerns).
    - Users are identified by a unique user_id string.
    - No authentication, no account status lifecycle (active/disabled/etc.).
    - No media attachments -- posts and comments are text-only.

Main Use Cases Implemented:
    1. Create a user with a basic profile (name, bio, work experience).
    2. Send, accept, and reject friend requests (full lifecycle).
    3. Create posts.
    4. Comment on posts.
    5. Generate a chronological news feed (posts from friends, newest first).

What Was Left Out:
    - Full Account / Person / Admin hierarchy and account status management.
    - Pages, Groups, and Recommendations.
    - Search system (SearchIndex).
    - Messaging between users.
    - Notifications (push / email).
    - Privacy lists and visibility controls.
    - Media handling (photos, videos).
    - Like / share counters and actions.
    - Connection-suggestion algorithm (BFS-based).
    - Follow (without friending) semantics.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FriendRequestStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class Profile:
    """Lightweight profile attached to every user."""

    def __init__(self, bio: str = "", work_experiences: Optional[list[str]] = None):
        self.bio = bio
        self.work_experiences: list[str] = work_experiences or []

    def add_work_experience(self, experience: str) -> None:
        self.work_experiences.append(experience)

    def __repr__(self) -> str:
        return f"Profile(bio={self.bio!r}, work={self.work_experiences})"


# ---------------------------------------------------------------------------
# FriendRequest
# ---------------------------------------------------------------------------

class FriendRequest:
    """
    Represents a directional friend request from one user to another.
    Lifecycle: PENDING -> ACCEPTED | REJECTED
    """

    def __init__(self, from_user: User, to_user: User):
        self.request_id: str = str(uuid.uuid4())[:8]
        self.from_user = from_user
        self.to_user = to_user
        self.status: FriendRequestStatus = FriendRequestStatus.PENDING
        self.created_at: datetime = datetime.now()

    def accept(self) -> None:
        if self.status != FriendRequestStatus.PENDING:
            raise ValueError(f"Cannot accept a request that is {self.status.value}")
        self.status = FriendRequestStatus.ACCEPTED
        # Friendship is mutual: add each user to the other's friend list.
        self.from_user._friends.add(self.to_user.user_id)
        self.to_user._friends.add(self.from_user.user_id)

    def reject(self) -> None:
        if self.status != FriendRequestStatus.PENDING:
            raise ValueError(f"Cannot reject a request that is {self.status.value}")
        self.status = FriendRequestStatus.REJECTED

    def __repr__(self) -> str:
        return (
            f"FriendRequest({self.from_user.user_id} -> "
            f"{self.to_user.user_id}, {self.status.value})"
        )


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class Post:
    """A text post created by a user."""

    def __init__(self, author: User, text: str):
        self.post_id: str = str(uuid.uuid4())[:8]
        self.author = author
        self.text = text
        self.created_at: datetime = datetime.now()
        self.comments: list[Comment] = []

    def add_comment(self, author: User, text: str) -> Comment:
        comment = Comment(author=author, text=text, post=self)
        self.comments.append(comment)
        return comment

    def __repr__(self) -> str:
        return (
            f"Post(id={self.post_id}, author={self.author.user_id}, "
            f"text={self.text!r}, comments={len(self.comments)})"
        )


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class Comment:
    """A comment on a post."""

    def __init__(self, author: User, text: str, post: Post):
        self.comment_id: str = str(uuid.uuid4())[:8]
        self.author = author
        self.text = text
        self.post = post
        self.created_at: datetime = datetime.now()

    def __repr__(self) -> str:
        return (
            f"Comment(id={self.comment_id}, author={self.author.user_id}, "
            f"text={self.text!r})"
        )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User:
    """Core user entity.  Owns a profile, friend list, posts, and requests."""

    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.profile = Profile()
        self.posts: list[Post] = []
        self._friends: set[str] = set()  # set of user_id strings
        self._sent_requests: list[FriendRequest] = []
        self._received_requests: list[FriendRequest] = []

    # -- Profile helpers -----------------------------------------------------

    def update_profile(self, bio: str = "", work_experiences: Optional[list[str]] = None) -> None:
        self.profile.bio = bio
        if work_experiences:
            self.profile.work_experiences = work_experiences

    # -- Friend-request workflow --------------------------------------------

    def send_friend_request(self, other: User) -> FriendRequest:
        if other.user_id == self.user_id:
            raise ValueError("Cannot send a friend request to yourself")
        if other.user_id in self._friends:
            raise ValueError(f"Already friends with {other.user_id}")
        request = FriendRequest(from_user=self, to_user=other)
        self._sent_requests.append(request)
        other._received_requests.append(request)
        return request

    def get_pending_requests(self) -> list[FriendRequest]:
        return [r for r in self._received_requests
                if r.status == FriendRequestStatus.PENDING]

    def get_friends(self) -> set[str]:
        return set(self._friends)

    # -- Post creation -------------------------------------------------------

    def create_post(self, text: str) -> Post:
        post = Post(author=self, text=text)
        self.posts.append(post)
        return post

    def __repr__(self) -> str:
        return f"User(id={self.user_id}, name={self.name!r})"


# ---------------------------------------------------------------------------
# NewsFeed
# ---------------------------------------------------------------------------

class NewsFeed:
    """
    Generates a chronological feed for a user.
    Strategy: collect all posts authored by friends, sort newest-first.
    """

    def __init__(self, social_network: SocialNetwork):
        self._network = social_network

    def generate(self, user_id: str, limit: int = 10) -> list[Post]:
        user = self._network.get_user(user_id)
        friend_posts: list[Post] = []
        for friend_id in user.get_friends():
            friend = self._network.get_user(friend_id)
            friend_posts.extend(friend.posts)
        # Most-recent first
        friend_posts.sort(key=lambda p: p.created_at, reverse=True)
        return friend_posts[:limit]


# ---------------------------------------------------------------------------
# SocialNetwork  (top-level service / facade)
# ---------------------------------------------------------------------------

class SocialNetwork:
    """Facade that ties together users, requests, and the news feed."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self.news_feed = NewsFeed(self)

    # -- User management -----------------------------------------------------

    def create_user(self, user_id: str, name: str) -> User:
        if user_id in self._users:
            raise ValueError(f"User {user_id!r} already exists")
        user = User(user_id=user_id, name=name)
        self._users[user_id] = user
        return user

    def get_user(self, user_id: str) -> User:
        if user_id not in self._users:
            raise KeyError(f"User {user_id!r} not found")
        return self._users[user_id]

    # -- Convenience wrappers ------------------------------------------------

    def send_friend_request(self, from_id: str, to_id: str) -> FriendRequest:
        return self.get_user(from_id).send_friend_request(self.get_user(to_id))

    def get_news_feed(self, user_id: str, limit: int = 10) -> list[Post]:
        return self.news_feed.generate(user_id, limit)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fb = SocialNetwork()

    # 1. Create users and set up profiles
    alice = fb.create_user("alice", "Alice Johnson")
    alice.update_profile(bio="Software Engineer", work_experiences=["Meta", "Google"])

    bob = fb.create_user("bob", "Bob Smith")
    bob.update_profile(bio="Product Manager", work_experiences=["Amazon"])

    charlie = fb.create_user("charlie", "Charlie Lee")
    charlie.update_profile(bio="Designer")

    print("=== Profiles ===")
    for u in [alice, bob, charlie]:
        print(f"  {u} -> {u.profile}")

    # 2. Friend-request lifecycle
    req1 = fb.send_friend_request("alice", "bob")
    req2 = fb.send_friend_request("alice", "charlie")
    print(f"\n=== Friend Requests ===")
    print(f"  {req1}")
    print(f"  {req2}")

    # Bob accepts; Charlie rejects
    req1.accept()
    req2.reject()
    print(f"\nAfter responses:")
    print(f"  {req1}")
    print(f"  {req2}")
    print(f"  Alice's friends: {alice.get_friends()}")
    print(f"  Bob's friends:   {bob.get_friends()}")

    # 3. Create posts
    p1 = alice.create_post("Hello world! This is my first post.")
    p2 = bob.create_post("Excited to join the platform!")
    p3 = alice.create_post("Working on a new feature today.")
    print(f"\n=== Posts ===")
    for p in [p1, p2, p3]:
        print(f"  {p}")

    # 4. Comment on a post
    c1 = p1.add_comment(bob, "Welcome, Alice!")
    c2 = p2.add_comment(alice, "Glad to have you, Bob!")
    print(f"\n=== Comments ===")
    print(f"  On '{p1.text}': {p1.comments}")
    print(f"  On '{p2.text}': {p2.comments}")

    # 5. News feed -- Bob sees Alice's posts (they are friends)
    feed = fb.get_news_feed("bob")
    print(f"\n=== Bob's News Feed ===")
    for post in feed:
        print(f"  [{post.author.name}] {post.text}")

    # Charlie is NOT Alice's friend, so Charlie's feed is empty
    feed_charlie = fb.get_news_feed("charlie")
    print(f"\n=== Charlie's News Feed ===")
    print(f"  (empty)" if not feed_charlie else feed_charlie)
