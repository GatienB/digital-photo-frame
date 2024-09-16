import requests
from bs4 import BeautifulSoup
from src.logger import Logger


class WeatherDotCom:
    def __init__(self, city_name: str) -> None:
        if not city_name:
            raise Exception(f"Invalid parameters[{city_name}]")
        if city_name.lower() == "hussar":
            self._cityId = "1ad569b85e14c5cbb78e086a90c9ff2930207affb1de5c3ac61440807172f73c"
        elif city_name.lower() == "lille":
            self._cityId = "e83a2bc15fa5503ca0afe77c2121f8cdb6ba19c1b081db84278bfc5e74a78c5e"
        else:
            raise NotImplementedError(f"city[{city_name}] not implemented")
        self.logger = Logger(self.__class__.__name__)

    def __send_get_request(self, url):
        try:
            res = requests.get(url)
            if res and res.status_code == 200:
                return True, res.text
            else:
                self.logger.info("__send_get_request", f"status[{res.status_code}] - text: {res.text}")
        except Exception as e:
            self.logger.error("__send_get_request", "Exception", e)
        return False, None

    def __parse_feels_like_temp(self, soup: BeautifulSoup):
        try:
            res = soup.find("span", class_=lambda c: c and c.startswith("TodayDetailsCard--feelsLikeTempValue"))
            if res and res.text and res.text.strip():
                return res.text.strip()
            else:
                if res:
                    self.logger.warning("__parse_feels_like_temp", f"can't find feels_like_temperature[{res.text}]")
                else:
                    self.logger.warning("__parse_feels_like_temp", f"can't find feels_like_temperature[!res]")
        except Exception as e:
            self.logger.error("__parse_feels_like_temp", f"Error parsing webpage", e)
        return None

    def __parse_temp(self, soup: BeautifulSoup):
        try:
            res = soup.find("span", class_=lambda c: c and c.startswith("CurrentConditions--tempValue"))
            if res and res.text and res.text.strip():
                return res.text.strip()
            else:
                if res:
                    self.logger.warning("__parse_temp", f"can't find temperature[{res.text}]")
                else:
                    self.logger.warning("__parse_temp", f"can't find temperature[!res]")
        except Exception as e:
            self.logger.error("__parse_temp", f"Error parsing webpage", e)
        return None

    def get_temp_and_feels_temp(self):
        self.logger.info("get_temp_and_feels_temp", "getting temperature...")
        url = "https://weather.com/weather/today/l/{}?unit=m".format(self._cityId)
        success, data = self.__send_get_request(url)
        if success and data:
            try:
                soup = BeautifulSoup(data, "html.parser")
                temp = self.__parse_temp(soup)
                feels_temp = self.__parse_feels_like_temp(soup)
                if temp is not None:
                    temp = temp.replace("°", "") + "°C"
                if feels_temp is not None:
                    feels_temp = feels_temp.replace("°", "") + "°C"
                self.logger.info("get_temp_and_feels_temp", f"temp[{temp}], feelsLike[{feels_temp}]")
                return temp, feels_temp
            except Exception as e:
                self.logger.error("get_temp_and_feels_temp", f"Error parsing webpage", e)
        else:
            self.logger.error("get_temp_and_feels_temp", "can't get temperature")

        return None, None
