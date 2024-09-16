from os import path, listdir
import base64
import time
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import Error, HttpError
import src.helper as hlpr
from src.logger import Logger
from datetime import datetime as dt


class GmailApi():
    # If modifying these scopes, delete the file token.json.
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, outpath: str, label_id: str) -> None:
        if not outpath:
            raise Error(f"outpath invalid [{outpath}]")
        if outpath.find("attachments") > 0:
            self.project_path = outpath.split("attachments")[0]
        else:
            self.project_path = outpath
        self._label_id = label_id
        self.logger = Logger(self.__class__.__name__)
        hlpr.create_attachments_path(self.project_path)
        self.service = self.__get_service()

    def __download_attachments(self, user_id, msg):
        msg_id = ""
        try:
            path_files_downloaded = []
            msg_id = msg["id"]
            self.logger.info("__download_attachments", "Start", f"Message_id[{msg_id}]")
            message = self.service.users().messages().get(userId=user_id, id=msg_id).execute()
            if message:
                msg_date = message["internalDate"]
                count_attachments = 0
                self.logger.info("__download_attachments",
                                 f"Message[{msg_id}], {dt.fromtimestamp(int(msg_date) / 1000)}")
                for part in message['payload']['parts']:
                    if 'filename' in part and part['filename'] and part['mimeType'] != 'text/plain':
                        if 'attachmentId' in part['body']:
                            att_id = part['body']['attachmentId']
                            self.logger.info("__download_attachments",
                                             f"Getting attachment: partId[{part['partId']}], name[{part['filename']}]...")
                            att = None
                            retry_count = 0
                            while retry_count >= 0 and retry_count < 3:
                                try:
                                    att = self.service.users().messages().attachments().get(userId=user_id,
                                                                                            messageId=msg_id,
                                                                                            id=att_id).execute()
                                    retry_count = -1
                                except HttpError as error:
                                    self.logger.error("__download_attachments", "attchment HttpError", error)
                                    retry_count += 1
                                except Exception as e:
                                    self.logger.error("__download_attachments", "attchment Exception", e)
                                    retry_count += 1
                                if retry_count > 0 and retry_count < 3:
                                    self.logger.info("__download_attachments", "Waiting before next try...")
                                    time.sleep(10)
                                    self.logger.info("__download_attachments", f"...retry: {retry_count}")
                            if att and 'data' in att:
                                ext = hlpr.get_file_extension_if_valid(part['filename'])
                                if not ext:
                                    self.logger.info("__download_attachments",
                                                     f"Bad file extension[{part['filename']}]")
                                    continue
                                count_attachments += 1
                                file_data = base64.urlsafe_b64decode(att['data'].encode('UTF-8'))
                                filename = msg_id + "_" + msg_date + "_" + str(count_attachments) + ext
                                filepath = path.join(hlpr.get_path_attachments(self.project_path), filename)
                                with open(filepath, "wb") as f:
                                    f.write(file_data)
                                path_files_downloaded.append(filepath)
                                self.logger.info("__download_attachments", f"filename[{filename}] downloaded",
                                                 f"attachment: partId[{part['partId']}], name[{part['filename']}]")
                            else:
                                self.logger.info("__download_attachments", "attachment not found", att)
                return path_files_downloaded
            else:
                self.logger.warning("__download_attachments", "message null", message)
        except HttpError as error:
            self.logger.error("__download_attachments", "HttpError", error)
        except Exception as e:
            self.logger.error("__download_attachments", "Exception", e)
        finally:
            self.logger.info("__download_attachments", "End", f"Message_id[{msg_id}]")

        return None

    def __get_service(self):
        """Shows basic usage of the Gmail API.
        Lists the user's Gmail labels.
        """
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        # if os.path.exists('token.json'):
        p_token = path.join(path.splitext(self.project_path)[0], "token.json")
        if path.exists(p_token):
            self.logger.info("__get_service", "token exists")
            # creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            creds = Credentials.from_authorized_user_file(p_token, self.SCOPES)
        else:
            self.logger.warning("__get_service", "token doesn't exist", p_token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info("__get_service", "refreshing credentials...")
                try:
                    creds.refresh(Request())
                    self.logger.info("__get_service", "credentials refreshed")
                except RefreshError as refreshError:
                    self.logger.error("__get_service", "RefreshError, error refreshing token", refreshError)
                except Exception as e:
                    self.logger.error("__get_service", "Exception, error refreshing token", e)
            else:
                p_creds = path.join(path.splitext(self.project_path)[0], "credentials.json")
                # flow = InstalledAppFlow.from_client_secrets_file(
                #     'credentials.json', self.SCOPES)
                flow = InstalledAppFlow.from_client_secrets_file(p_creds, self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(p_token, 'w') as token:
                token.write(creds.to_json())

        try:
            # Call the Gmail API
            service = build('gmail', 'v1', credentials=creds)
            return service
            # https://stackoverflow.com/questions/25832631/download-attachments-from-gmail-using-gmail-api

        except HttpError as error:
            self.logger.error("__get_service", "HttpError, build", error)
        except Exception as e:
            self.logger.error("__get_service", "Exception, build", e)

    def __get_messages_in_label_cadre_photo(self):
        fetch = True
        messages_list = []
        nextPageToken = None
        try:
            # within last 3 weeks
            d_3w_before = hlpr.get_date_yyyymmdd_minus_3_weeks()
            query = f"after:{d_3w_before} before:{hlpr.get_date_yyyymmdd()}"
            while fetch:
                messages_in_label = self.service.users().messages().list(userId="me", labelIds=[self._label_id],
                                                                         q=query, maxResults=500,
                                                                         pageToken=nextPageToken).execute()
                if messages_in_label and 'messages' in messages_in_label:
                    messages_list.extend(messages_in_label['messages'])
                    # print(messages_in_label)
                    if not ('nextPageToken' in messages_in_label and messages_in_label['nextPageToken']):
                        fetch = False
                        nextPageToken = None
                    else:
                        nextPageToken = messages_in_label['nextPageToken']
                else:
                    fetch = False

            self.logger.info("__get_messages_in_label_cadre_photo",
                             f"{len(messages_list)} message(s) found in label since {d_3w_before}")
        except HttpError as error:
            self.logger.error("__get_messages_in_label_cadre_photo", "HttpError", error)
        except Exception as error:
            self.logger.error("__get_messages_in_label_cadre_photo", "Exception", error)

        return messages_list

    def __is_message_already_downloaded(self, msg_id, files_downloaded):
        for f in files_downloaded:
            if f.startswith(msg_id):
                return True
        return False

    def __remove_messages_if_exists(self, messages):
        filtered_messages = []
        if messages:
            files_downloaded = listdir(hlpr.get_path_attachments(self.project_path))
            if messages and len(messages) > 0:
                for m in messages:
                    id = m['id']
                    if not self.__is_message_already_downloaded(id, files_downloaded):
                        filtered_messages.append(m)
            self.logger.info("__remove_messages_if_exists", f"{len(filtered_messages)} new message(s)")
        return filtered_messages

    def download_new_images(self):
        if self.service:
            messages = self.__get_messages_in_label_cadre_photo()
            if messages:
                new_messages = self.__remove_messages_if_exists(messages)
                new_files = []
                for msg in new_messages:
                    new_downloads = self.__download_attachments("me", msg)
                    if new_downloads:
                        new_files.extend(new_downloads)
                return new_files
        return None

    def get_all_labels(self):
        results = self.service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        if not labels:
            print('No labels found.')
            return
        print('Labels:')
        for label in labels:
            print(label['id'], " - ", label['name'])

# if __name__ == '__main__':
#     main()
