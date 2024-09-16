from datetime import datetime as dt, timedelta
from os import path, mkdir
import pytz


def _is_valid_extension_for_image(ext: str) -> bool:
    if ext:
        return ext.lower() in [".png", ".jpeg", ".jpg"]

    return False


def _is_valid_extension_for_video(ext: str) -> bool:
    if ext:
        return ext.lower() in [".avi", ".mp4"]

    return False


def get_file_extension_if_valid(filename) -> str:
    """
        photos/videos
    """
    if filename:
        ext = path.splitext(filename)[1]
        if _is_valid_extension_for_image(ext) or _is_valid_extension_for_video(ext):
            return ext
    return None


def is_valid_video_file(filename):
    """
        Checks if the filename has a valid video file extension
    """
    if filename:
        ext = path.splitext(filename)[1]
        return _is_valid_extension_for_video(ext)
    return False


def is_valid_image_file(filename):
    """
        Checks if the filename is a valid image file
    """
    if filename:
        ext = path.splitext(filename)[1]
        return _is_valid_extension_for_image(ext)
    return False


def is_new_image(imageName):
    """
        returns True if today - date < 24h
        False otherwise
    """
    EXPIRATION_NEW = timedelta(hours=24)  # 12h
    filename = path.basename(imageName)
    if filename and len(filename.split("_")) > 2:
        date = filename.split("_")[1]
        tmstp = -1
        try:
            tmstp = int(date) / 1000  # ajouter check longueur
            if (dt.now() - dt.fromtimestamp(tmstp)) < EXPIRATION_NEW:
                return True
        except Exception as e:
            print("is_new_image - parsing error: ", e)

        return False


# region Date & time

def get_time_in_alberta():
    tz = pytz.timezone("Canada/Mountain")
    # return dt.now(tz).strftime("%H:%M:%S")
    return dt.now(tz).strftime("%H:%M")


def get_current_time():
    """
        Returns timestamp in milliseconds
    """
    return int(dt.now().timestamp() * 1000)


def get_date_yyyymmdd():
    return dt.now().strftime("%Y/%m/%d")


def get_date_yyyymmdd_minus_3_weeks():
    return (dt.now() - timedelta(weeks=3)).strftime("%Y/%m/%d")


# endregion

# region Video

import cv2


def get_video_infos(file_path):
    """
        Returns error, frames, fps
    """
    MAX_FRAMES = 500
    error, frames, fps = None, [], 0
    i = 0
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            error = "not isOpened"
        else:
            fps = cap.get(cv2.CAP_PROP_FPS)
            # total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            while cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # take 1 out of 2 frames
                    if i % 2 == 0:
                        frames.append(frame)
                        if len(frames) > MAX_FRAMES:
                            break
                    i += 1
                else:
                    break

    except Exception as e:
        frames = []
        fps = 0
        error = e
    finally:
        if cap and cap.isOpened():
            cap.release()

    return error, frames, fps


# endregion

# region Path

def get_path_attachments(projectPath):
    # abs_path = "\\".join(os.path.abspath(__file__).split('\\')[:-2])
    return path.join(projectPath, "attachments")


def create_attachments_path(projectPath):
    p = get_path_attachments(projectPath)
    if not path.exists(p):
        print("hlpr.create_attachments_path", f"creating path {p}...")
        mkdir(p)
        print("hlpr.create_attachments_path", f"Path created")

# endregion
