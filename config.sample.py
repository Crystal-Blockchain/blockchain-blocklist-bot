telegram_bot_token = ''  # type: str
# token for telegram bot given to you by BotFather

bot_name = ''  # type: str
# name of the bot that will be used in  start message and logfile name,

bot_about = ''  # type: str
# text to be shown in answer to /about command

answer_to_forbidden_user = ''  # type: str
# text to be shown in answer to any command (except /about) for user that is not in the allowed list

parent_attachments_folder_id = ''  # type: str
# id of the folder on Google Drive where folders for attachments for each group will be created

workbook_sheet_id = ''  # type: str
# id of the workbook on Google Sheet where all collected addresses will be stored

workbook_name = ''  # type: str
# name of the workbook on Google Sheet where all collected addresses will be stored

worksheet_name = ''  # type: str
# name of the sheet of the workbook on Google Sheet where all collected addresses will be stored

logs_location = '{}_bot_logs.log'.format(bot_name)  # type: str
# path and file name for bot logs

notification_receivers_df_location_name = 'notification_receivers_df.csv'  # type: str
# path and file name of the csv with list of added address notification receivers

allowed_users_df_location_name = 'allowed_users_df.csv'  # type: str
# path and file name of the csv with allowed to interact users

error_message_receiver_telegram_user_id = 0  # type: int
# telegram user id of the person who will receive error messages

admin_password = ''  # type: str
# password for entering administration settings
