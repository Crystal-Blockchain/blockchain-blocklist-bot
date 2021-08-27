The blockchain blocklist bot is the telegram bot which allows to add and remove hashes of addresses recommended to blocklist to a Google Sheet workbook.  
It also allows to add attachments to a Google Drive folder.

Python version required - python 3.5 and higher (wasn't tested on lower versions).  
Modules required are located in ```requirements.txt``` 

**Google part:**

* Initially you should create a workbook with a sheet with columns [address, currency, group_name, group_description, reported_by, telegram_user_id, utc_time, attachments] and a folder in Google Drive.
* For the first time you also need to set up authentication for:
    * Google Sheet (module pygsheet) - [link](https://pygsheets.readthedocs.io/en/stable/authorization.html)
    * Google Drive (module pydrive) - [link](https://pythonhosted.org/PyDrive/oauth.html)
* Move the received auth files to the work directory. Don't change the file names.
* In results you should have the following auth files in the work directory:
    * sheets.googleapis.com-python.json
    * mycreds.txt
    * client_secret.json
    * client_secrets.json (the copy of client_secret.json)
  

**Telegram part:**  
* [Create](https://core.telegram.org/bots#6-botfather) a bot and get its token
* Set the commands as an example:  
```
showdescription - show a description for any of the added groups of addresses
showaddresses - show addresses added by you or all users
checkaddresses - check if addresses are present in the table
addaddresses - add addresses to the table
addattachments - add an attachment to a group of addresses
removeaddresses - remove addresses added by the user
cancel - cancel the conversation any time
about - the detailed info about the bot
```
  

**Python part:**
* Install modules from the ```requirements.txt```
* Fill up the ```config.py``` from the ```config.sample.py``` with your parameters
Entry-point:  ```python main.py```


**Allowed users and notification receivers csv:**
* Add yourself (username OR telegram id) manually to the allowed users csv (allowed_users_df.csv by default)
* The allowed users csv can be filled both: manually or through the /admin command in the bot. You need to fill telegram_user_id OR telegram_user_nickname (username) column.
* The notification receivers csv can be filled both manually and through the /admin command in the bot. You need to fill telegram_user_id and comment columns.


**Administration:**  
The bot has the hidden admin command. 
To execute this command you should type /admin - there will be no answer, but you should send the message with the password set in config.py file.
After the password is received you will automatically enter the administration settings menu.
