#!/usr/bin/env python

# TUIWEATHERGIRL
# 2026 by Evgueni Antonov (StrayF)

import argparse
import configparser
import csv
import curses
import math
import os
import random
import re
import socket
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pprint import pformat as pf
from pprint import pprint as pp
from zoneinfo import ZoneInfo

import requests
from babel import Locale
from babel.dates import format_date
from babel.languages import get_official_languages

# Normally I don't leave global variables hanging in the source but
# I intentionally left these here, as I tend to change them time to time
# and don't want to scroll too much to find them

DEBUG_MODE: bool = False
DEFAULT_VIEW: str = "color"
APPVERSION: str = "1.0"
DESCRIPTION_HELP: str = (
    f"TUIWEATHERGIRL {APPVERSION} by Evgueni Antonov (StrayF) 2026. Your daily terminal weathergirl."
)
EPILOGUE_HELP: str = """VIEWS:
    motivate and basic
        Best for barebone terminals.
        Printing to STDOUT then exit. You would enjoy the Motivate view a lot.

    nice
        Monochrome ncurses text interface.
    
    color
        Same as Nice view, but with colors.
    
    setup
        Prints the currently set cities.

NOTE: --addcity and --country must be passed together.

HOW DOES TUIWEATHERGIRL WORKS:
    - The app would auto-configure. Config file: ~/.tuiweathergirlrc
    - You may edit it, but if you mess-it up, better delete it and run the app again
    - You may add up to 10 additional cities, but not every view will show them all

PROJECT URL: https://github.com/StrayFeral/tuiweathergirl
Variable TIMEZONEAPIKEY must be set with a free API key from https://timezonedb.com/
"""
APIKEYENVVARNAME: str = "TIMEZONEAPIKEY"
MIN_COLS: int = 79
MIN_LINES: int = 24
SUBMIT_BUG: str = "Submit a bug to the project GitHub page and attach your config file."
REFRESH_INTERVAL: int = 1200  # 20 minutes
DEFAULT_LOCALE: str = "en_US"  # The fallback plan

# Color indexes
COL_YELOWRED: int = 1
COL_YELOWBLACK: int = 2
COL_WHITEBLACK: int = 3
COL_BLUEBLACK: int = 4
COL_REDBLACK: int = 5
COL_GREENBLACK: int = 6
COL_CYANBLACK: int = 7


class InstanceGuard:
    @staticmethod
    def ensure_single_instance(port=47382):
        ip: str = "127.0.0.1"
        global lock_socket
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            lock_socket.bind((ip, port))
        except socket.error:
            raise Exception(
                "Error: Application is already running. If you suspect another instance stalled, please check applications listening at {ip}:{port}."
            )


class APIIssues:
    _API_PROBLEMS: dict[int, str] = {
        400: f"Bad request. Fix the API request. {SUBMIT_BUG}",
        401: "You have been PERMANENTLY banned by the API. There is nothing I could do to help. Sorry.",
        402: "Payment required.",
        403: "You have been soft-banned by the API. Please wait 24 hours and try again.",
        407: "Proxy Authentication Required.",
        408: "Request Timeout.",
        410: f"Seems the API provider does not exist anymore. {SUBMIT_BUG}",
        429: "You have been temporarely banned by the API. Please wait 2 minutes and try again.",
        500: "The API server crashed. Please try again in few hours.",
        502: "API server problem. Please try again in few hours.",
        503: "The API server is down for maintenance. Please try again in few hours.",
        504: "Problem with the API server. Please try again in 10 minutes",
        505: f"HTTP version not supported. {SUBMIT_BUG}",
    }

    @staticmethod
    def get_api_problem(http_code: int) -> str:
        return (
            APIIssues._API_PROBLEMS[http_code]
            if http_code in APIIssues._API_PROBLEMS
            else ""
        )


class Theme:
    def __init__(self, **kwargs) -> None:
        self.general: int = kwargs["general"]
        self.border: int = kwargs["border"]
        self.header: int = kwargs["header"]
        self.home: int = kwargs["home"]
        self.title: int = kwargs["title"]
        self.warntitle: int = kwargs["warntitle"]
        self.warnborder: int = kwargs["warnborder"]

        self._last_used: int = None
        self._last_win: curses.window = None

    def on(self, win: curses.window, attr: str | int) -> None:
        cp: str | int = attr
        if isinstance(attr, str):
            if not hasattr(self, attr):
                raise Exception(f"Theme object does not have attribute '{key}'.")
            cp = getattr(self, attr, None)
        win.attron(curses.color_pair(cp))
        self._last_used = cp
        self._last_window = win

    def off(self) -> None:
        self._last_win.attroff(curses.color_pair(self._last_used))


class MainTheme(Theme):
    def __init__(self) -> None:
        super.__init__(
            {
                "general": COL_WHITEBLACK | curses.A_DIM,
                "border": COL_BLUEBLACK | curses.A_DIM,
                "header": COL_WHITEBLACK | curses.A_DIM,
                "home": COL_WHITEBLACK,
                "title": COL_CYANBLACK,
                "warntitle": COL_WHITEBLACK,
                "warnborder": COL_REDBLACK,
            }
        )


class ThemePalette:
    def __init__(self) -> None:
        self.box: dict[str, Theme] = {"main": MainTheme}

    def get_theme(self, themename: str = "main") -> Theme:
        if not themename in self.box:
            raise Exception(f"Invalid theme name '{themename}'.")
        return self.box[themename]


class TUIBox:
    def __init__(self, **kwargs):
        theme: Theme | None = kwargs.get("theme", None)
        stdscr: curses.window = kwargs.get("stdscr")
        y: int = kwargs.get("y")
        x: int = kwargs.get("x")
        height: int = kwargs.get("height")
        width: int = kwargs.get("width")
        title: str = kwargs.get("title", "")

        inner_height = height - 2
        inner_width = width - 2
        if inner_height < 1:
            raise Exception(f"Window '{title}' is too shallow.")
        if inner_width < 1:
            raise Exception(f"Window '{title}' is too narrow.")
        if len(title) + 4 > width:
            raise Exception(f"The title for window '{title}' is too long.")

        self.theme: Theme | None = theme
        self.scr: curses.window = stdscr
        self.boxwin: curses.window = curses.newwin(height, width, y, x)
        # self.win: curses.window = curses.newwin(lines-2, cols-2, y+1, x+1)
        self.boxwin.derwin(inner_height, inner_width, y + 1, x + 1)
        self.win.scrollok(True)
        self.title: str = title

    def draw_box(self) -> None:
        if self.theme:
            self.theme.on(self.boxwin, "border")
            self.boxwin.box()
            self.theme.off()
            if self.title and len(self.title) > 0:
                self.theme.on(self.boxwin, "title")
                self.boxwin.addstr(0, 2, f"[ {self.title} ]")
                self.theme.off()
        else:
            self.boxwin.box()
            if self.title and len(self.title) > 0:
                self.boxwin.addstr(0, 2, f"[ {self.title} ]")
        # self.boxwin.refresh()

    def printyx(self, y: int, x: int, s: str, theme_key: str = "general"):
        if self.theme:
            self.theme.on(self.win, theme_key)
            self.win.addstr(y, x, s)
            self.theme.off()
        else:
            self.win.addstr(y, x, s)

    def print(self, s: str, theme_key: str = "general"):
        if self.theme:
            self.theme.on(self.win, theme_key)
            self.win.addstr(s)
            self.theme.off()
        else:
            self.win.addstr(s)

    def refresh(self) -> None:
        self.win.noutrefresh()

    def clear(self) -> None:
        self.win.erase()


class TUICanvas:
    def __init__(self, stdscr: curses.window) -> None:
        self.scr: curses.window = stdscr
        self.boxes: list[TUIBox] = []

    def init_colors(self) -> None:
        # Color definitions
        curses.start_color()
        curses.init_pair(
            COL_YELOWRED, curses.COLOR_YELLOW, curses.COLOR_RED
        )  # Warnings
        curses.init_pair(
            COL_YELOWBLACK, curses.COLOR_YELLOW, curses.COLOR_BLACK
        )  # Sunny
        curses.init_pair(
            COL_WHITEBLACK, curses.COLOR_WHITE, curses.COLOR_BLACK
        )  # Cloudy
        curses.init_pair(COL_BLUEBLACK, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Rain
        curses.init_pair(COL_REDBLACK, curses.COLOR_RED, curses.COLOR_BLACK)  # Bad
        curses.init_pair(COL_GREENBLACK, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Good
        curses.init_pair(COL_CYANBLACK, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Title

        # Global settings
        self.scr.erase()
        self.scr.nodelay(True)
        curses.curs_set(False)  # Hide cursor

    def refresh(self) -> None:
        """Pushes all changes to screen at once"""
        for box in self.boxes:
            box.refresh()
        curses.doupdate()


class LayoutColumn:
    def __init__(self, **kwargs) -> None:
        self.x: int = kwargs["x"]
        self.width: int = kwargs["width"]


class Layout:
    """Defines a layout.

    An entity made of columns, with horizontal (top and bottom) and vertical
    (left and right) margins, horizontal and vertical spacings between the
    columns and the boxes (windows).

    The columns are defined from left to right. If there is only one column
    it can be set centered.
    """

    def __init__(self, **kwargs) -> None:
        self.xspacing: int = kwargs.get("xspacing", 0)
        self.yspacing: int = kwargs.get("yspacing", 0)
        self.xmargin: int = kwargs.get("xmargin", 0)
        self.ymargin: int = kwargs.get("ymargin", 0)
        self.maxy: int = kwargs.get("maxy")
        self.maxx: int = kwargs.get("maxx")
        self.columns: list[LayoutColumn] = []

        # One of the columns has been centered
        self.__centered: bool = False

    @property
    def __free_column_space(self) -> int:
        return self.maxx - (
            (self.xmargin * 2)
            + sum([c.width for c in self.columns])
            + (len(self.columns) * self.xspacing)
        )

    @property
    def __next_column_x(self) -> int:
        if len(self.columns) == 0:
            return 0
        return self.columns[-1].x + self.columns[-1].width + self.xspacing

    def add_column(self, width: int) -> None:
        if self.__centered:
            raise Exception(
                "Cannot add more columns. One column has been already centered."
            )
        if width > self.__free_column_space:
            raise Exception(
                f"Cannot add the {len(self.columns)+1} column to layout: Wider than the remaining free width space of {self.__free_column_space} chars."
            )

        column: LayoutColumn = LayoutColumn(x=self.__next_column_x, width=width)
        self.columns.append(column)

    def set_centered(self) -> None:
        if len(self.columns) > 1:
            raise Exception(
                "Method set_centered() could be used only if there is just one column. Currently there are more."
            )
        self.columns[0].x = self.maxx // 2 - self.columns[0].width // 2
        self.__centered = True


class LayoutManager:
    def __init__(self, **kwargs) -> None:
        self.stdscr: curses.window = kwargs.get("stdscr")
        self.canvas: TUICanvas = TUICanvas(stdscr)
        maxy, maxx = self.stdscr.getmaxyx()
        self.maxy: int = maxy
        self.maxx: int = maxx
        self.layout: Layout = Layout(
            maxx=maxx,
            maxy=maxy,
            xspacing=kwargs.get("xspacing", 0),
            yspacing=kwargs.get("yspacing", 0),
            xmargin=kwargs.get("xmargin", 0),
            ymargin=kwargs.get("ymargin", 0),
        )
        self.theme: Theme = kwargs.get("theme", ThemePalette().get_theme())
        self.boxes: list[list[TUIBox]] = []

        self.canvas.init_colors()

    def add_column(self, width: int) -> None:
        self.layout.add_column(width)

    def add_box(self, **kwargs) -> TUIBox:
        """Creates a new box, adds it to the internal list and returns it as well."""

        column_num: int = kwargs.get("column_num", 0)
        title: str = kwargs.get("title", "")
        height: int = kwargs.get("height", 3)
        width: int = kwargs.get("width", 1)
        overflow: bool = kwargs.getboolean("overflow", False)
        y: int | None = kwargs.get("y", None)
        x: int | None = kwargs.get("x", None)

        if len(self.layout.columns) == 0:
            raise Exception("No layout columns defined. New box cannot be added.")
        if column_num > len(self.layout.columns) - 1:
            raise Exception(
                f"New box cannot be added as column '{column_num}' does not exist."
            )

        if len(self.boxes) < len(self.layout.columns):
            self.boxes.append([])

        box_index: int = 0
        if len(self.boxes[column_num]) > 0:
            box_index = len(self.boxes[column_num]) - 1

        if not x:
            x = self.layout.columns[column_num].x

        if not overflow and (
            width > self.layout.columns[column_num].width or x + width > self.maxx
        ):
            raise Exception(
                f"New Box[{column_num}][{box_index}] is wider than the column."
            )
        if overflow and (width > self.maxx or x + width > self.maxx):
            raise Exception(
                f"New Box[{column_num}][{box_index}] is wider than the screen."
            )

        # y: int = 0
        if not y and len(self.boxes[column_num]) > 0:
            y = (
                self.boxes[column_num][-1].y
                + self.boxes[column_num][-1].height
                + self.layout.ymargin
            )

        if y + height > self.maxy:
            raise Exception(
                f"New Box[{column_num}][{box_index}] height is going below the screen."
            )

        box: TUIBox = TUIBox(
            theme=self.theme,
            stdscr=self.stdscr,
            y=y,
            x=x,
            height=height,
            width=width,
            title=title,
        )
        self.boxes[column_num].append(box)

        return box

    def draw_boxes(self) -> None:
        for column in self.boxes:
            for box in column:
                box.draw_box()
    
    def refresh_screen(self) -> None:
        """Pushes all the changes to the screen"""
        for column in self.boxes:
            for box in column:
                box.refresh()
        curses.doupdate()  # Pushes all changes to screen at once


class LogEntry:
    def __init__(
        self,
        city: str,
        country: str,
        message: str,
        datestr: str = "",
        timestr: str = "",
    ) -> None:
        self.city = city
        self.country: str = country
        self.message: str = message
        self.date: str = datestr
        self.time: str = timestr


class MajorEventsLogger:
    def __init__(self):
        self.keep_max_days: int = 7
        self.filename: str = "~/.tuiweathergirl_event_log"

        if os.name == "nt":
            self.filename = Path(tempfile.gettempdir()) / "tuiweathergirl_event.log"

    def __cleanup(self) -> None:
        """Removes entries older than keep_max_days."""

        full_path = Path(self.filename).expanduser()
        if not full_path.exists():
            return

        cutoff = datetime.now() - timedelta(days=self.keep_max_days)
        remaining_rows = []

        with open(full_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                try:
                    log_date = datetime.strptime(row[0], "%Y-%m-%d")
                    if log_date >= cutoff:
                        remaining_rows.append(row)
                except (ValueError, IndexError):
                    continue

        with open(full_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(remaining_rows)

    def append(self, s: str) -> None:
        full_path = Path(self.filename).expanduser()
        # Format: yyyy-mm-dd, HH:MM:SS
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        # Append mode ensures we don't overwrite
        with open(full_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([date_str, time_str, s[:50]])

        # Optional: Housekeeping to keep file small
        self.__cleanup()

    def read(self, i: int = 4) -> list[list[str]]:
        full_path = Path(self.filename).expanduser()
        if not full_path.exists():
            return []

        # Calculate the threshold: 00:00:00 of the previous day
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today - timedelta(days=1)

        valid_entries = []

        with open(full_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue

                # Parse the date and time from the log
                log_dt = datetime.strptime(f"{row[0]} {row[1]}", "%Y-%m-%d %H:%M:%S")

                if log_dt >= yesterday_start:
                    # Combine date/time as one timestamp string for the return format
                    timestamp = f"{row[0]} {row[1]}"
                    valid_entries.append([timestamp, row[2]])

        # Sort newest first and slice the last 'i' elements
        valid_entries.reverse()
        return valid_entries[:i]


class CachedData:
    r"""For when doing tests often or just restarting the app too often
    and avoid being banned by the APIs
    """

    def __init__(self) -> None:
        self.testfilename: str = "tuiweathergirl_test.ini"
        self.cachefilename: str = (
            Path(tempfile.gettempdir()) / "tuiweathergirl_cache.ini"
        )
        self.filename: str = self.testfilename
        self.loaded: bool = False

        self.is_day: bool = True
        self.sky: str = ""
        self.temperature: int = 0
        self.tmin: int = 0
        self.tmax: int = 0
        self.wind: int = 0
        self.wind_direction: str = "NOTLOADED"
        self.aqi: int = 0
        self.precipitation: int = 0
        self.weather_code: int = 0
        self.warning: str = "NOTLOADED"
        self.hmin: int = 0
        self.hmax: int = 0

        self.daynames: list[str] = []
        self.mins: list[str] = []
        self.maxs: list[str] = []
        self.precipitations: list[str] = []

        self.followcities: list[dict[str | bool | int]] = []

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
        return now - last_modified_date < timedelta(minutes=REFRESH_INTERVAL // 60)

    @property
    def saved(self) -> bool:
        test_path = Path(self.testfilename).expanduser()
        cache_path = Path(self.cachefilename).expanduser()
        if test_path.exists():
            self.filename: str = self.testfilename
            return True
        if cache_path.exists():
            self.filename: str = self.cachefilename

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

        self.is_day = config.getboolean("TODAY", "is_day")
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
        self.hmin = int(config["TODAY"]["hmin"])
        self.hmax = int(config["TODAY"]["hmax"])

        self.daynames = config.get("FORECAST", "daynames").split(",")
        self.mins = config.get("FORECAST", "mins").split(",")
        self.maxs = config.get("FORECAST", "maxs").split(",")
        self.precipitations = config.get("FORECAST", "precipitations").split(",")

        for i in range(10):
            index: str = f"FOLLOWCITY{i+1}"
            if index in config:
                city: dict[str | bool | int] = {
                    "is_day": config.getboolean(index, "is_day"),
                    "temperature": int(config[index]["temperature"]),
                    "tmin": int(config[index]["tmin"]),
                    "tmax": int(config[index]["tmax"]),
                }
                self.followcities.append(city)

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
            "is_day": self.is_day,
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
            "hmin": self.hmin,
            "hmax": self.hmax,
        }

        config["FORECAST"] = {
            "daynames": ",".join(self.daynames),
            "mins": ",".join(map(str, self.mins)),
            "maxs": ",".join(map(str, self.maxs)),
            "precipitations": ",".join(map(str, self.precipitations)),
        }

        i: int = 0
        for city in self.followcities:
            config[f"FOLLOWCITY{i+1}"] = {
                "is_day": city["is_day"],
                "temperature": str(city["temperature"]),
                "tmin": str(self["tmin"]),
                "tmax": str(self["tmax"]),
            }
            i += 1

        with open(self.cachefilename, "w", encoding="utf-8") as f:
            config.write(f)


class Configuration:
    r"""Weather configuration"""

    def __init__(self) -> None:
        self._country: str = ""
        self._country_code2: str = ""
        self._city: str = ""
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
        self.view: str = DEFAULT_VIEW

        self.followcities: list[dict[str | int]] = []

        self.filename = "~/.tuiweathergirlrc"

        if os.name == "nt":
            self.filename = "~/tuiweathergirl.ini"

    @property
    def country(self) -> str:
        return self._country

    @country.setter
    def country(self, s: str) -> None:
        self._country = s.title()

        # Proper abbreviations support
        if self._country.upper() in ["USA", "US", "UK", "UAE", "CAR", "DRC"]:
            self._country = self._country.upper()

    @property
    def country_code2(self) -> str:
        return self._country_code2

    @country_code2.setter
    def country_code2(self, s: str) -> None:
        self._country_code2 = s.upper()

    @property
    def city(self) -> str:
        return self._city

    @city.setter
    def city(self, s: str) -> None:
        self._city = s.title()

    def __str__(self) -> str:
        return f"{self.city}/{self.province}/{self.country}/{self.continent_code}"

    def __repr__(self) -> str:
        s: str = f"""CONFIGURATION OBJECT:
City: {self.city}/{self.province}/{self.country}({self.country_code2})/{self.continent_code}
Postal code: {self.postal_code}
Coordinates: {self.lat},{self.lon}
Primary language: {self.language}
Timezone: {self.timezone}"""
        s += f"Time: 24h\n" if self.time24 else f"Time: 12h\n"
        s += f"Speed units: Metric\n" if self.metric else f"Speed units: Imperial\n"
        s += (
            f"Temperature units: Celsius\n"
            if self.celsius
            else f"Temperature units: Fahrenheit\n"
        )
        s += f"Date format length: {self.date_format_length}\n"
        s += f"Default view: {self.view}\n"
        s += f"Filename: {self.filename}\n"

        s += "\nFOLLOWED CITIES:\n"
        s += pf(self.followcities)
        s += "\n"

        return s

    @property
    def dst(self) -> bool:
        if len(self.timezone) == 0:
            return False
        now = datetime.now(ZoneInfo(self.timezone))
        return now.dst().total_seconds() != 0

    @property
    def saved(self) -> bool:
        return Path(self.filename).expanduser().exists()

    def save(self) -> None:
        r"""Write the configuration to the config file"""

        config = configparser.ConfigParser()

        config["HOME"] = {
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

        for i, city in enumerate(self.followcities):
            config[f"FOLLOWCITY{i+1}"] = {
                "country": city["country"],
                "country_code2": city["country_code2"],
                "city": city["city"],
                "postal_code": str(city["postal_code"]),
                "province": str(city["province"]),
                "lat": str(city["lat"]),
                "lon": str(city["lon"]),
                "continent_code": city["continent_code"],
                "timezone": city["timezone"],
            }

        # Write to a file
        full_path = Path(self.filename).expanduser()
        with open(full_path, "w") as configfile:
            config.write(configfile)

    def load(self) -> None:
        r"""Read the configuration from the config file"""

        if not self.saved:
            raise Exception("Tried to load unsaved configuration.")

        config = configparser.ConfigParser()
        full_path = Path(self.filename).expanduser()
        config.read(full_path)

        self.country = config["HOME"]["country"]
        self.country_code2 = config["HOME"]["country_code2"]
        self.city = config["HOME"]["city"]
        self.postal_code = config["HOME"]["postal_code"]
        self.province = config["HOME"]["province"]
        self.lat = config["HOME"]["lat"]
        self.lon = config["HOME"]["lon"]
        self.continent_code = config["HOME"]["continent_code"]
        self.timezone = config["HOME"]["timezone"]
        self.language = config["PREFERENCES"]["language"]
        self.time24 = config.getboolean("PREFERENCES", "time24")
        self.metric = config.getboolean("PREFERENCES", "metric")
        self.celsius = config.getboolean("PREFERENCES", "celsius")
        # self.date_format_length = config["PREFERENCES"]["date_format_length"]
        self.view = config["PREFERENCES"]["view"]

        for i in range(10):
            index: str = f"FOLLOWCITY{i+1}"
            if index in config:
                city: dict[str | int] = {
                    "country": config[index]["country"],
                    "country_code2": config[index]["country_code2"],
                    "city": config[index]["city"],
                    "postal_code": config[index]["postal_code"],
                    "province": config[index]["province"],
                    "lat": config[index]["lat"],
                    "lon": config[index]["lon"],
                    "continent_code": config[index]["continent_code"],
                    "timezone": config[index]["timezone"],
                }
                self.followcities.append(city)

    def follow_city(self, city: str, country: str) -> None:
        for city_entry in self.followcities:
            if (
                city.upper() == city_entry["city"].upper()
                and country.upper() == city_entry["country"].upper()
            ):
                raise Exception(f"City '{city}/{country}' is already followed.")
        if len(self.followcities) > 9:
            raise Exception("Cannot follow city. Max cities limit is 10.")

        city_entry: dict[str | int] = {
            "country": country,
            "city": city,
        }
        self.followcities.append(city_entry)


class Locator:
    r"""Gets location data"""

    __CONTINENT_MAP: dict[str, list[str]] = {
        "AF": [
            "DZ",
            "AO",
            "BJ",
            "BW",
            "BF",
            "BI",
            "CV",
            "CM",
            "CF",
            "TD",
            "KM",
            "CD",
            "CG",
            "CI",
            "DJ",
            "EG",
            "GQ",
            "ER",
            "SZ",
            "ET",
            "GA",
            "GM",
            "GH",
            "GN",
            "GW",
            "KE",
            "LS",
            "LR",
            "LY",
            "MG",
            "MW",
            "ML",
            "MR",
            "MU",
            "MA",
            "MZ",
            "NA",
            "NE",
            "NG",
            "RW",
            "ST",
            "SN",
            "SC",
            "SL",
            "SO",
            "ZA",
            "SS",
            "SD",
            "TZ",
            "TG",
            "TN",
            "UG",
            "ZM",
            "ZW",
        ],
        "AS": [
            "AF",
            "AM",
            "AZ",
            "BH",
            "BD",
            "BT",
            "BN",
            "KH",
            "CN",
            "CY",
            "GE",
            "IN",
            "ID",
            "IR",
            "IQ",
            "IL",
            "JP",
            "JO",
            "KZ",
            "KW",
            "KG",
            "LA",
            "LB",
            "MY",
            "MV",
            "MN",
            "MM",
            "NP",
            "KP",
            "OM",
            "PK",
            "PS",
            "PH",
            "QA",
            "SA",
            "SG",
            "KR",
            "LK",
            "SY",
            "TW",
            "TJ",
            "TH",
            "TL",
            "TR",
            "TM",
            "AE",
            "UZ",
            "VN",
            "YE",
        ],
        "EU": [
            "AL",
            "AD",
            "AT",
            "BY",
            "BE",
            "BA",
            "BG",
            "HR",
            "CZ",
            "DK",
            "EE",
            "FI",
            "FR",
            "DE",
            "GR",
            "HU",
            "IS",
            "IE",
            "IT",
            "LV",
            "LI",
            "LT",
            "LU",
            "MT",
            "MD",
            "MC",
            "ME",
            "NL",
            "MK",
            "NO",
            "PL",
            "PT",
            "RO",
            "RU",
            "SM",
            "RS",
            "SK",
            "SI",
            "ES",
            "SE",
            "CH",
            "UA",
            "GB",
            "VA",
        ],
        "NA": [
            "AG",
            "BS",
            "BB",
            "BZ",
            "CA",
            "CR",
            "CU",
            "DM",
            "DO",
            "SV",
            "GD",
            "GT",
            "HT",
            "HN",
            "JM",
            "MX",
            "NI",
            "PA",
            "KN",
            "LC",
            "VC",
            "TT",
            "US",
        ],
        "OC": [
            "AU",
            "FJ",
            "KI",
            "MH",
            "FM",
            "NR",
            "NZ",
            "PW",
            "PG",
            "WS",
            "SB",
            "TO",
            "TV",
            "VU",
        ],
        "SA": ["AR", "BO", "BR", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE"],
        "AN": ["AQ"],
    }

    _USERAGENT: str = (
        f"TUIWeatherGirl/{APPVERSION} (https://github.com/StrayFeral/tuiweathergirl)"
    )

    def __init__(self) -> None:
        self.tzapi_calls: int = 0  # Counts the TZ data API calls

    def __get_continent_code(self, country: str) -> str:
        return next(
            (key for key, values in self.__CONTINENT_MAP.items() if country in values),
            "Unknown",
        )

    def config(
        self, config: Configuration, city: str = "", country: str = ""
    ) -> None | dict[str | int]:
        if city == "" or country == "":
            # Attempt auto-location

            url: str = (
                "http://ip-api.com/json/?fields=status,message,continentCode,country,countryCode,region,regionName,city,zip,lat,lon,timezone"
                "&lang=en"
            )
            response: requests.Response = requests.get(url)

            if not response:
                raise Exception(
                    f"Cannot autoconfigure. Error {response.status_code}: {APIIssues.get_api_problem(response.status_code)}"
                )

            response = response.json()

            if response.get("status") == "fail":
                raise Exception(
                    f"Request failed: {response.get("message")}. Try again!"
                )

            config.country = response.get("country")
            config.country_code2 = response.get("countryCode")
            config.city = response.get("city")
            config.postal_code = response.get("zip")
            config.province = response.get("region")
            config.lat = response.get("lat")  # XX.XXX, Fallback plan
            config.lon = response.get("lon")  # XX.XXX
            config.timezone = response.get("timezone")
            config.continent_code = response.get("continentCode")
        else:
            # Attempt to get information for the city and the country

            city = city.title()
            country = country.title()

            if country.upper() in ["USA", "US", "UK", "UAE", "CAR", "DRC"]:
                country = country.upper()

            headers: dict[str, str] = {
                "User-Agent": self._USERAGENT,
                "Accept-Language": "en",
            }
            url: str = (
                f"https://nominatim.openstreetmap.org/search?city={city}&country={country}&format=json&addressdetails=1"
            )
            response: requests.Response = requests.get(url, headers=headers)

            if not response.ok:
                raise Exception(
                    f"Location API server error. Error {response.status_code}: {APIIssues.get_api_problem(response.status_code)}"
                )

            response = response.json()

            if not response:
                raise Exception(
                    f"Cannot locate city '{city}/{country}'. Please check your syntax and try again."
                )

            location: dict = response[0]
            addr: dict = location.get("address", {})
            lat: str = location.get("lat", "")
            lon: str = location.get("lon", "")
            apikey: str = os.getenv(APIKEYENVVARNAME)

            if not apikey:
                raise Exception(
                    f"Environment variable {APIKEYENVVARNAME} is not set. Please get API key and set it in this variable before running this application."
                )

            if self.tzapi_calls > 0:
                time.sleep(1)  # API limit
            url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={apikey}&format=json&by=position&lat={lat}&lng={lon}"
            response: requests.Response = requests.get(url)
            self.tzapi_calls += 1

            if not response.ok:
                raise Exception(
                    f"Timezone API server error. Error {response.status_code}: {APIIssues.get_api_problem(response.status_code)}"
                )

            if not response:
                raise Exception(
                    f"Cannot obtain timezone for '{city}/{country}'. Please check your syntax and try again."
                )

            response = response.json()

            if response.get("status") == "FAILED":
                raise Exception(f"Timezone request failed. Try again later.")

            city_entry: dict[str | int] = {
                "city": location.get("name", "").title(),
                "country": addr.get("country", "").title(),
                "country_code2": addr.get("country_code", "").upper(),
                "postal_code": addr.get("postcode", ""),
                "province": addr.get("state_code", addr.get("state", "")),
                "lat": lat,
                "lon": lon,
                "continent_code": self.__get_continent_code(
                    addr.get("country_code", "").upper()
                ),
                "timezone": response.get("zoneName", ""),
            }

            time.sleep(1)  # API requirement

            return city_entry


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


class Motivator:
    r"""Daily motivator"""

    @staticmethod
    def get_motivation() -> list[str]:
        r"""Fetches a random inspirational quote from Quotable API."""

        try:
            response = requests.get("https://zenquotes.io/api/random", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return [data[0].get("q"), data[0].get("a")]
        except Exception:
            pass

        time.sleep(1)
        # Fallback quote in case the internet is slow or API is down
        return [
            "To appreciate the beauty of a snowflake, it is necessary to stand out in the cold.",
            "Aristotle",
        ]


class MindDrifter:
    r"""Letting your mind drift into eternity"""

    @staticmethod
    def drift() -> str:
        insomnias: list[str] = [
            "It is by walking into the forest that you unfold the steps of eternity",
            "It is the sound of the waves that brings the smell of the ocean",
            "It is the sand of the beach that tickles the voice of the seagulls",
            "It is the song of the starlings that makes the wind whisper to the ears of the hopeless",
            "It is by the will of time that we walk towards the sands of eternity",
            "It is the bloom of the ages that makes us drink the wine of wisdom",
            "It is the void of silence that makes us a whisper apart",
            "It is the fragrance of the innocence that makes the time whisper to the face of creation",
            "It is by the the well of eternity that we embrace the fate of the time",
            "It is by the blood of the roses that one hears the echoes of the untruth",
            "It is by defying the restlessness that we deny the shackles of mortality",
            "It is the sound of eternity that defines the song of the righteousness",
        ]
        return random.choice(insomnias)


class BriefDailyForecast:
    r"""For the daily forecast for the upcoming week we don't need all data"""

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
        self.is_day: bool = True
        self.hmin: int = 0
        self.hmax: int = 0
        self.wind_type: str = ""
        self.precipitation_type: str = ""
        self.humidity_level_min: str = ""
        self.humidity_level_max: str = ""
        self.wind_direction_long: str = ""

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

    def __get_wind_direction_long(self, winddir: str) -> str:
        dirs: dict(str, str) = {
            "N": "North",
            "NNE": "North-Northeast",
            "NE": "Northeast",
            "ENE": "East-Northeast",
            "E": "East",
            "ESE": "East-Southeast",
            "SE": "Southeast",
            "SSE": "South-Southeast",
            "S": "South",
            "SSW": "South-Southwest",
            "SW": "Southwest",
            "WSW": "West-Southwest",
            "W": "West",
            "WNW": "West-Northwest",
            "NW": "Northwest",
            "NNW": "North-Northwest",
        }
        return dirs.get(winddir, "Unknown")

    def __get_wind_type(self, wind_speed: int, unit: str) -> str:
        r"""Beaufort Scale"""

        if (wind_speed < 6 and unit == "kmh") or (wind_speed < 4 and unit == "mph"):
            return "Calm"
        if (6 >= wind_speed <= 11 and unit == "kmh") or (
            4 >= wind_speed <= 7 and unit == "mph"
        ):
            return "Light Breeze"
        if (12 >= wind_speed <= 19 and unit == "kmh") or (
            8 >= wind_speed <= 12 and unit == "mph"
        ):
            return "Gentle Breeze"
        if (20 >= wind_speed <= 28 and unit == "kmh") or (
            13 >= wind_speed <= 18 and unit == "mph"
        ):
            return "Moderate Breeze"
        if (29 >= wind_speed <= 38 and unit == "kmh") or (
            19 >= wind_speed <= 24 and unit == "mph"
        ):
            return "Fresh Breeze"
        if (39 >= wind_speed <= 49 and unit == "kmh") or (
            25 >= wind_speed <= 31 and unit == "mph"
        ):
            return "Strong Breeze"
        # Yellow
        if (50 >= wind_speed <= 61 and unit == "kmh") or (
            32 >= wind_speed <= 38 and unit == "mph"
        ):
            return "Near Gale"
        if (62 >= wind_speed <= 74 and unit == "kmh") or (
            39 >= wind_speed <= 46 and unit == "mph"
        ):
            return "Gale"
        if (75 >= wind_speed <= 88 and unit == "kmh") or (
            47 >= wind_speed <= 54 and unit == "mph"
        ):
            return "Strong Gale"
        # Red
        if (89 >= wind_speed <= 102 and unit == "kmh") or (
            55 >= wind_speed <= 63 and unit == "mph"
        ):
            return "STORM"
        if (103 >= wind_speed <= 117 and unit == "kmh") or (
            64 >= wind_speed <= 72 and unit == "mph"
        ):
            return "VIOLENT STORM"
        if (wind_speed > 117 and unit == "kmh") or (wind_speed > 72 and unit == "mph"):
            return "HURRICANE"

        return ""

    def __get_weather_description(self, weather_code: int) -> str:
        r"""Simplified WMO Weather interpretation codes"""

        mapping: dict[int, str] = {
            0: "Clear",
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
        return mapping.get(weather_code, "Cloudy")

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

    def __get_humidity_risk(self, humidity: int) -> str:
        """Returns a message only if humidity poses a risk for people with
        medical conditions (resporatory)"""

        if humidity < 30:
            return f"Humidity {humidity}%: Risk for people with asthma or chronic respiratory conditions: Airway irritation."

        if humidity < 40:
            return f"Humidity {humidity}%: Moderate risk for people with sensitive respiratory systems."

        if humidity <= 60:
            return ""  # Safe

        if humidity <= 70:
            return f"Humidity {humidity}%: Risk for people with asthma: Increased allergens and air density."

        return f"Humidity {humidity}%: HIGH RISK for people with respiratory conditions: Severe bronchoconstriction and labored breathing!"

    def __get_humidity_assessment(self, humidity: int, temperature: int) -> str:
        r"""Returns a human-readable assessment based on the humidity and temperature."""

        if humidity >= 70 and temperature > 30:
            return "HIGH"
        if humidity >= 80 and 27 <= temperature <= 31:
            return "Caution"
        if humidity >= 50 and 32 <= temperature <= 34:
            return "Extreme Caution"
        if humidity >= 40 and 35 <= temperature <= 37:
            return "DANGER"
        if humidity >= 35 and temperature > 38:
            return "EXTREME DANGER"

        if humidity < 15:
            return "LOW"
        if humidity < 30:
            return "Dry"
        if humidity <= 60:
            return "Comfortable"

        return "Humid"

    def __get_precipitation_type(self, weather_code: int) -> str:
        if 51 <= weather_code <= 67 or 80 <= weather_code <= 82:
            return "Rain"
        if 71 <= weather_code <= 77 or 85 <= weather_code <= 86:
            return "Snow"
        if 95 <= weather_code <= 99:
            return "Storm"
        return "Precipitation"

    def __get_storm_warning(self, weather_code: int, wind: int) -> str:
        if 95 <= weather_code <= 99:
            if weather_code in [96, 99]:
                return "HAIL STORM WARNING"
            return "THUNDERSTORM WARNING"

        if 38 <= weather_code <= 39:
            return "BLIZZARD WARNING"

        # Wind Storms
        if wind > 60:
            return "HIGH WIND WARNING"

        return ""

    def __is_daytime(self, lat: str, lon: str, dt: datetime = None) -> bool:
        """
        Calculates if it is daytime at a specific coordinate and time
        without using external APIs.

        Code written with a Gemini formula.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)

        lat = float(lat)
        lon = float(lon)

        zenith = 96.0
        day_of_year = dt.timetuple().tm_yday

        # Convert longitude to hour offset and calculate approximate sunrise/sunset
        # This is a simplified version of the General Solar Position Algorithm
        lng_hour = lon / 15.0

        # Calculate sunrise/sunset times
        t_rise = day_of_year + ((6 - lng_hour) / 24)
        t_set = day_of_year + ((18 - lng_hour) / 24)

        # Calculate Solar Mean Anomaly
        m_rise = (0.9856 * t_rise) - 3.289
        m_set = (0.9856 * t_set) - 3.289

        # Calculate True Longitude
        l_rise = (
            m_rise
            + (1.916 * math.sin(math.radians(m_rise)))
            + (0.020 * math.sin(math.radians(2 * m_rise)))
            + 282.634
        )
        l_set = (
            m_set
            + (1.916 * math.sin(math.radians(m_set)))
            + (0.020 * math.sin(math.radians(2 * m_set)))
            + 282.634
        )

        l_rise = l_rise % 360
        l_set = l_set % 360

        # Calculate Right Ascension
        ra_rise = (
            math.degrees(math.atan(0.91764 * math.tan(math.radians(l_rise)))) % 360
        )
        ra_set = math.degrees(math.atan(0.91764 * math.tan(math.radians(l_set)))) % 360

        # Adjust RA to be in the same quadrant as L
        l_quadrant = (math.floor(l_rise / 90)) * 90
        ra_quadrant = (math.floor(ra_rise / 90)) * 90
        ra_rise = ra_rise + (l_quadrant - ra_quadrant)

        l_quadrant = (math.floor(l_set / 90)) * 90
        ra_quadrant = (math.floor(ra_set / 90)) * 90
        ra_set = ra_set + (l_quadrant - ra_quadrant)

        # Convert RA to hours
        ra_rise /= 15
        ra_set /= 15

        # Calculate Declination
        sin_dec = 0.39782 * math.sin(math.radians(l_rise))
        cos_dec = math.cos(math.asin(sin_dec))

        # Calculate Local Hour Angle
        cos_h = (
            math.cos(math.radians(zenith)) - (sin_dec * math.sin(math.radians(lat)))
        ) / (cos_dec * math.cos(math.radians(lat)))

        # If cos_h > 1, sun never rises (Polar Night)
        # If cos_h < -1, sun never sets (Midnight Sun)
        if cos_h > 1:
            return False
        if cos_h < -1:
            return True

        h_rise = (360 - math.degrees(math.acos(cos_h))) / 15
        h_set = math.degrees(math.acos(cos_h)) / 15

        # Calculate Local Mean Time of rise/set
        t_rise = h_rise + ra_rise - (0.06571 * t_rise) - 6.622
        t_set = h_set + ra_set - (0.06571 * t_set) - 6.622

        # Convert to UTC
        utc_rise = (t_rise - lng_hour) % 24
        utc_set = (t_set - lng_hour) % 24

        # Current UTC time as a float
        current_utc_hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

        # Handle the wrap-around for night (if sunset is before sunrise)
        if utc_rise < utc_set:
            return utc_rise <= current_utc_hour <= utc_set
        else:
            return current_utc_hour >= utc_rise or current_utc_hour <= utc_set

    def get_data(self, weather_data: WeatherData) -> None:
        # Build the API URL with your config preferences
        tunit = "celsius" if self.config.celsius else "fahrenheit"
        wunit = "kmh" if self.config.metric else "mph"

        #  &timezone=auto # current
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.config.lat}&longitude={self.config.lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,relative_humidity_2m_min,relative_humidity_2m_max"
            f"&timezone={self.config.timezone.replace('/', '%2F')}"
            f"&temperature_unit={tunit}&wind_speed_unit={wunit}"
            f"&forecast_days=8"
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
            # weather_data.is_day = cache.is_day
            weather_data.sky = cache.sky
            weather_data.temperature = cache.temperature
            weather_data.min = cache.tmin
            weather_data.max = cache.tmax
            weather_data.hmin = cache.hmin
            weather_data.hmax = cache.hmax
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
            weather_result: requests.Response = requests.get(url)
            aq_result: requests.Response = requests.get(aq_url)

            if not weather_result:
                raise Exception(
                    f"Cannot obtain weather data. Error {weather_result.status_code}: {APIIssues.get_api_problem(weather_result.status_code)}"
                )
            if not aq_result:
                raise Exception(
                    f"Cannot obtain air quality data. Error {aq_result.status_code}: {APIIssues.get_api_problem(aq_result.status_code)}"
                )

            weather_result = weather_result.json()
            aq_result = aq_result.json()

            # Extract Data
            current: dict[str] = weather_result["current"]
            daily: dict[str] = weather_result["daily"]
            aqi: str = aq_result["current"]["us_aqi"]

            # Fill the object with data
            # weather_data.is_day = True if current["is_day"] == "1" else False
            weather_data.sky = self.__get_weather_description(current["weather_code"])
            weather_data.temperature = int(current["temperature_2m"])
            weather_data.min = int(daily["temperature_2m_min"][0])
            weather_data.max = int(daily["temperature_2m_max"][0])
            weather_data.hmin = int(daily["relative_humidity_2m_min"][0])
            weather_data.hmax = int(daily["relative_humidity_2m_max"][0])
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
                day.dow = (now + timedelta(days=i)).strftime("%a")
                weather_data.week.append(day)

        weather_data.wind_type = self.__get_wind_type(weather_data.wind, wunit)
        weather_data.precipitation_type = self.__get_precipitation_type(
            weather_data.weather_code
        )  # Rain, Snow, Storm, Precip
        weather_data.humidity_level_min = self.__get_humidity_assessment(
            weather_data.hmin, weather_data.temperature
        )
        weather_data.humidity_level_max = self.__get_humidity_assessment(
            weather_data.hmax, weather_data.temperature
        )
        weather_data.wind_direction_long = self.__get_wind_direction_long(
            weather_data.wind_direction
        )
        weather_data.is_day = self.__is_daytime(self.config.lat, self.config.lon)


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
        self.continent_code: str = config.continent_code

        self.date: str = ""
        self.time: str = ""
        self.dow: str = ""
        self.season: str = ""

    def get_season(self, continent_code: str) -> str:
        now: datetime = datetime.now()
        md: int = now.month * 100 + now.day  # May 2nd is 502
        season: str = "Winter"

        if 320 <= md < 621:
            season = "Spring"
        if 621 <= md < 922:
            season = "Summer"
        if 922 <= md < 1221:
            season = "Fall"

        if continent_code in ["SA", "OC", "AN", "AF"]:
            # Logic to flip seasons for the South
            flip = {
                "Spring": "Fall",
                "Summer": "Winter",
                "Fall": "Spring",
                "Winter": "Summer",
            }
            return flip[season]

        return season

    def update_time(self) -> str:
        now = datetime.now(ZoneInfo(self.timezone))
        try:
            self.date = format_date(
                now, format=self.date_format_length, locale=self.locale_id
            )
        except Exception:
            self.date = format_date(
                now, format=self.date_format_length, locale=DEFAULT_LOCALE
            )
        # self.dow = format_date(now, format="cccccc", locale=self.locale_id).title()
        self.dow = format_date(now, format="EEE", locale=DEFAULT_LOCALE).title()
        self.season = self.get_season(self.continent_code)

        # Time 12/24
        time_pattern = "%H:%M" if self.time24 else "%I:%M %p"
        self.time = now.strftime(time_pattern)

        return self.time


class Views:
    r"""Definition of views"""

    def __init__(
        self,
        config: Configuration,
        data: WeatherData,
        present_config: PresentationConfiguration,
    ) -> None:
        self.config: Configuration = config
        self.data: WeatherData = data
        self.presconf: PresentationConfiguration = present_config
        self.weather_refresh_interval: int = REFRESH_INTERVAL

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


class ColorViews(Views):
    r"""Definition of color views"""

    def _get_humidity_cp(self, humidity: int, temperature) -> int:
        r"""Get the humidity color pair"""

        if humidity >= 70 and temperature > 30:
            return COL_YELOWBLACK
        if humidity >= 80 and 27 <= temperature <= 31:
            return COL_YELOWBLACK
        if humidity >= 50 and 32 <= temperature <= 34:
            return COL_YELOWBLACK
        if humidity >= 40 and 35 <= temperature <= 37:
            return COL_YELOWBLACK
        if humidity >= 35 and temperature > 38:
            return COL_YELOWRED

        if humidity < 15:
            return COL_YELOWRED
        if humidity < 30:
            return COL_YELOWBLACK
        if humidity <= 60:
            return COL_GREENBLACK

        return COL_CYANBLACK

    def _get_daynight_cp(self, is_day: bool) -> int:
        r"""Get the day or night color pair"""
        if is_day:
            return COL_WHITEBLACK
        return COL_BLUEBLACK

    def _get_temp_cp(self, t: int) -> int:
        r"""Get the appropriate temperature color pair"""

        if t < 11:
            return COL_CYANBLACK
        if 11 <= t <= 20:
            return COL_GREENBLACK
        if 21 <= t <= 38:
            return COL_YELOWBLACK
        if 39 <= t <= 44:
            return COL_REDBLACK
        return COL_YELOWRED

    def _get_wind_cp(self, wind_speed: int, unit: str) -> int:
        r"""Beaufort Scale"""

        scale: dict[str, dict[int, int]] = {
            "kmh": {50: COL_WHITEBLACK, 89: COL_YELOWBLACK, 117: COL_REDBLACK},
            "mph": {32: COL_WHITEBLACK, 55: COL_YELOWBLACK, 72: COL_REDBLACK},
        }

        for treshold in scale[unit].keys():
            if wind_speed < treshold:
                return scale[unit][treshold]

        return COL_YELOWRED  # Extreme (Hurricane)

    def _get_sky_cp(self, sky: str) -> int:
        r"""Get the appropriate sky color pair"""

        d: dict[str, int] = {
            # -------------------- nice
            "Clear": COL_YELOWBLACK,
            "Mainly Clear": COL_YELOWBLACK,
            # -------------------- clouds
            "Partly Cloudy": COL_WHITEBLACK,
            "Overcast": COL_WHITEBLACK,
            "Foggy": COL_WHITEBLACK,
            "Rime Fog": COL_WHITEBLACK,
            "Cloudy": COL_WHITEBLACK,
            # -------------------- rains
            "Drizzle": COL_BLUEBLACK,
            "Rain": COL_BLUEBLACK,
            "Snow": COL_BLUEBLACK,
            "Rain Showers": COL_BLUEBLACK,
            "Thunderstorm": COL_BLUEBLACK,
        }
        if sky not in d:
            raise Exception(f"Invalid sky value '{sky}'.")
        return d[sky]

    def _get_aqistr_cp(self, aqistr: str) -> int:
        r"""Get the appropriate aqi color pair"""

        d: dict[str, int] = {
            # -------------------- green
            "Good": COL_GREENBLACK,
            # -------------------- yellow
            "Moderate": COL_YELOWBLACK,
            "Unhealthy for Sensitive Groups": COL_YELOWBLACK,
            # -------------------- red
            "Unhealthy": COL_REDBLACK,
            "Very Unhealthy": COL_REDBLACK,
            "Hazardous": COL_REDBLACK,
        }
        if aqistr not in d:
            raise Exception(f"Invalid AQI value '{aqistr}'.")
        return d[aqistr]

    def _get_progbar_cp(self, p: int) -> int:
        if p < 40:
            return COL_BLUEBLACK
        return COL_CYANBLACK


class SetupView(Views):
    r"""Prints the setup"""

    def display(self) -> None:
        # Data to display
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        followed_cities: list[dict[str | int]] = self.config.followcities

        print(f"""TUIWEATHERGIRL {APPVERSION} by Evgueni Antonov (StrayF) 2026

==================================================[ SETUP ]
HOME CITY         |  {city}, {province}{country}""")

        print("ADDITIONAL CITIES |  ", end="")
        if len(followed_cities) == 0:
            print("None")
        else:
            for i, c in enumerate(followed_cities):
                (
                    print(f"{i+1}) {c["city"]}, {c["country"]}")
                    if i == 0
                    else print(
                        f"                  |  {i+1}) {c["city"]}, {c["country"]}"
                    )
                )

        print("\nTry: tuiweathergirl --help")


class BasicView(Views):
    r"""Just prints"""

    def display(self) -> None:
        # Data to display
        timenow: str = self.presconf.update_time()
        datenow: str = self.presconf.date
        dow: str = self.presconf.dow
        season: str = self.presconf.season
        dstmark: str = "*" if self.config.dst else ""
        # ---
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        sky: str = self.data.sky
        temperature: int = self.data.temperature
        tmin: int = self.data.min
        tmax: int = self.data.max
        hmin: int = self.data.hmin
        hmax: int = self.data.hmax
        tsuffix: str = self.presconf.tsuffix
        wunit: str = self.presconf.wunit
        wind: int = self.data.wind
        winddir: str = self.data.wind_direction
        aqi: int = self.data.aqi
        airquality: str = self.data.air_quality
        precipitation: int = self.data.precipitation
        is_day: bool = self.data.is_day
        wind_type: str = self.data.wind_type
        precipitation_type: str = self.data.precipitation_type
        humidity_level_min: str = self.data.humidity_level_min
        humidity_level_max: str = self.data.humidity_level_max
        wind_direction_long: str = self.data.wind_direction_long
        # ---
        warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week

        day: str = "day" if is_day else "night"

        hr: str = "==============================="

        print(f"""TUIWEATHERGIRL {APPVERSION} by Evgueni Antonov (StrayF) 2026

TODAY                     ({dow})
{hr}
Time             | {timenow}{dstmark} ({day}), {datenow} ({season})
Home             | {city}, {province}{country}
Sky              | {sky}
Temperature      | {temperature} deg {tsuffix} (Today: {tmin} deg /{tmax} deg {tsuffix})
Wind             | {wind_type}, {wind}{wunit}, {wind_direction_long}.
Air Quality      | {airquality} ({aqi})
{precipitation_type:17}| {precipitation}% chance
Humidity         | {humidity_level_min}/{humidity_level_max} ({hmin}%/{hmax}%)
""")

        print("7-DAY FORECAST")
        print(hr)
        for day in week:
            dmin: int = day.min
            dmax: int = day.max
            dprecip: int = day.precip
            dow: str = day.dow

            temperatures = f"{dmin:>2} deg /{dmax:>2} deg {tsuffix}"
            print(f"  {dow} | {temperatures:<6} | {dprecip:>3}%")

        for warning in warnings:
            print(f"\n{warning}")

        print("\nTry: tuiweathergirl --help")

        # Saving the cache
        cache = CachedData()
        cache.sky = sky
        cache.temperature = temperature
        cache.tmin = tmin
        cache.tmax = tmax
        cache.hmin = hmin
        cache.hmax = hmax
        cache.wind = wind
        cache.wind_direction = winddir
        cache.aqi = aqi
        cache.precipitation = precipitation
        cache.weather_code = self.data.weather_code
        cache.is_day = is_day

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


class MotivationalView(Views):
    r"""Just prints"""

    def display(self) -> None:
        # Data to display
        timenow: str = self.presconf.update_time()
        datenow: str = self.presconf.date
        dow: str = self.presconf.dow
        season: str = self.presconf.season
        dstmark: str = "*" if self.config.dst else ""
        # ---
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        sky: str = self.data.sky
        temperature: int = self.data.temperature
        tmin: int = self.data.min
        tmax: int = self.data.max
        hmin: int = self.data.hmin
        hmax: int = self.data.hmax
        tsuffix: str = self.presconf.tsuffix
        wunit: str = self.presconf.wunit
        wind: int = self.data.wind
        winddir: str = self.data.wind_direction
        aqi: int = self.data.aqi
        airquality: str = self.data.air_quality
        precipitation: int = self.data.precipitation
        is_day: bool = self.data.is_day
        wind_type: str = self.data.wind_type
        precipitation_type: str = self.data.precipitation_type
        humidity_level_min: str = self.data.humidity_level_min
        humidity_level_max: str = self.data.humidity_level_max
        wind_direction_long: str = self.data.wind_direction_long
        # ---
        warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week

        day: str = "day" if is_day else "night"

        motivation: str = Motivator.get_motivation()
        mind_drift: str = MindDrifter.drift()

        hr: str = "============================"
        hr2: str = "~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
        hr3: str = "~~,~~`~~,~~`~~,~~`~~,~~`~~,~~"

        print(f"""TUIWEATHERGIRL {APPVERSION} by Evgueni Antonov (StrayF) 2026

By unfolding the dusty ancient scrolls, we uncover these secrets of the future:

{hr3}
{mind_drift}
as today it is a beautiful, {sky.lower()} {season} {day.lower()} in {city}, {province}{country} on {datenow} at {timenow}{dstmark}.
The current temperature is {temperature}°{tsuffix} with a forecasted range between {tmin} deg and {tmax} deg {tsuffix}.
The wind is {wind_type.lower()}, blowing at {wind}{wunit} from the {wind_direction_long}.
Air quality is currently {airquality.lower()} with an AQI value of {aqi}.
There is a {precipitation}% chance of {precipitation_type.lower()} today.
Humidity levels range from a {humidity_level_min.lower()} {hmin}% to a {humidity_level_max.lower()} of {hmax}%.
{hr3}
{motivation[0]}
                                            ~{motivation[1]}

{hr3}""")

        print("And by the next seven days one's fate would go like this")
        print(hr3)
        for day in week:
            dmin: int = day.min
            dmax: int = day.max
            dprecip: int = day.precip
            dow: str = day.dow

            temperatures = f"{dmin:>2} deg/{dmax:>2} deg {tsuffix}"
            print(f"{dow} ~ {temperatures:<6} ~ {dprecip:>3}%")

        for warning in warnings:
            print(f"\n{warning}")

        print("\nTry: tuiweathergirl --help")

        # Saving the cache
        cache = CachedData()
        cache.sky = sky
        cache.temperature = temperature
        cache.tmin = tmin
        cache.tmax = tmax
        cache.hmin = hmin
        cache.hmax = hmax
        cache.wind = wind
        cache.wind_direction = winddir
        cache.aqi = aqi
        cache.precipitation = precipitation
        cache.weather_code = self.data.weather_code
        cache.is_day = is_day

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


class NiceView(Views):
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
            f"TUIWEATHERGIRL {APPVERSION}                      Evgueni Antonov (StrayF) 2026",
        )

        location_win.attron(curses.A_DIM)
        location_win.addstr(0, 0, f"Home: {city}, {province}{country}")

        last_refresh: str = ""

        # -------------------------------------------------- VIEW MAIN LOOP
        elapsed: int = 0
        while True:
            elapsed += 1

            stdscr.attron(curses.A_DIM)

            # Data to display
            timenow: str = self.presconf.update_time()
            datenow: str = self.presconf.date
            dow: str = self.presconf.dow
            season: str = self.presconf.season
            dstmark: str = "*" if self.config.dst else ""

            if len(last_refresh) == 0:
                last_refresh = f"Last refresh: {datenow} {timenow}"

            # Technically we do not need this, but filling up the addstr()s
            # later would be more messy without it
            sky: str = self.data.sky
            temperature: int = self.data.temperature
            tmin: int = self.data.min
            tmax: int = self.data.max
            hmin: int = self.data.hmin
            hmax: int = self.data.hmax
            tsuffix: str = self.presconf.tsuffix
            wunit: str = self.presconf.wunit
            wind: int = self.data.wind
            winddir: str = self.data.wind_direction
            aqi: int = self.data.aqi
            airquality: str = self.data.air_quality
            precipitation: int = self.data.precipitation
            is_day: bool = self.data.is_day
            wind_type: str = self.data.wind_type
            precipitation_type: str = self.data.precipitation_type
            humidity_level_min: str = self.data.humidity_level_min
            humidity_level_max: str = self.data.humidity_level_max
            wind_direction_long: str = self.data.wind_direction_long
            # ---
            warnings: list[str] = self.data.warnings
            week: list[BriefDailyForecast] = self.data.week

            # Saving the cache
            cache = CachedData()
            cache.sky = sky
            cache.temperature = temperature
            cache.tmin = tmin
            cache.tmax = tmax
            cache.hmin = hmin
            cache.hmax = hmax
            cache.wind = wind
            cache.wind_direction = winddir
            cache.aqi = aqi
            cache.precipitation = precipitation
            cache.weather_code = self.data.weather_code
            cache.is_day = is_day

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
                temperatures = f"{dmin:>2}°/{dmax:>2}°{tsuffix}"

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


class ColorView(ColorViews):
    """Color view - same as NiceView but with colors"""

    def screen(self, stdscr: curses.window) -> None:
        # Color definitions
        curses.start_color()
        curses.init_pair(
            COL_YELOWRED, curses.COLOR_YELLOW, curses.COLOR_RED
        )  # Warnings
        curses.init_pair(
            COL_YELOWBLACK, curses.COLOR_YELLOW, curses.COLOR_BLACK
        )  # Sunny
        curses.init_pair(
            COL_WHITEBLACK, curses.COLOR_WHITE, curses.COLOR_BLACK
        )  # Cloudy
        curses.init_pair(COL_BLUEBLACK, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Rain
        curses.init_pair(COL_REDBLACK, curses.COLOR_RED, curses.COLOR_BLACK)  # Bad
        curses.init_pair(COL_GREENBLACK, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Good
        curses.init_pair(COL_CYANBLACK, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Title

        stdscr.attron(curses.A_DIM)

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

        title_win.attron(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
        title_win.box()
        title_win.attroff(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
        title_win.attron(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
        title_win.addstr(
            1,
            2,
            f"TUIWEATHERGIRL {APPVERSION}                      Evgueni Antonov (StrayF) 2026",
        )
        title_win.attroff(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)

        location_win.addstr(0, 0, f"Home: {city}, {province}{country}")

        last_refresh: str = ""

        # -------------------------------------------------- VIEW MAIN LOOP
        elapsed: int = 0
        while True:
            elapsed += 1

            # Data to display
            timenow: str = self.presconf.update_time()
            datenow: str = self.presconf.date
            dow: str = self.presconf.dow
            season: str = self.presconf.season
            dstmark: str = "*" if self.config.dst else ""

            if len(last_refresh) == 0:
                last_refresh = f"Last refresh: {datenow} {timenow}"

            # Technically we do not need this, but filling up the addstr()s
            # later would be more messy without it
            sky: str = self.data.sky
            temperature: int = self.data.temperature
            tmin: int = self.data.min
            tmax: int = self.data.max
            hmin: int = self.data.hmin
            hmax: int = self.data.hmax
            tsuffix: str = self.presconf.tsuffix
            wunit: str = self.presconf.wunit
            wind: int = self.data.wind
            winddir: str = self.data.wind_direction
            aqi: int = self.data.aqi
            airquality: str = self.data.air_quality
            precipitation: int = self.data.precipitation
            is_day: bool = self.data.is_day
            wind_type: str = self.data.wind_type
            precipitation_type: str = self.data.precipitation_type
            humidity_level_min: str = self.data.humidity_level_min
            humidity_level_max: str = self.data.humidity_level_max
            wind_direction_long: str = self.data.wind_direction_long
            # ---
            warnings: list[str] = self.data.warnings
            week: list[BriefDailyForecast] = self.data.week

            # Saving the cache
            cache = CachedData()
            cache.sky = sky
            cache.temperature = temperature
            cache.tmin = tmin
            cache.tmax = tmax
            cache.hmin = hmin
            cache.hmax = hmax
            cache.wind = wind
            cache.wind_direction = winddir
            cache.aqi = aqi
            cache.precipitation = precipitation
            cache.weather_code = self.data.weather_code
            cache.is_day = is_day

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
            status_win.attron(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            status_win.box()
            status_win.addstr(2, 0, "├──────────────────────────────────┤")
            status_win.attroff(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            status_win.attron(curses.color_pair(COL_CYANBLACK))
            status_win.addstr(1, 11, "CURRENT STATUS")
            status_win.attroff(curses.color_pair(COL_CYANBLACK))
            status_win.attron(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
            status_win.addstr(3, 3, "Sky    :")
            status_win.addstr(4, 3, "Temp   :")
            status_win.addstr(5, 3, "Range  :")
            status_win.attroff(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
            status_win.attron(curses.color_pair(self._get_sky_cp(sky)))
            status_win.addstr(3, datax, sky)
            status_win.attroff(curses.color_pair(self._get_sky_cp(sky)))
            status_win.attron(curses.color_pair(self._get_temp_cp(temperature)))
            status_win.addstr(4, datax, f"{temperature}°{tsuffix}")
            status_win.attroff(curses.color_pair(self._get_temp_cp(temperature)))
            status_win.attron(curses.color_pair(self._get_temp_cp(tmin)))
            status_win.addstr(5, datax, f"{tmin}°{tsuffix}")
            status_win.attroff(curses.color_pair(self._get_temp_cp(tmin)))
            status_win.addstr(5, datax + 4, "/")
            status_win.attron(curses.color_pair(self._get_temp_cp(tmax)))
            status_win.addstr(5, datax + 6, f"{tmax}°{tsuffix}")
            status_win.attron(curses.color_pair(self._get_temp_cp(tmax)))

            air_win.erase()
            air_win.move(0, 0)
            air_win.attron(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            air_win.box()
            air_win.addstr(2, 0, "├──────────────────────────────────┤")
            air_win.attroff(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            air_win.attron(curses.color_pair(COL_CYANBLACK))
            air_win.addstr(1, 10, "AIR & CONDITIONS")
            air_win.attroff(curses.color_pair(COL_CYANBLACK))
            air_win.attron(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
            air_win.addstr(3, 3, "Wind   :")
            air_win.addstr(4, 3, "AQI    :")
            air_win.addstr(5, 3, "Precip :")
            air_win.attroff(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
            air_win.attron(curses.color_pair(COL_WHITEBLACK))
            air_win.addstr(3, datax, f"{wind}{wunit} {winddir}")
            air_win.attroff(curses.color_pair(COL_WHITEBLACK))
            air_win.attron(curses.color_pair(self._get_aqistr_cp(airquality)))
            air_win.addstr(4, datax, f"{aqi} ({airquality})")
            air_win.attroff(curses.color_pair(self._get_aqistr_cp(airquality)))
            air_win.attron(curses.color_pair(COL_BLUEBLACK))
            air_win.addstr(5, datax, "[")
            air_win.attroff(curses.color_pair(COL_BLUEBLACK))
            air_win.attron(curses.color_pair(self._get_progbar_cp(precipitation)))
            air_win.addstr(5, datax + 1, self.prog_bar(precipitation))
            air_win.attroff(curses.color_pair(self._get_progbar_cp(precipitation)))
            air_win.attron(curses.color_pair(COL_BLUEBLACK))
            air_win.addstr(5, datax + 10, "]")
            air_win.attroff(curses.color_pair(COL_BLUEBLACK))
            air_win.attron(curses.color_pair(self._get_progbar_cp(precipitation)))
            air_win.addstr(5, datax + 12, f"{precipitation}%  ")
            air_win.attroff(curses.color_pair(self._get_progbar_cp(precipitation)))

            forecast_win.erase()
            forecast_win.move(0, 0)
            forecast_win.attron(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            forecast_win.box()
            forecast_win.attroff(curses.color_pair(COL_BLUEBLACK) | curses.A_DIM)
            forecast_win.attron(curses.color_pair(COL_CYANBLACK))
            forecast_win.addstr(0, 28, " 7-DAY FORECAST ")
            forecast_win.attroff(curses.color_pair(COL_CYANBLACK))
            forecast_win.attroff(curses.A_DIM)

            warnings_win.erase()
            warnings_win.move(0, 0)
            warnings_win.attron(curses.color_pair(COL_REDBLACK))
            warnings_win.box()
            warnings_win.attroff(curses.color_pair(COL_REDBLACK))
            warnings_win.attron(curses.color_pair(COL_WHITEBLACK))
            warnings_win.addstr(0, 30, " WARNINGS ")
            warnings_win.attroff(curses.color_pair(COL_WHITEBLACK))
            if len(warnings) > 0:
                warnings_win.attron(curses.color_pair(COL_YELOWBLACK))
                for i in range(len(warnings)):
                    warnings_win.addstr(1 + i, 2, warnings[i])
                warnings_win.attroff(curses.color_pair(COL_YELOWBLACK))
            else:
                warnings_win.attron(curses.color_pair(COL_GREENBLACK) | curses.A_DIM)
                warnings_win.addstr(1, 2, "No warnings.")
                warnings_win.attroff(curses.color_pair(COL_GREENBLACK) | curses.A_DIM)

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
                forecast_win.attron(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
                forecast_win.addstr(wy, wx, f"{dow}:")
                forecast_win.attroff(curses.color_pair(COL_WHITEBLACK) | curses.A_DIM)
                forecast_win.attron(curses.color_pair(self._get_temp_cp(dmin)))
                tmins = f"{dmin:>2}°"
                forecast_win.addstr(wy, wx + 5, f"{tmins}:")
                forecast_win.attroff(curses.color_pair(self._get_temp_cp(dmin)))
                forecast_win.attron(curses.color_pair(COL_WHITEBLACK))
                forecast_win.addstr(wy, wx + 8, "/")
                forecast_win.attroff(curses.color_pair(COL_WHITEBLACK))
                forecast_win.attron(curses.color_pair(self._get_temp_cp(dmax)))
                tmaxs = f"{dmax:>2}°{tsuffix}"
                forecast_win.addstr(wy, wx + 9, f"{tmaxs}")
                forecast_win.attroff(curses.color_pair(self._get_temp_cp(dmax)))
                forecast_win.attron(curses.color_pair(COL_BLUEBLACK))
                forecast_win.addstr(wy, wx + 14, "[")
                forecast_win.attroff(curses.color_pair(COL_BLUEBLACK))
                forecast_win.attron(curses.color_pair(self._get_progbar_cp(dprecip)))
                forecast_win.addstr(wy, wx + 15, self.prog_bar(dprecip))
                forecast_win.attroff(curses.color_pair(self._get_progbar_cp(dprecip)))
                forecast_win.attron(curses.color_pair(COL_BLUEBLACK))
                forecast_win.addstr(wy, wx + 25, "]")
                forecast_win.attroff(curses.color_pair(COL_BLUEBLACK))
                forecast_win.attron(curses.color_pair(self._get_progbar_cp(dprecip)))
                forecast_win.addstr(wy, wx + 27, f"{dprecip}%  ")
                forecast_win.attroff(curses.color_pair(self._get_progbar_cp(dprecip)))

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
        self.views: dict[str, Views] = {
            "setup": SetupView(config, data, present_config),
            "basic": BasicView(config, data, present_config),
            "motivate": MotivationalView(config, data, present_config),
            "nice": NiceView(config, data, present_config),
            "color": ColorView(config, data, present_config),
        }

    def present(self, view: str = "") -> None:
        if len(view) > 0 and view not in self.views:
            raise Exception(f"View not defined '{view}'. Run with --help for help.")
        self.views[view or self.view].display()


class ParseCommandline:
    def parse(self) -> dict[str, str | int | bool]:
        cli_parser: argparse.ArgumentParser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="tuiweathergirl",
            epilog=EPILOGUE_HELP,
            description=DESCRIPTION_HELP,
        )
        action_group = cli_parser.add_mutually_exclusive_group()
        cli_parser.add_argument(
            "--version",
            action="store_true",
            help="Print the version",
        )
        cli_parser.add_argument(
            "--view",
            choices=["setup", "basic", "motivate", "nice", "color"],
            default="",
            help="Select the view",
        )
        action_group.add_argument(
            "--addcity",
            dest="newcity",
            default="",
            help="Add a new city to follow",
        )
        action_group.add_argument(
            "--removecity",
            type=int,
            help="Remove a city which is currently followed",
        )
        action_group.add_argument(
            "--sethome",
            dest="homecity",
            type=int,
            help="Set which city is home (city must be already added)",
        )
        cli_parser.add_argument(
            "--country",
            dest="country",
            default="",
            help="Which country is that city in",
        )
        cli_parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="A bit more printing on errors",
        )
        cli_arguments: argparse.Namespace = cli_parser.parse_args()
        args: dict[str, str | int | bool] = vars(cli_arguments)

        if args.get("version"):
            print(DESCRIPTION_HELP)
            sys.exit(0)

        if args.get("newcity"):
            args["newcity"] = args["newcity"].strip().title()
        if args.get("country"):
            args["country"] = args["country"].strip().title()

            # Proper abbreviations support
            if args["country"].upper() in ["USA", "US", "UK", "UAE", "CAR", "DRC"]:
                args["country"] = args["country"].upper()

        return args


class LocationManager:
    def set_home(self, citynum: int, config: Configuration) -> None:
        r"""Change home city"""

        if len(config.followcities) == 0:
            raise Exception(
                "There are no currently added cities. You must first add a city with `--addcity`."
            )
        if 1 <= citynum > len(config.followcities):
            raise Exception(
                f"City must be a number between 1 and {len(config.followcities)}."
            )

        (
            config.country,
            config.followcities[citynum - 1]["country"],
        ) = (
            config.followcities[citynum - 1]["country"],
            config.country,
        )
        (
            config.country_code2,
            config.followcities[citynum - 1]["country_code2"],
        ) = (
            config.followcities[citynum - 1]["country_code2"],
            config.country_code2,
        )
        config.city, config.followcities[citynum - 1]["city"] = (
            config.followcities[citynum - 1]["city"],
            config.city,
        )
        (
            config.postal_code,
            config.followcities[citynum - 1]["postal_code"],
        ) = (
            config.followcities[citynum - 1]["postal_code"],
            config.postal_code,
        )
        (
            config.province,
            config.followcities[citynum - 1]["province"],
        ) = (
            config.followcities[citynum - 1]["province"],
            config.province,
        )
        config.lat, config.followcities[citynum - 1]["lat"] = (
            config.followcities[citynum - 1]["lat"],
            config.lat,
        )
        config.lon, config.followcities[citynum - 1]["lon"] = (
            config.followcities[citynum - 1]["lon"],
            config.lon,
        )
        (
            config.continent_code,
            config.followcities[citynum - 1]["continent_code"],
        ) = (
            config.followcities[citynum - 1]["continent_code"],
            config.continent_code,
        )
        (
            config.timezone,
            config.followcities[citynum - 1]["timezone"],
        ) = (
            config.followcities[citynum - 1]["timezone"],
            config.timezone,
        )

        config.save()  # Update config
        print(f"Home city is now set to: {config.city}, {config.country}")
        sys.exit(0)

    def remove_city(self, citynum: int, config: Configuration) -> None:
        r"""Remove a currently followed city"""

        if len(config.followcities) == 0:
            raise Exception(
                "There are no currently added cities. You must first add a city with `--addcity`."
            )
        if 1 <= citynum > len(config.followcities):
            raise Exception(
                f"City must be a number between 1 and {len(config.followcities)}."
            )

        # city: str = config.followcities[citynum - 1]["city"]
        # country: str = config.followcities[citynum - 1]["country"]
        del config.followcities[citynum - 1]

        config.save()  # Update config
        # print(f"Removed city: {city}, {country}")
        # sys.exit(0)

    def add_city(self, city: str, country: str, config: Configuration) -> None:
        r"""Add a new city to follow"""

        config.follow_city(city, country)

        for i in range(len(config.followcities)):
            locator: Locator = Locator()

            if "lat" not in config.followcities[i]:
                city_entry: dict[str | int] = locator.config(
                    config,
                    config.followcities[i]["city"],
                    config.followcities[i]["country"],
                )
                config.followcities[i] = {
                    **config.followcities[i],
                    **city_entry,
                }  # Update values
        config.save()  # Update config


# ================================================================[ MAIN LOOP ]
if __name__ == "__main__":
    try:
        InstanceGuard.ensure_single_instance()
        parser: ParseCommandline = ParseCommandline()
        cli_arguments: dict[str, str | int | bool] = parser.parse()

        DEBUG_MODE = cli_arguments["debug"]

        if bool(cli_arguments.get("newcity")) ^ bool(cli_arguments.get("country")):
            raise Exception("City and country must be provided together.")

        # No point to run everything if this is not set
        apikey: str = os.getenv(APIKEYENVVARNAME)
        if not apikey:
            raise Exception(
                f"Environment variable {APIKEYENVVARNAME} is not set. Run the app with --help"
            )

        # script_dir: str = str(Path(sys.argv[0]).resolve().parent)
        config: Configuration = Configuration()
        location_manager: LocationManager = LocationManager()

        # Attempt auto-configuration
        if not config.saved:
            locator: Locator = Locator()
            configurator: Configurator = Configurator()
            locator.config(config)
            configurator.config(config)
            config.save()

        config.load()

        # Location management
        if cli_arguments.get("newcity"):
            location_manager.add_city(
                cli_arguments["newcity"], cli_arguments["country"], config
            )
        if cli_arguments.get("removecity"):
            location_manager.remove_city(cli_arguments["removecity"], config)
        if cli_arguments.get("homecity"):
            location_manager.set_home(cli_arguments["homecity"], config)

        forecaster: WeatherForecaster = WeatherForecaster(config)
        weather_data: WeatherData = WeatherData()
        forecaster.get_data(weather_data)

        weather_girl: WeatherGirl = WeatherGirl(config, weather_data)
        weather_girl.present(cli_arguments.get("view"))

    except Exception as e:
        print(
            f"\nTUIWEATHERGIRL {APPVERSION} =============================================[ EXCEPTION ]"
        )
        print(e)

        if DEBUG_MODE:
            print(
                "\n---------------------------------------------------------------[ STACKTRACE ]"
            )
            traceback.print_exc()
        sys.exit(1)
