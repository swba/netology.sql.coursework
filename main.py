from environs import env

from cards_bot import CardsBot

if __name__ == "__main__":
    # Read environment variables.
    env.read_env()

    # Start the Cards telebot.
    CardsBot().launch()