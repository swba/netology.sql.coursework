import json
import os
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from db_ import Db
import model_


class StudyManager:
    """Manages users and cards"""

    def __init__(self):
        self.engine = Db().get_engine()

    def setup(self):
        """Creates tables in the database and adds default data"""
        # Add tables, if they don't exist yet.
        model.create_tables(self.engine)
        # Add card collections if they aren't added yet.
        if self.count_cards() == 0:
            # Load all JSON files from the ./cards folder.
            input_folder = os.path.join(os.getcwd(), 'assets', 'cards')
            for filename in os.listdir(input_folder):
                if filename.endswith('.json'):
                    filepath = os.path.join(input_folder, filename)
                    with open(filepath, encoding='UTF-8') as file:
                        data = json.load(file)
                        # Add a new collection.
                        collection = self.add_collection(data['name'])
                        # Add new words to the collection.
                        for item in data['words']:
                            self.add_card(
                                item['word'],
                                item['translation'],
                                collection
                            )

    def ensure_user(self, uid: int) -> model.User:
        """Checks if user with given ID exists and creates it if needed

        Args:
            uid: User ID.
        """
        with Session(self.engine) as session:
            # Try to select existing user.
            stmt = select(model.User).where(model.User.id == uid)
            user = session.scalar(stmt)
            # Create a new user, if no user found.
            if not user:
                user = model.User(id=uid)
                session.add(user)
                session.commit()
            return user

    def add_collection(self, name: str) -> model.Collection:
        """Adds card collection entity

        Args:
            name: Card collection name.
        """
        with Session(self.engine, expire_on_commit=False) as session:
            collection = model.Collection(name=name)
            session.add(collection)
            session.commit()
        return collection

    def count_cards(self) -> int:
        """Returns total count of cards int the database"""
        with Session(self.engine) as session:
            return session.query(model.Card).count()

    def add_card(
            self,
            word: str,
            translation: str,
            collection: model.Collection = None,
            append: bool = False
    ) -> model.Card:
        """Adds a new card

        Args:
            word: English word.
            translation: Russian translation.
            collection: (optional) Collection card belongs to.
            append: (optional) Whether to append card's translation.
        """
        card = self.get_card(word)
        with Session(self.engine) as session:
            if not card:
                # Create a new card.
                card = model.Card(word=word, translation=translation)
                session.add(card)
            elif append and translation not in card.translation:
                # Append translation of an existing card.
                card.translation += f', {translation}'
            # Add card to the collection, if needed.
            if collection and not card.in_collection(collection):
                card.collections.append(collection)
            session.commit()
        return card

    def get_card(self, word: str) -> model.Card:
        """Returns card given a corresponding English word

        Args:
            word: English word to get card for.
        """
        with Session(self.engine) as session:
            stmt = (
                select(model.Card)
                .where(func.lower(model.Card.word) == word.lower())
                .options(joinedload(model.Card.collections))
            )
            return session.scalar(stmt)

    def get_user_card(self, word: str, uid: int) -> model.UserCard or None:
        """Returns user card given a corresponding English word

        Args:
            word: English word.
            uid: ID of user who owns a card.
        """
        with Session(self.engine) as session:
            stmt = (
                select(model.UserCard)
                .where(model.User.id == uid)
                .where(func.lower(model.Card.word) == word.lower())
            )
            return session.scalar(stmt)

    def get_user_cards(self, user_id: int) -> List[model.UserCard]:
        """Loads user cards given their external ID

        Args:
            user_id: User's external ID.
        """
        with Session(self.engine) as session:
            stmt = (
                select(model.User)
                .where(model.User.id == user_id)
                .options(joinedload(model.User.cards))
            )
            return session.scalars(stmt).one()
