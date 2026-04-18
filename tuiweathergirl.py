#!/usr/bin/env python

# TUIWEATHERGIRL
# 2026 by StrayF

import configparser
import curses
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from pprint import pprint as pp
from zoneinfo import ZoneInfo

import requests
from babel import Locale
from babel.dates import format_date
from babel.languages import get_official_languages

DEFAULT_ARG: str = "simple"
VALID_ARGS: list[str] = ["help", "simple", "nice", "fancy" "glamour"]
VERSION: str = "1.0"
USAGE: str = f"""TUIWEATHERGIRL {VERSION} by StrayF 2026

USAGE: tuiweathergirl [--help|<VIEW>]

VIEWS:
    --simple
        Best for barebone terminals.
        Simple print of the date, time, weather data and then exit.

    --nice
        Still nice for barebone terminals.
        Basic text interface with tables (ncurses).

    --fancy
        Better for moderate to modern terminals.
        Color text interface.

    --glamour
        ***WIP***

HOW DOES TUIWEATHERGIRL WORKS:
    - The application would first check for ~/.tuiweathergirlrc
    - If file is not found, the application would try to auto-configure
    - Once configured, the application would always load the config from the file
    - Feel free to edit the config file
    - To enforce auto-configuration or if you mess-up the config file,
        just delete it and run the application again
"""
MIN_COLS: int = 79
MIN_LINES: int = 24


class TestCase:
    r"""For when doing tests often and avoid being banned by the APIs"""

    def __init__(self) -> None:
        self.testfilename: str = "tuiweathergirl_test.ini"
        self.loaded: bool = False
        if self.saved:
            self.load()

    @property
    def saved(self) -> bool:
        return Path(self.testfilename).expanduser().exists()

    def load(self) -> None:
        r"""Read the test configuration from the config file"""

        if not self.saved:
            raise Exception("Tried to load unsaved test configuration.")

        config = configparser.ConfigParser()
        full_path = Path(self.testfilename).expanduser()
        config.read(full_path)

        self.sky: str = config["TODAY"]["sky"]
        self.temperature: int = int(config["TODAY"]["temperature"])
        self.tmin: int = int(config["TODAY"]["tmin"])
        self.tmax: int = int(config["TODAY"]["tmax"])
        self.wind: int = int(config["TODAY"]["wind"])
        self.wind_direction: str = config["TODAY"]["wind_direction"]
        self.aqi: int = int(config["TODAY"]["aqi"])
        self.precipitation: int = int(config["TODAY"]["precipitation"])
        self.weather_code: int = int(config["TODAY"]["weather_code"])
        self.warning: str = config["TODAY"]["warning"]

        self.daynames: list[str] = config.get("FORECAST", "daynames").split(",")
        self.mins: list[str] = config.get("FORECAST", "mins").split(",")
        self.maxs: list[str] = config.get("FORECAST", "maxs").split(",")
        self.precipitations: list[str] = config.get("FORECAST", "precipitations").split(
            ","
        )

        self.loaded = True


class Configuration:
    r"""Weather configuration"""

    __CONFIGFILE: str = "~/.tuiweathergirlrc"

    def __init__(self) -> None:
        self.country: str = ""
        self.country_code2: str = ""
        self.city: str = ""
        self.postal_code: str = ""
        self.province: str = ""
        self.lat: str = ""
        self.lon: str = ""
        self.continent_code: str = ""
        self.timezone: str = ""
        self.language: str = ""
        # ---
        self.time24: bool = True
        self.metric: bool = True
        self.celsius: bool = True
        self.date_format_length: str = "medium"
        self.view: str = DEFAULT_ARG

        self.configfile = self.__CONFIGFILE

        if os.name == "nt":
            self.configfile = "~/tuiweathergirl.rc"

    def __str__(self) -> str:
        return f"{self.city}/{self.province}/{self.country}/{self.continent_code}"

    @property
    def saved(self) -> bool:
        return Path(self.configfile).expanduser().exists()

    def save(self) -> None:
        r"""Write the configuration to the config file"""

        config = configparser.ConfigParser()

        config["LOCATION"] = {
            "country": self.country,
            "country_code2": self.country_code2,
            "city": self.city,
            "postal_code": self.postal_code,
            "province": self.province,
            "lat": self.lat,
            "lon": self.lon,
            "continent_code": self.continent_code,
            "timezone": self.timezone,
        }

        config["PREFERENCES"] = {
            "language": self.language,
            "time24": str(self.time24).lower(),
            "metric": str(self.metric).lower(),
            "celsius": str(self.celsius).lower(),
            # "date_format_length": self.date_format_length,
            "view": self.view,
        }

        # Write to a file
        full_path = Path(self.configfile).expanduser()
        with open(full_path, "w") as configfile:
            config.write(configfile)

    def load(self) -> None:
        r"""Read the configuration from the config file"""

        if not self.saved:
            raise Exception("Tried to load unsaved configuration.")

        config = configparser.ConfigParser()
        full_path = Path(self.configfile).expanduser()
        config.read(full_path)

        self.country = config["LOCATION"]["country"]
        self.country_code2 = config["LOCATION"]["country_code2"]
        self.city = config["LOCATION"]["city"]
        self.postal_code = config["LOCATION"]["postal_code"]
        self.province = config["LOCATION"]["province"]
        self.lat = config["LOCATION"]["lat"]
        self.lon = config["LOCATION"]["lon"]
        self.continent_code = config["LOCATION"]["continent_code"]
        self.timezone = config["LOCATION"]["timezone"]
        self.language = config["PREFERENCES"]["language"]
        self.time24 = config.getboolean("PREFERENCES", "time24")
        self.metric = config.getboolean("PREFERENCES", "metric")
        self.celsius = config.getboolean("PREFERENCES", "celsius")
        # self.date_format_length = config["PREFERENCES"]["date_format_length"]
        self.view = config["PREFERENCES"]["view"]


class Locator:
    r"""Gets location data"""

    def config(self, config: Configuration) -> None:
        url: str = (
            "http://ip-api.com/json/?fields=status,message,continentCode,country,countryCode,region,regionName,city,zip,lat,lon,timezone"
        )
        response = requests.get(url).json()

        if response.get("status") == "fail":
            raise Exception(f"Request failed: {response.get("message")}. Try again!")

        config.country = response.get("country")
        config.country_code2 = response.get("countryCode")
        config.city = response.get("city")
        config.postal_code = response.get("zip")
        config.province = response.get("region")
        config.lat = response.get("lat")  # XX.XXX, Fallback plan
        config.lon = response.get("lon")  # XX.XXX
        config.timezone = response.get("timezone")
        config.continent_code = response.get("continentCode")


class Configurator:
    r"""Configures the application"""

    def __detect_language(self, country_code, province) -> str:
        exceptions = {
            "CA": {"QC": "fr"},  # Canada: Quebec
            "CH": {"TI": "it", "GE": "fr"},  # Switzerland
        }

        if country_code in exceptions and province in exceptions[country_code]:
            return exceptions[country_code][province]

        langs = get_official_languages(country_code)
        return langs[0].lower() if langs else "en"

    def __detect_metric(self, language_code, country_code) -> bool:
        loc = Locale.parse(f"{language_code}_{country_code}", sep="_")
        return loc.measurement_systems != "US"

    def __detect_celsius(self, country_code) -> bool:
        fahrenheit_countries = ["US", "BS", "KY", "LR", "PW", "MH", "FM"]
        return country_code not in fahrenheit_countries

    def __detect_time24(self, language_code, country_code) -> bool:
        locale_id = f"{language_code}_{country_code}"
        try:
            loc = Locale.parse(locale_id, sep="_")
            # Get the default short time format (e.g., "HH:mm" or "h:mm a")
            time_format = loc.time_formats["short"].pattern
            # In Unicode patterns, 'H' is 24h, 'h' is 12h
            return "H" in time_format
        except Exception:
            return True  # Default to 24h if unsure

    def config(self, c: Configuration) -> None:
        if config.country_code2 == "" or config.province == "":
            raise Exception(
                "Cannot auto-configure. Country code and province code not set."
            )

        config.language = self.__detect_language(config.country_code2, config.province)
        config.time24 = self.__detect_time24(config.language, config.country_code2)
        config.metric = self.__detect_metric(config.language, config.country_code2)
        config.celsius = self.__detect_celsius(config.country_code2)


class BriefDailyForecast:
    """For the daily forecast for the upcoming week we don't need all data"""

    def __init__(self) -> None:
        self.dow: str = ""
        self.min: int = 0
        self.max: int = 0
        self.precip: int = 0


class WeatherData:
    r"""Weather data"""

    def __init__(self) -> None:
        # Today
        self.wind_direction: str = ""
        self.sky: str = ""
        self.air_quality: str = ""
        self.aqi: int = 0
        self.temperature: int = 0
        self.wind: int = 0
        self.precipitation: int = 0
        self.min: int = 0
        self.max: int = 0
        self.weather_code: int = 0

        self.warnings: list[str] = []
        self.week: list[BriefDailyForecast] = []


class WeatherForecaster:
    r"""Gets the weather forecast"""

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.locale_id = f"{config.language}_{config.country_code2}"

    def __get_wind_direction(self, degrees: float) -> str:
        dirs = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        ix = int((degrees + 11.25) / 22.5)
        return dirs[ix % 16]

    def __get_weather_description(self, code: int) -> str:
        # Simplified WMO Weather interpretation codes
        mapping: dict[int, str] = {
            0: "Sunny",
            1: "Mainly Clear",
            2: "Partly Cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Rime Fog",
            51: "Drizzle",
            61: "Rain",
            71: "Snow",
            80: "Rain Showers",
            95: "Thunderstorm",
        }
        return mapping.get(code, "Cloudy")

    def __get_air_quality_assessment(self, aqi: int) -> str:
        r"""Returns a human-readable assessment based on the US EPA AQI scale."""

        assessments: dict[int, str] = {
            50: "Good",
            100: "Moderate",
            150: "Unhealthy for Sensitive Groups",
            200: "Unhealthy",
            300: "Very Unhealthy",
        }

        for aqilevel in sorted(assessments):
            if aqi <= aqilevel:
                return assessments[aqilevel]

        return "Hazardous"

    def get_data(self, weather_data: WeatherData) -> None:
        # Build the API URL with your config preferences
        tunit = "celsius" if self.config.celsius else "fahrenheit"
        wunit = "kmh" if self.config.metric else "mph"

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.config.lat}&longitude={self.config.lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&timezone={self.config.timezone.replace('/', '%2F')}"
            f"&temperature_unit={tunit}&wind_speed_unit={wunit}"
            f"&forecast_days=8"  # <--- ADD THIS PARAMETER
        )

        # Air Quality API (Separate endpoint but same coordinates)
        aq_url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={self.config.lat}&longitude={self.config.lon}&current=us_aqi"
        )

        # Format Date and Time
        now = datetime.now(ZoneInfo(self.config.timezone))

        test = TestCase()

        if test.loaded:
            # Fill the object with data
            weather_data.sky = test.sky
            weather_data.temperature = test.temperature
            weather_data.min = test.tmin
            weather_data.max = test.tmax
            weather_data.aqi = test.aqi
            weather_data.air_quality = self.__get_air_quality_assessment(test.aqi)
            weather_data.precipitation = test.precipitation
            weather_data.weather_code = test.weather_code
            weather_data.wind = test.wind
            weather_data.wind_direction = test.wind_direction
            weather_data.warnings.append(test.warning)

            # 7 day forecast
            for i in range(0, 7):
                day: BriefDailyForecast = BriefDailyForecast()
                day.min = int(test.mins[i])
                day.max = int(test.maxs[i])
                day.precip = int(test.precipitations[i])
                day.dow = test.daynames[i]
                weather_data.week.append(day)

        else:
            # Send the requests
            weather_result = requests.get(url).json()
            aq_result = requests.get(aq_url).json()

            # Extract Data
            current = weather_result["current"]
            daily = weather_result["daily"]
            aqi = aq_result["current"]["us_aqi"]

            # Fill the object with data
            weather_data.sky = self.__get_weather_description(current["weather_code"])
            weather_data.temperature = int(current["temperature_2m"])
            weather_data.min = int(daily["temperature_2m_min"][0])
            weather_data.max = int(daily["temperature_2m_max"][0])
            weather_data.aqi = int(aqi)
            weather_data.air_quality = self.__get_air_quality_assessment(aqi)
            weather_data.precipitation = daily["precipitation_probability_max"][0]
            weather_data.weather_code = current["weather_code"]
            weather_data.wind = int(current["wind_speed_10m"])
            weather_data.wind_direction = self.__get_wind_direction(
                current["wind_direction_10m"]
            )

            if weather_data.weather_code >= 95:
                weather_data.warnings.append(
                    "WARNING: SEVERE THUNDERSTORMS DETECTED IN YOUR AREA"
                )

            # 7 day forecast
            for i in range(1, 8):
                day = BriefDailyForecast()
                day.min = int(daily["temperature_2m_min"][i])
                day.max = int(daily["temperature_2m_max"][i])
                day.precip = int(daily["precipitation_probability_max"][i])
                day.dow = (now.replace(day=now.day + i)).strftime("%a")
                weather_data.week.append(day)


class PresentationConfiguration:
    r"""Common presentation logic"""

    def __init__(self, config: Configuration) -> None:
        self.locale_id = f"{config.language}_{config.country_code2}"

        # Units
        self.tsuffix: str = "C" if config.celsius else "F"
        self.tunit: str = "celsius" if config.celsius else "fahrenheit"
        self.wunit: str = "kmh" if config.metric else "mph"

        # Removing provinces which contain only numbers
        province_has_letters = bool(re.search(r"\D", config.province))
        self.province: str = ""
        if province_has_letters:
            self.province = f"{config.province}, "

        self.time24: bool = config.time24
        self.timezone: str = config.timezone
        self.date_format_length: str = config.date_format_length

        self.date: str = ""
        self.time: str = ""

    def update_time(self) -> str:
        now = datetime.now(ZoneInfo(self.timezone))
        self.date = format_date(
            now, format=self.date_format_length, locale=self.locale_id
        )

        # Time 12/24
        time_pattern = "%H:%M" if self.time24 else "%I:%M %p"
        self.time = now.strftime(time_pattern)

        return self.time


class View:
    def __init__(
        self,
        config: Configuration,
        data: WeatherData,
        present_config: PresentationConfiguration,
    ) -> None:
        self.config: Configuration = config
        self.data: WeatherData = data
        self.presconf: PresentationConfiguration = present_config
        self.weather_refresh_interval: int = 300  # 5 minutes

    def get_sky_cp(self, sky: str) -> int:
        """Get the appropriate sky color pair"""

        d: dict[str, int] = {
            # -------------------- nice
            "Sunny": 2,
            "Mainly Clear": 2,
            # -------------------- clouds
            "Partly Cloudy": 3,
            "Overcast": 3,
            "Foggy": 3,
            "Rime Fog": 3,
            "Cloudy": 3,
            # -------------------- rains
            "Drizzle": 4,
            "Rain": 4,
            "Snow": 4,
            "Rain Showers": 4,
            "Thunderstorm": 4,
        }
        if sky not in d:
            raise Exception("Invalid sky value '{sky}'.")
        return d[sky]

    def get_aqi_cp(self, aqi: str) -> int:
        """Get the appropriate aqi color pair"""

        d: dict[str, int] = {
            # -------------------- green
            "Good": 6,
            # -------------------- yellow
            "Moderate": 2,
            "Unhealthy for Sensitive Groups": 2,
            # -------------------- red
            "Unhealthy": 5,
            "Very Unhealthy": 5,
            "Hazardous": 5,
        }
        if aqi not in d:
            raise Exception("Invalid sky value '{aqi}'.")
        return d[aqi]

    def prog_bar(self, percent: int, maxchar: int = 10) -> str:
        # Ensure percent stays within 0-100 bounds
        percent = max(0, min(100, percent))

        count = round(percent / maxchar)

        # DOS Era characters:
        # █ (Full Block) or ▓ (Dark Shade) for progress
        # ░ (Light Shade) for the background/remaining
        fill_char = "▓"
        empty_char = "░"

        bar = (fill_char * count) + (empty_char * (maxchar - count))
        return bar

    def test_terminal_size(self, stdscr: curses.window) -> None:
        lines, cols = stdscr.getmaxyx()
        if lines < MIN_LINES or cols < MIN_COLS:
            raise Exception(
                f"Current terminal size ({cols}x{lines}) is smaller than the required minimum terminal size ({MIN_COLS}x{MIN_LINES})."
            )

    def screen(self, stdscr: curses.window) -> None:
        r"""The actual TUI screen to display"""
        pass

    def display(self) -> None:
        r"""Wrapper for screen(), unless simple printing"""
        pass


class SimpleView(View):
    r"""Just prints"""

    def display(self) -> None:
        # Data to display
        timenow: str = self.presconf.update_time()
        datenow: str = self.presconf.date
        # ---
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        sky: str = self.data.sky
        temperature: int = self.data.temperature
        tmin: int = self.data.min
        tmax: int = self.data.max
        tsuffix: str = self.presconf.tsuffix
        wunit: str = self.presconf.wunit
        wind: int = self.data.wind
        winddir: str = self.data.wind_direction
        aqi: int = self.data.aqi
        airquality: str = self.data.air_quality
        precipitation: int = self.data.precipitation
        # ---
        warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week

        print(f"""TUIWEATHERGIRL {VERSION} by StrayF 2026

TODAY: {timenow}, {datenow}
Location: {city}, {province}{country}
Sky: {sky}
Current Temp: {temperature}{tsuffix}, Today: {tmin}{tsuffix}/{tmax}{tsuffix}
Wind: {wind}{wunit} {winddir}
Air Quality (AQI): {aqi} ({airquality})
Precipitation: {precipitation}%
""")

        print("7-DAY FORECAST:")
        for day in week:
            dmin: int = day.min
            dmax: int = day.max
            dprecip: int = day.precip
            dow: str = day.dow

            temperatures = f"{dmin:>2}/{dmax}{tsuffix}"
            print(f"  {dow}: {temperatures:<6} | {dprecip:>3}%")

        for warning in warnings:
            print(f"\n{warning}")

        print("\nTry: tuiweathergirl --help")


class NiceView(View):
    """Nice view"""

    def screen(self, stdscr: curses.window) -> None:
        forecaster: WeatherForecaster = WeatherForecaster(self.config)

        # Data to display
        timenow: str = self.presconf.update_time()
        datenow: str = self.presconf.date
        # ---
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        # ---
        sky: str = self.data.sky
        temperature: int = self.data.temperature
        tmin: int = self.data.min
        tmax: int = self.data.max
        tsuffix: str = self.presconf.tsuffix
        wunit: str = self.presconf.wunit
        wind: int = self.data.wind
        winddir: str = self.data.wind_direction
        aqi: int = self.data.aqi
        airquality: str = self.data.air_quality
        precipitation: int = self.data.precipitation
        # ---
        warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week

        view_width: int = 73
        data_box_width: int = 36

        datax: int = 16
        time24_x: int = 45
        if not self.config.time24:
            time24_x = time24_x - 2

        stdscr.clear()
        self.test_terminal_size(stdscr)
        stdscr.nodelay(True)
        curses.curs_set(False)  # Hide cursor
        stdscr.erase()

        # Stats
        # colors: bool = curses.has_colors()
        maxy, maxx = stdscr.getmaxyx()

        title_win = curses.newwin(3, view_width, 0, 1)
        title_win.box()
        title_win.addstr(
            1,
            2,
            f"TUIWEATHERGIRL {VERSION}                                     by StrayF 2026",
        )

        location_win = curses.newwin(1, view_width - 1, 3, 2)
        location_win.addstr(0, 0, f"Location: {city}, {province}{country}")
        location_win.addstr(0, time24_x, f"Today: {datenow} {timenow}")

        status_win = curses.newwin(7, data_box_width, 4, 1)
        status_win.box()
        status_win.addstr(1, 11, "CURRENT STATUS")
        status_win.addstr(3, 3, "Sky    :")
        status_win.addstr(4, 3, "Temp   :")
        status_win.addstr(5, 3, "Range  :")
        status_win.addstr(3, datax, sky)
        status_win.addstr(4, datax, f"{temperature}°{tsuffix}")
        status_win.addstr(5, datax, f"{tmin}°{tsuffix} / {tmax}°{tsuffix}")

        air_win = curses.newwin(7, data_box_width, 4, 38)
        air_win.box()
        air_win.addstr(1, 10, "AIR & CONDITIONS")
        air_win.addstr(3, 3, "Wind   :")
        air_win.addstr(4, 3, "AQI    :")
        air_win.addstr(5, 3, "Precip :")
        air_win.addstr(3, datax, f"{wind}{wunit} {winddir}")
        air_win.addstr(4, datax, f"{aqi} ({airquality})")
        air_win.addstr(5, datax, f"{precipitation}%")

        forecast_win = curses.newwin(8, view_width, 12, 1)
        forecast_win.box()

        warnings_win = curses.newwin(4, view_width, 21, 1)
        warnings_win.box()
        warnings_win.addstr(0, 30, " WARNINGS ")
        if len(warnings) > 0:
            for i in range(len(warnings)):
                warnings_win.addstr(1 + i, 2, warnings[i])
        else:
            warnings_win.addstr(1, 2, "No warnings.")

        stdscr.addstr(
            25,
            2,
            f"[q] Quit                                            Auto-refresh: {self.weather_refresh_interval // 60}min",
        )

        wy: int = 1
        wx: int = 3
        day_cnt: int = 0
        for day in week:
            wy = wy + 1
            day_cnt = day_cnt + 1
            if day_cnt == 4:
                wy = 2
                wx = 40

            dmin: int = day.min
            dmax: int = day.max
            dprecip: int = day.precip
            dow: str = day.dow
            temperatures = f"{dmin:>2}°/{dmax}°{tsuffix}"
            forecast_win.addstr(
                wy,
                wx,
                f"{dow}: {temperatures:<6} [{self.prog_bar(dprecip)}] {dprecip}%",
            )

        # -------------------------------------------------- VIEW MAIN LOOP
        elapsed: int = 0
        while True:
            elapsed = elapsed + 1
            timenow = self.presconf.update_time()
            datenow = self.presconf.date
            location_win.addstr(0, 45, f"Today: {datenow} {timenow}")

            # Data to refresh
            status_win.addstr(3, datax, sky)
            status_win.addstr(4, datax, f"{temperature}°{tsuffix}")
            status_win.addstr(5, datax, f"{tmin}°{tsuffix} / {tmax}°{tsuffix}")
            air_win.addstr(3, datax, f"{wind}{wunit} {winddir}")
            air_win.addstr(4, datax, f"{aqi} ({airquality})")
            air_win.addstr(5, datax, f"{precipitation}%")

            if len(warnings) > 0:
                for i in range(len(warnings)):
                    warnings_win.addstr(1 + i, 2, warnings[i])
                else:
                    warnings_win.addstr(1, 2, "No warnings.")

            if elapsed % self.weather_refresh_interval == 0:
                # stdscr.erase()
                forecaster.get_data(self.data)
                # ---
                city = self.config.city
                province = self.presconf.province
                country = self.config.country
                # ---
                sky = self.data.sky
                temperature = self.data.temperature
                tmin = self.data.min
                tmax = self.data.max
                tsuffix = self.presconf.tsuffix
                wunit = self.presconf.wunit
                wind = self.data.wind
                winddir = self.data.wind_direction
                aqi = self.data.aqi
                airquality = self.data.air_quality
                precipitation = self.data.precipitation
                # ---
                warnings = self.data.warnings
                week = self.data.week

            # stdscr.addstr(y,x, "", curses.color_pair(1))

            keypressed = stdscr.getch()
            if keypressed == ord("q"):
                break

            title_win.refresh()
            location_win.refresh()
            status_win.refresh()
            air_win.refresh()
            forecast_win.refresh()
            warnings_win.refresh()

            stdscr.addstr(6, 1, "├──────────────────────────────────┤")
            stdscr.addstr(6, 38, "├──────────────────────────────────┤")
            stdscr.addstr(12, 28, " 7-DAY FORECAST ")
            stdscr.refresh()

            time.sleep(1)  # Prevent 100% CPU usage

    def display(self) -> None:
        curses.wrapper(self.screen)


class WeatherGirl:
    r"""Your daily weather girl"""

    def __init__(self, config: Configuration, data: WeatherData) -> None:
        self.view: str = config.view
        present_config: PresentationConfiguration = PresentationConfiguration(config)
        self.views: dict[str, View] = {
            "simple": SimpleView(config, data, present_config),
            "nice": NiceView(config, data, present_config),
        }

    def present(self, view: str = "") -> None:
        if len(view) > 0 and view not in self.views:
            raise Exception(f"View not defined '{view}'. Run with --help for help.")
        self.views[view or self.view].display()


def get_view() -> str:
    r"""Get the view name from the command-line argument"""

    args: list[str] = []
    if len(sys.argv) > 1:
        args = [arg.lower().lstrip("-") for arg in sys.argv]
        del args[0]  # Deleting the script name
    else:
        # args.append(DEFAULT_ARG)  # Defaulting
        args.append("")

    # Technically these two should be outside this function,
    # but will leave them here

    for ar in args:
        if len(ar) > 0 and ar not in VALID_ARGS:
            print(f"Unknown option '{ar}'. Run with --help for help.")
            sys.exit(os.EX_USAGE)

    if "help" in args:
        print(USAGE)
        sys.exit()

    # At the moment we use only the first argument, disregarding what's next
    return args[0]


if __name__ == "__main__":
    view: str = get_view()
    script_dir: str = str(Path(sys.argv[0]).resolve().parent)
    config: Configuration = Configuration()

    # Attempt auto-configuration
    if not config.saved:
        locator: Locator = Locator()
        configurator: Configurator = Configurator()
        locator.config(config)
        configurator.config(config)
        config.save()

    config.load()

    forecaster: WeatherForecaster = WeatherForecaster(config)
    weather_data: WeatherData = WeatherData()
    forecaster.get_data(weather_data)

    weather_girl: WeatherGirl = WeatherGirl(config, weather_data)
    weather_girl.present(view)
