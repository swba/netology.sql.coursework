import json
import os
import re
from typing import List

from telebot import custom_filters, TeleBot
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext
from telebot.storage import StateMemoryStorage
from telebot.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyParameters
)

import db
import schema
from study_manager import StudyManager


class CardsBotStates(StatesGroup):
    """Defines bot states"""
    add_word = State()
    add_trans = State()
    delete_word = State()
    import_collection = State()


class CardsBot:
    """Telegram bot wrapper"""

    def __init__(self):
        # Parse bot strings.
        with open(os.path.join(os.getcwd(), 'assets', 'bot_strings.json'), encoding='UTF-8') as file:
            self.strings = json.load(file)
        commands = self.strings['commands']

        # Create a bot.
        self.bot = TeleBot(
            os.getenv('TG_TOKEN'),
            state_storage=StateMemoryStorage(),
            use_class_middlewares=True
        )

    def launch(self):
        """Prepares the environment and starts the bot"""
        with db.connect() as commands:
            schema.ensure_tables(commands)
            StudyManager(commands).ensure_default_data()

        commands = self.strings['commands']

        # Set bot commands to be shown in the menu.
        self.bot.set_my_commands([
            BotCommand(command, commands[command]) for command in commands
        ])

        # Register bot callbacks.
        for command in commands:
            self.bot.message_handler(commands=[command])(getattr(self, f'handle_{command}'))
        self.bot.message_handler(state=CardsBotStates.add_word)(self.handle_add_word)
        self.bot.message_handler(state=CardsBotStates.add_trans)(self.handle_add_trans)
        self.bot.message_handler(state=CardsBotStates.delete_word)(self.handle_delete_word)
        self.bot.message_handler(state=CardsBotStates.import_collection)(self.handle_import_collection)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)

        # Add custom filters.
        self.bot.add_custom_filter(custom_filters.StateFilter(self.bot))

        self.bot.infinity_polling()

    def handle_start(self, message: Message):
        """Handles "start" command"""
        with db.connect() as commands:
            sm = StudyManager(commands)

            uid = message.from_user.id
            sm.user_ensure(uid)

            if sm.user_card_count(uid) == 0:
                markup = self.inline_keyboard(['add', 'import'])
                self.bot.send_message(
                    uid,
                    self.strings['messages']['start_no_cards'],
                    reply_markup=markup
                )

    def handle_manage(self, message: Message):
        """Handles "manage" command"""
        uid = message.chat.id
        with db.connect() as commands:
            sm = StudyManager(commands)
            card_count = sm.user_card_count(uid)
            self._manage_send_message(
                uid,
                self.strings['messages']['manage'].format(card_count=card_count),
                card_count
            )

    def handle_add(self, message: Message):
        """Handles "add word" command"""
        uid = message.chat.id
        self.bot.send_message(
            uid,
            self.strings['messages']['add_word'],
        )
        self.bot.set_state(uid, CardsBotStates.add_word)

    def handle_add_word(self, message: Message):
        """Handles "input word" step of the "add_word" command"""
        uid = message.chat.id
        word = message.text
        # A very basic check that the word is correct.
        if re.fullmatch(r'[a-zA-Z-]+', word) is None:
            self.bot.send_message(uid, self.strings['messages']['word_error'])
        else:
            with db.connect() as commands:
                sm = StudyManager(commands)
                # User card already exists.
                if user_card := sm.user_card_load(uid, word):
                    self.bot.send_message(
                        uid,
                        self.strings['messages']['user_card_exists'].format(
                            word=user_card.word
                        )
                    )
                # General card already exists.
                elif card := sm.card_load(word):
                    self.bot.send_message(
                        uid,
                        self.strings['messages']['card_exists'].format(
                            word=card.word,
                            trans=card.trans
                        ),
                        reply_markup=self.reply_keyboard([card.trans])
                    )
                    self.bot.set_state(uid, CardsBotStates.add_trans)
                    self.bot.add_data(uid, word=card.word)
                # A brand-new word is about te be added.
                else:
                    self.bot.send_message(
                        uid,
                        self.strings['messages']['add_trans']
                    )
                    self.bot.set_state(uid, CardsBotStates.add_trans)
                    self.bot.add_data(uid, word=word)

    def handle_add_trans(self, message: Message):
        """Handles "add translation" step of the "add_word" command"""
        uid = message.chat.id
        trans = message.text
        with self.bot.retrieve_data(uid) as data:
            word = data.get('word')

        # Do add the user card to the database.
        with db.connect() as commands:
            sm = StudyManager(commands)
            sm.user_card_add(uid, word, trans)
            card_count = sm.user_card_count(uid)

        self.bot.send_message(
            uid,
            self.strings['messages']['user_card_added'].format(
                word=word,
                trans=message.text,
                card_count=card_count
            ),
            reply_markup=ReplyKeyboardRemove()
        )

        self._manage_send_message(
            uid,
            self.strings['messages']['manage'].format(card_count=card_count),
            card_count
        )

        # Clear bot's state and data on exit.
        self.bot.delete_state(uid)
        self.bot.reset_data(uid)

    def handle_delete(self, message: Message):
        """Handles "delete word" step/command"""
        uid = message.chat.id
        self.bot.send_message(
            uid,
            self.strings['messages']['delete_word'],
        )
        self.bot.set_state(uid, CardsBotStates.delete_word)

    def handle_delete_word(self, message: Message):
        """Handles "input word" step of the "delete word" command"""
        uid = message.chat.id
        word = message.text

        with db.connect() as commands:
            sm = StudyManager(commands)

            # Delete all user cards.
            if word == 'ALL':
                sm.user_card_delete_all(uid)

                self.bot.send_message(
                    uid,
                    self.strings['messages']['user_card_deleted_all']
                )

                self._manage_send_message(
                    uid,
                    self.strings['messages']['manage'].format(
                        card_count=0
                    ),
                    0
                )

                # Clear bot's state on exit.
                self.bot.delete_state(uid)

            # Delete a single card.
            elif sm.user_card_exists(uid, word):
                # Do remove the user card to the database.
                sm.user_card_delete(uid, word)
                card_count = sm.user_card_count(uid)

                self.bot.send_message(
                    uid,
                    self.strings['messages']['user_card_deleted'].format(
                        word=word,
                        card_count=card_count
                    )
                )

                self._manage_send_message(
                    uid,
                    self.strings['messages']['manage'].format(
                        card_count=card_count
                    ),
                    card_count
                )

                # Clear bot's state on exit.
                self.bot.delete_state(uid)
            else:
                self.bot.send_message(
                    uid,
                    self.strings['messages']['user_card_missing'].format(
                        word=word
                    )
                )

    def handle_list(self, message: Message):
        """Handles "list words" command"""
        uid = message.chat.id
        with db.connect() as commands:
            sm = StudyManager(commands)
            user_cards = sm.user_card_list(uid)

        self._manage_send_message(
            uid,
            '\n'.join(f'{uc.word} — {uc.trans}' for uc in user_cards),
            len(user_cards)
        )

    def handle_import(self, message: Message):
        """Handles "import" command"""
        markup = InlineKeyboardMarkup()

        with db.connect() as commands:
            sm = StudyManager(commands)
            # Make inline buttons for all collections.
            for collection in sm.collection_list():
                button = InlineKeyboardButton(
                    collection.name,
                    callback_data=f'import:{collection.id}'
                )
                markup.add(button)

        self.bot.send_message(
            message.chat.id,
            self.strings['messages']['import'],
            reply_markup=markup
        )

    def handle_import_collection(self, message: Message):
        """Handles "import collection" step of the "import" command"""
        uid = message.chat.id
        with self.bot.retrieve_data(uid) as data:
            cid = data.get('cid')

        with db.connect() as commands:
            sm = StudyManager(commands)
            added_count = sm.collection_import(uid, cid)
            card_count = sm.user_card_count(uid)

        self._manage_send_message(
            uid,
            self.strings['messages']['user_cards_imported'].format(
                added_count=added_count,
                card_count=card_count
            ),
            card_count
        )

        # Clear bot's state and data on exit.
        self.bot.delete_state(uid)
        self.bot.reset_data(uid)

    def _manage_send_message(self, uid: int, text: str, card_count: int):
        """Sends a message while in the /manage context

        Args:
            uid: The ID of the user.
            text: The text to send.
            card_count: How many cards the user has.
        """
        # Manage user's dictionary with inline buttons.
        buttons = [['add', 'delete'], 'import']

        # Card listing only makes sense if the user has at least
        # one card.
        if card_count > 0:
            buttons.append('list')

        markup = self.inline_keyboard(buttons)
        self.bot.send_message(uid, text, reply_markup=markup)

    def handle_study(self, message: Message):
        """Handles /study command"""
        pass

    def handle_callback_query(self, call: CallbackQuery):
        """Default callback query handler"""
        message = call.message
        uid = message.chat.id
        match call.data:
            case 'add':
                self.handle_add(message)
            case 'delete':
                self.handle_delete(message)
            case 'import':
                self.handle_import(message)
            case 'list':
                self.handle_list(message)
            case _:
                # Import a collection.
                if call.data.startswith('import:'):
                    cid = int(call.data.split(':')[-1])
                    self.bot.set_state(uid, CardsBotStates.import_collection)
                    self.bot.add_data(uid, cid=cid)
                    self.handle_import_collection(message)

    def inline_button(self, name: str):
        """Returns inline keyboard button

        Args:
            name: The button name.
        """
        return InlineKeyboardButton(
            self.strings['buttons'][name],
            callback_data=name
        )

    def inline_keyboard(self, names: List[str | List[str]]):
        """Returns inline keyboard markup

        Args:
            names: The list of button names. Each internal list
                represents a markup row.
        """
        markup = InlineKeyboardMarkup()
        for name in names:
            if type(name) == str:
                markup.add(self.inline_button(name))
            else:
                markup.add(*map(self.inline_button, name))
        return markup

    @staticmethod
    def reply_button(text: str):
        """Returns reply keyboard button

        Args:
            text: The text on the button.
        """
        return KeyboardButton(text)

    def reply_keyboard(self, buttons: List[str]):
        """Returns reply keyboard markup

        Args:
            buttons: The list of button names.
        """
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(*map(self.reply_button, buttons))
        return markup
