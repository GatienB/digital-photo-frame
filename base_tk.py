import tkinter
from tkinter import Event, Frame, Label
from PIL import Image, ImageTk, ExifTags
from src.gmail_api import GmailApi
from src.firebase_storage import FirebaseStorage
from os import listdir, path, getenv
import src.helper as hlpr
from src.logger import Logger
from src.weather_com import WeatherDotCom
from threading import Thread
import cv2
import numpy as np
from src.zoom import Zoom, ZoomAction, ZoomNavigationDirections
from dotenv import load_dotenv

load_dotenv()

GMAIL_LABEL_ID = getenv("GMAIL_LABEL_ID")
PROJECT_PATH = getenv("PROJECT_PATH")

# Zoom
VERSION = "6.0.0"

MAIL_REFRESH_INTERVAL_MS = 1000 * 60 * 30  # 30min
SLIDESHOW_INTERVAL_MS = 1000 * 10  # 10s
WEATHER_REFRESH_INTERVAL_MS = 1000 * 60 * 15  # 15min

BACKGROUND_NEW_IMAGE = "green"
BORDER_SIZE_NEW_IMAGE = 3

RESTART_SLIDESHOW = "RESTART_SLIDESHOW"
PREVIOUS_IMAGE = "PREVIOUS_IMAGE"
NEXT_IMAGE = "NEXT_IMAGE"
LIST_ACTIONS = [RESTART_SLIDESHOW, PREVIOUS_IMAGE, NEXT_IMAGE]


class SlideShow():
    NO_IMAGE_LABEL = "No photo"

    def __init__(self):
        self.PROJECT_PATH = PROJECT_PATH
        self.video_frames, self.index_video_frame = [], -1
        self.logger = Logger(self.__class__.__name__)
        self.logger.info("__init__", f"Slideshow Version[{VERSION}]")
        self.is_paused = False
        self.label_pause = None
        self.list_images = []
        self.image_name = None
        self.label = None
        self.label_image = None
        self.canvas = None
        self.frame = None
        self.identifier_change_image = None
        self.main_window, self.width, self.height = self.__create_main_window()
        self.zoom_helper = Zoom()
        self.weatherCom = WeatherDotCom("Hussar")
        self.gmail_api = GmailApi(self.PROJECT_PATH, GMAIL_LABEL_ID)
        self.firebase = FirebaseStorage(self.PROJECT_PATH)
        self.list_images = self.__get_saved_images()
        self.logger.info("__init___", f"{len(self.list_images)} images taken from cache")

    def __get_index(self, item_to_find, items):
        try:
            return items.index(item_to_find)
        except ValueError:
            return -1

    def __play_video(self, frame_delay_ms, time_start_ms):
        # pause non pris en compte car en pause = on ne defile plus le slideshow
        if self.video_frames:
            nb_frames = len(self.video_frames)
            if nb_frames > 0:
                if self.label_image["text"] == self.NO_IMAGE_LABEL:
                    self.label_image["text"] = None
                self.index_video_frame = self.index_video_frame + 1
                # pause pris en compte ici, car on joue la video meme si en pause
                if not self.is_paused and self.index_video_frame >= nb_frames and (
                        hlpr.get_current_time() - time_start_ms > SLIDESHOW_INTERVAL_MS):
                    self.logger.debug("__play_video", "playing video enough, changing image")
                    del self.video_frames
                    self.video_frames = []
                    self.index_video_frame = -1
                    self.__change_image()
                    return
                if self.index_video_frame < 0 or self.index_video_frame >= nb_frames:
                    self.index_video_frame = 0

                img_array = self.video_frames[self.index_video_frame]
                pilImage = Image.fromarray(img_array)

                self.showPIL(pilImage)
            else:
                # no frames, calling change image to skip video
                self.logger.info("__play_video", "No frames")
                if self.label_image["text"] != self.NO_IMAGE_LABEL:
                    self.label_image["text"] = self.NO_IMAGE_LABEL
                self.__change_image()
                return

        self.identifier_change_image = self.main_window.after(frame_delay_ms,
                                                              lambda: self.__play_video(frame_delay_ms, time_start_ms))

    def __change_image(self, action: str = None):
        self.__set_label_time(hlpr.get_time_in_alberta())
        call_again = True

        if not self.is_paused or action in LIST_ACTIONS:
            self.zoom_helper.reset()
            nb_images = len(self.list_images)
            if nb_images > 0:
                if self.label_image["text"] == self.NO_IMAGE_LABEL:
                    self.label_image["text"] = None
                next_index = -1
                if action in LIST_ACTIONS:
                    if self.identifier_change_image:
                        self.main_window.after_cancel(self.identifier_change_image)
                    if action == RESTART_SLIDESHOW:
                        next_index = 0
                    elif action == PREVIOUS_IMAGE:
                        next_index = self.__get_index(self.image_name, self.list_images) - 1
                        if next_index < 0:
                            next_index = nb_images - 1
                    elif action == NEXT_IMAGE:
                        next_index = self.__get_index(self.image_name, self.list_images) + 1
                        if next_index >= nb_images:
                            next_index = 0
                else:
                    if self.image_name:
                        next_index = self.__get_index(self.image_name, self.list_images) + 1

                if next_index < 0 or next_index >= nb_images:
                    next_index = 0

                self.image_name = self.list_images[next_index]
                if hlpr.is_valid_video_file(self.image_name):
                    del self.video_frames
                    self.video_frames = []
                    self.index_video_frame = -1
                    err, frames, fps = hlpr.get_video_infos(self.image_name)
                    if not err and frames and fps > 0:
                        self.video_frames = frames
                        del frames
                        # reducing delay by 4 for fluidity reason on raspberry
                        self.__play_video(int((1000 / fps) * 0.25), hlpr.get_current_time())
                        call_again = False
                    else:
                        self.logger.error("__change_image",
                                          "error getting video infos[" + path.basename(self.image_name) + "]", err)
                else:
                    pilImage = self.__get_image(self.image_name)
                    if not pilImage:
                        pilImage = Image.open(self.image_name)
                    self.showPIL(pilImage)
                    if self.is_paused:
                        self.zoom_helper.init(self.get_image_array())

                self.__set_frame_border(self.image_name)
            else:
                self.logger.info("__change_image", "No images")
                if self.label_image["text"] != self.NO_IMAGE_LABEL:
                    self.label_image["text"] = self.NO_IMAGE_LABEL
        if call_again:
            self.identifier_change_image = self.main_window.after(SLIDESHOW_INTERVAL_MS, self.__change_image)

    def __get_saved_images(self, nombre_maxi=30):
        img_folder = hlpr.get_path_attachments(self.PROJECT_PATH)
        img_list = listdir(img_folder)
        # sort by date descending
        img_list.sort(key=lambda x: x.split("_")[1] if x and len(x.split("_")) > 2 else "000000000000000", reverse=True)
        tmp_images = []
        for i in range(len(img_list)):
            if hlpr.get_file_extension_if_valid(img_list[i]):
                tmp_images.append(path.join(img_folder, img_list[i]))
            if len(tmp_images) >= nombre_maxi:
                break

        return tmp_images

    def __check_new_files(self):
        self.logger.info("__check_new_files", "checking new mails...")
        new_images = self.gmail_api.download_new_images()
        if new_images and len(new_images) > 0:
            self.logger.info("__check_new_files", f"{len(new_images)} new mail file(s) downloaded")
            self.list_images = self.__get_saved_images()

        self.logger.info("__check_new_files", "checking new firebase media...")
        new_files_firebase = self.firebase.download_new_medias()
        if new_files_firebase and len(new_files_firebase) > 0:
            self.logger.info("__check_new_files", f"{len(new_files_firebase)} new firebase media(s) downloaded")
            self.list_images = self.__get_saved_images()

        self.logger.info("__check_new_files", "...checked")

        self.main_window.after(MAIL_REFRESH_INTERVAL_MS, self.__check_new_files)

    def __refresh_weatherV2(self):
        temp, feels_temp = self.weatherCom.get_temp_and_feels_temp()
        if temp != None:
            self.__set_label_temp(temp)
        if feels_temp != None:
            self.__set_label_feels_temp(feels_temp)
        self.main_window.after(WEATHER_REFRESH_INTERVAL_MS, self.__refresh_weatherV2)

    def __set_label_temp(self, temp: str):
        current_txt = self.label.cget("text")
        if current_txt and temp != None:
            txtSplit = current_txt.split("\n")
            if len(txtSplit) > 0:
                new_txt = txtSplit[0] + "\n" + temp
                self.label.config(text=new_txt)

    def __set_label_feels_temp(self, feels: str):
        if feels != None:
            self.labelFeels.config(text=feels)

    def __set_label_time(self, time: str):
        new_txt = time
        current_txt = self.label.cget("text")
        if current_txt:
            txtSplit = current_txt.split("\n")
            if len(txtSplit) == 2:
                new_txt = new_txt + "\n" + txtSplit[1]

        self.label.config(text=new_txt)

    def __set_frame_border(self, image_name):
        if hlpr.is_new_image(image_name):
            self.frame.configure(border=BORDER_SIZE_NEW_IMAGE, background=BACKGROUND_NEW_IMAGE)
        else:
            self.frame.configure(border=0, background="black")

    def __get_image(self, filepath) -> Image:
        try:
            image = Image.open(filepath)
            orientation = ""
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break

            exif = image._getexif()

            if exif and orientation in exif:
                if exif[orientation] == 3:
                    image = image.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    image = image.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    image = image.rotate(90, expand=True)

            return image
        except (AttributeError, KeyError, IndexError):
            # cases: image don't have getexif
            pass
        except Exception as e:
            self.logger.error("__get_image", "exif Exception", e)

        return None

    def showPIL(self, pil_image: Image):
        imgWidth, imgHeight = pil_image.size
        ratio = min(self.width / imgWidth, self.height / imgHeight)
        imgWidth = int(imgWidth * ratio)
        imgHeight = int(imgHeight * ratio)
        pil_image = pil_image.resize((imgWidth, imgHeight), Image.ANTIALIAS)

        image = ImageTk.PhotoImage(pil_image)
        self.label_image.image = image
        self.label_image.configure(image=image)

    def zoom(self, action: ZoomAction, direction: ZoomNavigationDirections):
        """
            :param action: Zoom/Dezoom
            :param direction: navigation direction
        """
        cropped = self.zoom_helper.set_zoom(action, direction)

        if cropped is None or not cropped.any():
            self.logger.info("zoom", "NOT CROPPED")
            return

        array_img = cv2.resize(cropped, (self.zoom_helper.get_width(), self.zoom_helper.get_height()))
        image = ImageTk.PhotoImage(Image.fromarray(array_img))
        self.label_image.image = image
        self.label_image.configure(image=image)

    def onDestroy(self, e):
        self.logger.info("onDestroy", e.widget)
        if not e.widget.master:
            exit()

    def __create_main_window(self):
        window = tkinter.Tk()
        window["bg"] = "black"
        w, h = window.winfo_screenwidth(), window.winfo_screenheight()
        # window.overrideredirect(1)
        window.wm_attributes("-fullscreen", "True")
        window.geometry("%dx%d+0+0" % (w, h))
        window.focus_set()
        window.bind("<Escape>", lambda e: (e.widget.withdraw(), e.widget.quit(), exit()))
        window.bind("<Destroy>", self.onDestroy)
        self.canvas = tkinter.Canvas(window, width=w, height=h)

        d = hlpr.get_time_in_alberta()
        self.label = Label(window, text=d, font=("", 15))
        self.label.place(x=0, y=0)
        self.labelFeels = Label(window, text=None, font=("", 15), name="labelFeels")
        self.labelFeels.config(cursor="none")
        self.labelFeels.place(anchor="ne", relx=1)
        self.frame = Frame(self.canvas, width=w, height=h)
        self.frame.pack()
        self.label_pause = Label(self.canvas, text="⏸︎", font=("", 16, "bold"), foreground="white", background="black",
                                 name="labelPause")
        self.label_image = Label(self.frame, width=w, height=h, bg="black", foreground="white", font=("", 25))
        self.label_image.config(cursor="none")
        self.label_image.pack()
        self.canvas.pack()
        self.label.bind("<Button-1>", self.restartSlideshow)
        window.bind("<Button-1>", self.onWindowClick)
        # window.bind("<Key>", self.onKeyPressed)
        return window, w, h

    # def onKeyPressed(self, event: Event):
    #     print("onKeyPressed: ", event.keycode)

    #     # Up
    #     if event.keycode == 38:
    #         print("Up")
    #         self.zoom(None, ZoomNavigationDirections.UP)
    #     # Right
    #     if event.keycode == 39:
    #         print("Right")
    #         self.zoom(None, ZoomNavigationDirections.RIGHT)
    #     # Bottom
    #     if event.keycode == 40:
    #         print("Bottom")
    #         self.zoom(None, ZoomNavigationDirections.BOTTOM)
    #     # Left
    #     if event.keycode == 37:
    #         print("Left")
    #         self.zoom(None, ZoomNavigationDirections.LEFT)
    #     # z
    #     if event.keycode == 90:
    #         print("Z")
    #         self.zoom(ZoomAction.ZOOM, None)
    #     # d
    #     if event.keycode == 68:
    #         print("D")
    #         self.zoom(ZoomAction.DEZOOM, None)

    def get_image_array(self):
        if self.is_paused and hlpr.is_valid_image_file(self.image_name):
            pil_image = self.__get_image(self.image_name)
            if not pil_image:
                pil_image = Image.open(self.image_name)
            imgWidth, imgHeight = pil_image.size
            ratio = min(self.width / imgWidth, self.height / imgHeight)
            imgWidth = int(imgWidth * ratio)
            imgHeight = int(imgHeight * ratio)
            pil_image = pil_image.resize((imgWidth, imgHeight), Image.ANTIALIAS)
            return np.asarray(pil_image)

        return np.array([], dtype=np.uint8)

    def start_slideshow(self):
        self.logger.info("start_slideshow", "starting slideshow...")
        self.__change_image()
        t_mail = Thread(target=self.__check_new_files)
        t_mail.start()
        t_weather = Thread(target=self.__refresh_weatherV2)
        t_weather.start()
        self.logger.info("start_slideshow", "slideshow started")
        self.main_window.mainloop()

    def restartSlideshow(self, e):
        self.logger.info("restartSlideshow", "restartSlideshow", e)
        self.__change_image(RESTART_SLIDESHOW)
        return "break"

    def onWindowClick(self, e: Event):
        if e and self.width and self.height and self.width > 0 and self.height > 0:
            if self.is_paused and self.zoom_helper.isReady:
                if e.widget and e.widget._name == "labelPause":
                    self.logger.info("onWindowClick", "Zoom LEFT", e)
                    self.zoom(None, ZoomNavigationDirections.LEFT)
                elif e.y < self.height / 3:
                    # slideshow controls
                    if e.widget and e.widget._name == "labelFeels":
                        self.logger.info("onWindowClick", "Next, click on labelFeels", e)
                        self.__change_image(NEXT_IMAGE)
                    elif e.x >= 0 and e.x < self.width / 3:
                        self.logger.info("onWindowClick", "Previous", e)
                        self.__change_image(PREVIOUS_IMAGE)
                    elif e.x >= self.width / 3 and e.x < self.width / 3 * 2:
                        self.is_paused = not self.is_paused
                        if self.is_paused:
                            self.zoom_helper.init(self.get_image_array())
                            self.logger.info("onWindowClick", "Pause", e)
                            self.label_pause.place(anchor="sw", rely=1)
                        else:
                            self.zoom_helper.reset()
                            self.logger.info("onWindowClick", "Resume", e)
                            self.label_pause.place_forget()
                    elif e.x >= self.width / 3 * 2 and e.x < self.width:
                        self.logger.info("onWindowClick", "Next", e)
                        self.__change_image(NEXT_IMAGE)
                else:
                    # Zoom controls
                    if e.x >= 0 and e.x < self.width / 3:
                        if e.y > self.height / 3 * 2:
                            self.logger.info("onWindowClick", "Zoom LEFT", e)
                            self.zoom(None, ZoomNavigationDirections.LEFT)
                        else:
                            self.logger.info("onWindowClick", "Dezoom", e)
                            self.zoom(ZoomAction.DEZOOM, None)
                    elif e.x >= self.width / 3 and e.x < self.width / 3 * 2:
                        if e.y > self.height / 3 * 2:
                            self.logger.info("onWindowClick", "Zoom BOTTOM", e)
                            self.zoom(None, ZoomNavigationDirections.BOTTOM)
                        else:
                            self.logger.info("onWindowClick", "Zoom UP", e)
                            self.zoom(None, ZoomNavigationDirections.UP)
                    elif e.x >= self.width / 3 * 2 and e.x < self.width:
                        if e.y > self.height / 3 * 2:
                            self.logger.info("onWindowClick", "Zoom RIGHT", e)
                            self.zoom(None, ZoomNavigationDirections.RIGHT)
                        else:
                            self.logger.info("onWindowClick", "Zoom", e)
                            self.zoom(ZoomAction.ZOOM, None)
            else:
                if e.widget and e.widget._name == "labelFeels":
                    self.logger.info("onWindowClick", "Next, click on labelFeels", e)
                    self.__change_image(NEXT_IMAGE)
                elif e.x >= 0 and e.x < self.width / 3:
                    self.logger.info("onWindowClick", "Previous", e)
                    self.__change_image(PREVIOUS_IMAGE)
                elif e.x >= self.width / 3 and e.x < self.width / 3 * 2:
                    self.is_paused = not self.is_paused
                    if self.is_paused:
                        self.zoom_helper.init(self.get_image_array())
                        self.logger.info("onWindowClick", "Pause", e)
                        self.label_pause.place(anchor="sw", rely=1)
                    else:
                        self.zoom_helper.reset()
                        self.logger.info("onWindowClick", "Resume", e)
                        self.label_pause.place_forget()
                elif e.x >= self.width / 3 * 2 and e.x < self.width:
                    self.logger.info("onWindowClick", "Next", e)
                    self.__change_image(NEXT_IMAGE)


app = SlideShow()
app.start_slideshow()
