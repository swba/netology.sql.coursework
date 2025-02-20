from os import getenv

from telebot import types, TeleBot

from study_manager_ import StudyManager


class TgBot:
    """Telegram bot wrapper"""

    def __init__(self):
        self.study_manager = StudyManager()
        self.bot = TeleBot(getenv('TG_TOKEN'))

        # Register callbacks for the bot commands.
        self.bot.message_handler(commands=['start'])(self.command_start)

    def start(self):
        """Prepares the environment and starts the bot"""
        self.study_manager.setup()
        self.bot.infinity_polling()

    def command_start(self, message: types.Message):
        """Handles /start command"""
        print(message.__dict__)
        print(message.chat.__dict__)
        print(message.from_user.__dict__)
        user = self.study_manager.ensure_user(message.from_user.id)
        print(user)
        self.bot.reply_to(message, 'Hello there!')
