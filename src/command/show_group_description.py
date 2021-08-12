from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup

from src.google.sheets_functions import *
from src.utils import *

CHECK_PRESENT_GROUP, SHOW_GROUP_DESCRIPTION, ANOTHER_GROUP = range(3)


def start_show_description(update, context):
    if check_user(update, context):
        pass
    else:
        return ConversationHandler.END

    user_id = update.effective_user.id
    context.user_data[user_id] = {}

    worksheet = open_worksheet(workbook_name, worksheet_name)
    ws_df = worksheet.get_as_df()
    present_group_names = [str(name) for name
                           in ws_df.sort_values('utc_time', ascending=False)[
                               'group_name'].drop_duplicates().to_list()]

    context.user_data[user_id]['ws_df'] = ws_df
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
                     '<b>{}</b>\n\n' \
                     'Please, choose one of presents or type the name of the group ' \
                     'which descriptions you want me to show:' \
            .format(
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
                'Select or type the group name.\n'
                'PS There is the limitation of the number of buttons. '
                'You can just type your group name or copy it from the file.',
                reply_markup=keyboard,
                parse_mode='HTML')
            reply.text += '\n' + file_obj.name + '\n' + reply2.text

        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return CHECK_PRESENT_GROUP
    else:
        reply = update.message.reply_text(
            'There is no existing addresses group in table.')
        log_this(update, inspect.currentframe().f_code.co_name, reply)
        return finish_conversation(update, context)


def check_present_group(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    present_group_names = context.user_data[user_id]['present_group_names']

    log_this(update, inspect.currentframe().f_code.co_name)
    if text in present_group_names or text == 'Show all':
        context.user_data[user_id]['group_name'] = text
        return sent_description(update, context)
    else:
        context.user_data[user_id]['group_name_chosen'] = True
        return ask_group_name(update, context)


def sent_description(update, context):
    user_id = update.effective_user.id
    group_name = context.user_data[user_id]['group_name']
    ws_df = context.user_data[user_id]['ws_df']
    ws_df['group_name'] = ws_df['group_name'].astype(str)
    keyboard = ReplyKeyboardMarkup([['Show another group description', 'Finish']], one_time_keyboard=True)
    reply = update.message.reply_text('<b>{}</b> description:\n\n{}'.format(
        group_name,
        ws_df.loc[ws_df['group_name'] == group_name, 'group_description'].values[0]),
        reply_markup=keyboard,
        parse_mode='HTML')
    context.user_data[user_id]['group_name_chosen'] = False

    log_this(update, inspect.currentframe().f_code.co_name, reply)
    return ANOTHER_GROUP


show_description_conv = ConversationHandler(
    entry_points=[CommandHandler('show_description', start_show_description)],
    states={
        CHECK_PRESENT_GROUP:
            [MessageHandler(Filters.text & ~Filters.command, check_present_group)],

        SHOW_GROUP_DESCRIPTION:
            [MessageHandler(Filters.text & ~Filters.command, sent_description)],

        ANOTHER_GROUP:
            [MessageHandler(Filters.text & Filters.regex('^Show another group description$'), ask_group_name),
             MessageHandler(Filters.text & Filters.regex('^Finish$'), finish_conversation)]
    },
    fallbacks=[CommandHandler('cancel', cancel),
               MessageHandler(Filters.command, fallback)],
    allow_reentry=True)
