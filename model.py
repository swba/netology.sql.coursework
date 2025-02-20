import datetime
from dataclasses import dataclass


@dataclass
class Card:
    """A card model"""
    id: int
    word: str
    trans: str


@dataclass
class Collection:
    """A collection model"""
    id: int
    name: str


@dataclass
class User:
    """A user model"""
    id: int
    score: int = 0
    level: int = 0


@dataclass
class UserCard:
    """A user card model"""
    user_id: int
    card_id: int
    trans: str
    last_study: datetime.datetime = 0
    score: int = 0
    # Fields not in the `user_card` table.
    word: str = None
