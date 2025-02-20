from datetime import datetime
from dataclasses import dataclass
from math import log2


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

    def calc_level(self) -> int:
        """Calculates user's level based on their score"""
        # The higher the level, the more additional points it takes to
        # increase it.
        # Score distribution per level:
        # lvl 1: 0-4
        # lvl 2: 5-9
        # lvl 3: 10-18
        # lvl 4: 19-29
        # lvl 5: 30-46
        # lvl 6: 47-69
        # lvl 7: 70-103
        # lvl 8: 104-149
        # lvl 9: 150-216
        # etc.
        return int(2 * log2(self.score / 10 + 1) + 1)


@dataclass
class UserCard:
    """A user card model"""
    user_id: int
    card_id: int
    trans: str
    last_study: datetime = datetime.now
    score: int = 0
    # Fields not in the `user_card` table.
    word: str = None
