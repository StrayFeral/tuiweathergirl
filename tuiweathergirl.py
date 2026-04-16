#!/usr/bin/env python

# TUIWEATHERGIRL
# 2026 by StrayF

import requests
import configparser
from datetime import datetime
from pathlib import Path
from babel import Locale
import sys
import os
import re

from zoneinfo import ZoneInfo

from babel.languages import get_official_languages
from babel.dates import format_date

DEFAULT_ARG: str = "simple"
VALID_ARGS: list[str] = ["help", "simple", "nice", "fancy" "glamour"]
VERSION: str = "1.0"
USAGE: str = f"""TUIWEATHERGIRL {VERSION} by StrayF 2026

USAGE: tuiweathergirl.py [--help|<VIEW>]

VIEWS:
    --simple
        Best for barebone terminals.
        Simple print of the date, time, weather data and then exit.

    --nice
        Still nice for barebone terminals.
        Print with some colors.

    --fancy
        Better for moderate to modern terminals.
        Print in colored table with some icons.

    --glamour

HOW DOES TUIWEATHERGIRL.PY WORKS:
    - The application would first check for ~/.tuiweathergirlrc
    - If file is not found, the application would try to auto-configure
        (internet connection required)
    - Once configured, the application would always load the config from the file
    - Feel free to edit the config file
    - To enforce auto-configuration, just delete the config file
"""


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

        self.configfile = self.__CONFIGFILE

        if os.name == "nt":
            self.configfile = "~/tuiweathergirl.rc"

    def __str__(self) -> str:
        return f"{self.city}/{self.province}/{self.country}/{self.continent_code}"

    @property
    def saved(self) -> bool:
        return Path(self.configfile).expanduser().exists()

    def save(self) -> int:
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
            "date_format_length": self.date_format_length,
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
        self.date_format_length = config["PREFERENCES"]["date_format_length"]


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
        mapping = {
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

        assessments: dict[int:str] = {
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

        weather_res = requests.get(url).json()
        aq_res = requests.get(aq_url).json()

        # Extract Data
        curr = weather_res["current"]
        daily = weather_res["daily"]
        aqi = aq_res["current"]["us_aqi"]

        # Format Date and Time
        now = datetime.now(ZoneInfo(self.config.timezone))

        # Fill the object with data
        weather_data.sky = self.__get_weather_description(curr["weather_code"])
        weather_data.temperature = int(curr["temperature_2m"])
        weather_data.min: int = int(daily["temperature_2m_min"][0])
        weather_data.max: int = int(daily["temperature_2m_max"][0])
        weather_data.aqi = int(aqi)
        weather_data.air_quality = self.__get_air_quality_assessment(aqi)
        weather_data.precipitation = daily["precipitation_probability_max"][0]
        weather_data.weather_code = curr["weather_code"]
        weather_data.wind = int(curr["wind_speed_10m"])
        weather_data.wind_direction = self.__get_wind_direction(
            curr["wind_direction_10m"]
        )

        if weather_data.weather_code >= 95:
            weather_data.warnings.append(
                "WARNING: SEVERE THUNDERSTORMS DETECTED IN YOUR AREA"
            )

        # 7 day forecast
        for i in range(1, 8):
            day: BriefDailyForecast = BriefDailyForecast()
            day.min = int(daily["temperature_2m_min"][i])
            day.max = int(daily["temperature_2m_max"][i])
            day.precip = int(daily["precipitation_probability_max"][i])
            day.dow = (now.replace(day=now.day + i)).strftime("%a")
            weather_data.week.append(day)

        return weather_data


class PresentationConfiguration:
    r"""Common presentation logic"""

    def __init__(self, config: Configuration) -> None:
        self.locale_id = f"{config.language}_{config.country_code2}"

        # Units
        self.tunit: str = "celsius" if config.celsius else "fahrenheit"
        self.wunit: str = "kmh" if config.metric else "mph"

        # Removing provinces which contain only numbers
        province_has_letters = bool(re.search(r"\D", config.province))
        self.province: str = ""
        if province_has_letters:
            self.province = f"{self.config.province}, "

        # Temperature & Wind (Using your XXC / XXunit Direction format)
        self.tsuffix: str = "C" if config.celsius else "F"
        self.wunit: str = "kmh" if config.metric else "mph"

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


class SimpleView:
    r"""Just prints"""

    def __init__(
        self,
        config: Configuration,
        data: WeatherData,
        present_config: PresentationConfiguration,
    ) -> None:
        self.config: Configuration = config
        self.data: WeatherData = data
        self.presconf: PresentationConfiguration = present_config

    def display(self) -> None:
        timenow: str = self.presconf.update_time()
        datenow: str = self.presconf.date

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
        precipitation: str = self.data.precipitation

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

            print(f"  {dow}: {dmin}/{dmax}{tsuffix} | {dprecip}%")

        print("\n")
        for warning in warnings:
            print(warning)

        print("Try: tuiweathergirl.py --help")


class WeatherGirl:
    r"""Your daily weather girl"""

    def __init__(self, config: Configuration, data: WeatherData) -> None:
        present_config: PresentationConfiguration = PresentationConfiguration(config)
        self.views: dict[obj] = {"simple": SimpleView(config, data, present_config)}

    def present(self, view: str) -> None:
        self.views[view].display()


def get_view() -> str:
    args: list[str] = []
    if len(sys.argv) > 1:
        args = [arg.lower().lstrip("-") for arg in sys.argv]
        del args[0]  # Deleting the script name
    else:
        args.append(DEFAULT_ARG)  # Defaulting

    # Technically these two should be outside this function,
    # but will leave them here

    for ar in args:
        if not ar in VALID_ARGS:
            print(f"Unknown option '{ar}'. Run with --help for help.")
            sys.exit(os.EX_USAGE)

    if "help" in args:
        print(USAGE)
        sys.exit()

    return args[0]


if __name__ == "__main__":
    view: str = get_view()
    script_dir: str = Path(sys.argv[0]).resolve().parent
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
