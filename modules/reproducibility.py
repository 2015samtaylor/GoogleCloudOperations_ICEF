import pandas as pd
import pysftp
import logging
import os
from queue import Queue
from threading import Lock
cnopts = pysftp.CnOpts()
cnopts.hostkeys = None


def read_file(file_path):

    # Get the file extension
    file_extension = file_path.split('.')[-1].lower()

    # Read the file based on its extension
    if file_extension == 'csv':
        df = pd.read_csv(file_path)
    elif file_extension == 'xlsx' or file_extension == 'xls':
        df = pd.read_excel(file_path)
    elif file_extension == 'json':
        df = pd.read_json(file_path)
    elif file_extension == 'txt':
        # You can specify additional parameters for reading text files
        df = pd.read_csv(file_path, sep='\t')  # Example: tab-separated text file
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    return df


# --------------------------------------------------

# def SFTP_conn(sftp_pass, folder_name):
    
#     cnopts = pysftp.CnOpts()
#     cnopts.hostkeys = None  # Disable host key checking
#     sftp = None
#     try:
#         sftp = pysftp.Connection(
#             host="sftp.iotaschools.org",
#             username="iota.sftp",
#             password=sftp_pass,
#             cnopts=cnopts,
#         )
        
#         logging.info('SFTP connection established successfully')

#         # Set local directory to save SFTP files to computer
#         local_directory = os.path.join('SFTP_folders', folder_name)
#         os.makedirs(local_directory, exist_ok=True)  # Create local directory if it doesn't exist
        
#         # Change to the remote directory
#         sftp.chdir(folder_name)
        
#         dir_contents = sftp.listdir()
#         logging.info(f'Dir contents of {folder_name}: {dir_contents}')


#         for file_name in dir_contents:
#             remote_file_path = os.path.join(folder_name, file_name)
#             local_file_path = os.path.join(local_directory, file_name)
            
#             # Log the paths to ensure they are correct
#             logging.info(f'Trying to download remote file: {remote_file_path} to local path: {local_file_path}')
#             print(f'Trying to download remote file: {remote_file_path} to local path: {local_file_path}')
            
#             sftp.get(file_name, local_file_path)
#             logging.info(f'File "{file_name}" downloaded to local directory "{local_directory}"')

#         logging.info(f'All files in folder "{folder_name}" downloaded to local directory "{local_directory}"')

        
#     except pysftp.ConnectionException as ce:
#         logging.error(f'Failed to establish SFTP connection: {ce}')
#     except pysftp.AuthenticationException as ae:
#         logging.error(f'Authentication error during SFTP connection: {ae}')
#     except Exception as e:
#         logging.error(f'An error occurred during SFTP operation: {e}')
#     finally:
#         if sftp:
#             pass
#             # sftp.close()  # Close the connection if it was successfully opened
#             logging.info('SFTP connection close passed')




# ----------------------------------------------------------

def pre_processing(df):
        
        df = df.fillna('')
        df = df.astype(str)
        df.columns = [col.replace('.', '_') for col in df.columns]

        return(df)

# ----------------------------------------------------
#Bucket names must contain only lowercase letters, numbers, hyphens (-), and cannot start or end with a hyphen

#Alter the SFTP folder name variable within the main func
#Rename the local dir to be the same convention
#Assume the SFTP_folder_name variable

def initial_schema_check(SFTP_folder_name):

    SFTP_folder_name = SFTP_folder_name.lower()
    SFTP_folder_name = SFTP_folder_name.replace('_', '-')

    return(SFTP_folder_name)


# ---------------------------------------------------------

def remove_extension_from_file(file_name):

    parts = file_name.split('.')  # Split the filename by dot
    if len(parts) > 1:  # Check if there is an extension
        return '.'.join(parts[:-1])  # Join all parts except the last one
    else:
        return file_name  # If there's no extension, return the original filename




class SFTPConnectionPool:
    def __init__(self, host, username, password, cnopts, max_connections=5):
        self.host = host
        self.username = username
        self.password = password
        self.cnopts = cnopts
        self.max_connections = max_connections
        self.pool = Queue(max_connections)
        self.lock = Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        for _ in range(self.max_connections):
            self.pool.put(self._create_new_connection())

    def _create_new_connection(self):
        return pysftp.Connection(
            host=self.host,
            username=self.username,
            password=self.password,
            cnopts=self.cnopts
        )

    def get_connection(self):
        with self.lock:
            if self.pool.empty():
                return self._create_new_connection()
            return self.pool.get()

    def return_connection(self, conn):
        with self.lock:
            if self.pool.full():
                conn.close()
            else:
                self.pool.put(conn)

    def close_all_connections(self):
        while not self.pool.empty():
            conn = self.pool.get()
            conn.close()
            logging.info('SFTP connection closed')


def SFTP_conn(folder_name, sftp_pool):
    sftp = None
    try:
        # Get a connection from the pool
        sftp = sftp_pool.get_connection()
        logging.info('SFTP connection established successfully')

        local_directory = os.path.join('SFTP_folders', folder_name)
        os.makedirs(local_directory, exist_ok=True)  # Create local directory if it doesn't exist

        sftp.chdir(folder_name)
        dir_contents = sftp.listdir()
        logging.info(f'Dir contents of {folder_name}: {dir_contents}')

        for file_name in dir_contents:
            remote_file_path = os.path.join(folder_name, file_name)
            local_file_path = os.path.join(local_directory, file_name)

            logging.info(f'Trying to download remote file: {remote_file_path} to local path: {local_file_path}')
            print(f'Trying to download remote file: {remote_file_path} to local path: {local_file_path}')

            sftp.get(file_name, local_file_path)
            logging.info(f'File "{file_name}" downloaded to local directory "{local_directory}"')

        logging.info(f'All files in folder "{folder_name}" downloaded to local directory "{local_directory}"')

    except pysftp.ConnectionException as ce:
        logging.error(f'Failed to establish SFTP connection: {ce}')
    except pysftp.AuthenticationException as ae:
        logging.error(f'Authentication error during SFTP connection: {ae}')
    except Exception as e:
        logging.error(f'An error occurred during SFTP operation: {e}')
    finally:
        if sftp:
            sftp_pool.return_connection(sftp)  # Return the connection to the pool
            logging.info('SFTP connection returned to pool')

