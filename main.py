import pathlib
import pandas as pd
import dropbox
import os
import sys
import re
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import AuthError
from tqdm import tqdm

directory = ""

APP_KEY = "tazmj3z0w1ps942"
APP_SECRET = "gfb5o5gjo6krlkz"
DROPBOX_ACCESS_TOKEN = ''
DBMID = 'dbmid:AADG0vV5jytTmJYHxONlD4JODdLNLssdWyA'
_team_name_space_id = '9796794208'

sys.tracebacklimit = 0
class Found(Exception): pass

def update_directory():
    with open('config.txt') as f:
        lines = f.readlines()
    global directory, DBMID, DROPBOX_ACCESS_TOKEN, _team_name_space_id

    lines = [line.rstrip('\n') for line in lines]

    directory = lines[0]
    if len(lines) > 1:
        DROPBOX_ACCESS_TOKEN = lines[1]
    if len(lines) > 2:
        DBMID = lines[2]
    if len(lines) > 3:
        _team_name_space_id = lines[3]

def delete_file(filename):
    try: os.remove(os.path.join(directory,filename))
    except: raise RuntimeError(f"ERROR: {filename} could not be deleted as it was not found")

def dropbox_connect(token,id):
    """
    Create a connection to Dropbox.
    
    Returns:
        dbx: a connection to the users dropbox
    """
    
    try:
        dbx = dropbox.DropboxTeam(token).with_path_root(dropbox.common.PathRoot.root(_team_name_space_id)).as_admin(id) 
        # dbx = dropbox.Dropbox(token)
    except:
        print('Error connecting to Dropbox with access token')
        auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
        authorize_url = auth_flow.start()
        print("1. Go to: " + authorize_url)
        print("2. Click \"Allow\" (you might have to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()

        try:
            oauth_result = auth_flow.finish(auth_code)
        except Exception as e:
            print('Error: %s' % (e,))
            exit(1)

        # Update config.txt with new access code
        with open("config.txt","r+") as f:
            lines = f.readlines()
            f.seek(0)
            if(len(lines)>1): lines[1] = oauth_result.access_token
            else: lines.append(oauth_result.access_token) 
            lines = [f"{line}\n" for line in lines]
            f.writelines(lines)
            f.truncate()
        dbx = dropbox.DropboxTeam(oauth2_access_token=oauth_result.access_token).with_path_root(dropbox.common.PathRoot.root(_team_name_space_id)).as_admin(id) 
    return dbx

def dropbox_upload_file(dbx, local_path, local_file, dropbox_file_path):
    """
    Upload a file from the local machine to a path in the Dropbox app directory.

    Args:
        dbx: Dropbox connection
        local_path (str): The path to the local file.
        local_file (str): The name of the local file.
        dropbox_file_path (str): The path to the file in the Dropbox app directory.

    Example:
        dropbox_upload_file('.', 'test.csv', '/stuff/test.csv')

    Returns:
        meta: The Dropbox file metadata.
    """

    try:
        local_file_path = pathlib.Path(local_path) / local_file

        with local_file_path.open("rb") as f:
            meta = dbx.files_upload(f.read(), dropbox_file_path, mode=dropbox.files.WriteMode("overwrite"))

            return meta
    except Exception as e:
        print('Error uploading file to Dropbox: ' + str(e))



def find_folder(dbx, name, category):
    result = dbx.files_list_folder("")

    folder_list = []

    def process_entries(entries):
        for entry in entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                folder_list.append(entry.name)

    process_entries(result.entries)
    
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        process_entries(result.entries)
    
    path = ""

    try:
        for folder_name in tqdm(folder_list, ncols=100, desc="Searching for "+name):
            for entry in dbx.files_list_folder('/'+folder_name).entries:
                if name in entry.name:
                    path = '/' + folder_name + '/' + entry.name
                    raise Found

    except Found:
        path += '/Personal'
        proof_of_address = ["Utility", "Car Insurance", "Vehicle Registration", "Lease", "Mortgage Statement"]
        if category in proof_of_address:
            category = 'Proof of Address'
        for entry in dbx.files_list_folder('/'+path).entries:
            if category in entry.name:
                path += '/' + entry.name
                break
        
        else:
            categories = ["Utility", "Phone", "Bank", "Car Insurance", "Vehicle Registration", "Lease", "Mortgage Statement"]
            print(f"Please choose a document category that's one of {categories}")
            raise RuntimeError(f"❌ ERROR: {name}'s reseller folder doesn't contain a folder for {category}")

        # match category:
        #     case 'Phone' | 'Utility':
        #         path += '/Utility & Phone Bills'
        #     case 'Bank':
        #         path += '/Bank Statements'
        #     case 'Mortgage Statement' | 'Car Insurance':
        #         path += '/Proof of Address'

        return path

    else:
        raise RuntimeError(f"❌ ERROR: no reseller named {name} has been found")

def main():
    dbx = dropbox_connect(DROPBOX_ACCESS_TOKEN, DBMID)
    directory_bytes = os.fsencode(directory)
    success_count = 0
    total_count = 0
    missed = []
    for file in os.listdir(directory_bytes):
        total_count += 1
        filename = os.fsdecode(file)
        # Checking for files that look like ("00-00-00 - John Doe - Bank")
        m = re.match("\d\d-\d\d-\d\d - (\w* \w*) - (\w* ?\w*)", filename)
        if m is not None:
            name = m.group(1)
            category = m.group(2)
            dropbox_folder = find_folder(dbx, name, category)
            try:
                # Verify that the folder exists before attempting anything
                dbx.files_list_folder(dropbox_folder).entries
            except: 
                raise RuntimeError(f"❌ ERROR: folder {dropbox_folder} not found")
            else:
                print(f"✔️ Success: uploading {filename} to {dropbox_folder}")
                dropbox_upload_file(dbx, directory, filename, dropbox_folder + "/" + filename)
                delete_file(filename)
                success_count += 1
        else:
            missed.append(filename)

    if success_count != 0:  print(f"👍 Successfully uploaded {success_count} documents to dropbox!")
    if missed != []:        print(f"Didn't upload files {missed} \nMaybe check for unneccessary spaces? Or remove middle names?")
    if success_count == 0 and missed == []: print(f"Found {total_count} files, stopping upload")

def run_tests():
    dbx = dropbox_connect(DROPBOX_ACCESS_TOKEN, DBMID)

    print(dbx.users_get_current_account())
    print(dbx.files_list_folder(""))
    print(find_folder(dbx, "Arthur Drexler", "Phone"))

if __name__ == '__main__':
    try:
        update_directory()
        main()
    except Exception as e:
        print(e)
    finally:
        input("Press Enter to quit...")