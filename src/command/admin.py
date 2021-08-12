from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup

from src.google.sheets_functions import *
from src.utils import *
import numpy

CHECK_PASSWORD, SELECT_MAIN_MENU_OPTION, SELECT_ADMIN_ALLOWED_USERS_MENU_OPTION, GET_ALLOWED_USERS_ID_NICKNAME, \
    SELECT_ADMIN_NOTIFICATION_MENU_OPTION, GET_RECEIVER_ID, GET_RECEIVER_COMMENT = range(7)


def start_admin(update, context):
    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    context.user_data[user_id].update({'notification_receivers_df': None,
                                       'receiver_id': 0,
                                       'receiver_comment': None})

    log_this(update, inspect.currentframe().f_code.co_name)
    return CHECK_PASSWORD


def silent_end(update, context):
    log_this(update, inspect.currentframe().f_code.co_name)
    return ConversationHandler.END


def send_admin_menu(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END
    keyboard = ReplyKeyboardMarkup(
        [['Export the whole table', 'Allowed users settings', 'Notification receivers settings']],
        one_time_keyboard=True)
    reply = update.message.reply_text('Select the action you want to process:',
                                      reply_markup=keyboard)
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_MAIN_MENU_OPTION


def export_csv(update, context, ws_df, csv_name):
    file_obj = io.BytesIO()
    file_obj.write(ws_df.to_csv(index=False).encode())
    file_obj.seek(0)

    file_obj.name = '{}.csv'.format(csv_name)

    context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)
    reply = file_obj.name

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def export_csv_all_addresses(update, context):
    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()

    file_obj = io.BytesIO()
    file_obj.write(ws_df.to_csv(index=False).encode())
    file_obj.seek(0)

    file_obj.name = 'reported_addresses_{}.csv'.format(datetime.datetime.utcnow().strftime('%Y-%m-%d_%H-%M'))

    context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)
    reply = file_obj.name

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def send_allowed_users_menu(update, context):
    context.bot_data['allowed_users_df'] = pd.read_csv(allowed_users_df_location_name)

    df = context.bot_data['allowed_users_df']
    df['telegram_user_id'] = df.apply(
        lambda x: numpy.nan if pd.isna(x['telegram_user_id']) else str(int(x['telegram_user_id'])), axis=1)

    keyboard = ReplyKeyboardMarkup([['Add allowed user', 'Remove allowed user']],
                                   one_time_keyboard=True)
    reply_text = 'Here is the list of allowed users:\n' \
                 '<pre>{}</pre>'.format(tabulate.tabulate(df, headers='keys', tablefmt='simple', disable_numparse=True))

    if len(reply_text) < MAX_MESSAGE_LENGTH:
        reply = update.message.reply_text(reply_text,
                                          parse_mode='HTML',
                                          reply_markup=keyboard)
    else:
        reply = update.message.reply_text('Here is the list of allowed users.\n'
                                          'The Telegram message length limit is exceeded, check the csv file.',
                                          parse_mode='HTML',
                                          reply_markup=keyboard)
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        export_csv(update, context, df, 'allowed_users')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_ADMIN_ALLOWED_USERS_MENU_OPTION


def ask_allowed_user_id_nickname(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    add_remove = text.split()[0].lower()
    context.user_data[user_id]['add_remove_allowed'] = add_remove

    reply = update.message.reply_text('Please send me telegram_user_id or '
                                      'telegram_nickname(without @) you want to {}'.format(add_remove),
                                      reply_markup=ReplyKeyboardRemove())
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_ALLOWED_USERS_ID_NICKNAME


def get_allowed_user_id_nickname(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    context.user_data[user_id]['allowed_user_id_nickname'] = text
    log_this(update, inspect.currentframe().f_code.co_name)
    if context.user_data[user_id]['add_remove_allowed'] == 'add':
        return add_allowed_user(update, context)
    else:
        return remove_allowed_user(update, context)


def add_allowed_user(update, context):
    user_id = update.effective_user.id
    allowed_users_df = context.bot_data['allowed_users_df']
    allowed_user_id_nickname = context.user_data[user_id]['allowed_user_id_nickname']

    try:
        int(allowed_user_id_nickname)
        id_nickname = 'id'
    except ValueError:
        id_nickname = 'nickname'

    already_present = False

    if id_nickname == 'id':
        if allowed_user_id_nickname in allowed_users_df['telegram_user_id'].to_list():
            already_present = True
    else:
        if allowed_user_id_nickname in allowed_users_df['telegram_user_nickname'].to_list():
            already_present = True

    if not already_present:
        allowed_users_df = allowed_users_df.append(
            {'telegram_user_id': allowed_user_id_nickname if id_nickname == 'id' else '',
             'telegram_user_nickname': allowed_user_id_nickname if id_nickname == 'nickname' else '', },
            ignore_index=True)
    else:
        reply = update.message.reply_text('User with {} {} is alraedy present in allowed users list.'.
                                          format(id_nickname, allowed_user_id_nickname,
                                                 parse_mode='HTML'))
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return finish_conversation(update, context)

    allowed_users_df.reset_index(drop=True, inplace=True)
    allowed_users_df.index += 1

    context.bot_data['allowed_users_df'] = allowed_users_df
    allowed_users_df.to_csv(allowed_users_df_location_name, index=False)

    reply = update.message.reply_text('User with {} {} was added to allowed users list.'.
                                      format(id_nickname, allowed_user_id_nickname,
                                             parse_mode='HTML'))
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def remove_allowed_user(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    allowed_users_df = context.bot_data['allowed_users_df']
    allowed_user_id_nickname = context.user_data[user_id]['allowed_user_id_nickname']

    try:
        int(allowed_user_id_nickname)
        id_nickname = 'id'
    except ValueError:
        id_nickname = 'nickname'

    allowed_users_df = allowed_users_df[
        allowed_users_df['telegram_user_{}'.format(id_nickname)] != allowed_user_id_nickname]

    allowed_users_df.reset_index(drop=True, inplace=True)
    allowed_users_df.index += 1

    context.bot_data['allowed_users_df'] = allowed_users_df
    allowed_users_df.to_csv(allowed_users_df_location_name, index=False)

    reply = update.message.reply_text('User with {} {} was removed from allowed users list.'.
                                      format(id_nickname, allowed_user_id_nickname,
                                             parse_mode='HTML'))
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def ask_notification_receiver_id(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    add_remove = text.split()[0].lower()
    context.user_data[user_id]['add_remove_receiver'] = add_remove

    reply = update.message.reply_text('Please send me user_id '
                                      'of the telegram account you want to {} as notification receiver.\n\n'
                                      'If you don\'t know the user_id of the telegram account, '
                                      'please ask him to execute /show_me_my_user_id command in the bot '
                                      'and share the result with you.'.format(add_remove),
                                      reply_markup=ReplyKeyboardRemove())
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_RECEIVER_ID


def send_admin_notification_menu(update, context):
    user_id = update.effective_user.id
    try:
        context.user_data[user_id]['notification_receivers_df'] = pd.read_csv(notification_receivers_df_location_name)
    except FileNotFoundError:
        context.user_data[user_id]['notification_receivers_df'] = pd.DataFrame({'telegram_user_id': [], 'comment': []})

    df = context.user_data[user_id]['notification_receivers_df']
    keyboard = ReplyKeyboardMarkup([['Add notification receiver', 'Remove notification receiver']],
                                   one_time_keyboard=True)
    reply = update.message.reply_text('Here is the list of notification receivers:\n'
                                      '<pre>{}</pre>'.format(tabulate.tabulate(df, headers='keys', tablefmt='simple')),
                                      reply_markup=keyboard,
                                      parse_mode='HTML')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_ADMIN_NOTIFICATION_MENU_OPTION


def get_receiver_id(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    context.user_data[user_id]['receiver_id'] = text

    if context.user_data[user_id]['add_remove_receiver'] == 'add':
        reply = update.message.reply_text('Type some comment about this receiver, eg. name.')
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return GET_RECEIVER_COMMENT
    else:
        log_this(update, inspect.currentframe().f_code.co_name)
        return remove_notification_receiver(update, context)


def get_receiver_comment(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    context.user_data[user_id]['receiver_comment'] = text
    log_this(update, inspect.currentframe().f_code.co_name)
    return add_new_notification_receiver(update, context)


def add_new_notification_receiver(update, context):
    user_id = update.effective_user.id
    receiver_id = context.user_data[user_id]['receiver_id']
    receiver_comment = context.user_data[user_id]['receiver_comment']

    notification_receivers_df = context.user_data[user_id]['notification_receivers_df']
    notification_receivers_df = \
        notification_receivers_df[notification_receivers_df['telegram_user_id'] != int(receiver_id)]
    notification_receivers_df = notification_receivers_df.append({'telegram_user_id': receiver_id,
                                                                  'comment': receiver_comment},
                                                                 ignore_index=True)
    notification_receivers_df.reset_index(drop=True, inplace=True)
    notification_receivers_df.index += 1

    notification_receivers_df.to_csv(notification_receivers_df_location_name, index=False)

    reply = update.message.reply_text('User {}({}) was added to notification receivers.\n\n'
                                      'Now the list of receivers looks like:\n<pre>{}</pre>'.
                                      format(receiver_id, receiver_comment,
                                             tabulate.tabulate(notification_receivers_df,
                                                               headers='keys', tablefmt='simple')),
                                      parse_mode='HTML')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def remove_notification_receiver(update, context):
    user_id = update.effective_user.id
    receiver_id = int(context.user_data[user_id]['receiver_id'])

    notification_receivers_df = context.user_data[user_id]['notification_receivers_df']

    notification_receivers_df = notification_receivers_df[notification_receivers_df['telegram_user_id'] != receiver_id]

    notification_receivers_df.reset_index(drop=True, inplace=True)
    notification_receivers_df.index += 1

    notification_receivers_df.to_csv(notification_receivers_df_location_name, index=False)

    reply = update.message.reply_text('User {} was removed from notification receivers.\n\n'
                                      'Now the list of receivers looks like:\n<pre>{}</pre>'.
                                      format(receiver_id,
                                             tabulate.tabulate(notification_receivers_df,
                                                               headers='keys', tablefmt='simple')),
                                      parse_mode='HTML')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


admin_conv = ConversationHandler(
    entry_points=[CommandHandler('admin', start_admin)],
    states={
        CHECK_PASSWORD:
            [MessageHandler(Filters.text & Filters.regex('^{}$'.format(admin_password)), send_admin_menu)],

        SELECT_MAIN_MENU_OPTION:
            [MessageHandler(Filters.text & Filters.regex('^Export the whole table$'), export_csv_all_addresses),
             MessageHandler(Filters.text & Filters.regex('^Notification receivers settings$'),
                            send_admin_notification_menu),
             MessageHandler(Filters.text & Filters.regex('^Allowed users settings$'),
                            send_allowed_users_menu)],

        SELECT_ADMIN_NOTIFICATION_MENU_OPTION:
            [MessageHandler(Filters.text & Filters.regex('^(Add notification receiver|Remove notification receiver)$'),
                            ask_notification_receiver_id)],

        GET_ALLOWED_USERS_ID_NICKNAME:
            [MessageHandler(Filters.text & ~Filters.command, get_allowed_user_id_nickname)],

        SELECT_ADMIN_ALLOWED_USERS_MENU_OPTION:
            [MessageHandler(Filters.text & Filters.regex('^(Add allowed user|Remove allowed user)$'),
                            ask_allowed_user_id_nickname)],

        GET_RECEIVER_ID:
            [MessageHandler(Filters.text & Filters.regex(r'^-*\d+$'), get_receiver_id)],

        GET_RECEIVER_COMMENT:
            [MessageHandler(Filters.text & ~Filters.command, get_receiver_comment)]
    },

    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
