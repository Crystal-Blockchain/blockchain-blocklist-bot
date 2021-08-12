import numpy
from telegram.ext import Updater, CommandHandler
from src.command.add_addresses import add_address_conv
from src.command.add_attachments import add_attachments_conv
from src.command.show_addresses import show_addresses_conv
from src.command.show_group_description import show_description_conv
from src.utils import catch_error, bot_start, about, show_my_user_id
from src.command.check_addresses import check_addresses_conv
from src.command.remove_addresses import remove_addresses_conv
from src.command.admin import admin_conv
from config import *
import pandas as pd


def start_bot():
    updater = Updater(telegram_bot_token, use_context=True)
    dp = updater.dispatcher  # dp - dispatcher to register handlers
    allowed_users_df = pd.read_csv(allowed_users_df_location_name)
    allowed_users_df['telegram_user_id'] = allowed_users_df.apply(
        lambda x: numpy.nan if pd.isna(x['telegram_user_id']) else str(int(x['telegram_user_id'])), axis=1)
    dp.bot_data['allowed_users_df'] = allowed_users_df

    # setting each handler to separate group to correctly end the conversation while executing another command
    dp.add_handler(CommandHandler('start', bot_start), 1)
    dp.add_handler(CommandHandler('about', about), 2)
    dp.add_handler(CommandHandler('show_me_my_user_id', show_my_user_id), 3)

    dp.add_handler(admin_conv, 4)
    dp.add_handler(check_addresses_conv, 5)
    dp.add_handler(add_address_conv, 6)
    dp.add_handler(add_attachments_conv, 7)
    dp.add_handler(show_addresses_conv, 8)
    dp.add_handler(show_description_conv, 9)
    dp.add_handler(remove_addresses_conv, 10)

    dp.add_error_handler(catch_error)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    print('Starting the bot')
    start_bot()
    print('\nBye')
