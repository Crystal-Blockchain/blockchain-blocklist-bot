from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup
from telegram.error import BadRequest

from src.google.sheets_functions import *
from src.google.drive_functions import *
from src.utils import *
from src.utils import log_this, workbook_name, worksheet_name

# set constants for conversation states
NEW_OLD_GROUP, GROUP_NAME, GROUP_DESCRIPTION, CHOOSE_GROUP, ADDRESSES, WRITE_OR_CHANGE, \
    ASK_TO_CHANGE, CHANGE_PARAM, DUP_ADDRESSES, CHECK_PRESENT_GROUP, SELECT_CURRENCY, \
    MORE_CURRENCY, CURRENCY_TO_CHANGE, GET_CSV = range(14)


def start_add_addresses(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}  # clearing user data to avoid unwanted parameters left from any previous command

    # getting data from Google Sheet as df(data frame)
    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()  # ws_df - worksheet data frame

    # getting all unique group names as list from data frame, sorted descending by the last addresses adding time
    present_group_names = [str(name) for name
                           in ws_df.sort_values('utc_time', ascending=False)['group_name'].drop_duplicates().to_list()]

    # getting all unique currency names as list from data frame, sorted ascending by the name
    currencies = sorted([str(cur) for cur in ws_df['currency'].drop_duplicates().sort_values().to_list()])

    # saving all needed variables to bot user_data
    context.user_data[user_id]['ws_df'] = ws_df
    context.user_data[user_id]['present_group_names'] = present_group_names
    context.user_data[user_id]['currencies'] = currencies

    # creating empty objects that will be used for sure
    context.user_data[user_id]['cur_to_add'] = []
    context.user_data[user_id]['addresses'] = {}

    # logging the action, "inspect.currentframe().f_code.co_name" gets the name of current function to log
    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_new_old_group(update, context)


def ask_new_old_group(update, context):
    user_id = update.effective_user.id
    present_group_names = context.user_data[user_id].get('present_group_names', False)

    if present_group_names:
        keyboard_markup = ReplyKeyboardMarkup([['Existing group', 'New group']], one_time_keyboard=True)
        reply = update.message.reply_text(
            'Would you like to create new address group or add to existing?',
            reply_markup=keyboard_markup)

    else:
        keyboard_markup = ReplyKeyboardMarkup([['New group']], one_time_keyboard=True)
        reply = update.message.reply_text(
            'There is no existing addresses group, create new one.',
            reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return NEW_OLD_GROUP


def save_new_old_group(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    context.user_data[user_id]['action'] = text

    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_group_name(update, context)


def ask_group_name(update, context):
    user_id = update.effective_user.id

    if context.user_data[user_id]['action'] == 'New group':
        reply = update.message.reply_text('What would you like this address group to be called?',
                                          reply_markup=ReplyKeyboardRemove())

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return GROUP_NAME
    else:
        present_group_names = context.user_data[user_id]['present_group_names']

        # splitting list of group names by 3 names per row to correct viewing without abbreviation of names
        group_keyboard = split_list(present_group_names, 3)

        keyboard_markup = ReplyKeyboardMarkup(group_keyboard, one_time_keyboard=True)
        reply_text = '{}' \
                     'There are such group names in table:\n' \
                     '<b>{}</b>\n\n' \
                     'Please, choose one of presents or type the name of the group to which you want add addresses:' \
            .format('You typed wrong group name!\n'
                    if context.user_data[user_id].get('group_name_chosen', False) else '',
                    # if chosen name was wrong
                    '\n'.join(present_group_names))

        if len(reply_text) < MAX_MESSAGE_LENGTH:
            reply = update.message.reply_text(reply_text,
                                              parse_mode='HTML',
                                              reply_markup=keyboard_markup)
            log_this(update, inspect.currentframe().f_code.co_name, reply)

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
                'Select or type the group name.\n'
                'PS There is the limitation of the number of buttons. '
                'You can just type your group name or copy it from the file.',
                reply_markup=keyboard_markup,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

        log_this(update, inspect.currentframe().f_code.co_name, reply)

    return CHECK_PRESENT_GROUP


def write_group_name(update, context):
    user_id = update.effective_user.id
    # "change" variable is for determining whether it was initial asking of group name or changing (available in the
    # end of the conversation)
    change = context.user_data[user_id].get('param_to_change', False)
    present_group_names = context.user_data[user_id]['present_group_names']
    group_name = update.message.text.strip()
    context.user_data[user_id]['group_name'] = group_name

    if group_name in present_group_names:
        reply = update.message.reply_text('Sorry, this name is already taken. Try to type another group name:')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return GROUP_NAME
    else:
        log_this(update, inspect.currentframe().f_code.co_name)
        if not change:
            return ask_group_description(update, context)
        else:
            return confirm_writing(update, context)


def ask_group_description(update, context):
    reply = update.message.reply_text(
        'Please describe why blocklisting is requested for this incident, essentially an incident summary.\n'
        '[Follow Who, What, Where, When, How]:')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GROUP_DESCRIPTION


def write_group_description(update, context):
    user_id = update.effective_user.id
    change = context.user_data[user_id].get('param_to_change', False)
    group_description = update.message.text
    context.user_data[user_id]['group_description'] = group_description

    log_this(update, inspect.currentframe().f_code.co_name)
    if not change:
        return ask_currency(update, context)
    else:
        return confirm_writing(update, context)


def ask_currency(update, context):
    user_id = update.effective_user.id
    currencies = context.user_data[user_id]['currencies']

    if currencies:
        # getting split list of currency names from that are present in Google Sheet and not added by user yet
        # split by 3 per row to good readability
        currency_keyboard = split_list(
            [cur for cur in currencies if cur not in context.user_data[user_id]['cur_to_add']], 3)

        if context.user_data[user_id].get('param_to_change', False):
            keyboard_markup = ReplyKeyboardMarkup(currency_keyboard, one_time_keyboard=True)
        else:
            keyboard_markup = ReplyKeyboardMarkup(currency_keyboard + [['Add all addresses and currencies via csv']],
                                                  one_time_keyboard=True)
        reply = update.message.reply_text('What currency do you want to add?\n'
                                          'Choose one of presents or <b>type your own</b>.',
                                          reply_markup=keyboard_markup,
                                          parse_mode='HTML')
    else:
        if context.user_data[user_id].get('param_to_change', False):
            reply = update.message.reply_text('What currency do you want to add?\n'
                                              'There is no currency in table to choose, type your own.',
                                              reply_markup=ReplyKeyboardRemove())
        else:
            keyboard_markup = ReplyKeyboardMarkup([['Add all addresses and currencies via csv']],
                                                  one_time_keyboard=True)
            reply = update.message.reply_text('What currency do you want to add?\n'
                                              'There is no currency in table to choose, type your own.',
                                              reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_CURRENCY


def select_currency(update, context):
    user_id = update.effective_user.id
    currency_name = update.message.text

    # remove currency name from list of already added currency to avoid name duplication and to append this currency
    # name in the end of the list (it will be appended back in the next code rows)
    if currency_name in context.user_data[user_id]['cur_to_add']:
        context.user_data[user_id]['cur_to_add'].remove(currency_name)

    context.user_data[user_id]['cur_to_add'].append(currency_name.strip())

    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_addresses(update, context)


def ask_addresses(update, context):
    user_id = update.effective_user.id
    currency_name = update.message.text.strip()

    # if "change CUR_NAME" selected we need to get only currency name part from received message
    if 'change' in currency_name:
        currency_name = currency_name.replace('change ', '')

    if currency_name in context.user_data[user_id]['cur_to_add']:
        context.user_data[user_id]['cur_to_add'].remove(currency_name)

    context.user_data[user_id]['cur_to_add'].append(currency_name)

    reply = update.message.reply_text(
        'Please add the <b>{}</b> address(es) for this group as a plain text.\n'
        'The text will be split by any non-alphanumeric character and only latin letters and numbers will be parsed. '
        'No validation is being applied.'.format(context.user_data[user_id]['cur_to_add'][-1]),
        reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return ADDRESSES


def check_present_group(update, context):
    user_id = update.effective_user.id
    group_name = update.message.text.strip()
    present_group_names = context.user_data[user_id].get('present_group_names', [])

    if group_name in present_group_names:
        context.user_data[user_id]['group_name'] = group_name
        log_this(update, inspect.currentframe().f_code.co_name)

        if context.user_data[user_id].get('param_to_change', False):
            return confirm_writing(update, context)
        else:
            return ask_currency(update, context)
    else:
        context.user_data[user_id]['group_name_chosen'] = True

        log_this(update, inspect.currentframe().f_code.co_name)
        return ask_group_name(update, context)


def confirm_writing(update, context):
    user_id = update.effective_user.id
    any_address_added = any(context.user_data[user_id].get('addresses', {'empty': []}).values())

    if any_address_added:
        keyboard_markup = ReplyKeyboardMarkup(
            [['Yes, write to table', 'Change']], one_time_keyboard=True)

        #   making the string with whole details about adding addresses to send to user to confirm
        details = ''
        for k, v in sorted(context.user_data[user_id].items(), reverse=True):
            if k in ['addresses', 'group_name', 'group_description']:
                if v:
                    if k == 'addresses':
                        v = '\n'.join(['{}: {}'.format(k, v) for k, v in v.items() if v])
                    details += '<b>{}</b>:\n{}\n\n'.format(k, v)

        reply_text = '{}' \
                     'Write to table?'.format(details)

        if len(reply_text) < MAX_MESSAGE_LENGTH:
            reply = update.message.reply_text(reply_text,
                                              reply_markup=keyboard_markup,
                                              parse_mode='HTML')

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return WRITE_OR_CHANGE
        else:
            reply = update.message.reply_text(
                'The added addresses details are too long to sent them in Telegram message,\n'
                'please check details in sent txt file and confirm writing.')

            # creating and sending the file with details to user
            file_obj = io.BytesIO()
            file_obj.write(details.replace('<b>', '').replace('</b>', '').encode())
            file_obj.seek(0)
            file_obj.name = 'added_addresses_details.txt'
            context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)

            reply2 = update.message.reply_text(
                'Write to table?',
                reply_markup=keyboard_markup,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return WRITE_OR_CHANGE
    else:
        if context.user_data[user_id].get('csv_used', False):
            reply = update.message.reply_text(
                'There is no address to add, all your addresses are already present in table.\n'
                'Conversation will be finished.',
                reply_markup=ReplyKeyboardRemove())

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return finish_conversation(update, context)
        else:
            reply = update.message.reply_text('There is no address to add.',
                                              reply_markup=ReplyKeyboardRemove())

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return ask_more_currency(update, context)


def get_addresses(update, context):
    user_id = update.effective_user.id
    ws_df = context.user_data[user_id]['ws_df']
    change = context.user_data[user_id].get('param_to_change', False)
    present_addresses = [str(address) for address in ws_df['address'].drop_duplicates().to_list()]

    if context.user_data[user_id].get('csv_used', False):
        addresses_to_add = []
        for addresses in context.user_data[user_id]['addresses'].values():
            addresses_to_add.extend(addresses)
    else:
        string_with_addresses = update.message.text
        # split the string_with_addresses by any non-alphanumeric character
        addresses_to_add = list(set([address for address in re.split(r'[^a-zA-Z0-9]', string_with_addresses)
                                     if address]))

        # adding parsed addresses to last added currency
        context.user_data[user_id]['addresses'].update({context.user_data[user_id]['cur_to_add'][-1]: addresses_to_add})

    # check if duplicate addresses are already present in Google Sheet
    duplicate_addresses = [address for address in addresses_to_add if address in present_addresses]
    context.user_data[user_id]['dup_addresses'] = duplicate_addresses

    if duplicate_addresses:
        keyboard_markup = ReplyKeyboardMarkup([['Add anyway', 'Add other except duplicated']], one_time_keyboard=True)

        # preparing the duplicate addresses table to show to user
        addresses_to_show = ws_df[['address', 'currency', 'group_name', 'telegram_user_id']]
        addresses_to_show = addresses_to_show[addresses_to_show['address'].isin(duplicate_addresses)]
        addresses_to_show['added_by_you'] = addresses_to_show['telegram_user_id'] == update.effective_user.id
        del addresses_to_show['telegram_user_id']
        addresses_to_show.sort_values(['group_name', 'currency', 'address'], inplace=True)
        addresses_to_show.reset_index(drop=True, inplace=True)
        addresses_to_show.index += 1

        reply_text = 'There are some addresses already present in the table.\n' \
                     'Already present addresses:\n<pre>{}</pre>\n\n' \
                     'What do you want to do with them?\n' \
                     '<b>Please note</b>: already present in table duplicate addresses ' \
                     'can be removed by another user!'.format(tabulate.tabulate(addresses_to_show,
                                                                                headers='keys',
                                                                                tablefmt='simple'))

        if len(reply_text) < MAX_MESSAGE_LENGTH:
            reply = update.message.reply_text(reply_text,
                                              reply_markup=keyboard_markup,
                                              parse_mode='HTML')

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return DUP_ADDRESSES
        else:
            reply = update.message.reply_text(
                'There are some addresses already present in the table.\n\n'
                'The duplicate addresses list is too long to sent it in Telegram message,\n'
                'please check duplicate address in sent csv file and choose action.',
                parse_mode='HTML')

            file_obj = io.BytesIO()
            file_obj.write(addresses_to_show.to_csv().encode())
            file_obj.seek(0)
            file_obj.name = 'duplicate_addresses.csv'
            context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)

            reply2 = update.message.reply_text(
                'What do you want to do with them?\n'
                '<b>Please note</b>: already present in table duplicate addresses '
                'can be removed by another user!',
                reply_markup=keyboard_markup,
                parse_mode='HTML')

            reply.text += '\n' + file_obj.name + '\n' + reply2.text
            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return DUP_ADDRESSES

    else:
        log_this(update, inspect.currentframe().f_code.co_name)
        if change or context.user_data[user_id].get('csv_used', False):
            return confirm_writing(update, context)
        else:
            return ask_more_currency(update, context)


def ask_more_currency(update, context):
    user_id = update.effective_user.id
    last_added_cur = context.user_data[user_id]['cur_to_add'][-1]
    last_added_addresses = context.user_data[user_id]['addresses'][last_added_cur]

    if last_added_addresses:
        # adding reply keyboard with included suggestions to change already addede addresses
        keyboard_markup = ReplyKeyboardMarkup(
            [['Add more currencies']] +
            split_list(['change {}'.format(currency) for currency in context.user_data[user_id]['cur_to_add']], 3) + [
                ['Finish']])

        reply = update.message.reply_text('<b>{} {}</b> addresses were parsed from your input:\n'
                                          '<b>{}</b>\n\n'
                                          'Do you want to add another currency addresses?'.
                                          format(len(last_added_addresses), last_added_cur,
                                                 '\n'.join(last_added_addresses)),
                                          reply_markup=keyboard_markup,
                                          parse_mode='HTML')

    elif not last_added_addresses and any(context.user_data[user_id]['addresses'].values()):
        keyboard_markup = ReplyKeyboardMarkup([['Add more currencies', 'Finish']])
        reply = update.message.reply_text('Do you want to add another currency addresses?',
                                          reply_markup=keyboard_markup,
                                          parse_mode='HTML')

        # removing last added currency name from list if no address added
        context.user_data[user_id]['cur_to_add'].remove(last_added_cur)
    else:
        keyboard_markup = ReplyKeyboardMarkup([['Add more currencies', 'Cancel']])
        reply = update.message.reply_text(
            'Do you want to add another currency addresses or cancel conversation?',
            reply_markup=keyboard_markup,
            parse_mode='HTML')
        context.user_data[user_id]['cur_to_add'].remove(last_added_cur)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return MORE_CURRENCY


def ask_currency_to_change(update, context):
    user_id = update.effective_user.id

    keyboard_markup = ReplyKeyboardMarkup([context.user_data[user_id]['cur_to_add'], ['Add another one']])
    reply = update.message.reply_text('What currency addresses you want to change?',
                                      reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return CURRENCY_TO_CHANGE


def change_currency(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if text != 'Add another one':
        if text in context.user_data[user_id]['cur_to_add']:
            context.user_data[user_id]['cur_to_add'].remove(text)
            context.user_data[user_id]['cur_to_add'].append(text)

            log_this(update, inspect.currentframe().f_code.co_name)
            return ask_addresses(update, context)
        else:
            reply = update.message.reply_text('You haven\'t added currency that you want to change.')

            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return ask_currency_to_change(update, context)
    else:
        log_this(update, inspect.currentframe().f_code.co_name)
        return ask_currency(update, context)


def more_currency(update, context):
    text = update.message.text

    log_this(update, inspect.currentframe().f_code.co_name)
    if text == 'Finish':
        return confirm_writing(update, context)
    elif text == 'Cancel':
        return cancel(update, context)
    else:
        return ask_currency(update, context)


def address_present_confirm(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    change = context.user_data[user_id].get('param_to_change', False)

    if text == 'Add anyway':
        log_this(update, inspect.currentframe().f_code.co_name)
        if change or context.user_data[user_id].get('csv_used', False):
            return confirm_writing(update, context)
        else:
            return ask_more_currency(update, context)
    else:
        if context.user_data[user_id].get('csv_used', False):
            #  filter addresses by removing duplicate addresses
            for currency, addresses in context.user_data[user_id]['addresses'].items():
                context.user_data[user_id]['addresses'][currency] = \
                    [address for address in context.user_data[user_id]['addresses'][currency]
                     if address not in context.user_data[user_id]['dup_addresses']]

        else:
            last_added_cur = context.user_data[user_id]['cur_to_add'][-1]
            #  filter addresses by removing duplicate addresses
            addresses_to_add = [address for address in context.user_data[user_id]['addresses'][last_added_cur]
                                if address not in context.user_data[user_id]['dup_addresses']]
            context.user_data[user_id]['addresses'].update({last_added_cur: addresses_to_add})

            if not addresses_to_add:
                reply = update.message.reply_text('All your <b>{0}</b> addresses were present in table, '
                                                  'so there is no <b>{0}</b> address to add.'.format(last_added_cur),
                                                  parse_mode='HTML',
                                                  reply_markup=ReplyKeyboardRemove())

                log_this(update, inspect.currentframe().f_code.co_name, reply)

        log_this(update, inspect.currentframe().f_code.co_name)

        if (change and any([addresses for addresses in context.user_data[user_id]['addresses'].values()])) or \
                (context.user_data[user_id].get('csv_used', False)):
            return confirm_writing(update, context)
        else:

            return ask_more_currency(update, context)


def ask_csv(update, context):
    reply = update.message.reply_text(
        'Send csv up to 20MB with header where at least '
        'two <b>exactly named</b> columns are present: \'address\', \'currency\'.',
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML')

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_CSV


def parse_csv(update, context):
    user_id = update.effective_user.id
    attachment = update.message.document
    try:
        byte_file = io.BytesIO(attachment.get_file().download_as_bytearray())
    except BadRequest as br:
        reply = update.message.reply_text('Telegram error: {}'.format(
            '{}.\nThe size of the file you want to add is {}MB.'.format(br,
                                                                        round(attachment.file_size / float(1 << 20), 2))
            if br.message == 'File is too big' else br))

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)

    df = pd.read_csv(byte_file, skip_blank_lines=True)
    df = df.drop_duplicates(['address', 'currency'])

    if not ('address' in df.columns and 'currency' in df.columns):
        reply = update.message.reply_text('Can\'t find \'address\' or/and \'currency\' column in csv. '
                                          'Please make sure your csv has header with needed columns')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)

    elif any([pd.isna(cell) for cell in df['currency'].to_list()]):
        reply = update.message.reply_text('Some addresses don\'t have currency. Please set currency for all addresses')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)
    else:
        currency_addresses_dict = {}

        # creating a dict of addresses from data frame to add to the bot user_data
        for cur in df['currency'].drop_duplicates():
            currency_addresses_dict.setdefault(cur, [])
            currency_addresses_dict[cur] = [address.strip() for address in
                                            df.loc[df['currency'] == cur, 'address'].to_list()]

        context.user_data[user_id]['addresses'].update(currency_addresses_dict)
        context.user_data[user_id]['csv_used'] = True

        log_this(update, inspect.currentframe().f_code.co_name)
        return get_addresses(update, context)


def write_to_table(update, context):
    user_id = update.effective_user.id
    ws_df = context.user_data[user_id]['ws_df']

    # if adding to existing group get already present description from table
    if not context.user_data[user_id].get('group_description', False):
        context.user_data[user_id]['group_description'] = \
            ws_df.loc[ws_df['group_name'] == context.user_data[user_id]['group_name'], 'group_description'].values[0]

    dict_to_write = context.user_data[user_id]
    group_name = dict_to_write['group_name']
    df_to_write = pd.DataFrame()

    # making the data frame to write to Google Sheet
    for cur, addresses in dict_to_write['addresses'].items():
        temp_df = pd.DataFrame({'address': addresses})
        temp_df['currency'] = cur
        df_to_write = df_to_write.append(temp_df, sort=False)
    df_to_write['group_name'] = dict_to_write['group_name']
    df_to_write['group_description'] = dict_to_write['group_description']
    df_to_write['reported_by'] = update.effective_user.full_name
    df_to_write['utc_time'] = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    df_to_write['telegram_user_id'] = update.effective_user.id
    df_to_write['attachments'] = create_folder(drive, group_name, parent_attachments_folder_id)

    # get the Google Sheet data again to be sure about the newest data
    worksheet = open_worksheet(workbook_name, worksheet_name)

    # appending data and saving the new data frame to variable for notification sending
    new_df = append_data(worksheet, df_to_write)

    # changing colors of folders in Google Drive for group with addresses
    list_of_present_group_names = new_df['group_name'].drop_duplicates().to_list()
    change_color_for_folders_without_addresses(list_of_present_group_names)

    reply = update.message.reply_text('Addresses was added to table!')

    log_this(update, inspect.currentframe().f_code.co_name, reply)

    notify(update, context, text='<b>{}</b> added addresses to <b>{}</b> group.\n'.
           format(update.effective_user.full_name,
                  group_name),
           addresses='\n'.join(df_to_write['address'].to_list()))
    return finish_conversation(update, context)


def change_choose(update, context):
    user_id = update.effective_user.id

    if context.user_data[user_id]['action'] == 'New group':
        keyboard_markup = ReplyKeyboardMarkup([['Group name', 'Group description', 'Addresses']],
                                              one_time_keyboard=True)
    else:
        keyboard_markup = ReplyKeyboardMarkup([['Group name', 'Addresses']], one_time_keyboard=True)

    reply = update.message.reply_text('Please choose what parameter you want to change:',
                                      reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return ASK_TO_CHANGE


def ask_to_change(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    context.user_data[user_id]['param_to_change'] = text

    if text == 'Addresses':
        if context.user_data[user_id].get('csv_used', False):
            text = 'csv'
        else:
            text = 'currency_to_change'

    log_this(update, inspect.currentframe().f_code.co_name)

    return eval('ask_{}(update, context)'.format(text.lower().replace(' ', '_')))


add_address_conv = ConversationHandler(
    entry_points=[CommandHandler('add_addresses', start_add_addresses)],
    states={
        NEW_OLD_GROUP:
            [MessageHandler(Filters.text & Filters.regex('^(New group|Existing group)$'), save_new_old_group)],

        GROUP_NAME:
            [MessageHandler(Filters.text & ~Filters.command, write_group_name)],

        GROUP_DESCRIPTION:
            [MessageHandler(Filters.text & ~Filters.command, write_group_description)],

        ADDRESSES:
            [MessageHandler(Filters.text & ~Filters.command, get_addresses)],

        WRITE_OR_CHANGE:
            [MessageHandler(Filters.text & Filters.regex('^Yes, write to table$'), write_to_table),
             MessageHandler(Filters.text & Filters.regex('^Change$'), change_choose)],

        ASK_TO_CHANGE:
            [MessageHandler(Filters.text & Filters.regex('^(Group name|Group description|Addresses)$'), ask_to_change)],

        DUP_ADDRESSES:
            [MessageHandler(Filters.text & Filters.regex('^(Add anyway|Add other except duplicated)$'),
                            address_present_confirm)],

        CHECK_PRESENT_GROUP:
            [MessageHandler(Filters.text & ~Filters.command, check_present_group)],

        SELECT_CURRENCY:
            [MessageHandler(Filters.text & ~Filters.command &
                            ~Filters.regex('^Add all addresses and currencies via csv$'), select_currency),
             MessageHandler(Filters.text & Filters.regex('^Add all addresses and currencies via csv$'), ask_csv)],

        MORE_CURRENCY:
            [MessageHandler(Filters.text & Filters.regex('^(Add more currencies|Finish|Cancel)$'), more_currency),
             MessageHandler(Filters.text & Filters.regex('^change (.)*$'), ask_addresses)],

        CURRENCY_TO_CHANGE:
            [MessageHandler(Filters.text & ~Filters.command, change_currency)],

        GET_CSV:
            [MessageHandler(Filters.document, parse_csv)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
