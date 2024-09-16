from enum import Enum
from datetime import datetime as dt


class Level(Enum):
    INFO = 1
    DEBUG = 2
    WARNING = 3
    ERROR = 4


class Logger:
    def __init__(self, callerClass: str) -> None:
        self.callerClass = callerClass

    def __get_date(self) -> str:
        return dt.now().strftime("%Y-%m-%d %H:%M:%S")

    def info(self, caller: str, message: str, *args):
        self.__log(Level.INFO, caller, message, *args)

    def debug(self, caller: str, message: str, *args):
        self.__log(Level.DEBUG, caller, message, *args)

    def warning(self, caller: str, message: str, *args):
        self.__log(Level.WARNING, caller, message, *args)

    def error(self, caller: str, message: str, *args):
        self.__log(Level.ERROR, caller, message, *args)

    def __log(self, level: Level, caller: str, message: str, *args):
        if self.callerClass:
            _caller = f"{self.callerClass}.{caller}"
        else:
            _caller = caller
        if args and len(args) > 0:
            print(self.__get_date(), level.name.rjust(8, " "), "-", _caller, ":", message, *args)
        else:
            print(self.__get_date(), level.name.rjust(8, " "), "-", _caller, ":", message)

