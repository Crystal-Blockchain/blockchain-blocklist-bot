from telegram.ext import ConversationHandler
from telegram import ReplyKeyboardRemove
from telegram.constants import MAX_MESSAGE_LENGTH
from config import *
import pandas as pd
import datetime
import tabulate
import logging
import inspect
import time
import io
import re


def sent_continue_message(update, context):
    time.sleep(2)
    command_description = ''
    for command in context.bot.commands:
        command_description += '/{} - {}\n'.format(command.command, command.description)

    reply = update.message.reply_text('To continue work please select the command:\n'
                                      '{}'.format(command_description),
                                      reply_markup=ReplyKeyboardRemove())

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return ConversationHandler.END


def bot_start(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    command_description = ''
    for command in context.bot.commands:
        command_description += '/{} - {}\n'.format(command.command, command.description)

    update.message.reply_text('Hello, {}!\n'
                              'I\'m the {} bot.\n\n'
                              'Here is the list of commands you can use:\n'
                              '{}'.format(update.effective_user.full_name,
                                          bot_name,
                                          command_description))


def about(update, context):
    reply = update.message.reply_text(bot_about,
                                      disable_web_page_preview=False,
                                      reply_markup=ReplyKeyboardRemove())

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    sent_continue_message(update, context)
    return ConversationHandler.END


def show_my_user_id(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    reply = update.message.reply_text('Here is you telegram user_id: <b>{}</b>\n'.format(update.effective_user.id),
                                      reply_markup=ReplyKeyboardRemove(),
                                      parse_mode='HTML')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    sent_continue_message(update, context)
    return ConversationHandler.END


def split_list(list_to_split, split_by):
    res_list = []
    for i in range(0, len(list_to_split), split_by):
        res_list.append(list_to_split[i: i + split_by])
    return res_list


def cancel(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    reply = update.message.reply_text('The conversation with bot was canceled.',
                                      reply_markup=ReplyKeyboardRemove())

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    sent_continue_message(update, context)
    return ConversationHandler.END


def fallback(update, context):
    return ConversationHandler.END


def finish_conversation(update, context):
    reply = update.message.reply_text('We\'ve finished for now, thank you!')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    sent_continue_message(update, context)
    return ConversationHandler.END


def log_this(update, function_name, reply=None):
    logger.info(
        '{} - {} - {}\n------\n{}\n------\n'.format(update.effective_user.full_name,
                                                    update.effective_user.id,
                                                    function_name,
                                                    reply.text if (not isinstance(reply, str) and reply is not None)
                                                    else reply if reply is not None else update.message.text))


def catch_error(update, context):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    update.message.reply_text('There was an error during processing.\n'
                              'The conversation was finished. You can try again or contact support.',
                              reply_markup=ReplyKeyboardRemove())

    context.bot.send_message(chat_id=error_message_receiver_telegram_user_id,
                             text='User {} (id {}) caught an error: {}'.format(update.effective_user.full_name,
                                                                               update.effective_user.id,
                                                                               context.error))
    sent_continue_message(update, context)
    return ConversationHandler.END


def notify(update, context, text, addresses=''):
    notification_receivers = pd.read_csv(notification_receivers_df_location_name)['telegram_user_id'].to_list()

    for notification_receiver in notification_receivers:
        notification_text = \
            text + addresses + \
            ((
                 '\n<b><a href="https://docs.google.com/spreadsheets/d/{}">Blocklist table</a></b>'
                 '\n<b><a href="https://drive.google.com/drive/folders/{}">Group attachments</a></b>'.format(
                     workbook_sheet_id, parent_attachments_folder_id)) if int(
                notification_receiver) > 0 else '')
        if len(notification_text) < MAX_MESSAGE_LENGTH:
            context.bot.send_message(chat_id=int(notification_receiver),
                                     text=notification_text,
                                     parse_mode='HTML',
                                     disable_web_page_preview=True)
        else:
            context.bot.send_message\
            (chat_id=int(notification_receiver),
             text=text +
                "The list of addresses is too long to send it in telegram message."
                "Please find it attached in txt." +
             ((
                  '\n<b><a href="https://docs.google.com/spreadsheets/d/{}">Blocklist table</a></b>'
                  '\n<b><a href="https://drive.google.com/drive/folders/{}">Group attachments</a></b>'.format(
                      workbook_sheet_id,
                      parent_attachments_folder_id)) if int(
                 notification_receiver) > 0 else ''),
             parse_mode='HTML',
             disable_web_page_preview=True)

            file_obj = io.BytesIO()
            file_obj.write(addresses.encode())
            file_obj.seek(0)
            file_obj.name = 'list_of_addresses.txt'
            context.bot.send_document(chat_id=notification_receiver, document=file_obj)

        log_this(update, inspect.currentframe().f_code.co_name, notification_text)


def check_user(update, context):
    allowed_users_df = context.bot_data['allowed_users_df']
    user_id = str(update.effective_user.id)
    nickname = str(update.effective_user.username)
    first_last_name = '{} {}'.format(update.effective_user.first_name, update.effective_user.last_name)

    if user_id in allowed_users_df['telegram_user_id'].to_list():
        if pd.isna(allowed_users_df.loc[allowed_users_df['telegram_user_id'] == user_id,
                                        'telegram_user_nickname'].values[0]):
            allowed_users_df.loc[allowed_users_df['telegram_user_id'] == user_id,
                                 'telegram_user_nickname'] = nickname
            allowed_users_df.loc[allowed_users_df['telegram_user_id'] == user_id,
                                 'telegram_user_name'] = first_last_name
            allowed_users_df.drop_duplicates(inplace=True)
            allowed_users_df.to_csv(allowed_users_df_location_name, index=False)

        return True

    elif nickname in allowed_users_df['telegram_user_nickname'].to_list():
        if (allowed_users_df.loc[allowed_users_df['telegram_user_nickname'] == nickname,
                                 'telegram_user_id'].values[0] == '') or pd.isna(
            allowed_users_df.loc[allowed_users_df['telegram_user_nickname'] == nickname,
                                 'telegram_user_id'].values[0]):
            allowed_users_df.loc[allowed_users_df['telegram_user_nickname'] == nickname,
                                 'telegram_user_id'] = user_id
            allowed_users_df.loc[allowed_users_df['telegram_user_id'] == user_id,
                                 'telegram_user_name'] = first_last_name
            allowed_users_df.drop_duplicates(inplace=True)
            allowed_users_df.to_csv(allowed_users_df_location_name, index=False)
        return True

    reply = update.message.reply_text(answer_to_forbidden_user,
                                      reply_markup=ReplyKeyboardRemove())
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return False


# set up the logging
logging.basicConfig(filename=logs_location, filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# do not log discovery_cache warning
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)
