from datetime import datetime
import json
import os
from typing import List, Optional
from time import time

from numpy.random import choice
from pydapper.commands import Commands
from pydapper.exceptions import NoResultException

from model import Card, Collection, User, UserCard


class StudyManager:
    """Methods to manage cards and users"""

    def __init__(self, commands: Commands):
        self.commands = commands


    def ensure_default_data(self):
        """Adds default cards and collections, if needed"""
        card_count = self.commands.execute_scalar("SELECT COUNT(*) FROM card")
        if card_count == 0:
            # Load all JSON files from the ./cards folder.
            input_folder = os.path.join(os.getcwd(), 'assets', 'cards')
            for filename in os.listdir(input_folder):
                if filename.endswith('.json'):
                    filepath = os.path.join(input_folder, filename)
                    with open(filepath, encoding='UTF-8') as file:
                        data = json.load(file)
                        # Add a new collection.
                        cid = self.collection_add(data['name'])
                        # Add new cards to the collection.
                        for item in data['words']:
                            self.card_add(
                                item['word'],
                                item['translation'],
                                cid
                            )


    def card_exists(self, word: str) -> bool:
        """Checks whether card exists

        Args:
            word: The card's underlying English word.
        """
        card_count = self.commands.execute_scalar(
            "SELECT COUNT(*) FROM card WHERE LOWER(word)=LOWER(?word?)",
            param={'word': word}
        )
        return card_count > 0

    def card_load(self, word: str) -> Optional[Card]:
        """Loads a card given its underlying English word

        Args:
            word: The card's underlying English word.
        """
        try:
            return self.commands.query_single(
                "SELECT * FROM card WHERE LOWER(word)=LOWER(?word?)",
                model=Card,
                param={'word': word}
            )
        except NoResultException:
            return None

    def card_add(self, word: str, trans: str, cid: int = None) -> int:
        """Adds a new card or updates the existing one

        Args:
            word: The underlying English word.
            trans: The corresponding Russian translation.
            cid: (optional) The ID of the collection the card belongs to.
        """
        if not self.card_exists(word):
            # Create a new card.
            card_id: int = self.commands.execute_scalar(
                "INSERT INTO card (word, trans) VALUES(?word?, ?trans?) RETURNING id",
                param={'word': word, 'trans': trans}
            )
            if cid:
                # Add it to the collection.
                self.commands.execute(
                    "INSERT INTO card_collection VALUES(?card_id?, ?cid?)",
                    param={'card_id': card_id, 'cid': cid}
                )
            return card_id
        else:
            card: Card = self.card_load(word)
            if trans not in card.trans:
                self.commands.execute(
                    "UPDATE card SET trans = ?trans? WHERE id = ?id?",
                    param={'trans': f'{card.trans}, {trans}', 'id': card.id}
                )
            # Add the card to a new collection, if needed.
            if cid:
                # Check if the card belongs to the collection.
                collection_count = self.commands.execute_scalar(
                    """
                    SELECT COUNT(*) FROM card_collection
                        WHERE card_id = ?card_id? AND collection_id = ?cid?
                    """,
                    param={'card_id': card.id, 'cid': cid}
                )
                if collection_count == 0:
                    # Add card to the collection.
                    self.commands.execute(
                        "INSERT INTO card_collection VALUES(?card_id?, ?cid?)",
                        param={'card_id': card.id, 'cid': cid}
                    )
            return card.id


    def collection_list(self) -> List[Collection]:
        """Loads list of collections"""
        return self.commands.query("SELECT * FROM collection", model=Collection)

    def collection_add(self, name: str) -> int:
        """Adds a new collection

        Args:
            name: The name of the collection.
        """
        return self.commands.execute_scalar(
            "INSERT INTO collection (name) VALUES(?name?) RETURNING id",
            param={'name': name}
        )

    def collection_import(self, uid: int, cid: int) -> int:
        """Adds all cards from a collection to the user's dictionary

        Args:
            uid: The ID of the user.
            cid: The ID of the collection.

        Returns:
            Number of added cards.
        """
        added = 0

        cards = self.commands.query(
            """
            SELECT c.* FROM card c
                JOIN card_collection cc ON c.id = cc.card_id
                WHERE cc.collection_id = ?cid?
            """,
            param={'cid': cid},
            model=Card
        )

        for card in cards:
            user_card_count = self.commands.execute_scalar(
                """
                SELECT COUNT(*) FROM user_card
                    WHERE user_id = ?uid? AND card_id = ?cid?
                """,
                param={'uid': uid, 'cid': card.id}
            )
            if user_card_count == 0:
                added += self.commands.execute(
                    """
                    INSERT INTO user_card (user_id, card_id, trans) 
                        VALUES(?user_id?, ?card_id?, ?trans?)
                    """,
                    param={
                        'user_id': uid,
                        'card_id': card.id,
                        'trans': card.trans
                    }
                )

        return added

    def user_load(self, uid: int) -> Optional[User]:
        """Loads a user given its ID

        Args:
            uid: The ID of the user.
        """
        try:
            return self.commands.query_single(
                "SELECT * FROM users WHERE id=?id?",
                model=User,
                param={'id': uid}
            )
        except NoResultException:
            return None

    def user_ensure(self, uid: int):
        """Creates a user, if needed

        Args:
            uid: The ID of the user.
        """
        params = {'id': uid}
        user_count = self.commands.execute_scalar(
            "SELECT COUNT(*) FROM users WHERE id=?id?",
            param=params
        )
        if user_count == 0:
            self.commands.execute(
                "INSERT INTO users (id) VALUES(?id?)",
                param=params
            )

    def user_card_count(self, uid: int) -> int:
        """Counts user cards

        Args:
            uid: The ID of the user.
        """
        return self.commands.execute_scalar(
            "SELECT COUNT(*) FROM user_card WHERE user_id=?uid?",
            param={'uid': uid}
        )

    def user_card_list(self, uid: int) -> List[UserCard]:
        """Loads all user cards

        Args:
            uid: The ID of the user.
        """
        return self.commands.query(
            """
            SELECT uc.*, c.word FROM user_card uc
                JOIN card c ON uc.card_id = c.id
                WHERE uc.user_id = ?uid?
                ORDER BY c.word
            """,
            model=UserCard,
            param={'uid': uid}
        )

    def user_card_exists(self, uid: int, word: str) -> Optional[UserCard]:
        """Checks whether user card exists

        Args:
            uid: The ID of the user.
            word: The card's underlying English word.
        """
        card_count = self.commands.execute_scalar(
            """
            SELECT COUNT(uc.*) FROM user_card uc
                JOIN card c ON uc.card_id = c.id
                WHERE uc.user_id = ?uid? AND LOWER(c.word) = LOWER(?word?)
            """,
            param={'uid': uid, 'word': word}
        )
        return card_count > 0

    def user_card_load(self, uid: int, word: str) -> Optional[UserCard]:
        """Loads a user card given its underlying English word

        Args:
            uid: The ID of the user.
            word: The card's underlying English word.
        """
        try:
            return self.commands.query_single(
                """
                SELECT uc.*, c.word FROM user_card uc
                    JOIN card c ON uc.card_id = c.id
                    WHERE uc.user_id = ?uid? AND LOWER(c.word) = LOWER(?word?)
                """,
                model=UserCard,
                param={'uid': uid, 'word': word}
            )
        except NoResultException:
            return None

    def user_card_add(self, uid: int, word: str = None, trans: str = None):
        """Adds a user card

        Args:
            uid: The ID of the user.
            word: The underlying English word.
            trans: The English word's translation.
        """
        # Add a new card, if needed.
        card_id = self.card_add(word, trans)
        # Create a new user card.
        self.commands.execute(
            """
            INSERT INTO user_card (user_id, card_id, trans) 
                VALUES(?user_id?, ?card_id?, ?trans?)
            """,
            param={'user_id': uid, 'card_id': card_id, 'trans': trans}
        )

    def user_card_delete(self, uid: int, word: str) -> int:
        """Deletes a user card

        Args:
            uid: The ID of the user.
            word: The underlying English word.
        """
        return self.commands.execute(
            """
            DELETE FROM user_card uc USING card c
                WHERE uc.card_id = c.id AND uc.user_id = ?uid? AND
                    LOWER(c.word) = LOWER(?word?)
            """,
            param={'uid': uid, 'word': word}
        )

    def user_card_delete_all(self, uid: int) -> int:
        """Deletes all user card

        Args:
            uid: The ID of the user.

        Returns:
            How many user cards were deleted.
        """
        return self.commands.execute(
            "DELETE FROM user_card WHERE user_id = ?uid?",
            param={'uid': uid}
        )

    def user_card_study(self, uid: int, cid: int, success: bool) -> Optional[int]:
        """Updates user card after it was studied

        Args:
            uid: The ID of the user.
            cid: The ID of the card.
            success: Whether the user's answer was correct.

        Returns:
            (optional) New user's level, if it increased.
        """
        now = datetime.now()

        # Update the user card that has been studied.
        user_card = self.commands.query_single(
            "SELECT * FROM user_card WHERE user_id = ?uid? AND card_id = ?cid?",
            model=UserCard,
            param={'uid': uid, 'cid': cid}
        )
        # Score cannot be negative, as it'd break card selection.
        score = max(0, user_card.score + (1 if success else -1))
        self.commands.execute(
            """
            UPDATE user_card SET score = ?score?, last_study = ?now? 
                WHERE user_id = ?uid? AND card_id = ?cid?
            """,
            param={'uid': uid, 'cid': cid, 'score': score, 'now': now.isoformat()}
        )

        # Update the user's stats.
        user = self.user_load(uid)
        # User's score cannot be negative and cannot decrease, as we
        # can't allow user's level lowering.
        score = user.score + (1 if success else 0)
        level = user.calc_level()
        self.commands.execute(
            "UPDATE users SET score = ?score?, level = ?level? WHERE id = ?uid?",
            param={'uid': uid, 'score': score, 'level': level}
        )

        if level > user.level:
            return level

    def user_card_choices(self, uid: int, k = 4) -> List[UserCard]:
        """Returns list of k user cards chosen randomly

        Args:
            uid: The ID of the user.
            k: (optional) How many user cards to return. Defaults to 4.
        """
        now = time()
        user_cards = self.user_card_list(uid)
        # User cards are being randomly chosen taking their weights
        # into account. Card's weight depends on its score and when it
        # was studied last time:
        # - The less card score, the larger its weight.
        # - The greater the time since the card was studied, the larger
        #   its weight.
        weights = [(now - uc.last_study.timestamp()) / 86400 / (uc.score + 1)
                   for uc in user_cards]
        weight_sum = sum(weights) or 1
        probs = [w / weight_sum for w in weights]
        return list(choice(user_cards, size=k, replace=False, p=probs))

    def user_can_study(self, uid: int) -> bool:
        """Checks if the user has enough cards to study

        Args:
            uid: The ID of the user.
        """
        return self.user_card_count(uid) > 4
