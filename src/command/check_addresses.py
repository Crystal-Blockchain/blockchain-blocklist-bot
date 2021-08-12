from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup
from src.google.sheets_functions import *
from src.utils import *

SELECT_TEXT_OR_CSV, PARSE_TEXT_ADDRESSES, GET_CSV, ASK_EXPORT = range(4)


def start_check_addresses(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()
    context.user_data[user_id]['ws_df'] = ws_df

    context.user_data[user_id]['addresses'] = []
    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_text_or_csv(update, context)


def ask_text_or_csv(update, context):
    keyboard_markup = ReplyKeyboardMarkup([['Text', 'Import from csv']], one_time_keyboard=True)
    reply = update.message.reply_text(
        'Would you like to send me addresses as a text message or import from csv?',
        reply_markup=keyboard_markup)

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return SELECT_TEXT_OR_CSV


def ask_addresses(update, context):
    reply = update.message.reply_text(
        'Please sent the address(es) as a plain text.\n'
        'The text will be split by any non-alphanumeric character and only latin letters and numbers will be parsed. '
        'No validation is being applied.',
        reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return PARSE_TEXT_ADDRESSES


def ask_csv(update, context):
    reply = update.message.reply_text(
        'Send csv up to 20MB with header where at least '
        'one <b>exactly named</b> columns is present: \'address\'.',
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_CSV


def parse_csv(update, context):
    user_id = update.effective_user.id
    attachment = update.message.document
    byte_file = io.BytesIO(attachment.get_file().download_as_bytearray())
    df = pd.read_csv(byte_file, skip_blank_lines=True)

    if 'address' not in df.columns:
        reply = update.message.reply_text('Can\'t find \'address\' column in csv. '
                                          'Please make sure your csv has header with needed column')
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_csv(update, context)

    else:
        context.user_data[user_id]['addresses'] = [address for address in df['address'] if pd.notna(address)]
        context.user_data[user_id]['csv_used'] = True
        log_this(update, inspect.currentframe().f_code.co_name)
        return get_addresses(update, context)


def get_addresses(update, context):
    user_id = update.effective_user.id
    ws_df = context.user_data[user_id]['ws_df']
    present_addresses = [str(address) for address in ws_df['address'].drop_duplicates().to_list()]

    if context.user_data[user_id].get('csv_used', False):
        addresses_to_add = context.user_data[user_id]['addresses']

    else:
        text = update.message.text
        addresses_to_add = list(set([address for address in re.split(r'[^a-zA-Z0-9]', text) if address]))
        reply = update.message.reply_text('<b>{}</b> addresses were parsed from your input:\n<b>{}</b>\n\n'.
                                          format(len(addresses_to_add),
                                                 '\n'.join(addresses_to_add)),
                                          parse_mode='HTML')
        log_this(update, inspect.currentframe().f_code.co_name, reply)

    duplicate_addresses = [address for address in addresses_to_add if address in present_addresses]

    if duplicate_addresses:

        addresses_to_show = ws_df[['address', 'currency', 'group_name', 'telegram_user_id']]
        addresses_to_show = addresses_to_show[addresses_to_show['address'].isin(duplicate_addresses)]
        addresses_to_show['added_by_you'] = addresses_to_show['telegram_user_id'] == update.effective_user.id
        del addresses_to_show['telegram_user_id']
        addresses_to_show.sort_values(['group_name', 'currency', 'address'], inplace=True)
        addresses_to_show.reset_index(drop=True, inplace=True)
        addresses_to_show.index += 1

        context.user_data[user_id]['addresses_to_show_df'] = addresses_to_show

        reply_text = 'Already present addresses in table:\n<pre>{}</pre>\n\n'.format(
            tabulate.tabulate(addresses_to_show,
                              headers='keys',
                              tablefmt='simple'))
        if len(reply_text) < MAX_MESSAGE_LENGTH:
            keyboard = ReplyKeyboardMarkup([['Export to csv', 'Finish']], one_time_keyboard=True)
            reply = update.message.reply_text(reply_text,
                                              parse_mode='HTML',
                                              reply_markup=keyboard)
            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return ASK_EXPORT
        else:
            reply = update.message.reply_text(
                'The present addresses list is too long to sent it in Telegram message,\n'
                'please check them in the sent csv file.',
                parse_mode='HTML')
            log_this(update, inspect.currentframe().f_code.co_name, reply)
            return export_csv(update, context)
    else:
        reply = update.message.reply_text('Any addresses from given are <b>not</b> present in table.',
                                          parse_mode='HTML')
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return finish_conversation(update, context)


def export_csv(update, context):
    user_id = update.effective_user.id
    addresses_to_show = context.user_data[user_id]['addresses_to_show_df']
    file_obj = io.BytesIO()
    file_obj.write(addresses_to_show.to_csv().encode())
    file_obj.seek(0)
    file_obj.name = 'present_addresses.csv'

    reply = file_obj.name
    context.bot.send_document(chat_id=update.message.chat_id, document=file_obj)
    log_this(update, inspect.currentframe().f_code.co_name, reply)

    return finish_conversation(update, context)


check_addresses_conv = ConversationHandler(
    entry_points=[CommandHandler('check_addresses', start_check_addresses)],
    states={
        SELECT_TEXT_OR_CSV:
            [MessageHandler(Filters.text & Filters.regex('^Text$'), ask_addresses),
             MessageHandler(Filters.text & Filters.regex('^Import from csv'), ask_csv)],

        PARSE_TEXT_ADDRESSES:
            [MessageHandler(Filters.text & ~Filters.command, get_addresses)],

        GET_CSV:
            [MessageHandler(Filters.document, parse_csv)],

        ASK_EXPORT:
            [MessageHandler(Filters.text & Filters.regex('^Export to csv$'), export_csv),
             MessageHandler(Filters.text & Filters.regex('^Finish$'), finish_conversation)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
