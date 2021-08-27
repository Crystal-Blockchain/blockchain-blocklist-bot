from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup

from src.google.drive_functions import change_color_for_folders_without_addresses
from src.google.sheets_functions import *
from src.utils import *

SELECT_CSV_OR_CONV, CHECK_PRESENT_GROUP, SHOW_GROUP_ADDRESSES, SELECT_REMOVING_TYPE, ASK_EXPORT, \
    REMOVE_OR_CANCEL, SELECT_ADDRESSES_TO_REMOVE_LEAVE, GET_CSV = range(8)


def start_remove_addresses(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()
    ws_df_remove = ws_df[ws_df['telegram_user_id'] == update.effective_user.id].drop_duplicates()
    present_group_names = [str(name) for name
                           in ws_df_remove.sort_values('utc_time', ascending=False)[
                               'group_name'].drop_duplicates().to_list()]

    context.user_data[user_id]['present_group_names'] = present_group_names
    context.user_data[user_id]['ws_df_remove'] = ws_df_remove

    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_group_name(update, context)


def ask_group_name(update, context):
    user_id = update.effective_user.id
    present_group_names = context.user_data[user_id]['present_group_names']

    if present_group_names:
        group_keyboard = split_list(present_group_names, 3)
        keyboard = ReplyKeyboardMarkup(group_keyboard + [['Select all']], one_time_keyboard=True)

        reply_text = '{}' \
            'There are such group names in table:\n' \
            '<b>{}</b>\n\n' \
            'Please, select one of presents or type the name of the group ' \
            'which addresses you want me to show for future removing:'.format(
                'You typed wrong group name!\n' if context.user_data[user_id].get('group_name_chosen', False) else '',
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
                'There is also \'Select all\' option',
                reply_markup=keyboard,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return CHECK_PRESENT_GROUP
    else:
        reply = update.message.reply_text(
            'You haven\'t added any address.')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return finish_conversation(update, context)


def check_present_group(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    present_group_names = context.user_data[user_id]['present_group_names']
    ws_df_remove = context.user_data[user_id]['ws_df_remove']

    if text in present_group_names or text == 'Select all':
        context.user_data[user_id]['group_name'] = text
        group_name = context.user_data[user_id]['group_name']
        ws_df_remove = ws_df_remove.sort_values(['utc_time', 'group_name', 'address'])
        if context.user_data[user_id]['group_name'] != 'Select all':
            ws_df_remove = ws_df_remove[ws_df_remove['group_name'] == group_name]
            ws_df_remove = ws_df_remove[['address', 'currency', 'group_name', 'utc_time']]
        else:
            ws_df_remove = ws_df_remove
            ws_df_remove = ws_df_remove[['address', 'currency', 'group_name', 'utc_time']]
        ws_df_remove.reset_index(inplace=True, drop=True)
        ws_df_remove.index += 1
        context.user_data[user_id]['ws_df_remove'] = ws_df_remove
        log_this(update, inspect.currentframe().f_code.co_name)
        return ask_csv_or_conv(update, context)
    else:
        context.user_data[user_id]['group_name_chosen'] = True
        log_this(update, inspect.currentframe().f_code.co_name)
        return ask_group_name(update, context)


def ask_csv_or_conv(update, context):
    keyboard = ReplyKeyboardMarkup([['Conversation mode', 'Using csv file']], one_time_keyboard=True)
    reply = update.message.reply_text('What method do you prefer to use to remove addresses?\n\n'
                                      '<b>Conversation mode</b> - you will be able to remove all addresses from group, '
                                      'select addresses you want to remove or '
                                      'select addresses you want to leave '
                                      'and remove others by sending indexes to the bot.\n'
                                      '<b>Using csv file</b> - you get the csv with your addresses, '
                                      'it is needed to tag addresses you want to remove and send the file back to bot.',
                                      parse_mode='HTML',
                                      reply_markup=keyboard)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_CSV_OR_CONV


def send_table(update, context):
    user_id = update.effective_user.id
    ws_df_remove = context.user_data[user_id]['ws_df_remove']
    log_this(update, inspect.currentframe().f_code.co_name)
    group_name = context.user_data[user_id]['group_name']

    keyboard = ReplyKeyboardMarkup([['Remove all shown addresses', 'Select addresses to remove',
                                     'Select addresses to leave and remove others'], ['Continue using csv method']],
                                   one_time_keyboard=True)
    reply_text = '{}<pre>{}</pre>\n\n' \
                 'Please select preferred action.'.format('<b>{}</b> addresses group:\n\n'.format(group_name)
                                                          if group_name != 'Select all' else '',
                                                          tabulate.tabulate(ws_df_remove,
                                                                            headers='keys',
                                                                            tablefmt='simple'))
    if len(reply_text) < MAX_MESSAGE_LENGTH:
        reply = update.message.reply_text(reply_text,
                                          parse_mode='HTML',
                                          reply_markup=keyboard)

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return SELECT_REMOVING_TYPE
    else:
        reply = update.message.reply_text('The Telegram message length limit is exceeded, check the csv file.',
                                          parse_mode='HTML')

        log_this(update, inspect.currentframe().f_code.co_name, reply)

        export_csv_in_remove_command(update, context)
        reply = update.message.reply_text('Please select preferred action',
                                          reply_markup=keyboard)

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return SELECT_REMOVING_TYPE


def ask_addresses_to_remove_leave(update, context):
    user_id = update.effective_user.id
    log_this(update, inspect.currentframe().f_code.co_name)
    text = update.message.text

    if not context.user_data[user_id].get('remove_leave', False):
        remove_leave = 'leave' if 'leave' in text else 'remove'
        context.user_data[user_id]['remove_leave'] = remove_leave
    else:
        remove_leave = context.user_data[user_id]['remove_leave']

    reply = update.message.reply_text('Please send me indexes of addresses you want to {}.\n'
                                      'It should be split by comma (,) and you can also use ranges with hyphen (-).'.
                                      format(remove_leave),
                                      reply_markup=ReplyKeyboardRemove())

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_ADDRESSES_TO_REMOVE_LEAVE


def wrong_format(update, context):
    user_id = update.effective_user.id

    reply = update.message.reply_text(
        'Can\'t parse your answer, please split indexes by comma (,) and you can also use ranges with hyphen (-).\n'
        'For example: "1,5,7-10"'
        'Please send me indexes of addresses you want to {}.\n'.format(context.user_data[user_id]['remove_leave']),
        reply_markup=ReplyKeyboardRemove())

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_ADDRESSES_TO_REMOVE_LEAVE


def parse_indexes(text):
    index_list = []
    for item in text.split(','):
        if '-' not in item:
            index_list.append(int(item.strip()))
        else:
            range_list = [index for index in range(int(item.split('-')[0].strip()),
                                                   int(item.split('-')[1].strip()) + 1)]
            index_list.extend(range_list)
    return index_list


def select_addresses_to_remove_leave(update, context):
    user_id = update.effective_user.id
    index_list = parse_indexes(update.message.text)
    ws_df_remove = context.user_data[user_id]['ws_df_remove']

    if any([index in ws_df_remove.index for index in index_list]):
        if context.user_data[user_id]['remove_leave'] == 'remove':
            ws_df_remove = ws_df_remove[ws_df_remove.index.isin(index_list)]
        else:
            ws_df_remove = ws_df_remove[~ws_df_remove.index.isin(index_list)]

        context.user_data[user_id]['ws_df_remove'] = ws_df_remove

        log_this(update, inspect.currentframe().f_code.co_name)
        return confirm_addresses_removing(update, context)
    else:
        reply = update.message.reply_text('There are no such indexes in table.',
                                          reply_markup=ReplyKeyboardRemove())

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_addresses_to_remove_leave(update, context)


def confirm_addresses_removing(update, context):
    user_id = update.effective_user.id

    log_this(update, inspect.currentframe().f_code.co_name)

    ws_df_remove = context.user_data[user_id]['ws_df_remove']
    ws_df_remove = ws_df_remove[['address', 'currency', 'group_name', 'utc_time']]
    context.user_data[user_id]['ws_df_remove'] = ws_df_remove

    keyboard_markup = ReplyKeyboardMarkup(
        [['Yes, remove addresses', 'Cancel conversation']], one_time_keyboard=True)
    reply_text = 'You are going to remove the below addresses:\n' \
                 '<pre>{}</pre>\n\n' \
                 'Remove addresses from table?'.format(tabulate.tabulate(ws_df_remove, headers='keys',
                                                                         tablefmt='simple'))

    if len(reply_text) < MAX_MESSAGE_LENGTH:
        reply = update.message.reply_text(reply_text,
                                          parse_mode='HTML',
                                          reply_markup=keyboard_markup)

    else:
        reply = update.message.reply_text('The Telegram message length limit is exceeded, '
                                          'check the csv file with addresses you are going to remove',
                                          parse_mode='HTML')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        export_csv_in_remove_command(update, context)
        reply = update.message.reply_text('Remove addresses from table?',
                                          reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return REMOVE_OR_CANCEL


def remove_addresses(update, context):
    user_id = update.effective_user.id
    ws_df_remove = context.user_data[user_id]['ws_df_remove']

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df_remove['telegram_user_id'] = update.effective_user.id

    new_df = remove_data(worksheet, ws_df_remove, update)

    reply = update.message.reply_text('Addresses were removed from table!')

    log_this(update, inspect.currentframe().f_code.co_name, reply)

    group_from = ws_df_remove['group_name'].drop_duplicates().sort_values().to_list()

    notify(update, context,
           '<b>{}</b> removed addresses from <b>{}</b> group.\n'.format(
               update.effective_user.full_name, ', '.join(group_from)),
           addresses='\n'.join(ws_df_remove['address'].to_list()))

    list_of_left_groups = new_df['group_name'].drop_duplicates().to_list()
    change_color_for_folders_without_addresses(list_of_left_groups)
    return finish_conversation(update, context)


def export_csv_in_remove_command(update, context):
    user_id = update.effective_user.id
    log_this(update, inspect.currentframe().f_code.co_name)
    csv_group_name = context.user_data[user_id]['group_name'].replace(' ', '_')

    ws_df_remove = context.user_data[user_id]['ws_df_remove']
    sent_csv = ws_df_remove.copy()

    sent_csv['to_remove'] = False

    file_obj = io.BytesIO()
    file_obj.write(sent_csv.to_csv().encode())
    file_obj.seek(0)
    file_obj.name = '{}_addresses_to_remove.csv'.format(
        csv_group_name if csv_group_name != 'Select_all' else 'all')

    context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)
    reply = file_obj.name

    log_this(update, inspect.currentframe().f_code.co_name, reply)


def start_csv_mode(update, context):
    export_csv_in_remove_command(update, context)
    return ask_csv(update, context)


def ask_csv(update, context):
    reply = update.message.reply_text(
        'Send csv you got with filled column \'to_remove\'.\n'
        'Column should be filled with "True" for rows you want to remove.',
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_CSV


def parse_csv(update, context):

    user_id = update.effective_user.id
    attachment = update.message.document

    byte_file = io.BytesIO(attachment.get_file().download_as_bytearray())

    df = pd.read_csv(byte_file, skip_blank_lines=True)

    if not all([column in df.columns for column in ['address', 'group_name', 'currency', 'utc_time']]):
        reply = update.message.reply_text('Can\'t find needed columns in csv. '
                                          'Please make sure you use csv you got in previous message.')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)

    if df[~pd.isna(df['to_remove']) & df['to_remove']].empty:
        reply = update.message.reply_text('No address was tagged to remove. '
                                          'Please tag at least one address to remove.')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)

    else:
        df['telegram_user_id'] = update.effective_user.id
        df['utc_time'] = pd.to_datetime(df['utc_time'])
        ws_df_remove = context.user_data[user_id]['ws_df_remove']
        ws_df_remove['utc_time'] = pd.to_datetime(ws_df_remove['utc_time'])

        ws_df_remove = ws_df_remove.merge(df, on=['address', 'currency', 'group_name', 'utc_time'],
                                          indicator=True, how='left')

        ws_df_remove.index += 1
        ws_df_remove = ws_df_remove[~pd.isna(ws_df_remove['to_remove']) & ws_df_remove['to_remove']]
        context.user_data[user_id]['ws_df_remove'] = ws_df_remove

        log_this(update, inspect.currentframe().f_code.co_name)
        return confirm_addresses_removing(update, context)


remove_addresses_conv = ConversationHandler(
    entry_points=[CommandHandler('removeaddresses', start_remove_addresses)],
    states={
        SELECT_CSV_OR_CONV:
            [MessageHandler(Filters.text & Filters.regex('^Conversation mode$'), send_table),
             MessageHandler(Filters.text & Filters.regex('^Using csv file$'), start_csv_mode)],

        CHECK_PRESENT_GROUP:
            [MessageHandler(Filters.text & ~Filters.command, check_present_group)],

        SHOW_GROUP_ADDRESSES:
            [MessageHandler(Filters.text & ~Filters.command, send_table)],

        SELECT_REMOVING_TYPE:
            [MessageHandler(Filters.text & Filters.regex('^Remove all shown addresses$'), confirm_addresses_removing),
             MessageHandler(Filters.text & Filters.regex('^Select addresses to'),ask_addresses_to_remove_leave),
             MessageHandler(Filters.text & Filters.regex('^Continue using csv '), start_csv_mode)],

        SELECT_ADDRESSES_TO_REMOVE_LEAVE:
            [MessageHandler(Filters.text & Filters.regex('^[\s\d,-]*$'), select_addresses_to_remove_leave),
             MessageHandler(Filters.text & ~Filters.regex('^[\s\d,-]*$'), wrong_format)],

        ASK_EXPORT:
            [MessageHandler(Filters.text & Filters.regex('^Export to csv$'), export_csv_in_remove_command),
             MessageHandler(Filters.text & Filters.regex('^Finish$'), finish_conversation)],

        REMOVE_OR_CANCEL:
            [MessageHandler(Filters.text & Filters.regex('^Yes, remove addresses$'), remove_addresses),
             MessageHandler(Filters.text & Filters.regex('^Cancel conversation'), cancel)],

        GET_CSV:
            [MessageHandler(Filters.document, parse_csv)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
