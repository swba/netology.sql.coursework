from pydapper.commands import Commands

def ensure_tables(commands: Commands):
    """Safely creates the project's tables"""

    # A card is just a pair of a unique English `word` and a
    # default Russian `translation`.
    commands.execute("""
        CREATE TABLE IF NOT EXISTS card (
            id SERIAL PRIMARY KEY,
            word VARCHAR(100) NOT NULL UNIQUE,
            trans VARCHAR(100) NOT NULL);
        """)

    # A collection is just a group of cards with unique name.
    commands.execute("""
        CREATE TABLE IF NOT EXISTS collection (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE);
        """)

    # A many-to-many card-collection relationship.
    commands.execute("""
        CREATE TABLE IF NOT EXISTS card_collection (
            card_id INTEGER NOT NULL REFERENCES card(id) ON DELETE CASCADE,
            collection_id INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
            CONSTRAINT card_collection_pkey PRIMARY KEY (card_id, collection_id));
        """)

    # The user table. ID is not of serial type, because we are going to
    # save user IDs provided by Telegram, which are already unique.
    # Having a table with just entity ID would make little to no sense,
    # so we add some additional fields.
    commands.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER NOT NULL PRIMARY KEY,
            score INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 0);
        """)

    # A user card is a many-to-many user-card relationship, which
    # additionally keeps some study statistics and also a word
    # translation, which can be unique for a user.
    commands.execute("""
        CREATE TABLE IF NOT EXISTS user_card (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_id INTEGER NOT NULL REFERENCES card(id) ON DELETE CASCADE,
            trans VARCHAR(100) NOT NULL,
            last_study TIMESTAMP DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT user_card_pkey PRIMARY KEY (user_id, card_id));
        """)

def drop_tables(commands: Commands):
    """Drops the project's tables"""
    commands.execute("""
        DROP TABLE IF EXISTS card;
        DROP TABLE IF EXISTS collection;
        DROP TABLE IF EXISTS card_collection;
        DROP TABLE IF EXISTS user;
        DROP TABLE IF EXISTS user_card;
        """)
