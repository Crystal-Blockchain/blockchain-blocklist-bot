from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup
from telegram.error import BadRequest

from src.google.sheets_functions import *
from src.google.drive_functions import *
from src.utils import *

CHECK_PRESENT_GROUP, GET_FILE, ADD_MORE = range(3)


def start_add_attachments(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()
    present_group_names = [str(name) for name
                           in ws_df.sort_values('utc_time', ascending=False)['group_name'].drop_duplicates().to_list()]

    context.user_data[user_id]['present_group_names'] = present_group_names

    log_this(update, inspect.currentframe().f_code.co_name)
    return ask_group_name(update, context)


def ask_group_name(update, context):
    user_id = update.effective_user.id

    present_group_names = context.user_data[user_id]['present_group_names']
    if present_group_names:
        group_keyboard = split_list(present_group_names, 3)
        keyboard = ReplyKeyboardMarkup(group_keyboard, one_time_keyboard=True)
        reply_text = '{}' \
                     'There are such group names in table:\n' \
                     '<b>{}</b>\n' \
                     'Please, choose one of presents or type the name of the group to which you want add attachments:' \
            .format('You typed wrong group name!\n'
                    if context.user_data[user_id].get('group_name_chosen', False) else '',
                    ', '.join(present_group_names))

        if len(reply_text) < MAX_MESSAGE_LENGTH:
            reply = update.message.reply_text(reply_text,
                                              parse_mode='HTML',
                                              reply_markup=keyboard)
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
                'Select or type the group name.'
                'PS There is the limitation of the number of buttons. '
                'You can just type your group name or copy it from the file.',
                reply_markup=keyboard,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return CHECK_PRESENT_GROUP
    else:
        reply = update.message.reply_text('There is no addresses group in table to add attachments.\n'
                                          'Please add some addresses first using /add_address command.')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return finish_conversation(update, context)


def check_present_group(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    present_group_names = context.user_data[user_id]['present_group_names']

    log_this(update, inspect.currentframe().f_code.co_name)
    if text in present_group_names:
        context.user_data[user_id]['group_name'] = text
        return ask_file(update, context)
    else:
        context.user_data[user_id]['group_name_chosen'] = True
        return ask_group_name(update, context)


def ask_file(update, context):
    reply = update.message.reply_text('Please, send me ONE file you want to add as a document below 20MB')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_FILE


def ask_file_not_photo(update, context):
    reply = update.message.reply_text('If you want to send an image, '
                                      'please send it as a document (without compression)')
    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return GET_FILE


def get_file(update, context):
    user_id = update.effective_user.id
    reply = update.message.reply_text('Processing, please wait...')
    log_this(update, inspect.currentframe().f_code.co_name, reply)

    attachment = update.message.document
    attachment_name = attachment.file_name

    try:
        byte_file = io.BytesIO(attachment.get_file().download_as_bytearray())

        group_name = context.user_data[user_id]['group_name']
        group_folder_id = get_dict_of_files(drive, parent_attachments_folder_id)[group_name]['id']
        upload_file(drive, attachment_name, byte_file, group_folder_id)

        keyboard_markup = ReplyKeyboardMarkup([['Add one more file', 'Finish']], one_time_keyboard=True)
        reply = update.message.reply_text('File was uploaded to <b>{}</b> group folder'.format(group_name),
                                          reply_markup=keyboard_markup,
                                          parse_mode='HTML')

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ADD_MORE

    except BadRequest as br:
        reply = update.message.reply_text('Telegram error: {}'.format(
            '{}.\nThe size of the file you want to add is {}MB.'.format(br,
                                                                        round(attachment.file_size / float(1 << 20), 2))
            if br.message == 'File is too big' else br))

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return ask_file(update, context)


def finish_attachments_adding(update, context):
    user_id = update.effective_user.id
    group_name = context.user_data[user_id]['group_name']

    notify(update, context,
           '<b>{}</b> added attachments to <b>{}</b> group.'.format(update.effective_user.full_name, group_name))

    return finish_conversation(update, context)


add_attachments_conv = ConversationHandler(
    entry_points=[CommandHandler('addattachments', start_add_attachments)],
    states={
        CHECK_PRESENT_GROUP:
            [MessageHandler(Filters.text & ~Filters.command, check_present_group)],

        GET_FILE:
            [MessageHandler(Filters.document, get_file),
             MessageHandler(Filters.photo, ask_file_not_photo)],

        ADD_MORE:
            [MessageHandler(Filters.text & Filters.regex('^Add one more file$'), ask_file),
             MessageHandler(Filters.text & Filters.regex('^Finish$'), finish_attachments_adding)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
