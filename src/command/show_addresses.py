from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup

from src.google.sheets_functions import *
from src.utils import *

MY_OR_ALL, CHOOSE_GROUP, CHECK_PRESENT_GROUP, SHOW_GROUP_ADDRESSES, ASK_EXPORT = range(5)


def start_show_addresses(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()
    ws_df['added_by_me'] = ws_df['telegram_user_id'] == user_id

    context.user_data[user_id]['present_group_names'] = []
    context.user_data[user_id]['my_or_all'] = False
    context.user_data[user_id]['ws_df'] = ws_df
    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_my_or_all(update, context)


def ask_my_or_all(update, context):
    keyboard = ReplyKeyboardMarkup([['My addresses', 'All addresses']], one_time_keyboard=True)
    reply = update.message.reply_text(
        'Do you want only your or all added addresses to be shown?', parse_mode='HTML', reply_markup=keyboard)
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return MY_OR_ALL


def ask_group_name(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    context.user_data[user_id]['my_or_all'] = text
    ws_df = context.user_data[user_id]['ws_df']

    if text == 'My addresses':
        ws_df = ws_df[ws_df['telegram_user_id'] == update.effective_user.id]
        context.user_data[user_id]['ws_df'] = ws_df

    present_group_names = [str(name) for name
                           in ws_df.sort_values('utc_time', ascending=False)[
                               'group_name'].drop_duplicates().to_list()]
    context.user_data[user_id]['present_group_names'] = present_group_names

    if present_group_names:
        group_keyboard = split_list(present_group_names, 3)
        keyboard = ReplyKeyboardMarkup(group_keyboard + [['Show all']], one_time_keyboard=True)
        reply_text = '{}' \
                     'There are such group names in table:\n' \
                     '<b>{}</b>\n\n' \
                     'Please, choose one of presents or type the name of the group which ' \
                     'addresses you want me to show:'. \
            format('You typed wrong group name!\n'
                   if context.user_data[user_id].get('group_name_chosen', False) else '',
                   '\n'.join(present_group_names))

        if len(reply_text) < MAX_MESSAGE_LENGTH:
            reply = update.message.reply_text(reply_text,
                                              parse_mode='HTML',
                                              reply_markup=keyboard)

        else:
            reply = update.message.reply_text('The Telegram message length limit is exceeded, '
                                              'check the txt file with group names sent.',
                                              parse_mode='HTML')

            # creating and sending the file with details to user
            file_obj = io.BytesIO()
            file_obj.write('\n'.join(present_group_names).encode())
            file_obj.seek(0)
            file_obj.name = 'blocklisted_groups.txt'
            context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)

            reply2 = update.message.reply_text(
                'Select or type the group name. \n'
                'PS There is the limitation of the number of buttons. '
                'You can just type your group name or copy it from the file.\n'
                'There is also \'Show all\' option',

                reply_markup=keyboard,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return CHECK_PRESENT_GROUP
    else:
        reply = update.message.reply_text(
            'You haven\'t added any address')
        log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


def check_present_group(update, context):
    user_id = update.effective_user.id
    present_group_names = context.user_data[user_id].get('present_group_names')
    text = update.message.text
    if text in present_group_names or text == 'Show all':
        context.user_data[user_id]['group_name'] = text
        log_this(update, inspect.currentframe().f_code.co_name)
        return sent_table(update, context)
    else:
        context.user_data[user_id]['group_name_chosen'] = True
        log_this(update, inspect.currentframe().f_code.co_name)
        return ask_group_name(update, context)


def sent_table(update, context):
    user_id = update.effective_user.id
    group_name = context.user_data[user_id]['group_name']
    ws_df_user = context.user_data[user_id]['ws_df']
    ws_df_user = ws_df_user.sort_values(['group_name', 'added_by_me', 'utc_time', 'address', ])
    if context.user_data[user_id]['group_name'] != 'Show all':
        ws_df_sent = ws_df_user[ws_df_user['group_name'].apply(str) == group_name]
        if context.user_data[user_id]['my_or_all'] == 'My addresses':
            ws_df_sent = ws_df_sent[['address', 'currency']]
        else:
            ws_df_sent = ws_df_sent[['address', 'currency', 'added_by_me']]
    else:
        ws_df_sent = ws_df_user
        if context.user_data[user_id]['my_or_all'] == 'My addresses':
            ws_df_sent = ws_df_sent[['address', 'currency', 'group_name']]
        else:
            ws_df_sent = ws_df_sent[['address', 'currency', 'group_name', 'added_by_me']]

    ws_df_sent.reset_index(inplace=True, drop=True)
    ws_df_sent.index += 1
    context.user_data[user_id]['ws_df_sent'] = ws_df_sent

    keyboard = ReplyKeyboardMarkup([['Export to csv', 'Finish']], one_time_keyboard=True)

    reply_text = '{}<pre>{}</pre>'.format('<b>{}</b> addresses group:\n\n'.format(group_name)
                                          if group_name != 'Show all' else '',
                                          tabulate.tabulate(ws_df_sent, headers='keys',
                                                            tablefmt='simple'))
    if len(reply_text) < MAX_MESSAGE_LENGTH:
        reply = update.message.reply_text(reply_text,
                                          parse_mode='HTML',
                                          reply_markup=keyboard)
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ASK_EXPORT
    else:
        reply = update.message.reply_text('The Telegram message length limit is exceeded, check the csv file.',
                                          parse_mode='HTML',
                                          reply_markup=keyboard)
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        export_csv(update, context)


def export_csv(update, context):
    user_id = update.effective_user.id
    ws_df_sent = context.user_data[user_id]['ws_df_sent']
    group_name = context.user_data[user_id]['group_name'].replace(' ', '_')

    file_obj = io.BytesIO()
    file_obj.write(ws_df_sent.to_csv().encode())
    file_obj.seek(0)
    file_obj.name = 'addresses_reported.csv'.format(
        group_name if group_name != 'Show_all' else 'all')
    context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)
    reply = file_obj.name
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return finish_conversation(update, context)


show_addresses_conv = ConversationHandler(
    entry_points=[CommandHandler('show_addresses', start_show_addresses)],
    states={
        MY_OR_ALL:
            [MessageHandler(Filters.text & Filters.regex('^(My addresses|All addresses)$'), ask_group_name)],
        CHECK_PRESENT_GROUP:
            [MessageHandler(Filters.text & ~Filters.command, check_present_group)],

        SHOW_GROUP_ADDRESSES:
            [MessageHandler(Filters.text & ~Filters.command, sent_table)],

        ASK_EXPORT:
            [MessageHandler(Filters.text & Filters.regex('^Export to csv$'), export_csv),
             MessageHandler(Filters.text & Filters.regex('^Finish$'), finish_conversation)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
