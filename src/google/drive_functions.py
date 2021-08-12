from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from src.utils import parent_attachments_folder_id


def drive_auth():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("mycreds.txt")

    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile("mycreds.txt")
    return GoogleDrive(gauth)


def get_dict_of_files(drive_object, parent_folder_id):
    files_dict = {}
    file_list = drive_object.ListFile({'q': "'{}' in parents and trashed=False".format(parent_folder_id)}).GetList()

    for file in file_list:
        files_dict[file['title']] = {'id': file['id'], 'link': file['alternateLink']}

    return files_dict


def create_folder(drive_object, folder_name, parent_folder_id):
    dict_of_files = get_dict_of_files(drive_object, parent_folder_id)
    for title, params in dict_of_files.items():
        if title == folder_name:
            return params['link']
    folder = drive_object.CreateFile({'title': folder_name,
                                      "parents": [{"id": parent_folder_id}],
                                      "mimeType": "application/vnd.google-apps.folder"})
    folder.Upload()
    return folder['alternateLink']


def upload_file(drive_object, file_name, file_as_bytes, parent_folder_id):
    gfile = drive_object.CreateFile({'title': file_name,
                                     "parents": [{"id": parent_folder_id}]})
    gfile.content = file_as_bytes
    gfile.Upload()


def change_color_for_folders_without_addresses(list_of_left_groups):
    file_list = drive.ListFile({'q': "'{}' in parents and trashed=False".
                               format(parent_attachments_folder_id)}).GetList()

    for file in file_list:
        if file['title'] not in list_of_left_groups:
            if file['iconLink'] != 'https://drive-thirdparty.googleusercontent.com' \
                                   '/16/type/application/vnd.google-apps.folder+27+shared':
                file['folderColorRgb'] = '#f83a22'
                file.Upload()
        else:
            if file['iconLink'] != 'https://drive-thirdparty.googleusercontent.com/' \
                                   '16/type/application/vnd.google-apps.folder+shared':
                file['folderColorRgb'] = '#8f8f8f'
                file.Upload()


drive = drive_auth()
