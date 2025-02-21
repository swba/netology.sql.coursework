from environs import env

import db
from model import Card, Collection, User
from schema import drop_tables, ensure_tables
from study_manager import StudyManager

def test_study_manager():
    # Load environment variables.
    env.read_env('.env.test')

    with db.connect() as commands:
        # Make sure there are empty tables in the DB.
        drop_tables(commands)
        ensure_tables(commands)

        sm = StudyManager(commands)

        # There are no cards in the DB yet.
        assert sm.card_exists('Test1') is False

        # Create a card without a collection.
        card1_id = sm.card_add('Test1', 'Тест1')
        assert sm.card_exists('Test1') is True

        # Load the card by its translation.
        assert sm.card_load_by_translation('Тест1') == Card(card1_id, 'Test1', 'Тест1')

        # Add a collection.
        cid = sm.collection_add('Тест')

        # There is one collection so far.
        assert sm.collection_list() == [Collection(cid, 'Тест')]

        # Add new cards to the collection.
        card2_id = sm.card_add('Test2', 'Тест2', cid)
        assert sm.card_load('Test2') == Card(id=card2_id, word='Test2', trans='Тест2')
        card3_id = sm.card_add('Test3', 'Тест3', cid)
        assert sm.card_load('Test3') == Card(id=card3_id, word='Test3', trans='Тест3')

        # Create a new user.
        uid1 = 1
        sm.user_ensure(uid1)
        # Calling this method again won't lead to an error.
        sm.user_ensure(uid1)

         # Now the user exists.
        user = sm.user_load(uid1)
        assert user == User(id=uid1, score=0, level=1)

        # The user doesn't have cards yet.
        assert sm.user_card_count(uid1) == 0

        # Import cards from the test collection.
        sm.collection_import(uid1, cid)

        # Now there are 2 cards in the user's dictionary.
        assert sm.user_card_count(uid1) == 2

        # Check cards existence.
        assert sm.user_card_exists(uid1, 'Test1') is False
        assert sm.user_card_exists(uid1, 'Test2') is True
        assert sm.user_card_exists(uid1, 'Test3') is True

        # Check that we can load user cards both by English word and
        # by its translation.
        assert sm.user_card_load(uid1, 'Test2').trans == 'Тест2'
        assert sm.user_card_load_by_translation(uid1, 'Тест2').word == 'Test2'

        # Add one more user card "manually".
        sm.user_card_add(uid1, 'Test4', 'Тест4')

        # And now the user has 3 cards.
        assert sm.user_card_count(uid1) == 3

        # Now delete the newly created user card.
        sm.user_card_delete(uid1, 'Test4')

        # Check it doesn't exist anymore.
        assert sm.user_card_exists(uid1, 'Test4') is False

        # But the common card still exists.
        assert sm.card_exists('Test4') is True

        # Add another user...
        uid2 = 2
        sm.user_ensure(uid2)
        # ...add it some cards...
        sm.user_card_add(uid2, 'Test2', 'Мой очень оригинальный перевод 2')
        sm.user_card_add(uid2, 'Test3', 'Мой очень оригинальный перевод 3')
        # ...check it worked...
        assert sm.user_card_count(uid2) == 2
        assert sm.user_card_load(uid2, 'Test2').trans == 'Мой очень оригинальный перевод 2'
        # ...and now delete all its cards.
        sm.user_card_delete_all(uid2)
        assert sm.user_card_count(uid2) == 0

        # But again make sure the underlying card is still here.
        assert sm.card_exists('Test2') is True

        # Ensure that both users cannot study because they have too
        # little cards.
        assert sm.user_can_study(uid1) is False
        assert sm.user_can_study(uid2) is False

        # Anyway, make the first user study.
        sm.user_card_study(uid1, 2, True)
        sm.user_card_study(uid1, 3, True)
        sm.user_card_study(uid1, 2, False)
        sm.user_card_study(uid1, 3, True)

        # Check the results.
        assert sm.user_card_load(uid1, 'Test2').score == 0
        assert sm.user_card_load(uid1, 'Test3').score == 2
        assert sm.user_load(uid1) == User(uid1, 3, 1)

        # Make the first user level-up.
        sm.user_card_study(uid1, 2, True)
        sm.user_card_study(uid1, 3, True)
        sm.user_card_study(uid1, 2, True)
        assert sm.user_load(uid1) == User(uid1, 6, 2)
