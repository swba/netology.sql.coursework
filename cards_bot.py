import json
import os
from random import choice, shuffle
import re
from typing import List

from telebot import custom_filters, TeleBot
from telebot.states import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
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
    study_choice = State()


class CardsBot:
    """Telegram bot wrapper"""

    def __init__(self):
        # Parse bot strings.
        with open(os.path.join(os.getcwd(), 'assets', 'bot_strings.json'), encoding='UTF-8') as file:
            self.strings = json.load(file)

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
        self.bot.message_handler(state=CardsBotStates.study_choice)(self.handle_study_choice)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)

        # Add custom filters.
        self.bot.add_custom_filter(custom_filters.StateFilter(self.bot))

        self.bot.infinity_polling()

    def handle_start(self, message: Message):
        """Handles "start" command"""
        with db.connect() as commands:
            sm = StudyManager(commands)

            uid = message.chat.id
            sm.user_ensure(uid)

            self.bot.send_message(uid, self.strings['messages']['start'])

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
        if re.fullmatch(r"[a-zA-Z' -]+", word) is None:
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
        uid = message.chat.id
        with db.connect() as commands:
            sm = StudyManager(commands)

            # Check if the user has enough cards in their dictionary.
            if sm.user_can_study(uid):
                # Get 4 random user cards.
                user_cards = sm.user_card_choices(uid)

                # Card to study.
                user_card = user_cards[0]

                # Choose whether we are going to show an English word
                # and ask to select its Russian translation, or vice
                # versa.
                if (lng := choice(['en', 'ru'])) == 'en':
                    buttons = [uc.trans for uc in user_cards]
                    word = user_card.word
                    answer = user_card.trans
                else:
                    buttons = [uc.word for uc in user_cards]
                    word = user_card.trans
                    answer = user_card.word

                # Add answers as reply buttons in random order.
                shuffle(buttons)

                self.bot.send_message(
                    uid,
                    self.strings['messages'][f'study_choice_{lng}'].format(
                        word=word
                    ),
                    reply_markup=self.reply_keyboard(buttons)
                )

                self.bot.set_state(uid, CardsBotStates.study_choice)
                self.bot.add_data(uid, cid=user_card.card_id, answer=answer)

            else:
                # Ask user to add more cards.
                self.bot.send_message(
                    uid,
                    self.strings['messages']['study_not_enough'],
                    reply_markup=self.inline_keyboard(['add_long', 'import'])
                )

    def handle_study_choice(self, message: Message):
        """Handles "choice translation" step of the "study" command"""
        uid = message.chat.id
        text = message.text
        with self.bot.retrieve_data(uid) as data:
            cid = data.get('cid')
            answer = data.get('answer')

        # Whether the user's choice is correct.
        if success := text.lower() == answer.lower():
            self.bot.send_message(
                uid,
                self.strings['messages']['study_success'],
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            self.bot.send_message(
                uid,
                self.strings['messages']['study_fail'].format(answer=answer),
                reply_markup=ReplyKeyboardRemove()
            )

        with db.connect() as commands:
            sm = StudyManager(commands)
            # Congratulate the user if they leveled up.
            if level := sm.user_card_study(uid, cid, success):
                self.bot.send_message(
                    uid,
                    self.strings['messages']['level_up'].format(level=level),
                    parse_mode='MarkdownV2'
                )

        self.bot.send_message(
            uid,
            self.strings['messages']['study_continue'],
            reply_markup=self.inline_keyboard(['study'])
        )

        # Clear bot's state and data on exit.
        self.bot.delete_state(uid)
        self.bot.reset_data(uid)

    def handle_callback_query(self, call: CallbackQuery):
        """Default callback query handler"""
        message = call.message
        uid = message.chat.id
        match call.data:
            case 'add' | 'add_long':
                self.handle_add(message)
            case 'delete':
                self.handle_delete(message)
            case 'import':
                self.handle_import(message)
            case 'list':
                self.handle_list(message)
            case 'study':
                self.handle_study(message)
            case _:
                # Import a collection.
                if call.data.startswith('import:'):
                    cid = int(call.data.split(':')[-1])
                    self.bot.set_state(uid, CardsBotStates.import_collection)
                    self.bot.add_data(uid, cid=cid)
                    self.handle_import_collection(message)

    def handle_stats(self, message: Message):
        """Handles "stats" command"""
        uid = message.chat.id
        with db.connect() as commands:
            sm = StudyManager(commands)
            user = sm.user_load(uid)

            self.bot.send_message(
                uid,
                self.strings['messages']['stats'].format(
                    level=user.level,
                    score=user.score
                ),
                parse_mode='MarkdownV2'
            )

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

    def reply_keyboard(self, names: List[str]):
        """Returns reply keyboard markup

        Args:
            names: The list of button names.
        """
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        for name in names:
            markup.add(self.reply_button(name))
        return markup
