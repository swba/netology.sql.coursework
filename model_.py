from datetime import datetime
from typing import List

from sqlalchemy import (
    Column,
    Engine,
    ForeignKey,
    String,
    Table
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)


class User(Base):
    """User model"""

    __tablename__ = "user"

    cards: Mapped[List["UserCard"]] = relationship(
        back_populates = "user", cascade = "all, delete-orphan"
    )


card_collection = Table(
    "card_collection",
    Base.metadata,
    Column(
        "card_id",
        ForeignKey("card.id"),
        primary_key=True,
        nullable=False
    ),
    Column(
        "collection_id",
        ForeignKey("collection.id"),
        primary_key=True,
        nullable=False
    ),
)


class Collection(Base):
    """Card collection model"""

    __tablename__ = "collection"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    cards: Mapped[List["Card"]] = relationship(
        secondary=card_collection, back_populates="collections"
    )


class Card(Base):
    """Word card model"""

    __tablename__ = "card"

    word: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    translation: Mapped[str] = mapped_column(String(100), nullable=False)

    collections: Mapped[List["Collection"]] = relationship(
        secondary=card_collection, back_populates="cards"
    )

    def in_collection(self, collection: Collection) -> bool:
        """Checks if card is in collection

        Args:
            collection: Collection entity.
        """
        for c in self.collections:
            if c.id == collection.id:
                return True
        return False


class UserCard(Base):
    """User word card model"""

    __tablename__ = "user_card"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        primary_key=True,
        nullable=False
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("card.id"),
        primary_key=True,
        nullable = False
    )
    translation: Mapped[str] = mapped_column(String(100), nullable=False)
    last_study: Mapped[datetime] = mapped_column(DateTime, default=0)
    score: Mapped[int]

    user: Mapped["User"] = relationship(back_populates="cards")


def create_tables(engine: Engine):
    """Creates all model tables"""
    Base.metadata.create_all(engine)

def drop_tables(engine: Engine):
    """Drops all model tables"""
    Base.metadata.drop_all(engine)
