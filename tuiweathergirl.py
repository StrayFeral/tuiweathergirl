#!/usr/bin/env python

# TUIWEATHERGIRL
# 2026 by StrayF

import configparser
import curses
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pprint as pp
from zoneinfo import ZoneInfo

import requests
from babel import Locale
from babel.dates import format_date
from babel.languages import get_official_languages

DEFAULT_ARG: str = "nice"
VALID_ARGS: list[str] = ["help", "simple", "nice", "color", "fancy" "glamour"]
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
    
    --color
        This is just the Nice view, but with colors.

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


class CachedData:
    r"""For when doing tests often or just restarting the app too often
    and avoid being banned by the APIs
    """

    def __init__(self) -> None:
        self.testfilename: str = "tuiweathergirl_test.ini"
        self.cachefilename: str = "/tmp/tuiweathergirl_cache.ini"
        self.filename: str = self.testfilename
        self.loaded: bool = False

        self.sky: str = ""
        self.temperature: int = 0
        self.tmin: int = 0
        self.tmax: int = 0
        self.wind: int = 0
        self.wind_direction: str = "NOTLOADED"
        self.aqi: int = 0
        self.precipitation: int = 0
        self.weather_code: int = 0
        self.warning: str = "NOT LOADED"

        self.daynames: list[str] = []
        self.mins: list[str] = []
        self.maxs: list[str] = []
        self.precipitations: list[str] = []

        if self.saved:
            self.load()

    @property
    def too_soon(self):
        cache_path = Path(self.cachefilename).expanduser()
        if not cache_path.exists():
            return False

        mtime = cache_path.stat().st_mtime
        last_modified_date = datetime.fromtimestamp(mtime).astimezone()
        now = datetime.now().astimezone()

        # Modified less than 5 mins ago:
        return now - last_modified_date < timedelta(minutes=5)

    @property
    def saved(self) -> bool:
        test_path = Path(self.testfilename).expanduser()
        cache_path = Path(self.cachefilename).expanduser()
        if test_path.exists():
            self.filename: str = self.testfilename
            return True
        if cache_path.exists():
            self.filename: str = self.cachefilename
            mtime = cache_path.stat().st_mtime
            last_modified_date = datetime.fromtimestamp(mtime).astimezone()
            now = datetime.now().astimezone()

            # Modified less than 5 mins ago:
            # Load the cache, don't bother the API
            return self.too_soon
        return False

    def load(self) -> None:
        r"""Reads the cache"""

        if not self.saved:
            raise Exception("Tried to load unsaved cache.")

        config = configparser.ConfigParser()
        full_path = Path(self.filename).expanduser()
        config.read(full_path)

        self.sky = config["TODAY"]["sky"]
        self.temperature = int(config["TODAY"]["temperature"])
        self.tmin = int(config["TODAY"]["tmin"])
        self.tmax = int(config["TODAY"]["tmax"])
        self.wind = int(config["TODAY"]["wind"])
        self.wind_direction = config["TODAY"]["wind_direction"]
        self.aqi = int(config["TODAY"]["aqi"])
        self.precipitation = int(config["TODAY"]["precipitation"])
        self.weather_code = int(config["TODAY"]["weather_code"])
        self.warning = config["TODAY"]["warning"]

        self.daynames = config.get("FORECAST", "daynames").split(",")
        self.mins = config.get("FORECAST", "mins").split(",")
        self.maxs = config.get("FORECAST", "maxs").split(",")
        self.precipitations = config.get("FORECAST", "precipitations").split(",")

        self.loaded = True

    def save(self):
        """Saves the cache."""

        if self.too_soon:
            return

        # I don't care of a previous cache
        cachefile: Path = Path(self.cachefilename)
        cachefile.unlink(missing_ok=True)

        config = configparser.ConfigParser()

        config["TODAY"] = {
            "sky": self.sky,
            "temperature": str(self.temperature),
            "tmin": str(self.tmin),
            "tmax": str(self.tmax),
            "wind": str(self.wind),
            "wind_direction": self.wind_direction,
            "aqi": str(self.aqi),
            "precipitation": str(self.precipitation),
            "weather_code": str(self.weather_code),
            "warning": self.warning,
        }

        config["FORECAST"] = {
            "daynames": ",".join(self.daynames),
            "mins": ",".join(map(str, self.mins)),
            "maxs": ",".join(map(str, self.maxs)),
            "precipitations": ",".join(map(str, self.precipitations)),
        }

        with open(self.cachefilename, "w", encoding="utf-8") as f:
            config.write(f)


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

        cache = CachedData()

        if cache.loaded:
            # Fill the object with data
            weather_data.sky = cache.sky
            weather_data.temperature = cache.temperature
            weather_data.min = cache.tmin
            weather_data.max = cache.tmax
            weather_data.aqi = cache.aqi
            weather_data.air_quality = self.__get_air_quality_assessment(cache.aqi)
            weather_data.precipitation = cache.precipitation
            weather_data.weather_code = cache.weather_code
            weather_data.wind = cache.wind
            weather_data.wind_direction = cache.wind_direction
            weather_data.warnings = []
            weather_data.week = []
            weather_data.warnings.append(cache.warning)

            # 7 day forecast
            for i in range(0, 7):
                day: BriefDailyForecast = BriefDailyForecast()
                day.min = int(cache.mins[i])
                day.max = int(cache.maxs[i])
                day.precip = int(cache.precipitations[i])
                day.dow = cache.daynames[i]
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

            weather_data.warnings = []
            weather_data.week = []

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

    def get_temp_cp(self, t: int) -> int:
        r"""Get the appropriate temperature color pair"""

        if t < 11:
            return 7
        if 11 <= t <= 20:
            return 6
        if 21 <= t <= 38:
            return 2
        if 39 <= t <= 44:
            return 5
        return 1

    def get_sky_cp(self, sky: str) -> int:
        r"""Get the appropriate sky color pair"""

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
            raise Exception(f"Invalid sky value '{sky}'.")
        return d[sky]

    def get_aqistr_cp(self, aqistr: str) -> int:
        r"""Get the appropriate aqi color pair"""

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
        if aqistr not in d:
            raise Exception(f"Invalid AQI value '{aqistr}'.")
        return d[aqistr]

    def get_progbar_cp(self, p: int) -> int:
        if p < 40:
            return 4
        return 7

    def prog_bar(self, percent: int, maxchar: int = 10) -> str:
        # Ensure percent stays within 0-100 bounds
        percent = max(0, min(100, percent))

        count = round(percent / maxchar)

        # DOS Era characters:
        # █ (Full Block) or ▓ (Dark Shade) for progress
        # ░ (Light Shade) for the background/remaining
        fill_char = "#"
        empty_char = "."

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

        # Saving the cache
        cache = CachedData()
        cache.sky = sky
        cache.temperature = temperature
        cache.tmin = tmin
        cache.tmax = tmax
        cache.wind = wind
        cache.wind_direction = winddir
        cache.aqi = aqi
        cache.precipitation = precipitation
        cache.weather_code = self.data.weather_code

        cache.warning = "No warnings."
        if len(warnings) > 0:
            cache.warning = warnings[0]

        cache.daynames = []
        cache.mins = []
        cache.maxs = []
        cache.precipitations = []
        for day in week:
            cache.mins.append(day.min)
            cache.maxs.append(day.max)
            cache.precipitations.append(day.precip)
            cache.daynames.append(day.dow)

        cache.save()


class NiceView(View):
    """Nice view"""

    def screen(self, stdscr: curses.window) -> None:
        forecaster: WeatherForecaster = WeatherForecaster(self.config)

        # Global settings
        stdscr.erase()
        self.test_terminal_size(stdscr)
        stdscr.nodelay(True)
        curses.curs_set(False)  # Hide cursor

        # Data which won't change
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country

        # Init
        view_width: int = 73
        data_box_width: int = 36
        datax: int = 16
        time24_x: int = 45
        if not self.config.time24:
            time24_x = time24_x - 2

        # Windows initialization
        title_win = curses.newwin(3, view_width, 0, 1)
        location_win = curses.newwin(1, view_width - 1, 3, 2)
        status_win = curses.newwin(7, data_box_width, 4, 1)
        air_win = curses.newwin(7, data_box_width, 4, 38)
        forecast_win = curses.newwin(8, view_width, 12, 1)
        warnings_win = curses.newwin(4, view_width, 21, 1)
        brief_win = curses.newwin(1, view_width, 25, 1)
        last_refresh_win = curses.newwin(1, view_width, 26, 1)

        # Printing this just once
        title_win.attron(curses.A_DIM)
        title_win.box()
        title_win.addstr(
            1,
            2,
            f"TUIWEATHERGIRL {VERSION}                                     by StrayF 2026",
        )

        location_win.attron(curses.A_DIM)
        location_win.addstr(0, 0, f"Location: {city}, {province}{country}")

        last_refresh: str = ""

        # -------------------------------------------------- VIEW MAIN LOOP
        elapsed: int = 0
        while True:
            elapsed += 1

            stdscr.attron(curses.A_DIM)

            # Data to display
            timenow: str = self.presconf.update_time()
            datenow: str = self.presconf.date

            if len(last_refresh) == 0:
                last_refresh = f"Last refresh: {datenow} {timenow}"

            # Technically we do not need this, but filling up the addstr()s
            # later would be more messy without it
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

            # Saving the cache
            cache = CachedData()
            cache.sky = sky
            cache.temperature = temperature
            cache.tmin = tmin
            cache.tmax = tmax
            cache.wind = wind
            cache.wind_direction = winddir
            cache.aqi = aqi
            cache.precipitation = precipitation
            cache.weather_code = self.data.weather_code

            cache.warning = "No warnings."
            if len(warnings) > 0:
                cache.warning = warnings[0]

            cache.daynames = []
            cache.mins = []
            cache.maxs = []
            cache.precipitations = []
            for day in week:
                cache.mins.append(day.min)
                cache.maxs.append(day.max)
                cache.precipitations.append(day.precip)
                cache.daynames.append(day.dow)

            cache.save()

            # ----------------------------------------- Screen update
            location_win.move(0, time24_x)
            location_win.clrtoeol()
            location_win.addstr(0, time24_x, f"Today: {datenow} {timenow}")

            status_win.erase()
            status_win.move(0, 0)
            status_win.attron(curses.A_DIM)
            status_win.box()
            status_win.addstr(2, 0, "├──────────────────────────────────┤")
            status_win.addstr(1, 11, "CURRENT STATUS")
            status_win.attroff(curses.A_DIM)
            status_win.addstr(3, 3, "Sky    :")
            status_win.addstr(4, 3, "Temp   :")
            status_win.addstr(5, 3, "Range  :")
            status_win.addstr(3, datax, sky)
            status_win.addstr(4, datax, f"{temperature}°{tsuffix}")
            status_win.addstr(5, datax, f"{tmin}°{tsuffix} / {tmax}°{tsuffix}")

            air_win.erase()
            air_win.move(0, 0)
            air_win.attron(curses.A_DIM)
            air_win.box()
            air_win.addstr(2, 0, "├──────────────────────────────────┤")
            air_win.addstr(1, 10, "AIR & CONDITIONS")
            air_win.attroff(curses.A_DIM)
            air_win.addstr(3, 3, "Wind   :")
            air_win.addstr(4, 3, "AQI    :")
            air_win.addstr(5, 3, "Precip :")
            air_win.addstr(3, datax, f"{wind}{wunit} {winddir}")
            air_win.addstr(4, datax, f"{aqi} ({airquality})")
            air_win.addstr(
                5, datax, f"[{self.prog_bar(precipitation)}] {precipitation}%"
            )

            forecast_win.erase()
            forecast_win.move(0, 0)
            forecast_win.attron(curses.A_DIM)
            forecast_win.box()
            forecast_win.addstr(0, 28, " 7-DAY FORECAST ")
            forecast_win.attroff(curses.A_DIM)

            warnings_win.erase()
            warnings_win.move(0, 0)
            warnings_win.attron(curses.A_DIM)
            warnings_win.box()
            warnings_win.addstr(0, 30, " WARNINGS ")
            warnings_win.attroff(curses.A_DIM)
            if len(warnings) > 0:
                for i in range(len(warnings)):
                    warnings_win.addstr(1 + i, 2, warnings[i])
            else:
                warnings_win.addstr(1, 2, "No warnings.")

            brief_win.erase()
            brief_win.move(0, 0)
            brief_win.attron(curses.A_DIM)
            brief_win.addstr(
                0,
                1,
                f"Auto-refresh: {self.weather_refresh_interval // 60}min                                            [q] Quit",
            )

            last_refresh_win.erase()
            last_refresh_win.move(0, 0)
            last_refresh_win.attron(curses.A_DIM)
            last_refresh_win.addstr(0, 1, last_refresh)

            # 7 day forecast
            for day_cnt, day in enumerate(week):
                wy: int = 2 + (day_cnt % 4)
                wx: int = 3 if day_cnt < 4 else 40

                dmin: int = day.min
                dmax: int = day.max
                dprecip: int = day.precip
                dow: str = day.dow
                temperatures = f"{dmin:>2}°/{dmax}°{tsuffix}"

                forecast_win.move(wy, wx)
                forecast_win.addstr(
                    wy,
                    wx,
                    f"{dow}: {temperatures:<6} [{self.prog_bar(dprecip)}] {dprecip}%",
                )

            # Data update
            if elapsed % self.weather_refresh_interval == 0:
                forecaster.get_data(self.data)
                last_refresh = f"Last refresh: {datenow} {timenow}       "

            keypressed = stdscr.getch()
            if keypressed == ord("q"):
                break

            # Pushing the changes
            title_win.noutrefresh()
            location_win.noutrefresh()
            status_win.noutrefresh()
            air_win.noutrefresh()
            forecast_win.noutrefresh()
            warnings_win.noutrefresh()
            brief_win.noutrefresh()
            last_refresh_win.noutrefresh()
            curses.doupdate()  # Pushes all changes to screen at once

            time.sleep(1)  # Prevent 100% CPU usage

    def display(self) -> None:
        curses.wrapper(self.screen)


class ColorView(View):
    """Color view - same as NiceView but with colors"""

    def screen(self, stdscr: curses.window) -> None:
        # Color definitions
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_RED)  # Warnings
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Sunny
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Cloudy
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Rain
        curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)  # Bad
        curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Good
        curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Title

        stdscr.attron(curses.A_DIM)

        # Color indexes
        col_warn: int = 1
        col_sunny: int = 2
        col_cloudy: int = 3
        col_rain: int = 4
        col_bad: int = 5
        col_good: int = 6
        col_title: int = 7

        forecaster: WeatherForecaster = WeatherForecaster(self.config)

        # Global settings
        stdscr.erase()
        self.test_terminal_size(stdscr)
        stdscr.nodelay(True)
        curses.curs_set(False)  # Hide cursor

        # Data which won't change
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country

        # Init
        view_width: int = 73
        data_box_width: int = 36
        datax: int = 16
        time24_x: int = 45
        if not self.config.time24:
            time24_x = time24_x - 2

        # Windows initialization
        title_win = curses.newwin(3, view_width, 0, 1)
        location_win = curses.newwin(1, view_width - 1, 3, 2)
        status_win = curses.newwin(7, data_box_width, 4, 1)
        air_win = curses.newwin(7, data_box_width, 4, 38)
        forecast_win = curses.newwin(8, view_width, 12, 1)
        warnings_win = curses.newwin(4, view_width, 21, 1)
        brief_win = curses.newwin(1, view_width, 25, 1)
        last_refresh_win = curses.newwin(1, view_width, 26, 1)

        title_win.attron(curses.color_pair(col_rain) | curses.A_DIM)
        title_win.box()
        title_win.attroff(curses.color_pair(col_rain) | curses.A_DIM)
        title_win.attron(curses.color_pair(col_cloudy) | curses.A_DIM)
        title_win.addstr(
            1,
            2,
            f"TUIWEATHERGIRL {VERSION}                                     by StrayF 2026",
        )
        title_win.attroff(curses.color_pair(col_cloudy) | curses.A_DIM)

        location_win.addstr(0, 0, f"Location: {city}, {province}{country}")

        last_refresh: str = ""

        # -------------------------------------------------- VIEW MAIN LOOP
        elapsed: int = 0
        while True:
            elapsed += 1

            # Data to display
            timenow: str = self.presconf.update_time()
            datenow: str = self.presconf.date

            if len(last_refresh) == 0:
                last_refresh = f"Last refresh: {datenow} {timenow}"

            # Technically we do not need this, but filling up the addstr()s
            # later would be more messy without it
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

            # Saving the cache
            cache = CachedData()
            cache.sky = sky
            cache.temperature = temperature
            cache.tmin = tmin
            cache.tmax = tmax
            cache.wind = wind
            cache.wind_direction = winddir
            cache.aqi = aqi
            cache.precipitation = precipitation
            cache.weather_code = self.data.weather_code

            cache.warning = "No warnings."
            if len(warnings) > 0:
                cache.warning = warnings[0]

            cache.daynames = []
            cache.mins = []
            cache.maxs = []
            cache.precipitations = []
            for day in week:
                cache.mins.append(day.min)
                cache.maxs.append(day.max)
                cache.precipitations.append(day.precip)
                cache.daynames.append(day.dow)

            cache.save()

            # ----------------------------------------- Screen update
            location_win.move(0, time24_x)
            location_win.clrtoeol()
            location_win.addstr(0, time24_x, f"Today: {datenow} {timenow}")

            status_win.erase()
            status_win.move(0, 0)
            status_win.attron(curses.color_pair(col_rain) | curses.A_DIM)
            status_win.box()
            status_win.addstr(2, 0, "├──────────────────────────────────┤")
            status_win.attroff(curses.color_pair(col_rain) | curses.A_DIM)
            status_win.attron(curses.color_pair(col_title))
            status_win.addstr(1, 11, "CURRENT STATUS")
            status_win.attroff(curses.color_pair(col_title))
            status_win.attron(curses.color_pair(col_cloudy) | curses.A_DIM)
            status_win.addstr(3, 3, "Sky    :")
            status_win.addstr(4, 3, "Temp   :")
            status_win.addstr(5, 3, "Range  :")
            status_win.attroff(curses.color_pair(col_cloudy) | curses.A_DIM)
            status_win.attron(curses.color_pair(self.get_sky_cp(sky)))
            status_win.addstr(3, datax, sky)
            status_win.attroff(curses.color_pair(self.get_sky_cp(sky)))
            status_win.attron(curses.color_pair(self.get_temp_cp(temperature)))
            status_win.addstr(4, datax, f"{temperature}°{tsuffix}")
            status_win.attroff(curses.color_pair(self.get_temp_cp(temperature)))
            status_win.attron(curses.color_pair(self.get_temp_cp(tmin)))
            status_win.addstr(5, datax, f"{tmin}°{tsuffix}")
            status_win.attroff(curses.color_pair(self.get_temp_cp(tmin)))
            status_win.addstr(5, datax + 4, "/")
            status_win.attron(curses.color_pair(self.get_temp_cp(tmax)))
            status_win.addstr(5, datax + 6, f"{tmax}°{tsuffix}")
            status_win.attron(curses.color_pair(self.get_temp_cp(tmax)))

            air_win.erase()
            air_win.move(0, 0)
            air_win.attron(curses.color_pair(col_rain) | curses.A_DIM)
            air_win.box()
            air_win.addstr(2, 0, "├──────────────────────────────────┤")
            air_win.attroff(curses.color_pair(col_rain) | curses.A_DIM)
            air_win.attron(curses.color_pair(col_title))
            air_win.addstr(1, 10, "AIR & CONDITIONS")
            air_win.attroff(curses.color_pair(col_title))
            air_win.attron(curses.color_pair(col_cloudy) | curses.A_DIM)
            air_win.addstr(3, 3, "Wind   :")
            air_win.addstr(4, 3, "AQI    :")
            air_win.addstr(5, 3, "Precip :")
            air_win.attroff(curses.color_pair(col_cloudy) | curses.A_DIM)
            air_win.attron(curses.color_pair(col_cloudy))
            air_win.addstr(3, datax, f"{wind}{wunit} {winddir}")
            air_win.attroff(curses.color_pair(col_cloudy))
            air_win.attron(curses.color_pair(self.get_aqistr_cp(airquality)))
            air_win.addstr(4, datax, f"{aqi} ({airquality})")
            air_win.attroff(curses.color_pair(self.get_aqistr_cp(airquality)))
            air_win.attron(curses.color_pair(col_rain))
            air_win.addstr(5, datax, "[")
            air_win.attroff(curses.color_pair(col_rain))
            air_win.attron(curses.color_pair(self.get_progbar_cp(precipitation)))
            air_win.addstr(5, datax + 1, self.prog_bar(precipitation))
            air_win.attroff(curses.color_pair(self.get_progbar_cp(precipitation)))
            air_win.attron(curses.color_pair(col_rain))
            air_win.addstr(5, datax + 10, "]")
            air_win.attroff(curses.color_pair(col_rain))
            air_win.attron(curses.color_pair(self.get_progbar_cp(precipitation)))
            air_win.addstr(5, datax + 12, f"{precipitation}%  ")
            air_win.attroff(curses.color_pair(self.get_progbar_cp(precipitation)))

            forecast_win.erase()
            forecast_win.move(0, 0)
            forecast_win.attron(curses.color_pair(col_rain) | curses.A_DIM)
            forecast_win.box()
            forecast_win.attroff(curses.color_pair(col_rain) | curses.A_DIM)
            forecast_win.attron(curses.color_pair(col_title))
            forecast_win.addstr(0, 28, " 7-DAY FORECAST ")
            forecast_win.attroff(curses.color_pair(col_title))
            forecast_win.attroff(curses.A_DIM)

            warnings_win.erase()
            warnings_win.move(0, 0)
            warnings_win.attron(curses.color_pair(col_bad))
            warnings_win.box()
            warnings_win.attroff(curses.color_pair(col_bad))
            warnings_win.attron(curses.color_pair(col_cloudy))
            warnings_win.addstr(0, 30, " WARNINGS ")
            warnings_win.attroff(curses.color_pair(col_cloudy))
            if len(warnings) > 0:
                warnings_win.attron(curses.color_pair(col_sunny))
                for i in range(len(warnings)):
                    warnings_win.addstr(1 + i, 2, warnings[i])
                warnings_win.attroff(curses.color_pair(col_bad))
            else:
                warnings_win.attron(curses.color_pair(col_good) | curses.A_DIM)
                warnings_win.addstr(1, 2, "No warnings.")
                warnings_win.attroff(curses.color_pair(col_good) | curses.A_DIM)

            brief_win.erase()
            brief_win.move(0, 0)
            brief_win.attron(curses.A_DIM)
            brief_win.addstr(
                0,
                1,
                f"Auto-refresh: {self.weather_refresh_interval // 60}min                                            [q] Quit",
            )

            last_refresh_win.erase()
            last_refresh_win.move(0, 0)
            last_refresh_win.attron(curses.A_DIM)
            last_refresh_win.addstr(0, 1, last_refresh)

            # 7 day forecast
            for day_cnt, day in enumerate(week):
                wy: int = 2 + (day_cnt % 4)
                wx: int = 3 if day_cnt < 4 else 40

                dmin: int = day.min
                dmax: int = day.max
                dprecip: int = day.precip
                dow: str = day.dow

                forecast_win.move(wy, wx)
                forecast_win.attron(curses.color_pair(col_cloudy) | curses.A_DIM)
                forecast_win.addstr(wy, wx, f"{dow}:")
                forecast_win.attroff(curses.color_pair(col_cloudy) | curses.A_DIM)
                forecast_win.attron(curses.color_pair(self.get_temp_cp(dmin)))
                tmins = f"{dmin:>2}°"
                forecast_win.addstr(wy, wx + 5, f"{tmins}:")
                forecast_win.attroff(curses.color_pair(self.get_temp_cp(dmin)))
                forecast_win.attron(curses.color_pair(col_cloudy))
                forecast_win.addstr(wy, wx + 8, "/")
                forecast_win.attroff(curses.color_pair(col_cloudy))
                forecast_win.attron(curses.color_pair(self.get_temp_cp(dmax)))
                tmaxs = f"{dmax}°{tsuffix}"
                forecast_win.addstr(wy, wx + 9, f"{tmaxs}")
                forecast_win.attroff(curses.color_pair(self.get_temp_cp(dmax)))
                forecast_win.attron(curses.color_pair(col_rain))
                forecast_win.addstr(wy, wx + 14, "[")
                forecast_win.attroff(curses.color_pair(col_rain))
                forecast_win.attron(curses.color_pair(self.get_progbar_cp(dprecip)))
                forecast_win.addstr(wy, wx + 15, self.prog_bar(dprecip))
                forecast_win.attroff(curses.color_pair(self.get_progbar_cp(dprecip)))
                forecast_win.attron(curses.color_pair(col_rain))
                forecast_win.addstr(wy, wx + 25, "]")
                forecast_win.attroff(curses.color_pair(col_rain))
                forecast_win.attron(curses.color_pair(self.get_progbar_cp(dprecip)))
                forecast_win.addstr(wy, wx + 27, f"{dprecip}%  ")
                forecast_win.attroff(curses.color_pair(self.get_progbar_cp(dprecip)))

            # Data update
            if elapsed % self.weather_refresh_interval == 0:
                forecaster.get_data(self.data)
                last_refresh = f"Last refresh: {datenow} {timenow}       "

            keypressed = stdscr.getch()
            if keypressed == ord("q"):
                break

            # Pushing the changes
            title_win.noutrefresh()
            location_win.noutrefresh()
            status_win.noutrefresh()
            air_win.noutrefresh()
            forecast_win.noutrefresh()
            warnings_win.noutrefresh()
            brief_win.noutrefresh()
            last_refresh_win.noutrefresh()
            curses.doupdate()  # Pushes all changes to screen at once

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
            "color": ColorView(config, data, present_config),
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
