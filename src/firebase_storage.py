import firebase_admin
from firebase_admin import storage
from os import path, listdir, getenv
from google.api_core import retry
from src.logger import Logger
import src.helper as hlpr
import dotenv

dotenv.load_dotenv()


class FirebaseStorage:
    def __init__(self, outpath: str) -> None:
        if not outpath:
            raise Exception(f"outpath invalid [{outpath}]")
        if outpath.find("attachments") > 0:
            self.project_path = outpath.split("attachments")[0]
        else:
            self.project_path = outpath
        self.logger = Logger(self.__class__.__name__)
        hlpr.create_attachments_path(self.project_path)
        self._STORAGE_BUCKET = getenv("FIREBASE_STORAGE_BUCKET")
        self.bucket = self.__get_bucket()

    def __generate_filename(self, epoch_generation, _filename: str):
        """
            :dateGeneration: epoch in micro secondes (1643923130189601)
            :filename: filename (cadre_photos/maphoto.jpg)

            msg_id + _ + msg_epoch_ms + _ + str(count_attachments) + extension
            
            lambda x: x.split("_")[1] if x and len(x.split("_")) > 2 else "000000000000000"
        """
        # Todo: verifier si fichier extension est valide
        LEN_EPOCH_MS = len("1643923130189")
        epoch_ms = str(epoch_generation)[:LEN_EPOCH_MS]
        path_without_ext, extension = path.splitext(_filename)
        filename = path.basename(path_without_ext.replace("_", "").replace(" ", ""))
        return str(epoch_generation) + "_" + epoch_ms + "_" + filename + extension

    def __get_bucket(self):
        firebase_admin.initialize_app(options={
            'storageBucket': self._STORAGE_BUCKET
        })

        return storage.bucket()

        # blobs = bucket.list_blobs(prefix="cadre_photos/")
        # listBlobs = list(blobs)

        # # blob C:\Python38\Lib\site-packages\google\cloud\storage\blob.py
        # for blob in listBlobs:
        #     print("----- " + blob.id + " -----")
        #     print("-- name: " + blob.name)
        #     id = self.generate_filename(blob.generation, blob.name)
        #     print("-- generated_filename: " + id)
        #     if id:
        #         blob.download_to_filename(id, start=0, end=blob.size)

    def __get_all_blobs_uploaded(self):
        try:
            blobs = self.bucket.list_blobs(prefix="cadre_photos/", timeout=10,
                                           retry=retry.Retry(initial=2, maximum=4, deadline=10))
            listBlobs = list(blobs)
            self.logger.info("__get_all_blobs_uploaded", f"{len(listBlobs)} blobs found in 'cadre_photos/'")
            return listBlobs
        except Exception as e:
            self.logger.error("__get_all_blobs_uploaded", "Exception", e)
        return []

    def __is_file_already_downloaded(self, msg_id, files_downloaded):
        for f in files_downloaded:
            if f.startswith(msg_id):
                return True
        return False

    def download_new_medias(self):
        """
            Download new video/image uploaded
        """
        if self.bucket:
            listBlobs = self.__get_all_blobs_uploaded()
            if listBlobs and len(listBlobs) > 0:
                path_files_downloaded = []
                try:
                    files_downloaded = listdir(hlpr.get_path_attachments(self.project_path))
                    # blob C:\Python38\Lib\site-packages\google\cloud\storage\blob.py
                    for blob in listBlobs:
                        # print("----- " + blob.id + " -----")
                        # print("-- name: " + blob.name)
                        ext = hlpr.get_file_extension_if_valid(blob.name)
                        if not ext:
                            self.logger.info("download_new_medias", f"Bad file extension[{blob.name}]")
                            continue
                        id = str(blob.generation)
                        if not self.__is_file_already_downloaded(id, files_downloaded):
                            filename = self.__generate_filename(id, blob.name)
                            if filename:
                                filepath = path.join(hlpr.get_path_attachments(self.project_path), filename)
                                blob.download_to_filename(filepath, start=0, end=blob.size)
                                path_files_downloaded.append(filepath)
                                self.logger.info("download_new_medias", f"filename[{filename}] downloaded")
                except Exception as e:
                    self.logger.error("download_new_medias", "Exception", e)
                return path_files_downloaded
        return None
    
