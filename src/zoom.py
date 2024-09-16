from typing import Tuple
import numpy as np
from enum import Enum
from src.logger import Logger


class ZoomNavigationDirections(Enum):
    UP = 38
    RIGHT = 39
    BOTTOM = 40
    LEFT = 37


class ZoomAction(Enum):
    ZOOM = 101
    DEZOOM = 102


# 50   = x1
# 25   = x2
# 12.5 = x4
class ZoomLevels(Enum):
    NO_ZOOM = 50  # pas de zoom
    ZOOM_1 = 30  # level 1
    ZOOM_2 = 20  # level 2
    ZOOM_3 = 10  # level 3

    def get_zoom_levels():
        """
            Returns ZoomLevels in ascending order
        """
        return list(__class__.__members__.values())


class Zoom:
    NAVIGATION_OFFSET = 15

    def __init__(self) -> None:
        self.logger = Logger(self.__class__.__name__)
        self.reset()

    def __set_next_zoomLevel(self, is_zoom: bool):
        zooms = ZoomLevels.get_zoom_levels()
        if not is_zoom:
            zooms.sort(key=lambda x: x.value)
        i = -1
        try:
            i = zooms.index(self.zoomLevel)
        except ValueError:
            print("Value Error")

        if i == -1:
            self.zoomLevel = ZoomLevels.NO_ZOOM
        elif i < len(zooms) - 1:
            self.zoomLevel = zooms[i + 1]

    def init(self, img_array):
        self.reset()
        if not img_array is None and img_array.any():
            self.imageArray = img_array
            self.imgHeight = img_array.shape[0]
            self.imgWidth = img_array.shape[1]
            self.isReady = True

    def _reset_properties(self):
        self.zoomLevel = ZoomLevels.NO_ZOOM
        self.offsetX = 0
        self.offsetY = 0
        self.imageArray = np.array([], dtype=np.uint8)
        self.imgHeight = 0
        self.imgWidth = 0
        self.isReady = False

    def get_width(self):
        return self.imgWidth

    def get_height(self):
        return self.imgHeight

    def reset(self) -> None:
        self._reset_properties()

    def _set_zoom_level(self, action: ZoomAction) -> None:
        if action == ZoomAction.ZOOM:
            self.__set_next_zoomLevel(True)
        elif action == ZoomAction.DEZOOM:
            self.__set_next_zoomLevel(False)

    def _get_next_navigation_offsets(self, direction: ZoomNavigationDirections):
        x, y = self.offsetX, self.offsetY
        if direction == ZoomNavigationDirections.UP:
            y -= self.NAVIGATION_OFFSET
        elif direction == ZoomNavigationDirections.BOTTOM:
            y += self.NAVIGATION_OFFSET
        elif direction == ZoomNavigationDirections.LEFT:
            x -= self.NAVIGATION_OFFSET
        elif direction == ZoomNavigationDirections.RIGHT:
            x += self.NAVIGATION_OFFSET

        return x, y

    def _get_coordinates_cropped(self, newNavOffsets: Tuple):
        """
            :param imgSize: (Height, Width)
            :param navOffsets: (offsetX, offsetY)
        """
        imgHeight, imgWidth = self.imgHeight, self.imgWidth
        offsetX, offsetY = newNavOffsets
        zoomLevel = self.zoomLevel.value
        radiusX, radiusY = int(imgWidth * zoomLevel / 100), int(imgHeight * zoomLevel / 100)
        centerX, centerY = int(imgWidth / 2), int(imgHeight / 2)
        coord_x = centerX - radiusX + offsetX, centerX + radiusX + offsetX
        coord_y = centerY - radiusY + offsetY, centerY + radiusY + offsetY

        return coord_x, coord_y

    def __handle_navigation_offset_overflow(self, coordX, coordY, newNavOffsets):
        imgHeight, imgWidth = self.imgHeight, self.imgWidth
        offsetX, offsetY = newNavOffsets
        if coordX[0] < 0:
            difference = abs(coordX[0])
            coordX = tuple([c + difference for c in coordX])
            offsetX += difference
        if coordX[1] > imgWidth:
            difference = imgWidth - coordX[1]
            coordX = tuple([c + difference for c in coordX])
            offsetX += difference
        if coordY[0] < 0:
            difference = abs(coordY[0])
            coordY = tuple([c + difference for c in coordY])
            offsetY += difference
        if coordY[1] > imgHeight:
            difference = imgHeight - coordY[1]
            coordY = tuple([c + difference for c in coordY])
            offsetY += difference

        self.offsetX = offsetX
        self.offsetY = offsetY

        return coordX, coordY

    def set_zoom(self, action: ZoomAction, direction: ZoomNavigationDirections) -> None:
        """
            :param action: Zoom/Dezoom
            :param direction: direction navigation

            Rreturns cropped image array
        """
        if not self.imageArray is None and len(self.imageArray) > 0:
            self._set_zoom_level(action)
            navOffsets = self._get_next_navigation_offsets(direction)
            minMaxX, minMaxY = self._get_coordinates_cropped(navOffsets)
            minMaxX, minMaxY = self.__handle_navigation_offset_overflow(minMaxX, minMaxY, navOffsets)
            return self.imageArray[minMaxY[0]:minMaxY[1], minMaxX[0]:minMaxX[1]]
        else:
            self.logger.warning("set_zoom", "imageArray not set or empty")

        return np.array([], dtype=np.uint8)
