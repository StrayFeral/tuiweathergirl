#!/usr/bin/env python

# TUIWEATHERGIRL
# 2026 by Evgueni Antonov (StrayF)

import argparse
import concurrent.futures
import configparser
import csv
import curses
import logging
import math
import os
import pickle
import random
import re
import socket
import sys
import tempfile
import textwrap
import time
import traceback
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from pprint import pformat as pf
from pprint import pprint as pp
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from babel import Locale
from babel.dates import format_date
from babel.languages import get_official_languages

# Normally I don't leave global variables hanging in the source but
# I intentionally left these here, as I tend to change them time to time
# and don't want to scroll too much to find them

DEBUG_MODE: bool = False
DEFAULT_VIEW: str = "color"
DEFAULT_THEME: str = "main"
APPVERSION: str = "1.0"
DESCRIPTION_HELP: str = (
    f"TUIWEATHERGIRL {APPVERSION} by Evgueni Antonov (StrayF) 2026. Your daily terminal weathergirl."
)
EPILOGUE_HELP: str = """VIEWS:
    motivate and basic
        Best for barebone terminals.
        Printing to STDOUT then exit. You would enjoy the Motivate view a lot.
    
    dashboard
        A colorful ncurses dashboard. Requires terminal size at least 146x38.

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
USERAGENT: str = (
    f"TUIWeatherGirl/{APPVERSION} (https://github.com/StrayFeral/tuiweathergirl)"
)
TIMEZONE_APIKEY_ENV_VARNAME: str = "TIMEZONEAPIKEY"
NASAFIRMS_APIKEY_ENV_VARNAME: str = "NASAFIRMSAPIKEY"
REQTIMEOUT: int = 5
MIN_COLS: int = 79
MIN_LINES: int = 22
SUBMIT_BUG: str = "Submit a bug to the project GitHub page and attach your config file."
REFRESH_INTERVAL: int = 1200  # 20 minutes
DEFAULT_LOCALE: str = "en_US"  # The fallback plan
MAX_CITIES: int = 10  # This includes the home city

# Color indexes
COL_YELOWRED: int = 1
COL_YELOWBLACK: int = 2
COL_WHITEBLACK: int = 3
COL_BLUEBLACK: int = 4
COL_REDBLACK: int = 5
COL_GREENBLACK: int = 6
COL_CYANBLACK: int = 7

# logger = logging.getLogger(__name__)


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
        self.general: list[int] = kwargs["general"]
        self.border: list[int] = kwargs["border"]
        self.header: list[int] = kwargs["header"]
        self.home: list[int] = kwargs["home"]
        self.title: list[int] = kwargs["title"]
        self.warntitle: list[int] = kwargs["warntitle"]
        self.warnborder: list[int] = kwargs["warnborder"]

        self._last_used: int = None
        self._last_window: curses.window = None
        self._last_dim: bool = False

    def on(self, win: curses.window, attr: str | int | None, **kwargs) -> None:
        if attr == None:
            attr = "general"

        dim: bool = kwargs.get("dim", False)
        cp: str | int | None = attr
        
        if isinstance(attr, str):
            if not hasattr(self, attr):
                raise ValueError(f"Theme object does not have attribute '{attr}'.")
            color = getattr(self, attr, None)
            cp, dim = color
        
        if dim:
            win.attron(curses.color_pair(cp) | curses.A_DIM)
        else:
            win.attron(curses.color_pair(cp))
        
        self._last_used = cp
        self._last_window = win
        self._last_dim = dim

    def off(self) -> None:
        if self._last_dim:
            self._last_window.attroff(curses.color_pair(self._last_used) | curses.A_DIM)
            return
        self._last_window.attroff(curses.color_pair(self._last_used))


class MainTheme(Theme):
    def __init__(self) -> None:
        super().__init__(
            **{
                "general": [COL_WHITEBLACK, True],
                "border": [COL_BLUEBLACK, True],
                "header": [COL_WHITEBLACK, True],
                "home": [COL_WHITEBLACK, False],
                "title": [COL_CYANBLACK, False],
                "warntitle": [COL_WHITEBLACK, False],
                "warnborder": [COL_REDBLACK, False],
            }
        )


class ThemePalette:
    def __init__(self) -> None:
        self.palette: dict[str, Theme] = {"main": MainTheme()}

    def get_theme(self, themename: str = "main") -> Theme:
        if themename not in self.palette:
            raise ValueError(f"Invalid theme name '{themename}'.")
        return self.palette[themename]
    
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


class TextFlowStyle:
    r"""Class to define the flow of text for Paragraphs, TextLists, etc.
    
    It defines the side indents and above and below spacings."""

    def __init__(self, **kwargs) -> None:
        self.align: str = kwargs.get("align", "left")
        self.left_indent: int = kwargs.get("leftindent", 0)
        self.right_indent: int = kwargs.get("rightindent", 0)
        self.above_spacing: int = kwargs.get("abovespacing", 0)
        self.below_spacing: int = kwargs.get("belowspacing", 0)
        self.blockquote_indent: int = kwargs.get("blockquote", 0)
        self.bullet_space: int = kwargs.get("bulletspace", 1)

        # Yeah, I know. But I do sometimes make this typo.
        if "bellow" in kwargs:
            raise ValueError("Syntax error. Passed argument 'beLLowspacing', instead of 'beLowspacing'.")
    

class MainTextStyle(TextFlowStyle):
    def __init__(self) -> None:
        super().__init__(
            **{
                "align": "left",
                "leftindent": 0,
                "rightindent": 0,
                "abovespacing": 0,
                "belowspacing": 0,
                "blockquote": 4,
                "bulletspace": 1,
            }
        )


class TextParagraph:
    r"""Defines a paragraph of text.

    Any passed argument overrides the TextFlowStyle definition."""

    def __init__(self, text: str, **kwargs) -> None:
        self._data: str = text
        self.style: TextFlowStyle = kwargs.get("flowstyle", MainTextStyle())
        self.left_indent: int = kwargs.get("leftindent", self.style.left_indent)
        self.right_indent: int = kwargs.get("rightindent", self.style.right_indent)
        self.above_spacing: int = kwargs.get("abovespacing", self.style.above_spacing)
        self.below_spacing: int = kwargs.get("belowspacing", self.style.below_spacing)
        self.first_line: int = kwargs.get("firstline", 0)  # Indent

        self._wrapper: textwrap.TextWrapper = textwrap.TextWrapper(
            expand_tabs=True,
            replace_whitespace=True,
            drop_whitespace=True,
            break_long_words=False,
            break_on_hyphens=False,
            initial_indent=" " * self.first_line,
            subsequent_indent=" " * self.left_indent
        )
    
    def get_data(self, width: int = 0) -> list[str]:
        """Wraps the paragraph text into a list of strings, where each string's
        length is less than or equal to the desired width. Splits strictly by spaces.
        """

        if not self._data.strip():
            return []
        
        if width <= 0:
            return [self._data]

        actual_width: int = width - self.right_indent
        if actual_width <= 0:
            raise ValueError(f"Available layout width ({actual_width}) is too small.")

        self._wrapper.width = actual_width
        lines: list[str] = self._wrapper.wrap(self._data)

        for l in lines:
            if len(l) > width:
                raise ValueError(f"Cannot wrap paragraph. Shortest line is longer than the required width of {width} characters.")
        
        return lines


class TextList:
    r"""Defines a list of text.

    Any passed argument overrides the TextFlowStyle definition."""

    def __init__(self, text: list[str], **kwargs) -> None:
        self._data: list[str] = text
        self.style: TextFlowStyle = kwargs.get("flowstyle", MainTextStyle())
        self.left_indent: int = kwargs.get("leftindent", self.style.left_indent)
        self.right_indent: int = kwargs.get("rightindent", self.style.right_indent)
        self.above_spacing: int = kwargs.get("abovespacing", self.style.above_spacing)
        self.below_spacing: int = kwargs.get("belowspacing", self.style.below_spacing)
        self.bullet: str = kwargs.get("bullet", "*")
        self.number_separator: str = kwargs.get("numberseparator", ".")
        self.ordered: bool = kwargs.get("ordered", False)
        self.bullet_space: int = kwargs.get("belowspacing", self.bullet_space)

        first_line_prepend: str = self.number_separator + " " * self.bullet_space
        other_lines_prepend: str = " " * (len(first_line_prepend) + 2)  # Because of the number
        if not self.ordered:
            first_line_prepend = self.bullet + " " * self.bullet_space
            other_lines_prepend = " " * len(first_line_prepend)

        self._wrapper = textwrap.TextWrapper(
            expand_tabs=True,
            replace_whitespace=True,
            drop_whitespace=True,
            break_long_words=False,
            break_on_hyphens=False,
            initial_indent=first_line_prepend,
            subsequent_indent=other_lines_prepend
        )
    
    def get_data(self, width: int = 0) -> list[str]:
        if not self._data:
            return []
        
        # generate the wrapped lines for each list item
        # if ordered: replace the bulletchar with a number+number_separator
        # append all item_lines into lines and return lines
        actual_width: int = width - self.right_indent
        if actual_width <= 0:
            raise ValueError(f"Available layout width ({actual_width}) is too small.")

        self._wrapper.width = actual_width
        i: int = 0
        lines: list[str] = []
        for item in self.data:
            i += 1
            item_lines: list[str] = self._wrapper.wrap(self._data)

            # Prepending the number if the list is ordered.
            # And no - my use cases involve only lists with up to 20 items,
            # so I do not imagine anyone would want to print an ordered list
            # of 500 elements
            if len(item_lines) and self.ordered:
                item_lines[0] = f"{i}{item_lines[0]}"
            
            for l in item_lines:
                if len(l) > width:
                    raise ValueError(f"Cannot wrap paragraph. Shortest line is longer than the required width of {width} characters.")
                
            lines.extend(item_lines)
        
        return lines


class BlockQuote(TextParagraph):
    def __init__(self, text: str, **kwargs) -> None:
        self._data: str = text
        self.style: TextFlowStyle = kwargs.get("flowstyle", MainTextStyle())
        self.left_indent: int = kwargs.get("leftindent", self.style.left_indent)
        self.right_indent: int = kwargs.get("rightindent", self.style.right_indent)
        self.above_spacing: int = kwargs.get("abovespacing", self.style.above_spacing)
        self.below_spacing: int = kwargs.get("belowspacing", self.style.below_spacing)
        self.quotechar: str = kwargs.get("quotechar", "│")

        self._wrapper = textwrap.TextWrapper(
            expand_tabs=True,
            replace_whitespace=True,
            drop_whitespace=True,
            break_long_words=False,
            break_on_hyphens=False,
            initial_indent=f"{self.quotechar} ",
            subsequent_indent=f"{self.quotechar} "
        )
    

class Window:
    def __init__(self, **kwargs):
        theme: Theme | None = kwargs.get("theme", None)
        self.y: int = kwargs.get("y", 0)
        self.x: int = kwargs.get("x", 0)
        self.height: int = kwargs.get("height", 0)
        self.width: int = kwargs.get("width", 0)
        self.title: str = kwargs.get("title", "")
        self.border: bool = kwargs.get("border", False)
        self.cursor_x: int = 0
        self.cursor_y: int = 0

        # DEBUG INFO:
        self.column_num: int = kwargs.get("column_num", 0)
        self.column_len: int = kwargs.get("column_len", 0)

        self.inner_height: int = self.height
        self.inner_width: int = self.width

        if self.border:
            self.inner_height = self.height - 2
            self.inner_width = self.width - 2

        if self.inner_height < 1:
            raise ValueError(f"Window '{self.title}' is too shallow.")
        if self.inner_width < 1:
            raise ValueError(f"Window '{self.title}' is too narrow.")
        if len(self.title) + 2 > self.width:
            raise ValueError(f"The title for window '{self.title}' is too long.")

        self.theme: Theme | None = theme

        self.win: curses.window | None = curses.newwin(self.height, self.width, self.y, self.x)
        self.borderwin: curses.window | None = None
        if self.border:
            self.borderwin = self.win
            self.win = self.borderwin.derwin(self.inner_height, self.inner_width, 1, 1)
        self.win.scrollok(True)
    
    def __repr__(self) -> str:
        s: str = f"Window {self.column_num}-{self.column_len+1} [{self.title}]; Coord: {self.x},{self.y}, Dimensions: {self.width},{self.height}"
        if self.border:
            s += "; Bordered"
        return s

    def draw_border(self) -> None:
        if not self.border:
            return

        border_theme: str = "border"
        title_theme: str = "title"
        if self.title.lower() == "warning" or self.title.lower() == "warnings":
            border_theme: str = "warnborder"
            title_theme: str = "warntitle"

        if self.theme:
            self.theme.on(self.borderwin, border_theme)
            self.borderwin.box()
            self.theme.off()
            if self.title and len(self.title) > 0:
                self.theme.on(self.borderwin, title_theme)
                self.borderwin.addstr(0, 2, f"[{self.title}]")
                self.theme.off()
        else:
            self.borderwin.box()
            if self.title and len(self.title) > 0:
                self.borderwin.addstr(0, 2, f"[{self.title}]")
        # self.borderwin.refresh()

    def printyx(self, y: int, x: int, s: str, **kwargs):
        if x + len(s) >= self.inner_width:
            raise Exception(f"String {s!r} is too long and goes over the window right border: x={x}, len={len(s)}, inner_width={self.inner_width}.")

        theme_key: str = kwargs.get("theme", "general")
        if theme_key == "":
            theme_key = "general"  # Safeguard
        if self.theme:
            self.theme.on(self.win, theme_key)
            self.win.addstr(y, x, s)
            self.theme.off()
        else:
            self.win.addstr(y, x, s)

    def print(self, s: str | TextParagraph | TextList, **kwargs):
        theme_key: str = kwargs.get("theme", "general")
        align: str = kwargs.get("align", "left")
        y: int = kwargs.get("y", self.cursor_y)
        x: int = kwargs.get("x", self.cursor_x)
        newline: bool = kwargs.get("newline", False)
        width: int = kwargs.get("width", self.width - abs(x))
        max_lines: int = kwargs.get("maxlines", 0)

        if align not in ["left", "right", "center"]:
            raise ValueError(f"Invalid text alignment '{align}'. Use 'left', 'right' or 'center'.")
        
        if isinstance(s, str) and ("\n" in s or "\r" in s):
            raise ValueError(f"String {s!r} contains newline or carriage return characters.")

        if isinstance(s, str):
            if align == "right":
                if x < 0:
                    x = self.inner_width - len(s) - 1 + x
                else:
                    x = self.inner_width - len(s) - 1
            elif align == "center":
                if x < 0:
                    x = ((self.inner_width - len(s) - 1) // 2) + x
                else:
                    x = ((self.inner_width - len(s) - 1) // 2)
            
            self.printyx(y, x, s, theme=theme_key)
        
        elif isinstance(s, TextList) or isinstance(s, TextParagraph):
            last_x: int = 0
            for linenum, line in enumerate(s.get_data(width - 2)):
                if max_lines > 0 and linenum >= max_lines:
                    continue

                if align == "right":
                    if x < 0:
                        x = self.inner_width - len(line) - 1 + x
                    else:
                        x = self.inner_width - len(line) - 1
                elif align == "center":
                    if x < 0:
                        x = ((self.inner_width - len(line) - 1) // 2) + x
                    else:
                        x = ((self.inner_width - len(line) - 1) // 2)
                
                if y >= self.inner_height:
                    y = self.inner_height - 1

                if "\n" in line or "\r" in line:
                    raise ValueError(f"String {s!r} contains newline or carriage return characters.")
                self.printyx(y, x, line, theme=theme_key)
                last_x = x + len(line)

                y += 1
                if y >= self.inner_height:
                    y = self.inner_height - 1
            
            self.cursor_x = last_x
        
        # Calculating the new X
        if isinstance(s, str):
            self.cursor_x += x + len(s)

        if self.cursor_x >= self.inner_width - 1:
            self.cursor_x = 0
            self.cursor_y += 1
        
        # Calculating the new Y
        if newline:
            self.cursor_x = 0
            self.cursor_y += 1
        if self.cursor_y >= self.inner_height:
            self.win.scroll(self.cursor_y - self.inner_height)
            self.cursor_x = 0
            self.cursor_y = self.inner_height - 1

    def refresh(self) -> None:
        if self.borderwin:
            self.borderwin.noutrefresh()
        self.win.noutrefresh()

    def clear(self) -> None:
        self.win.erase()
    
    def draw_line(self, **kwargs) -> None:
        if not all(key in kwargs for key in ("x", "y", "direction", "length")):
            raise ValueError("Method draw_line() requires: x, y, direction and length.")
        y: int = kwargs.get("y")
        x: int = kwargs.get("x")
        direction: int = kwargs.get("direction")
        length: int = kwargs.get("length")
        theme: str = kwargs.get("theme", "border")

        if not direction in ["horizontal", "vertical", "h", "v"]:
            raise ValueError("Direction must be either horizontal or vertical.")
        
        if direction in ["horizontal", "h"] and x + length > self.width - x:
            raise ValueError(f"Cannot draw a horizontal line of {length} chars because only {self.width - x} chars are to the right of {x} in this window.")
        if direction in ["vertical", "v"] and y + length > self.height - y:
            raise ValueError(f"Cannot draw a vertical line of {length} chars because only {self.height - y} chars are down of {y} in this window.")

        hr: str = "─"
        vr: str = "│"

        s: str = vr
        if direction in ["horizontal", "h"]:
            s = hr * length
        
        # Draw a horizontal line
        if direction in ["horizontal", "h"]:
            self.print(y=y, x=x, s=s)
        else:
            # Draw a vertical line
            for n in range(length):
                self.print(y=y+n, x=x, s=s, theme=theme)


class LayoutColumn:
    def __init__(self, **kwargs) -> None:
        self.x: int = kwargs["x"]
        self.width: int = kwargs["width"]


class Layout:
    """Defines a layout.

    An entity made of columns, with top and bottom and left and right margins,
    left and right and top and bottom spacings between the columns and
    the windows.

    The columns are defined from left to right. If there is only one column
    it can be set center.
    """

    def __init__(self, **kwargs) -> None:
        self.xspacing: int = kwargs.get("xspacing", 0)
        self.yspacing: int = kwargs.get("yspacing", 0)
        self.xmargin: int = kwargs.get("xmargin", 0)
        self.ymargin: int = kwargs.get("ymargin", 0)
        self.maxy: int = kwargs.get("maxy")
        self.maxx: int = kwargs.get("maxx")
        self.columns: list[LayoutColumn] = []

        # One of the columns has been center
        self.__center: bool = False

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
        if self.__center:
            raise Exception(
                "Cannot add more columns. One column has been already center."
            )
        if width > self.__free_column_space:
            raise Exception(
                f"Cannot add the {len(self.columns)+1} column to layout: Wider than the remaining free width space of {self.__free_column_space} chars."
            )

        column: LayoutColumn = LayoutColumn(x=self.__next_column_x, width=width)
        self.columns.append(column)

    def set_center(self) -> None:
        if len(self.columns) > 1:
            raise Exception(
                "Method set_center() could be used only if there is just one column. Currently there are more."
            )
        self.columns[0].x = self.maxx // 2 - self.columns[0].width // 2
        self.__center = True


class LayoutManager:
    def __init__(self, **kwargs) -> None:
        self.stdscr: curses.window = kwargs.get("stdscr")
        maxy, maxx = self.stdscr.getmaxyx()
        self.layout: Layout = Layout(
            maxx=kwargs.get("maxx", maxx),
            maxy=kwargs.get("maxy", maxy),
            xspacing=kwargs.get("xspacing", 0),
            yspacing=kwargs.get("yspacing", 0),
            xmargin=kwargs.get("xmargin", 0),
            ymargin=kwargs.get("ymargin", 0),
        )
        self.theme: Theme = kwargs.get("theme", ThemePalette().get_theme())
        self.windows: list[list[Window]] = []

    def add_column(self, width: int | None = None) -> None:
        """Adds a new column to the layout.

        If width is None, it will assume the whole remaining width."""

        if width == None:
            width = self.layout.maxx - self.layout.xmargin * 2
            if len(self.layout.columns) > 0:
                width = self.layout.maxx - (self.layout.columns[-1].x + self.layout.columns[-1].width + self.layout.xspacing + self.layout.xmargin)

        self.layout.add_column(width)
    
    def set_two_columns(self) -> None:
        r"""Splits the screen in two columns with the same width"""

        maxx: int = self.layout.maxx - self.layout.xmargin * 2  # - self.layout.xspacing
        width: int = maxx // 2

        self.add_column(width)
        self.add_column(width)
    
    def set_three_columns(self) -> None:
        r"""Splits the screen in three columns with the same width"""

        maxx: int = self.layout.maxx - self.layout.xmargin * 2  # - self.layout.xspacing
        width: int = maxx // 3
        width_last: int = width

        # Just in case check:
        # The third column would be decreased if the total width exceeds maxx.
        # Seriously - no idea if such thing would ever happen, but as I said:
        # I am doing this right here just in case.
        width_last -= maxx - (width*2 + width_last)

        self.add_column(width)
        self.add_column(width)
        self.add_column(width_last)
    
    def set_four_columns(self) -> None:
        r"""Splits the screen in four columns with the same width"""

        maxx: int = self.layout.maxx - self.layout.xmargin * 2  # - self.layout.xspacing
        width: int = maxx // 4
        width_last: int = width

        # Just in case check:
        # The third column would be decreased if the total width exceeds maxx.
        # Seriously - no idea if such thing would ever happen, but as I said:
        # I am doing this right here just in case.
        width_last -= maxx - (width*3 + width_last)

        self.add_column(width)
        self.add_column(width)
        self.add_column(width)
        self.add_column(width_last)

    def add_window(self, **kwargs) -> Window:
        """Creates a new window, adds it to the internal list and returns it as well.

        Parameter Overlap controls if the window would overlap another column.
        It contains the column number to which end it will overflow.

        Default column_num is 0.
        If x or width are not set, defaults are the set column x and width.
        If overlap is set, width will be set to snap accordingly.
        """

        column_num: int = kwargs.get("column_num", 0)

        if len(self.layout.columns) == 0:
            raise Exception("No layout columns defined. New window cannot be added.")
        if not (0 <= column_num < len(self.layout.columns)):
            raise Exception(
                f"New window cannot be added as column '{column_num}' does not exist."
            )
        
        title: str = kwargs.get("title", "")
        height: int = kwargs.get("height", 3)
        width: int = kwargs.get("width", self.layout.columns[column_num].width)
        overlap: int = kwargs.get("overlap", column_num)
        y: int = kwargs.get("y", 0)
        x: int = kwargs.get("x", self.layout.columns[column_num].x)
        border: bool = kwargs.get("border", False)

        if len(self.windows) < len(self.layout.columns):
            self.windows.append([])

        window_index: int = 0
        if len(self.windows[column_num]) > 0:
            window_index = len(self.windows[column_num]) - 1

        if overlap < column_num:
            raise Exception(
                f"New Window[{column_num}][{window_index}]['{title}'] have an overlap set to a previous column."
            )
        if overlap > len(self.layout.columns) - 1:
            raise Exception(
                f"New Window[{column_num}][{window_index}]['{title}'] have an overlap set to a non-existing column."
            )
        if overlap != column_num:
            columns_width: int = 0
            for col in range(column_num, overlap+1):
                columns_width += self.layout.columns[col].width
            width = columns_width + (overlap - column_num) * self.layout.xspacing
        
        if x + width > self.layout.maxx:

            raise Exception(
                f"New Window[{column_num}][{window_index}]['{title}'] is wider than the screen."
            )

        # y: int = 0
        if y == 0:
            # Detect overlap of windows of previous columns
            col_index = 0
            for col_index in range(column_num + 1):
                for window in self.windows[col_index]:
                    if window.x + window.width > x:
                        y = (window.y + window.height + self.layout.ymargin)

        if y + height > self.layout.maxy:
            raise Exception(
                f"New Window[{column_num}][{window_index}]['{title}'] height is going below the screen. Has the terminal been resized?"
            )

        window: Window = Window(
            theme=self.theme,
            y=y,
            x=x,
            height=height,
            width=width,
            title=title,
            border=border,
            column_num=column_num,
            column_len=len(self.windows[column_num]),
        )
        self.windows[column_num].append(window)

        return window

    def draw_windows(self) -> None:
        for column in self.windows:
            for window in column:
                window.draw_border()
    
    def refresh_screen(self) -> None:
        """Pushes all the changes to the screen"""

        self.stdscr.noutrefresh()

        for column in self.windows:
            for window in column:
                if window.borderwin:
                    window.borderwin.touchwin()
                window.win.touchwin()
                window.refresh()


class WarningsManager:
    """Manages the warnings. This logger is responsible to read the disasters
    file, filter out the old events and show the new ones only.

    Log format (CSV):
    date, time, homeremote, location, label, message
    """

    RECLEN: int = 6  # The number of fields in the CSV

    def __init__(self):
        self.keep_max_days: int = 2
        self._messages: list[list[str]] = []
        self._filename: str = "~/.tuiweathergirl_warnings_log"
        self.home_location: str = ""

        if os.name == "nt":
            self.filename = Path(tempfile.gettempdir()) / "tuiweathergirl_warnings.log"
    
    def _is_old(self, message_date: str) -> bool:
        cutoff = datetime.now() - timedelta(days=self.keep_max_days)
        mdate = datetime.strptime(message_date, "%Y-%m-%d")
        if mdate >= cutoff:
            return False
        return True
    
    def _cleanup(self) -> None:
        # sublist[0] contains the message date
        self._messages = [
            sublist for sublist in self._messages
            if not self._is_old(sublist[0])
        ]

        # If the only message is a "No warnings" message - delete it
        # (we will insert new one with updated time)
        if len(self._messages) == 1 and self._messages[0][2] in ["", "***", "meh"] and "All quiet" in self._messages[0][-1]:
            self._messages = []
    
    def _load(self) -> None:
        full_path = Path(self._filename).expanduser()
        if not full_path.exists():
            return []
        
        with open(full_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            self._messages = [row for row in list(reader) if len(row) == self.RECLEN]

    def _save(self) -> None:
        full_path = Path(self._filename).expanduser()
        with open(full_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(self._messages)

    def get_warnings(self, number_of_messages: int) -> list[list[str]]:
        if len(self._messages) == 0:
            self._load()
            self._cleanup()
            self._save()

            # This will append a status message saying there are no
            # warnings at the moment
            if len(self._messages) == 0 and len(self.home_location) > 0:
                self.append("***")

        return self._messages[-number_of_messages:]

    def append(self, homeremote: str, location: str = "", label: str = "general", message: str = "No warnings at the moment. All quiet.") -> None:
        """Append and save all messages"""

        if homeremote.lower() not in ["home", "remote", "emergency", "disaster", "", "***", "meh"]:
            raise ValueError(f"Invalid value '{homeremote}' for homeremote.")

        if len(location) == 0:
            location = self.home_location

        now: datetime = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        message_entry: list[str] = [date_str, time_str, homeremote, location, label.upper(), message]

        # Appending, if not a duplicate or if no previous messages
        if len(self._messages) == 0 or (len(self._messages) > 0 and (message_entry[-1].lower() != self._messages[-1][-1].lower() or message_entry[0].lower() != self._messages[-1][0].lower())):
            self._cleanup()
            self._messages.append(message_entry)
            self._save()
    
    def apply_format(self, message_list) -> str:
        dates, times, homeremote, location, label, message = message_list
        message_str: str = f"[{dates}][{times}][{location:.15}][{label}]{message:.90}"
        return message_str


class Astronomer:
    """Celestial data"""

    def utc2local(self, utc_time_str: str, timezone_name: str) -> str:
        """Time converter"""
        hours, minutes = map(int, utc_time_str.split(':'))
        
        utc_dt: datetime.datetime = datetime.now(timezone.utc).replace(
            hour=hours, 
            minute=minutes, 
            second=0, 
            microsecond=0
        )
    
        local_tz = ZoneInfo(timezone_name)
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime('%H:%M')

    def get_sun_times(self, lat: float, lon: float, timezone_name: str) -> dict[str, str]:
        """Fetches sunrise and sunset for today in UTC."""
        
        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"

        data = requests.get(url, timeout=REQTIMEOUT).json()
        if data['status'] == 'OK':
            # Format: 2026-05-04T04:12:34+00:00
            sunrise: str = data['results']['sunrise'][11:16]
            sunset: str = data['results']['sunset'][11:16]
            sunrise = self.utc2local(sunrise, timezone_name)
            sunset = self.utc2local(sunset, timezone_name)
            return {"sunrise": sunrise, "sunset": sunset}
        
        return {}
    
    def get_zodiac_sign(self) -> str:
        """Returns the current Western astrological sign based on today's date."""
        
        now: datetime = datetime.now()
        m, d = now.month, now.day
        
        if (m == 12 and d >= 22) or (m == 1 and d <= 19): return "Capricorn"
        if (m == 1 and d >= 20) or (m == 2 and d <= 18): return "Aquarius"
        if (m == 2 and d >= 19) or (m == 3 and d <= 20): return "Pisces"
        if (m == 3 and d >= 21) or (m == 4 and d <= 19): return "Aries"
        if (m == 4 and d >= 20) or (m == 5 and d <= 20): return "Taurus"
        if (m == 5 and d >= 21) or (m == 6 and d <= 20): return "Gemini"
        if (m == 6 and d >= 21) or (m == 7 and d <= 22): return "Cancer"
        if (m == 7 and d >= 23) or (m == 8 and d <= 22): return "Leo"
        if (m == 8 and d >= 23) or (m == 9 and d <= 22): return "Virgo"
        if (m == 9 and d >= 23) or (m == 10 and d <= 22): return "Libra"
        if (m == 10 and d >= 23) or (m == 11 and d <= 21): return "Scorpio"
        if (m == 11 and d >= 22) or (m == 12 and d <= 21): return "Sagittarius"
        
        return ""
    
    def get_chinese_zodiac(self) -> str:
        """Returns the current Chinese Animal Year."""

        animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
        now: datetime = datetime.now()
        m, d, y = now.month, now.day, now.year

        animal: int = (y - 1900) % 12

        # Previous animal
        # Of course Chinese New Year fluctuates, but I have no intention to
        # calculate it properly. Roughly is enough for this app.
        if m == 1 and d < 20:
            animal -= 1
        
        return animals[animal]
    
    def get_moon_phase(self) -> str:
        """Returns a simple string description of the current moon phase."""

        # Simplified calculation based on the known New Moon of Jan 6, 2000
        now: datetime = datetime.now()
        diff = now - datetime(2000, 1, 6, 18, 14)
        days = diff.total_seconds() / 86400
        lunation = days % 29.530588853
        
        if lunation < 1.84: return "New Moon"
        if lunation < 5.53: return "Waxing Crescent"
        if lunation < 9.22: return "First Quarter"
        if lunation < 12.91: return "Waxing Gibbous"
        if lunation < 16.60: return "Full Moon"
        if lunation < 20.29: return "Waning Gibbous"
        if lunation < 23.98: return "Last Quarter"
        if lunation < 27.67: return "Waning Crescent"

        return "New Moon"


class Bulgarian:
    def get_history_fact(self, keyword: str = "") -> str:
        """Checks Wikipedia for major Bulgarian historical events occurring 
        today or yesterday.
        """

        now: datetime = datetime.now()
        yesterday: datetime = now - timedelta(days=1)
        
        # Specific keywords to filter for Bulgarian national history
        keywords: list[str] = [
            "Bulgaria", "Levski", "Botev", "Shipka", "Plovdiv", "Sofia", 
            "Turnovo", "Tarnovo", "Bulgarian Empire", "Cyrillic"
        ]

        if len(keyword) > 0:
            keywords.append(keyword)  # Just in case
        
        # Wikimedia requires a unique User-Agent identifying your app/contact info
        headers: dict[str, str] = {
            "User-Agent": USERAGENT,
            "Accept-Language": "en",
        }
        
        # We check today first, then yesterday
        for date_obj, label in [(now, "today"), (yesterday, "yesterday")]:
            # Wikipedia On This Day API expects month/day WITHOUT leading zeros (e.g. '3' instead of '03')
            month: str = str(int(date_obj.strftime('%m')))
            day: str = str(int(date_obj.strftime('%d')))
            
            # url: str = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/3/3"
            url: str = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}"
            
            response: requests.Response = requests.get(url, headers=headers, timeout=REQTIMEOUT)
            if response.status_code != 200:
                continue
                
            data = response.json()
            # We look through selected major events, general events, and deaths (for Tsars/Heroes)
            collections = data.get('selected', []) + data.get('events', []) + data.get('deaths', [])
            
            for event in collections:
                text: str = event.get('text', '')
                year: str = event.get('year', 'Unknown')
                
                if int(year) < 681:  # Bulgaria was found in 681AD
                    continue
                
                # Check if the event matches our Bulgarian history keywords
                if any(kw.lower() in text.lower() for kw in keywords):
                    # Clean the text slightly (removing Wikipedia's parentheticals)
                    clean_text = text.split(' (')[0].strip()
                        
                    return f"{year}: {clean_text}"

        return ""


class AllergyAndUVAdvisor:
    """Pollen (Trees/Grass) and UV (Sun Allergy) advisor"""

    def advise(self, lat: str, lon: str) -> list[str]:
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pollen_index_tree,pollen_index_grass,pollen_index_weed,uv_index&timezone=auto"

        warnings: list[str] = []

        response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
        if response.status_code != 200:
            return []
        
        tree_pollen: int = data.get('pollen_index_tree', 0)
        if tree_pollen >= 3:
            warnings.append(f"[HIGH RISK] High tree pollen levels: {tree_pollen}/5.")
        
        grass_pollen: int = data.get('pollen_index_grass', 0)
        if grass_pollen >= 3:
            warnings.append(f"[RISK][HAY FEVER/RESPIRATORY] Grass pollen levels: {grass_pollen}/5.")
        
        uv_index: int = data.get('uv_index', 0)
        if 6 <= uv_index < 8:
            warnings.append(f"[HIGH RISK][SUN ALLERGY] UV Index: {uv_index}. Limit direct sun exposure! Avoid being out 11:00-16:00!")
        if 8 <= uv_index < 10:
            warnings.append(f"[HIGH RISK][SUN ALLERGY] UV Index: {uv_index}. Extra protection needed!")
        if uv_index >= 10:
            warnings.append(f"[EXTREME RISK][SUN ALLERGY] UV Index: {uv_index}. Avoid exposure!")
        
        return warnings


class SpaceWeatherAdvisor:
    """NOAA advisories"""

    def get_geomagnetic_scales(self) -> dict[str, any]:
        """Fetches the active categorical NOAA scales (G, S, R)"""

        # NOTE: R-radio blackouts
        # Caused by: solar flares
        # Bursts of electromagnetic radiation: x-ray and extreme ultra-violet
        # Result: Commercial/any radiotransmissions are absorbed in the
        # upper athmosphere, thus not reaching receivers - blackout.
        # AFFECTED: Aviation, HAM, GPS precision

        # NOTE: S-solar radiation storms
        # Caused by: solar eruptions
        # AFFECTED: Satellite comms

        # NOTE: G-geomagnetic storms,
        # Caused by: coronal mass ejections, high-speed solar winds
        # AFFECTED: Power grids, satellites, migratory life, bio-sensitives

        url: str = "https://services.swpc.noaa.gov/products/noaa-scales.json"
        fallback: dict = {"G": 0, "S": 0, "R": 0, "DateStamp": "", "TimeStamp": ""}
        
        try:
            response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
            if response.status_code == 200:
                data = response.json()
                
                # '0' represents the latest observed metrics block
                latest_obs = data.get('0', {})
                if not latest_obs:
                    return fallback

                # Extract and parse categorical scales (G, S, R)
                # Converting values from strings (e.g., "0") to clean integers
                g_scale = int(latest_obs.get('G', {}).get('Scale', 0))
                s_scale = int(latest_obs.get('S', {}).get('Scale', 0))
                r_scale = int(latest_obs.get('R', {}).get('Scale', 0))
                
                return {
                    "G": g_scale,
                    "S": s_scale,
                    "R": r_scale,
                    "DateStamp": latest_obs.get('DateStamp', ''),
                    "TimeStamp": latest_obs.get('TimeStamp', '')
                }
        except Exception:
            pass
            
        return fallback

    def get_kp_index(self) -> float:
        """Fetches the current planetary Kp-index"""

        # NOTE: The Kp-index goes before the G-scale of geomagnetic anomalies
        # at least to my understanding

        url: str = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
        try:
            response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Entries are chronologically ordered; the last item is the most recent
                    latest_entry = data[-1]
                    
                    # Modern SWPC format represents Kp as a raw floating-point number
                    kp_val = latest_entry.get("Kp")
                    if kp_val is not None:
                        return float(kp_val)
        except Exception:
            pass
            
        return 0.0

    def _get_geomagnetic_warning(self, kp_index: float, g_scale: int = None) -> str:
        """Evaluates current space weather data to produce biomechanical alerts.
        Warns individuals with high electrosensitivity or barometric/magnetic sensitivity.
        """
        # If g_scale is not supplied, we mathematically derive it from Kp.
        # Kp 5 = G1, Kp 6 = G2, Kp 7 = G3, Kp 8 = G4, Kp 9 = G5
        if g_scale is None:
            g_scale = int(kp_index - 4) if kp_index >= 5 else 0

        # Kp index 4 represents 'Active' geomagnetic activity (borderline storm)
        if 4.0 <= kp_index < 5.0:
            return f"[RISK][Kp {kp_index:.2f}] Unsettled atmospheric charging. Eventual migraines, restlessness, or mild joint irritation."
            
        # Kp index 5+ marks the formal threshold for active Geomagnetic Storms
        elif kp_index >= 5.0:
            storm_descriptions = {
                1: "Minor",
                2: "Moderate",
                3: "Strong",
                4: "Severe",
                5: "Extreme"
            }
            storm_label = storm_descriptions.get(g_scale, f"Storm (G{g_scale})")
            
            return f"[HIGH RISK][Kp {kp_index:.2f}] {storm_label} Geomagnetic storm. Risk: Blood pressure, headaches, insomnia, severe joing pain."
            
        return ""
    
    def _get_solar_radiation_warning(self, s_scale: int) -> str:
        """Generates warning strings for the S-scale (0 to 5)."""
        
        if s_scale < 2:
            return ""
        
        warnings: dict[int, str] = {
            2: "[MODERATE RAD.STORM] Minor exposure to passengers and flight crews on high-altitude polar routes.",
            3: "[STRONG RAD.STORM] Increased exposure to passengers and crews on high-altitude on polar routes.",
            4: "[SEVERE RAD.STORM] Flights to avoid polar regions! Elevated radiation exposure for crews and passengers. Blackout for polar HF comms.",
            5: "[EXTREME RAD.STORM][CRITICAL] Shut down for polar and high alt.routes! High exposure for crews and passengers! Blackouts!",
        }
        
        warning: str = warnings.get(s_scale, f"[WARNING] Elevated Solar Radiation (S{s_scale}/5)")
        return warning
    
    def _get_radio_blackout_warning(self, r_scale: int) -> str:
        """Generates warning strings for the R-scale (0 to 5)."""
        
        if r_scale < 2:
            return ""
        
        warnings: dict[int, str] = {
            2: "[MODERATE RADIO BLACKOUT] HF comms limited. Marine and aviation operators may lose contact for tens of mins. Minor GPS errs.",
            3: "[STRONG RADIO BLACKOUT] Loss of contact for 1 hour for marine, aviation and amateur ops. GPS errors.",
            4: "[SEVERE RADIO BLACKOUT] HF radio blackout for entire sunlit side of Earth. No comms up to 2hrs. No GPS.",
            5: "[EXTREME RADIO BLACKOUT] COMPLETE HF RADIO BLACKOUT. No comms for few hrs. No GPS.",
        }
            
        warning = warnings.get(r_scale, f"[WARNING] Active Radio Blackout (R{r_scale}/5)")
        return warning
    
    def get_warnings(self, kp_index: float, geomagnetic_scales: dict[str, any]) -> list[list[str]]:
        geomagnetic_warning: str = self._get_geomagnetic_warning(kp_index, geomagnetic_scales["G"])
        solar_radiation_warning: str = self._get_solar_radiation_warning(geomagnetic_scales["S"])
        radio_blackout_warning: str = self._get_radio_blackout_warning(geomagnetic_scales["R"])

        warnings: list[list[str]] = []

        if geomagnetic_warning:
            geomagnetic_entry: list[str] = ["remote", "SPACE", "GEOMAGNETIC", geomagnetic_warning]
            if any(x in geomagnetic_warning for x in ("[STRONG", "[SEVERE", "[EXTREME")):
                geomagnetic_entry = ["EMERGENCY", "SPACE", "GEOMAGNETIC", geomagnetic_warning]
            warnings.append(geomagnetic_entry)

        if solar_radiation_warning:
            solar_radiation_entry: list[str] = ["remote", "SPACE", "SOLARRADIATION", solar_radiation_warning]
            if any(x in solar_radiation_warning for x in ("[STRONG", "[SEVERE", "[EXTREME")):
                solar_radiation_entry = ["EMERGENCY", "SPACE", "SOLARRADIATION", solar_radiation_warning]
            warnings.append(solar_radiation_entry)

        if radio_blackout_warning:
            radioblackout_entry: list[str] = ["remote", "SPACE", "RADIOBLACKOUT", radio_blackout_warning]
            if any(x in radio_blackout_warning for x in ("[STRONG", "[SEVERE", "[EXTREME")):
                radioblackout_entry = ["EMERGENCY", "SPACE", "RADIOBLACKOUT", radio_blackout_warning]
            warnings.append(radioblackout_entry)

        return warnings
            
    

class DisasterAdvisor:
    """Monitors the national disasters"""

    def __init__(self, **kwargs) -> None:
        # Controlling which types of disasters we want monitored
        # Default - we monitor everything
        self.earthquake: bool = True
        self.flood: bool = True
        self.wildfire: bool = True
        self.drought: bool = True
        self.storm: bool = True
        self.tsunami: bool = True
        self.volcano: bool = True

        params: dict[str, str] = {
            "quake": "earthquake",
            "earthquake": "earthquake",
            "flood": "flood",
            "fire": "wildfire",
            "wildfire": "wildfire",
            "drought": "drought",
            "storm": "storm",
            "cyclone": "storm",
            "tsunami": "tsunami",
            "volcanoe": "volcanoe"
        }

        for param in params.keys():
            if param in kwargs:
                setattr(self, params[param], kwargs[param])
        
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Calculates distance in km between two points. Implementation of the haversine formula for the planet Earth."""
        R: int = 6371  # Earth mean radius
        dlat: float = math.radians(lat2 - lat1)
        dlon: float = math.radians(lon2 - lon1)
        a: float = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
    def _get_affected_provinces(self, url: str) -> list[str]:
        """I assume that more than one province might be affected"""

        provinces: list[str] = []

        response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        if "datums" not in data:
            return []
        
        for datum in data["datums"]:
            for subdatum in datum["datum"]:
                for scalar in subdatum["scalars"]["scalar"]:
                    if scalar["name"].upper() == "ADMIN_NAME":
                        provinces.append(scalar["value"])
        
        return provinces

    def get_disasters(self, countries_list: list[str]) -> list[list[str]]:
        event_types: dict[str, str] = {
            "DR": "DROUGHT",
            "EQ": "EARTHQUAKE",
            "FL": "FLOOD",
            "TC": "STORM",
            "TS": "TSUNAMI",
            "VO": "VOLCANO",
            "WF": "WILDFIRE"
        }

        disasters: list[list[str]] = []
        url = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/latest"

        response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
        if response.status_code != 200:
            return []
        
        data = response.json()

        for feature in data["features"]:
            now: datetime = datetime.now()
            todate: datetime = datetime.fromisoformat(feature["properties"]["todate"])
            old: datetime = now - todate

            if old.days > 2 or feature["properties"]["istemporary"].lower() == "true" or feature["properties"]["iscurrent"].lower() == "false" or (feature["properties"]["alertlevel"].lower() == "green" and feature["properties"]["episodealertlevel"].lower() == "green"):
                    continue

            matching_locations: list[str] = []
            for location in feature["properties"]["affectedcountries"]:
                if location["iso2"] in countries_list:
                    matching_locations.append(location["countryname"])
            
            if len(matching_locations) == 0:
                continue
            
            # At this point we have a location of interest
            # but do we monitor this type of disasters?
            label: str = event_types[feature["properties"]["eventtype"]]
            if not getattr(self, label):
                continue

            source: str = feature["properties"]["source"]
            severity: str = feature["properties"]["severitydata"]["severitytext"]

            # Getting the details
            provinces: list[str] = []
            details_url: str = feature["properties"]["url"]["details"]
            details_response: requests.Response = requests.get(details_url, timeout=REQTIMEOUT)
            
            if details_response.status_code == 200:
                details_data = details_response.json()

                if "properties" in details_data and "impacts" in details_data["properties"]:
                    for impact in details_data["properties"]["impacts"]:
                        if "resource" in impact and "impact" in impact["resource"]:
                            provinces = self._get_affected_provinces(impact["resource"]["impact"])

            for location in matching_locations:
                if not provinces:
                    message: str = f"{severity} ({source})"
                    disasters.append(["DISASTER", location, label, message])
                else:
                    for province in provinces:
                        message: str = f"[{province}] {severity} ({source})"
                        disasters.append(["DISASTER", location, label, message])
        
        return disasters
    
    def get_detailed_fires(self, lat: str, lon: str) -> list[list[str]]:
        """This time pulling from NASA FIRMS if the API key is available"""

        apikey: str = os.getenv(NASAFIRMS_APIKEY_ENV_VARNAME)
        if not apikey:
            return []
        
        latt: float = float(lat)
        lonn: float = float(lon)
        fire_list: list[str] = []

        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{apikey}/VIIRS_NOAA21_NRT/{lonn-1},{latt-1},{lonn+1},{latt+1}/1"

        response: requests.Response = requests.get(url, timeout=REQTIMEOUT).text.split('\n')
        for line in response[1:]:  # Skipping the CSV header
            if not line:
                continue
            
            f_lat, f_lon, ti4, scan, track, f_date, f_time, satellite, instrument, confidence, ver_, ti5, frp, daynight = line.split(',')
            distance = self._haversine(latt, lonn, f_lat, f_lon)

            # Scanning pixel area
            pixel_area_km2: float = scan * track
            f_size: str = "LARGE"
            if pixel_area_km2 <= 0.20:
                f_size = "small area"
            elif pixel_area_km2 <= 0.45:
                f_size = "MEDIUM AREA"
            
            # Heat Signature via FRP (Fire Radiative Power)
            heat: str = "STRONG"
            if frp < 5.0:
                heat = "Weak"
            elif frp <= 20.0:
                heat = "MEDIUM"
            
            confident: str = ""
            if confidence == 'L':
                confident = " (Possible False Alarm/Low Certainty)"
            
            if distance <= 100:  # km
                location: str = f"[{f_lat}, {f_lon}]"
                message: str = f"[{f_date},{f_time}][{dist:.1f}km] {heat} fire on a {f_size} {confident}"
                fire_list.append(["DISASTER", location, "WILDFIRE", message])
        
        return fire_list
        
    def get_detailed_quakes(self, lat: str, lon: str) -> list[list[str]]:
        """USGS query"""

        min_mmi: float = 2  # I'm not interested in weaker ones

        start_of_yesterday: date = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_time: date = start_of_yesterday.isoformat()

        quakes: list[list[str]] = []
        url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_time}&latitude={lat}&longitude={lon}&maxradiuskm=200&minmagnitude=2.5"

        response = requests.get(url, timeout=REQTIMEOUT)
        if response.status_code != 200:
            return []
        
        data: requests.Response = response.json()
        
        for feature in data["features"]:
            magnitude: float = float(feature["properties"]["mag"])
            place: str = feature["properties"]["place"]
            alert: str = feature["properties"]["alert"]
            tsunami: int = feature["properties"]["tsunami"]
            mmi: float = float(feature["properties"]["tsunami"])
            depth: float = float(feature["geometry"]["coordinates"][-1])
            plane: str = "EARTH"

            if depth < 0:
                plane = "UNDERWATER"
            
            tsunami_str: str = ""
            if tsunami:
                tsunami_str = "[TSUNAMI!]"

            if mmi < min_mmi:
                continue
            
            location: str = f"***"
            message: str = f"[{magnitude}][{alert.upper()}][{plane}]{tsunami_str} {place}"
            quakes.append(["DISASTER", location, "EARTHQUAKE", message])
        
        return quakes

    def get_fireballs(self) -> list[list[str]]:
        """Querying NASA Fireballs"""

        start_of_yesterday: date = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        url: str = "https://ssd-api.jpl.nasa.gov/fireball.api?date-start=" + start_of_yesterday.strftime('%Y-%m-%d')

        response = requests.get(url, timeout=REQTIMEOUT)
        if response.status_code != 200:
            return []
        
        data: requests.Response = response.json()

        if data["count"] == "0":
            return []
        
        fireballs: list[list[str]] = []
        
        f: list[str] = data["fields"]
        for datum in data["data"]:
            date: str = datum[f.index["date"]]
            energy: str = datum[f.index["energy"]]
            impacte: float = float(datum[f.index["impact-e"]])
            altitude: str = datum[f.index["alt"]]
            velocity: str = datum[f.index["vel"]]

            if velocity is None:
                velocity = "UNKNOWN"
            
            size: str = "MINOR FIREBALL"
            homeremote: str = "REMOTE"
            if 0.1 >= impacte <= 1:
                size = "MODERATE BOLIDE"
            elif 1.1 >= impacte <= 10:
                size = "SEVERE AIRBURST"
                homeremote = "EMERGENCY"
            elif impacte > 10:
                size = "CATASTROPHE!!!"
                homeremote = "DISASTER"
            
            message: str = f"[{date}][SIZE: {size}] Altitude: {altitude}, velocity: {velocity}, impact-e: {impacte}."
            fireballs.append([homeremote, "SPACE", "FIREBALL", message])
        
        return fireballs


class ElectrostaticAdvisor:
    def get_xray_flux(self) -> str:
        """Fetches the current Solar X-ray flux class (e.g., 'B2.1', 'M5.0').
        Source: NOAA GOES Primary X-ray Flux
        """
        
        # This endpoint provides the 1-minute data for the last 24 hours
        url = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
        try:
            response = requests.get(url, timeout=REQTIMEOUT)
            if response.status_code == 200:
                data: requests.Response = response.json()
                # Get the very last measurement
                latest = data[-1]
                flux_value = latest.get('flux', 0.0)
                
                # Convert numeric flux to Class (A, B, C, M, X)
                # 1e-8 = A, 1e-7 = B, 1e-6 = C, 1e-5 = M, 1e-4 = X
                if flux_value < 1e-7: return f"A{flux_value/1e-8:.1f}"
                elif flux_value < 1e-6: return f"B{flux_value/1e-7:.1f}"
                elif flux_value < 1e-5: return f"C{flux_value/1e-6:.1f}"
                elif flux_value < 1e-4: return f"M{flux_value/1e-5:.1f}"
                else: return f"X{flux_value/1e-4:.1f}"
        except Exception:
            pass
        return "B1.0" # Default/Quiet background
    
    def get_electrostatic_warning(self, xray_flux: str) -> str:
        """Evaluates risk for electrosensitivity"""

        if not xray_flux:
            return ""
            
        class_letter = xray_flux[0].upper()
        
        if class_letter == 'M':
            return f"[RISK] Sol.X-ray flux: {xray_flux} (M-Class). Discomfort or 'phantom' skin sensations for sensitive people."
        elif class_letter == 'X':
            return f"[RISK] Sol.X-ray flux: {xray_flux} (X-Class). Neurological discomfort, dizziness, and localized pain."

        return ""

class HolidaysManager:
    """Taking care of the national holidays"""

    def _need_update(self, year: str, code1: str, code2: str) -> bool:
        this_year: str = datetime.now().year
        if this_year != year or code1 != code2:
            return True
        return False
    
    def update(self, holidays: dict[str, str], country_code2: str) -> dict[str, str]:
        """Method to update the holidays data.

        However no update would be needed if the holidays year is the same as
        today's year and the holidays country code is the same as our
        HOME's country code.
        """

        new_holidays: dict[str, str] = {}

        # Holidays data
        year: str = ""
        code1: str = ""
        separator: str = "#"

        if len(holidays) > 0:
            year = list(holidays.keys())[0].split("-")[0]
            code1 = holidays[list(holidays.keys())[0]].split(separator)[0]

            if not self._need_update(year, code1, country_code2):
                return holidays
        
        if len(year) == 0:
            year = datetime.now().year

        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code2.upper()}"
        data = requests.get(url, timeout=REQTIMEOUT).json()
        for holiday in data:
            new_holidays[holiday["date"]] = f"{holiday["countryCode"]}{separator}{holiday["name"]}"
        
        return new_holidays


class CacheManager:
    r"""For when restarting the app too often
    and avoid being banned by the APIs
    """

    def __init__(self) -> None:
        self.filename: str = (
            Path(tempfile.gettempdir()) / "tuiweathergirl_cache.pkl"
        )
        self.loaded: bool = False
        self._data: dict[str, Any] = {}

    def register(self, name: str, instance: any) -> None:
        """Register a client object that needs caching."""
        self._data[name] = instance

    @property
    def too_soon(self):
        cache_path = Path(self.filename).expanduser()
        if not cache_path.exists():
            return False

        mtime = cache_path.stat().st_mtime
        last_modified_date = datetime.fromtimestamp(mtime).astimezone()
        now: datetime = datetime.now().astimezone()

        # Modified less than 5 mins ago:
        return now - last_modified_date < timedelta(minutes=REFRESH_INTERVAL // 60)

    @property
    def saved(self) -> bool:
        cache_path = Path(self.filename).expanduser()
        return cache_path.exists()
    
    def load(self) -> None:
        r"""Reads the cache"""

        if len(self._data) == 0:
            raise Exception("Cannot load cache: No registered client objects.")
        if not self.saved:
            raise Exception("Tried to load unsaved cache.")
        
        full_path = Path(self.filename).expanduser()
        with open(full_path, "rb") as f:
            payload: dict[str, any] = pickle.load(f)

        for name, cached in payload.items():
            if name in self._data:
                # self._data[name].__dict__.update(cached)
                self._data[name].__dict__.clear()
                self._data[name].__dict__.update(cached.__dict__)
            else:
                raise Exception(f"Client '{name}' was cached but not registered to be loaded.")

        self.loaded = True

    
    def save(self) -> None:
        """Saves the cache."""

        if self.too_soon:
            return
        
        # I don't care of a previous cache
        cachefile: Path = Path(self.filename)
        cachefile.unlink(missing_ok=True)
        
        payload: dict[str, Any] = {
            name: instance for name, instance in self._data.items()
        }
        with open(cachefile, "wb") as f:
            pickle.dump(payload, f)

    def delete(self) -> None:
        """Deletes the cache."""

        cachefile: Path = Path(self.cachefilename)
        cachefile.unlink(missing_ok=True)


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
        self.theme: str = DEFAULT_THEME

        self.followcities: list[dict[str | int]] = []

        self.holidays: dict[str, str] = {}

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
    def countries_of_interest(self) -> list[str]:
        """Returns only the 2-letter country codes"""
        
        countries: list[str] = [self.country_code2]
        for city in self.followcities:
            countries.append(city["country_code2"])
        
        return countries

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
        s += f"Default theme: {self.theme}\n"
        s += f"Filename: {self.filename}\n"

        s += "\nFOLLOWED CITIES:\n"
        s += pf(self.followcities)
        s += "\n"

        return s

    @property
    def dst(self) -> bool:
        if len(self.timezone) == 0:
            return False
        now: datetime = datetime.now(ZoneInfo(self.timezone))
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
            "theme": self.theme,
        }

        config["HOLIDAYS"] = self.holidays

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
        self.theme = config["PREFERENCES"]["theme"]

        self.holidays = dict(config["HOLIDAYS"])

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
        if len(self.followcities) > MAX_CITIES-2:
            raise Exception(f"Cannot follow city. Max cities limit is {MAX_CITIES-1}.")

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

    __ISO3_TO_ISO2 = {
        "AFG": "AF", "ALB": "AL", "DZA": "DZ", "AND": "AD", "AGO": "AO", "ATG": "AG", "ARG": "AR", "ARM": "AM", "AUS": "AU",
        "AUT": "AT", "AZE": "AZ", "BHS": "BS", "BHR": "BH", "BGD": "BD", "BRB": "BB", "BLR": "BY", "BEL": "BE", "BLZ": "BZ",
        "BEN": "BJ", "BTN": "BT", "BOL": "BO", "BIH": "BA", "BWA": "BW", "BRA": "BR", "BRN": "BN", "BGR": "BG", "BFA": "BF",
        "BDI": "BI", "CPV": "CV", "KHM": "KH", "CMR": "CM", "CAN": "CA", "CAF": "CF", "TCD": "TD", "CHL": "CL", "CHN": "CN",
        "COL": "CO", "COM": "KM", "COG": "CG", "COD": "CD", "CRI": "CR", "CIV": "CI", "HRV": "HR", "CUB": "CU", "CYP": "CY",
        "CZE": "CZ", "DNK": "DK", "DJI": "DJ", "DMA": "DM", "DOM": "DO", "ECU": "EC", "EGY": "EG", "SLV": "SV", "GNQ": "GQ",
        "ERI": "ER", "EST": "EE", "SWZ": "SZ", "ETH": "ET", "FJI": "FJ", "FIN": "FI", "FRA": "FR", "GAB": "GA", "GMB": "GM",
        "GEO": "GE", "DEU": "DE", "GHA": "GH", "GRC": "GR", "GRD": "GD", "GTM": "GT", "GIN": "GN", "GNB": "GW", "GUY": "GY",
        "HTI": "HT", "HND": "HN", "HUN": "HU", "ISL": "IS", "IND": "IN", "IDN": "ID", "IRN": "IR", "IRQ": "IQ", "IRL": "IE",
        "ISR": "IL", "ITA": "IT", "JAM": "JM", "JPN": "JP", "JOR": "JO", "KAZ": "KZ", "KEN": "KE", "KIR": "KI", "KOR": "KR",
        "KWT": "KW", "KGZ": "KG", "LAO": "LA", "LVA": "LV", "LBN": "LB", "LSO": "LS", "LBR": "LR", "LBY": "LY", "LIE": "LI",
        "LTU": "LT", "LUX": "LU", "MDG": "MG", "MWI": "MW", "MYS": "MY", "MDV": "MV", "MLI": "ML", "MLT": "MT", "MHL": "MH",
        "MRT": "MR", "MUS": "MU", "MEX": "MX", "FSM": "FM", "MDA": "MD", "MCO": "MC", "MNG": "MN", "MNE": "ME", "MAR": "MA",
        "MOZ": "MZ", "MMR": "MM", "NAM": "NA", "NRU": "NR", "NPL": "NP", "NLD": "NL", "NZL": "NZ", "NIC": "NI", "NER": "NE",
        "NGA": "NG", "MKD": "MK", "NOR": "NO", "OMN": "OM", "PAK": "PK", "PLW": "PW", "PAN": "PA", "PNG": "PG", "PRY": "PY",
        "PER": "PE", "PHL": "PH", "POL": "PL", "PRT": "PT", "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "KNA": "KN",
        "LCA": "LC", "VCT": "VC", "WSM": "WS", "SMR": "SM", "STP": "ST", "SAU": "SA", "SEN": "SN", "SRB": "RS", "SYC": "SC",
        "SLE": "SL", "SGP": "SG", "SVK": "SK", "SVN": "SI", "SLB": "SB", "SOM": "SO", "ZAF": "ZA", "SSD": "SS", "ESP": "ES",
        "LKA": "LK", "SDN": "SD", "SUR": "SR", "SWE": "SE", "CHE": "CH", "SYR": "SY", "TWN": "TW", "TJK": "TJ", "TZA": "TZ",
        "THA": "TH", "TLS": "TL", "TGO": "TG", "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR", "TKM": "TM", "TUV": "TV",
        "UGA": "UG", "UKR": "UA", "ARE": "AE", "GBR": "GB", "USA": "US", "URY": "UY", "UZB": "UZ", "VUT": "VU", "VEN": "VE",
        "VNM": "VN", "YEM": "YE", "ZMB": "ZM", "ZWE": "ZW"
    }

    def __init__(self) -> None:
        self.tzapi_calls: int = 0  # Counts the TZ data API calls
    
    def convert_to_country_code2(self, country_code3: str):
        """Converts a 3-letter country code to a 2-letter country code"""
        if country_code3 not in self.__ISO3_TO_ISO2:
            raise ValueError(f"Unknown country code '{country_code3}'.")
        return self.__ISO3_TO_ISO2[country_code3]

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
            response: requests.Response = requests.get(url, timeout=REQTIMEOUT)

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
                "User-Agent": USERAGENT,
                "Accept-Language": "en",
            }
            url: str = (
                f"https://nominatim.openstreetmap.org/search?city={city}&country={country}&format=json&addressdetails=1"
            )
            response: requests.Response = requests.get(url, headers=headers, timeout=REQTIMEOUT)

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
            apikey: str = os.getenv(TIMEZONE_APIKEY_ENV_VARNAME)

            if not apikey:
                raise Exception(
                    f"Environment variable {TIMEZONE_APIKEY_ENV_VARNAME} is not set. Please get API key and set it in this variable before running this application."
                )

            if self.tzapi_calls > 0:
                time.sleep(1)  # API limit
            url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={apikey}&format=json&by=position&lat={lat}&lng={lon}"
            response: requests.Response = requests.get(url, timeout=REQTIMEOUT)
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
            response = requests.get("https://zenquotes.io/api/random", timeout=REQTIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return [data[0].get("q"), data[0].get("a")]
        except Exception:
            pass

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
        self.hcur: int = 0
        self.wind_type: str = ""
        self.precipitation_type: str = ""
        self.humidity_level_min: str = ""
        self.humidity_level_max: str = ""
        self.humidity: str = ""
        self.wind_direction_long: str = ""
        self.baropressure: float = 0

        self.warnings: list[str] = []
        self.week: list[BriefDailyForecast] = []
        self.cities_data: list[list[str | int]] = []

        # This was never planned originally
        # but I decided to add it in the last moment
        self.misc_data: dict[list[any]] = {}


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
        return "Precip"

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
    
    def _get_main_location_weather_data(self, lat: str, lon: str, timezone: str, tunit: str, wunit: str) -> requests.Response:
        r"""Gets various weather data for the main location"""

        #  &timezone=auto # current
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day,pressure_msl"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,relative_humidity_2m_min,relative_humidity_2m_max"
            f"&timezone={timezone.replace('/', '%2F')}"
            f"&temperature_unit={tunit}&wind_speed_unit={wunit}"
            f"&forecast_days=8"
        )
        result: requests.Response = requests.get(url, timeout=REQTIMEOUT)

        if not result:
            raise Exception(
                f"Cannot obtain weather data. Error {result.status_code}: {APIIssues.get_api_problem(result.status_code)}"
            )

        return result.json()
    

    def _get_brief_weather_data(self, lats: str, lons: str, timezones: str, tunit: str) -> requests.Response:
        r"""Gets only current temperatures for a given location"""

        #  &timezone=auto # current
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lats}&longitude={lons}"
            f"&current=temperature_2m,is_day"
            f"&timezone={timezones.replace('/', '%2F')}"
            f"&temperature_unit={tunit}"
        )
        result: requests.Response = requests.get(url, timeout=REQTIMEOUT)

        if not result:
            raise Exception(
                f"Cannot obtain weather data. Error {result.status_code}: {APIIssues.get_api_problem(result.status_code)}"
            )

        return result.json()
    

    def _get_aqi_data(self, lat: str, lon: str) -> requests.Response:
        r"""Gets only AQI data for the given location"""

        # Air Quality API (Separate endpoint but same coordinates)
        url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={lat}&longitude={lon}&current=us_aqi"
        )
        result: requests.Response = requests.get(url, timeout=REQTIMEOUT)

        if not result:
            raise Exception(
                f"Cannot obtain air quality data. Error {result.status_code}: {APIIssues.get_api_problem(result.status_code)}"
            )

        return result.json()
    
    def get_storm_warning(self, weather_code: int, wind: int) -> str:
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
    
    def get_baropressure_warning(self, baropressure: float) -> str:
        """Basic advisory"""

        if baropressure < 1000:
            return f"[{baropressure} hPa][RISK] Low atmospheric pressure. Risk for migraines, sinus headaches, arthritic joint pain, low blood pressure."
        if baropressure > 1026:
            return f"[{baropressure} hPa][RISK] High atmospheric pressure. Risk for high blood pressure, breathing issues."
        
        return ""
    
    def get_humidity_risk(self, humidity: int) -> str:
        """Returns a message only if humidity poses a risk for people with
        medical conditions (respiratory)"""

        if humidity < 30:
            return f"[{humidity}%][RISK] People with asthma or chronic resp. condt.: Airway irritation."

        if humidity < 40:
            return f"[{humidity}%][MOD.RISK] People with sensitive resp. systems: Mild airway irritation."

        if humidity <= 60:
            return ""  # Safe

        if humidity <= 70:
            return f"[{humidity}%][RISK] People with asthma: Increased allergens, difficult breathing."

        return f"[{humidity}%][HIGH RISK] People with resp. condt.: Labored breathing!"

    def get_data(self, weather_data: WeatherData) -> None:
        # Build the API URL with your config preferences
        tunit = "celsius" if self.config.celsius else "fahrenheit"
        wunit = "kmh" if self.config.metric else "mph"

        # Format Date and Time
        now: datetime = datetime.now(ZoneInfo(self.config.timezone))

        cache = CacheManager()
        cache.register("weather_data", weather_data)

        if not cache.loaded and cache.too_soon:
            cache.load()
            return

        warnings: WarningsManager = WarningsManager()

        bulgarian: Bulgarian = Bulgarian()
        astronomer: Astronomer = Astronomer()
        holidays_manager: HolidaysManager = HolidaysManager()
        allergy_uv_advisor: AllergyAndUVAdvisor = AllergyAndUVAdvisor()
        spaceweather_advisor: SpaceWeatherAdvisor = SpaceWeatherAdvisor()
        electrostatic_advisor: ElectrostaticAdvisor = ElectrostaticAdvisor()
        disaster_advisor: DisasterAdvisor = DisasterAdvisor()

        # Ok, let's be a bit more nicer
        additional_fact_country: str = ""
        if self.config.country != "Bulgaria":
            additional_fact_country = self.config.country

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:

            # Send the requests
            # -----------------
            future_weather = executor.submit(
                self._get_main_location_weather_data, 
                self.config.lat, self.config.lon, self.config.timezone, tunit, wunit
            )
            future_aq = executor.submit(
                self._get_aqi_data, 
                self.config.lat, self.config.lon
            )
            future_followcities = executor.submit(
                self._get_brief_weather_data,
                ",".join([e["lat"] for e in self.config.followcities]),
                ",".join([e["lon"] for e in self.config.followcities]),
                ",".join([e["timezone"] for e in self.config.followcities]),
                tunit
            )
            future_motivation = executor.submit(Motivator.get_motivation)
            future_fact = executor.submit(
                bulgarian.get_history_fact,
                additional_fact_country
            )
            future_sun_times = executor.submit(
                astronomer.get_sun_times, 
                self.config.lat, self.config.lon, self.config.timezone
            )
            future_holidays = executor.submit(
                holidays_manager.update, 
                self.config.holidays, self.config.country_code2
            )
            future_allergies_uv = executor.submit(
                allergy_uv_advisor.advise, 
                self.config.lat, self.config.lon
            )
            future_electrostatic_xray_flux = executor.submit(electrostatic_advisor.get_xray_flux)
            future_disasters = executor.submit(
                disaster_advisor.get_disasters,
                self.config.countries_of_interest
            )
            future_wildfires = executor.submit(
                disaster_advisor.get_detailed_fires,
                self.config.lat, self.config.lon
            )
            future_quakes = executor.submit(
                disaster_advisor.get_detailed_quakes,
                self.config.lat, self.config.lon
            )
            future_fireballs = executor.submit(disaster_advisor.get_fireballs)
            future_geomagnetic_scales = executor.submit(spaceweather_advisor.get_geomagnetic_scales)
            future_kp_index = executor.submit(spaceweather_advisor.get_kp_index)

            # Get the responses
            # -----------------
            weather_result: dict = future_weather.result()
            aq_result: dict = future_aq.result()
            followcities_result: dict | list = future_followcities.result()
            fireballs: list[list[str]] = future_fireballs.result()
            quakes: list[list[str]] = future_quakes.result()
            wildfires: list[list[str]] = future_wildfires.result()
            geomagnetic_scales: dict[str, any] = future_geomagnetic_scales.result()
            kp_index: float = future_kp_index.result()
            spaceweather_warnings: list[list[str]] = spaceweather_advisor.get_warnings(kp_index, geomagnetic_scales)
            motivation: list[str] = future_motivation.result()
            disasters: list[list[str]] = future_disasters.result()
            electrostatic_xray_flux: str = future_electrostatic_xray_flux.result()
            electrostatic_warning: str = electrostatic_advisor.get_electrostatic_warning(electrostatic_xray_flux)
            allergy_uv_warnings: list[str] = future_allergies_uv.result()
            
            new_holidays: dict[str, str] = future_holidays.result()
            if self.config.holidays != new_holidays:
                self.config.holidays = new_holidays
                self.config.save()

            history_fact: str = future_fact.result()

            celestial: dict[str, any] = {
                "sun": future_sun_times.result(),  # dict[str, str]
                "zodiac": astronomer.get_zodiac_sign(),  # str
                "chinese": astronomer.get_chinese_zodiac(),  # str
                "moon": astronomer.get_moon_phase()  # str
            }

            if history_fact == "":  # More motivation. Because why not?
                history_fact = f"'{motivation[0]}' //{motivation[1]}"
            fact_paragraph: TextParagraph = TextParagraph(history_fact)

            history_fact: dict[str, date | TextParagraph] = {
                "date": date.today(),
                "text": fact_paragraph,
            }


            # Apply data
            # ----------

            # Extract Data
            current: dict[str] = weather_result["current"]
            daily: dict[str] = weather_result["daily"]
            aqi: str = aq_result["current"]["us_aqi"]

            # Fill the object with data
            # weather_data.is_day = True if current["is_day"] == "1" else False
            weather_data.sky = self.__get_weather_description(current["weather_code"])
            weather_data.temperature = round(float(current["temperature_2m"]))
            weather_data.min = round(float(daily["temperature_2m_min"][0]))
            weather_data.max = round(float(daily["temperature_2m_max"][0]))
            weather_data.hmin = round(float(daily["relative_humidity_2m_min"][0]))
            weather_data.hmax = round(float(daily["relative_humidity_2m_max"][0]))
            weather_data.hcur = round(float(current["relative_humidity_2m"]))
            weather_data.baropressure = round(float(current["pressure_msl"]))
            weather_data.aqi = int(aqi)
            weather_data.air_quality = self.__get_air_quality_assessment(aqi)
            weather_data.precipitation = daily["precipitation_probability_max"][0]
            weather_data.weather_code = current["weather_code"]
            weather_data.wind = int(current["wind_speed_10m"])
            weather_data.wind_direction = self.__get_wind_direction(
                current["wind_direction_10m"]
            )

            weather_data.week = []
            
            # followcities_result[i]["current"]["temperature_2m"]
            # followcities_result[i]["current"]["is_day"]
            weather_data.cities_data = []
            if isinstance(followcities_result, dict):
                city_data: dict = {
                    "temperature": round(float(followcities_result["current"]["temperature_2m"])),
                    "is_day": followcities_result["current"]["is_day"],
                    "city": self.config.followcities[-1]["city"],
                    "country_code2": self.config.followcities[-1]["country_code2"],
                    "province": self.config.followcities[-1]["province"],
                }
                weather_data.cities_data = [city_data]
            if isinstance(followcities_result, list):
                # followcities_result = followcities_result
                for combodata in zip(self.config.followcities, followcities_result):
                    city_data: dict = {
                        "temperature": round(float(combodata[1]["current"]["temperature_2m"])),
                        "is_day": combodata[1]["current"]["is_day"],
                        "city": combodata[0]["city"],
                        "country_code2": combodata[0]["country_code2"],
                        "province": combodata[0]["province"],
                    }
                    weather_data.cities_data.append(city_data)

            # 7 day forecast
            for i in range(1, 8):
                day = BriefDailyForecast()
                day.min = round(float(daily["temperature_2m_min"][i]))
                day.max = round(float(daily["temperature_2m_max"][i]))
                day.precip = round(float(daily["precipitation_probability_max"][i]))
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
            weather_data.humidity = self.__get_humidity_assessment(
                weather_data.hcur, weather_data.temperature
            )
            weather_data.wind_direction_long = self.__get_wind_direction_long(
                weather_data.wind_direction
            )
            weather_data.is_day = self.__is_daytime(self.config.lat, self.config.lon)

            # Misc
            # ----
            # weather_data.misc_data["motivation"] = motivation
            weather_data.misc_data["histfact"] = history_fact
            weather_data.misc_data["celestial"] = celestial

            humidity_risk: str = self.get_humidity_risk(weather_data.hcur)
            storm_warning: str = self.get_storm_warning(weather_data.weather_code, weather_data.wind)
            baropressure_warning: str = self.get_baropressure_warning(weather_data.baropressure)

            # WARNINGS
            # --------
            if humidity_risk:
                warnings.append("home", "", "HUMIDITY", humidity_risk)
            if storm_warning:
                warnings.append("home", "", "STORM", storm_warning)
            if baropressure_warning:
                warnings.append("home", "", "BAROPRESSURE", baropressure_warning)
            for fireball in fireballs:
                warnings.append(*fireball)
            for quake in quakes:
                warnings.append(*quake)
            for wildfire in wildfires:
                warnings.append(*wildfire)
            for space_warning in spaceweather_warnings:
                warnings.append(*space_warning)
            for disaster in disasters:
                warnings.append(*disaster)
            if electrostatic_warning:
                warnings.append("home", "", "ELECTROSTATIC", electrostatic_warning)
            for message in allergy_uv_warnings:
                warnings.append("home", "", "ALLERGY", message)

            cache.save()


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
    
    def get_time_for_timezone(self, timezone_str: str) -> str:
        try:
            target_zone: ZoneInfo = ZoneInfo(timezone_str)
            city_time: datetime = datetime.now(target_zone)
            fmt: str = "%H:%M" if self.time24 else "%I:%M%p"
            return city_time.strftime(fmt)
        except ZoneInfoNotFoundError:
            return "00:00"

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
        now: datetime = datetime.now(ZoneInfo(self.timezone))
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
        self.warnings: WarningsManager = WarningsManager()
        self.presconf: PresentationConfiguration = present_config
        self.weather_refresh_interval: int = REFRESH_INTERVAL
        self.height: int | None = None
        self.width: int | None = None

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

    def test_terminal_resized(self, stdscr: curses.window, min_height: int, min_width: int) -> bool:
        """Test if terminal was resized. Also if terminal is the minimum size required."""
        
        height, width = stdscr.getmaxyx()
        if height < min_height or width < min_width:
            raise Exception(
                f"Current terminal size ({width}x{height}) is smaller than the required minimum terminal size ({min_width}x{min_height}) for this view. You might try another view. Run with --help"
            )
        if (width, height) != (self.width, self.height):
            self.width = width
            self.height = height
            return True
        
        return False

    def screen(self, stdscr: curses.window) -> None:
        r"""The actual TUI screen to display"""
        pass

    def display(self) -> None:
        r"""Wrapper for screen(), unless simple printing"""
        pass

    def update_screen(self) -> None:
        r"""Pushes all screen updates at once, if applicable"""
        pass


class ColorViews(Views):
    r"""Definition of color views"""

    def _get_warnings_cp(self, homeremote: str, label: str, message: str) -> int | str:
        r"""Gets the color pair for warning messages"""

        # Idea is to trigger different color on "home" and "remote"
        # the rest are just meh
        if homeremote.lower() not in ["home", "remote", "emergency", "disaster", "", "***", "meh"]:
            raise ValueError(f"Invalid value '{homeremote}' for homeremote.")
        
        homeremotes: dict[str, int | str] = {
            "home": COL_WHITEBLACK,
            "remote": "general",
            "emergency": COL_YELOWRED,
            "disaster": COL_YELOWRED,
        }
        labels: dict[str, int | str] = {
            "fire": COL_YELOWRED,
            "wildfire": COL_YELOWRED,
            "flood": COL_CYANBLACK,
            "tsunami": COL_CYANBLACK,
            "earthquake": COL_WHITEBLACK,
            "radioblackout": "general",
            "emergency": COL_YELOWRED,
            "disaster": COL_YELOWRED,
            "humidity": "general",
            "amber": COL_YELOWRED,
            "allergy": "general",
            "uv": COL_YELOWBLACK,
            "xray": COL_WHITEBLACK,
            "geomagnetic": "general",
            "electrostatic": "general",
            "solarradiation": "general",
            "fireball": "general",
            "space": "general",
            "air": COL_YELOWBLACK,
            "baropressure": COL_WHITEBLACK,
            "storm": COL_YELOWRED,
            "volcano": COL_YELOWRED,
            "drought": COL_WHITEBLACK,
        }

        # List of labels which does not apply for the majority of population
        generics: list[str] = ["remote", "humidity", "allergy", "geomagnetic", "electrostatic", "space", "radioblackout", "solarradiation", "fireball"]

        # Severities
        if homeremote.lower() == "home" and "extreme risk" in message.lower():
            return COL_YELOWRED
        if homeremote.lower() == "home" and label.lower() in generics and "high risk" in message.lower():
            return COL_WHITEBLACK

        # if homeremote.lower() in ["home", "disaster"] and label.lower() in labels:
        if homeremote.lower() == "home" and label.lower() in labels:
            return labels[label.lower()]

        if homeremote.lower() in homeremotes:
            return homeremotes[homeremote.lower()]
        
        return COL_BLUEBLACK

    def _get_humidity_cp(self, humidity: int, temperature: int) -> int:
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
            "Drizzle": COL_CYANBLACK,
            "Rain": COL_CYANBLACK,
            "Snow": COL_WHITEBLACK,
            "Rain Showers": COL_CYANBLACK,
            "Thunderstorm": COL_REDBLACK,
        }
        if sky not in d:
            raise ValueError(f"Invalid sky value '{sky}'.")
        return d[sky]
    
    def _get_precipitation_type_cp(self, precip_type: str) -> str:
        r"""Get the appropriate precipitation type color pair"""

        d: dict[str, int] = {
            "Rain": COL_CYANBLACK,
            "Snow": COL_WHITEBLACK,
            "Storm": COL_YELOWRED
        }
        if precip_type in d:
            return d[precip_type]

        return None  # COL_WHITEBLACK

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
            raise ValueError(f"Invalid AQI value '{aqistr}'.")
        return d[aqistr]

    def _get_progbar_cp(self, p: int) -> int:
        if p < 40:
            return COL_BLUEBLACK
        return COL_CYANBLACK
    
    def update_screen(self) -> None:
        r"""Pushes all changes to screen at once"""
        curses.doupdate()
    
    def test_exit_conditions(self, input: int) -> bool:
        if input == ord("q"):
            return True

        # The terminal window was closed; exit immediately
        if not os.isatty(sys.stdin.fileno()):
            # sys.exit(0)
            raise Exception("Not a TTY.")

        if not hasattr(self, "consecutive_errors"):
            self.consecutive_errors: int = 0
            self.last_error_time: float = time.time()

        if input == curses.ERR:
            current_time: float = time.time()
            elapsed: float = current_time - self.last_error_time
            self.consecutive_errors += 1
            
            # If we got 20 errors in less than 1 second, it's a 100% CPU ghost loop
            if self.consecutive_errors > 20 and elapsed < 1.0:
                raise Exception(f"Ghost loop detected: 20 errors in {elapsed:.2f}s")
            
            # If it's been more than a second, it's likely just a timeout, 
            # so we reset the timer and counter to start fresh.
            if elapsed >= 1.0:
                self.consecutive_errors = 0
                self.last_error_time = current_time
                
            return False
        else:
            self.consecutive_errors = 0
            return False


class SetupView(Views):
    r"""Prints the setup"""

    def display(self) -> None:
        # Data to display
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country
        followed_cities: list[dict[str | int]] = self.config.followcities

        print(f"""==================================================[ SETUP ]
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

        print("")


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
        baropressure: float = self.data.baropressure
        hcur: int = self.data.hcur
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
        humidity: str = self.data.humidity
        wind_direction_long: str = self.data.wind_direction_long
        # ---
        # warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week
        follow_cities: list = self.data.cities_data

        day: str = "day" if is_day else "night"

        hr: str = "==============================="

        print(f"""
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

        # for warning in warnings:
        #     print(f"\n{warning}")

        # print("\nTry: tuiweathergirl --help")
        print("\n")

        # Saving the cache
        cache = CacheManager()
        cache.register("weather_data", self.data)
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
        hcur: int = self.data.hcur
        baropressure: float = self.data.baropressure
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
        humidity: str = self.data.humidity
        wind_direction_long: str = self.data.wind_direction_long
        # ---
        # warnings: list[str] = self.data.warnings
        week: list[BriefDailyForecast] = self.data.week
        follow_cities: list = self.data.cities_data

        day: str = "day" if is_day else "night"

        motivation: str = Motivator.get_motivation()
        mind_drift: str = MindDrifter.drift()

        hr: str = "============================"
        hr2: str = "~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
        hr3: str = "~~,~~`~~,~~`~~,~~`~~,~~`~~,~~"

        print(f"""
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

        # for warning in warnings:
        #     print(f"\n{warning}")

        # print("\nTry: tuiweathergirl --help")
        print("\n")

        # Saving the cache
        cache = CacheManager()
        cache.register("weather_data", self.data)
        cache.save()


class DashboardView(ColorViews):
    """A dashboard color view"""

    def init_screen(self, stdscr: curses.window) -> None:
        # Global settings
        stdscr.erase()
        # stdscr.nodelay(True)
        curses.curs_set(False)  # Hide cursor
        stdscr.timeout(1000)  # Wait 1 second
    
    def screen(self, stdscr: curses.window) -> None:  # DEBUG: 
        theme_palette: ThemePalette = ThemePalette()
        theme_palette.init_colors()
        theme: Theme = theme_palette.get_theme(self.config.theme)
        self.init_screen(stdscr)

        view_required_lines: int = 38
        view_required_columns: int = 146
        
        # Initial test for the size and to save the initial width and height
        self.test_terminal_resized(stdscr, view_required_lines, view_required_columns)

        self.forecaster: WeatherForecaster = WeatherForecaster(self.config)
        last_refresh: str = ""
        
        # Global layout settings for this view
        first_two_windows_width: int = 38
        minimum_window_height: int = 1
        general_window_height: int = 4
        warnings_window_height: int = 10
        main_layout_columns_height: int = 6
        title_window_height: int = 3
        forecast_window_height: int = 6
        followcities_window_height: int = 12
        history_window_height: int = 2
        default_text_indent: int = 1
        labels_x: int = default_text_indent
        data_x: int = labels_x + 8

        # Data which won't change
        city: str = self.config.city
        province: str = self.presconf.province
        country: str = self.config.country

        province1: str = province
        if province1.isdigit():
            province1 = ""
        elif len(province1) > 0:
            province1 = f", {province1}"
        
        self.warnings.home_location = f"{city}-{self.config.country_code2}"

        layout_manager: LayoutManager | None = None

        title_window: Window | None = None
        location_window: Window | None = None
        currently_window: Window | None = None
        airquality_window: Window | None = None
        forecast_window: Window | None = None
        warnings_window: Window | None = None
        brief_window: Window | None = None
        lastrefresh_window: Window | None = None

        force_screen_update: bool = False

        # -------------------------------------------------- VIEW MAIN LOOP
        start_time: datetime = datetime.now()
        while True:
            # User input
            keypressed: int = stdscr.getch()

            # Exit view and application
            if self.test_exit_conditions(keypressed):
                break

            # ------------------------------------------------- DEFINE LAYOUT
            # Application just started or Terminal was resized
            # keypressed == curses.KEY_RESIZE
            if not layout_manager or self.test_terminal_resized(stdscr, view_required_lines, view_required_columns):
                layout_manager = LayoutManager(
                    stdscr=stdscr,
                    theme=theme
                )
                # layout_manager.set_three_columns()
                layout_manager.add_column(first_two_windows_width)
                layout_manager.add_column(first_two_windows_width)
                # This one will assume the remaining width
                layout_manager.add_column()

                title_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="About",
                    height=title_window_height,
                    border=True,
                )
                location_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Location",
                    height=minimum_window_height
                )
                currently_window = layout_manager.add_window(
                    column_num=0,
                    title="Currently",
                    height=main_layout_columns_height,
                    border=True,
                )
                airquality_window = layout_manager.add_window(
                    column_num=1,
                    title="Air & Conditions",
                    height=main_layout_columns_height,
                    border=True,
                )
                forecast_window = layout_manager.add_window(
                    column_num=0,
                    overlap=1,
                    title="7 Day Forecast",
                    height=forecast_window_height,
                    border=True,
                )
                followcities_window = layout_manager.add_window(
                    column_num=2,
                    title="Followed cities",
                    height=followcities_window_height,
                    border=True,
                )
                warnings_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Warnings",
                    height=warnings_window_height,
                    border=True,
                )
                history_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="On This Day",
                    height=general_window_height,  # history_window_height,
                    border=True
                )
                celestial_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Celestial",
                    height=3,
                    border=True
                )
                misc_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Misc",
                    height=3,
                    border=True
                )
                brief_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Brief",
                    height=minimum_window_height
                )
                lastrefresh_window = layout_manager.add_window(
                    column_num=0,
                    overlap=2,
                    title="Last Refresh",
                    height=minimum_window_height
                )

                layout_manager.draw_windows()

                # Screen labels
                # About
                title_window.print(f" TUIWEATHERGIRL {APPVERSION}")
                title_window.print("Evgueni Antonov (StrayF) 2026", align="right")
                # Home location
                # location_window.print(f" Home: {city}, {province}{country}", theme="home")
                location_window.print(f" Home: {city}{province1}, {country}", theme="home")
                # Current situation labels
                currently_window.print("Sky   :", x=labels_x, y=0)
                currently_window.print("Temp  :", x=labels_x, y=1)
                currently_window.print("Range :", x=labels_x, y=2)
                currently_window.print("Humidt:", x=labels_x, y=3)
                # Wind, air quality and precipitation labels
                airquality_window.print("Wind  :", x=labels_x, y=0)
                airquality_window.print("Air Q :", x=labels_x, y=1)
                airquality_window.print(self.data.precipitation_type, x=labels_x, y=2, theme=self._get_precipitation_type_cp(self.data.precipitation_type))
                airquality_window.print(":", x=labels_x+6, y=2, theme="general")
                airquality_window.print("Humidt:", x=labels_x, y=3)
                # 7 day forecast labels
                forecast_window.draw_line(x=first_two_windows_width-2, y=0, direction="vertical", length=4, theme="border")
                # Misc
                brief_window.print(f"Auto-refresh: {self.weather_refresh_interval // 60}min                    [q] Quit", x=1)

                # Get initial additional data
                # self.get_data()
                
                force_screen_update = True
            

            current_time: datetime = datetime.now()
            elapsed: timedelta = current_time - start_time
            
            # Data update
            if elapsed >= timedelta(minutes=self.weather_refresh_interval // 60):
                self.forecaster.get_data(self.data)
                last_refresh = f"Last refresh: {datenow} {timenow}       "
                lastrefresh_window.print(last_refresh, x=1, y=0)
                force_screen_update = True

            # ------------------------------------------------- REFRESH DATA
            # Data to display
            timenow: str = self.presconf.update_time()
            datenow: str = self.presconf.date
            dow: str = self.presconf.dow
            season: str = self.presconf.season
            dstmark: str = "*" if self.config.dst else ""

            if len(last_refresh) == 0:
                # last_refresh = f"Last refresh: {datenow} {timenow}"
                last_refresh = f"Last refresh: **none**"
                lastrefresh_window.print(last_refresh, x=1, y=0)

            # Technically we do not need this, but filling up the addstr()s
            # later would be more messy without it
            sky: str = self.data.sky
            temperature: int = self.data.temperature
            tmin: int = self.data.min
            tmax: int = self.data.max
            hmin: int = self.data.hmin
            hmax: int = self.data.hmax
            hcur: int = self.data.hcur
            baropressure: float = self.data.baropressure
            tsuffix: str = self.presconf.tsuffix
            wunit: str = self.presconf.wunit
            wind: int = self.data.wind
            winddir: str = self.data.wind_direction
            aqi: int = self.data.aqi
            airquality: str = self.data.air_quality
            precipitation: int = self.data.precipitation
            is_day: bool = self.data.is_day
            wind_type: str = self.data.wind_type
            # precipitation_type: str = self.data.precipitation_type
            humidity_level_min: str = self.data.humidity_level_min
            humidity_level_max: str = self.data.humidity_level_max
            humidity: str = self.data.humidity
            wind_direction_long: str = self.data.wind_direction_long
            # ---
            warnings: list[str] = self.data.warnings
            week: list[BriefDailyForecast] = self.data.week
            follow_cities: list = self.data.cities_data

            # Saving the cache
            cache = CacheManager()
            cache.register("weather_data", self.data)
            cache.save()

            home_day: str = "night"
            if is_day:
                home_day = "day"

            # ----------------------------------------- Screen update
            # Today's date and time - we need this to refresh more often
            location_window.print(f"Today: {datenow} {timenow}{dstmark}", x=-len(home_day)-3, align="right", theme="home")
            location_window.print(f"({home_day})", align="right", theme=self._get_daynight_cp(is_day))

            # The followed cities
            for city_cnt, city_data in enumerate(follow_cities):
                city_wx: int = 56
                citytimezone: str = self.config.followcities[city_cnt]["timezone"]
                city_time: str = self.presconf.get_time_for_timezone(citytimezone)
                followcities_window.print(city_time, x=city_wx, y=city_cnt)

            if force_screen_update:
                # Current sky, temperature and temperature range
                currently_window.print(sky, x=data_x, y=0, theme=self._get_sky_cp(sky))
                currently_window.print(f"{temperature}°{tsuffix}", x=data_x, y=1, theme=self._get_temp_cp(temperature))
                currently_window.print(f"{tmin}°{tsuffix}", x=data_x, y=2, theme=self._get_temp_cp(tmin))
                currently_window.print("/", x=data_x+4, y=2)
                currently_window.print(f"{tmax}°{tsuffix}", x=data_x+5, y=2, theme=self._get_temp_cp(tmax))
                currently_window.print(f"{self.data.hcur}% ({humidity})", x=data_x, y=3, theme=self._get_humidity_cp(int(self.data.hcur), int(temperature)))
                # Wind, air quality and precipitation
                airquality_window.print(f"{wind_type}, {winddir} {wind}{wunit}", x=data_x, y=0, theme=self._get_wind_cp(wind, wunit))
                airquality_window.print(self.data.precipitation_type, x=labels_x, y=2, theme=self._get_precipitation_type_cp(self.data.precipitation_type))
                airquality_window.print(":", x=labels_x+6, y=2, theme="general")
                airquality_window.print(f"{airquality} ({aqi})", x=data_x, y=1, theme=self._get_aqistr_cp(airquality))
                airquality_window.print("[", x=data_x, y=2, theme="border")
                airquality_window.print(self.prog_bar(precipitation), x=data_x+1, y=2, theme=self._get_progbar_cp(precipitation))
                airquality_window.print("]", x=data_x+10, y=2, theme="border")
                airquality_window.print(f"{precipitation}%  ", x=data_x+12, y=2, theme=self._get_progbar_cp(precipitation))
                humidity_str: str = f"{self.data.hmin}%({humidity_level_min:.7})"
                airquality_window.print(humidity_str, x=data_x, y=3, theme=self._get_humidity_cp(int(self.data.hmin), int(temperature)))
                airquality_window.print("/", x=data_x+len(humidity_str), y=3)
                airquality_window.print(f"{self.data.hmax}%({humidity_level_max:.7})", x=data_x+len(humidity_str)+1, y=3, theme=self._get_humidity_cp(int(self.data.hmax), int(temperature)))

                # 7 day forecast
                for day_cnt, day in enumerate(week):
                    wy: int = day_cnt % 4
                    wx: int = 1 if day_cnt < 4 else first_two_windows_width + 1
                    data_x2: int = wx + 5
                    precip_x: int = data_x2 + 10

                    dmin: int = day.min
                    dmax: int = day.max
                    dprecip: int = day.precip
                    dow: str = day.dow

                    forecast_window.print(f"{dow}:", x=wx, y=wy)
                    forecast_window.print(f"{dmin}°{tsuffix}", x=data_x2, y=wy, theme=self._get_temp_cp(dmin))
                    forecast_window.print("/", x=data_x2+4, y=wy)
                    forecast_window.print(f"{dmax}°{tsuffix}", x=data_x2+5, y=wy, theme=self._get_temp_cp(dmax))

                    forecast_window.print("[", x=precip_x, y=wy, theme="border")
                    forecast_window.print(self.prog_bar(dprecip), x=precip_x+1, y=wy, theme=self._get_progbar_cp(dprecip))
                    forecast_window.print("]", x=precip_x+10, y=wy, theme="border")
                    forecast_window.print(f"{dprecip}%  ", x=precip_x+12, y=wy, theme=self._get_progbar_cp(dprecip))
                
                # The followed cities
                for city_cnt, city_data in enumerate(follow_cities):
                    wy: int = city_cnt  # % 9
                    wx: int = 1  # if city_cnt < 9 else 15
                    data_x1: int = wx + 42
                    data_x2: int = data_x1 + 5

                    day: str = "night"
                    if city_data["is_day"]:
                        day = "day"
                    temp: int = city_data["temperature"]
                    city2: str = self.config.followcities[city_cnt]["city"]
                    province2: str = self.config.followcities[city_cnt]["province"]
                    country2: str = self.config.followcities[city_cnt]["country"]

                    if province2.isdigit():
                        province2 = ""
                    elif len(province2) > 0:
                        province2 = f", {province2}"

                    followcities_window.print(f"{city_cnt+1}. {city2}{province2}, {country2}", x=wx, y=wy)
                    followcities_window.print(f"{temp}°{tsuffix}", x=data_x1, y=wy, theme=self._get_temp_cp(temp))
                    followcities_window.print(f"({day})", x=data_x2, y=wy, theme=self._get_daynight_cp(city_data["is_day"]))

                # WARNINGS
                warnings_window.clear()
                warnings: list[list[str]] = self.warnings.get_warnings(warnings_window_height - 2)

                # Sure, the window is not 99 lines high.
                # Printing on a greater line will simply make it print on the
                # last line. I have a safeguard to make it happen.
                for warning in warnings:
                    warnings_window.print(self.warnings.apply_format(warning), x=0, newline=True, theme=self._get_warnings_cp(warning[2], warning[4], warning[-1]))
                
                if "histfact" in self.data.misc_data:
                    history_window.clear()
                    history_window.print(self.data.misc_data["histfact"]["text"], align="center", y=0, maxlines=3)

                if "celestial" in self.data.misc_data:
                    celestial_window.clear()
                    spc: str = f"{" " * 7}|{" " * 7}"  # Spacer
                    s: str = f"Sunrise: {self.data.misc_data["celestial"]["sun"]["sunrise"]}{spc}Sunset: {self.data.misc_data["celestial"]["sun"]["sunset"]}{spc}Zodiac: {self.data.misc_data["celestial"]["zodiac"]}{spc}Chinese: {self.data.misc_data["celestial"]["chinese"]}{spc}Moon: {self.data.misc_data["celestial"]["moon"]}"
                    celestial_window.print(s, align="center", y=0)
            
                now: datetime = datetime.now()
                date_str: str = now.strftime("%Y-%m-%d")
                if date_str in self.config.holidays:
                    holiday: str = self.config.holidays[date_str].split("#")[1]
                    
                    misc_window.clear()
                    misc_window.print(f"NATIONAL HOLIDAY: {holiday}", align="center", y=0)

                force_screen_update = False


            # Pushing the changes
            layout_manager.refresh_screen()
            self.update_screen()
            # time.sleep(1)  # Prevent 100% CPU usage

            

    
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
            "dashboard": DashboardView(config, data, present_config),
        }

    def present(self, view: str = "") -> None:
        if len(view) > 0 and view not in self.views:
            raise ValueError(f"View not defined '{view}'. Run with --help for help.")
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
            choices=["setup", "basic", "motivate", "dashboard"],
            default="",
            help="Select the view",
        )
        cli_parser.add_argument(
            "--theme",
            choices=["main"],
            default="",
            help="Select the application color scheme",
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
            raise ValueError(
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
            raise ValueError(
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
        # logging.basicConfig(filename='/tmp/tuiweathergirl.log', level=logging.INFO)

        InstanceGuard.ensure_single_instance()
        parser: ParseCommandline = ParseCommandline()
        cli_arguments: dict[str, str | int | bool] = parser.parse()

        DEBUG_MODE = cli_arguments["debug"]

        view_name: str = cli_arguments.get("view")

        if bool(cli_arguments.get("newcity")) ^ bool(cli_arguments.get("country")):
            raise ValueError("City and country must be provided together.")

        # No point to run everything if this is not set
        timezone_apikey: str = os.getenv(TIMEZONE_APIKEY_ENV_VARNAME)
        if not timezone_apikey:
            raise Exception(
                f"Environment variable {TIMEZONE_APIKEY_ENV_VARNAME} is not set. Run the app with --help"
            )
        
        nasafirms_apikey: str = os.getenv(NASAFIRMS_APIKEY_ENV_VARNAME)
        if not nasafirms_apikey:
            print(f"WARNING: Environment variable {NASAFIRMS_APIKEY_ENV_VARNAME} is not set. You will not be able to get fires disasters information. Run the app with --help")
        
        print("\nPlease wait while loading... (might take a while)\n")

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
            view_name = "setup"
            location_manager.add_city(
                cli_arguments["newcity"], cli_arguments["country"], config
            )
            cache = CacheManager()
            cache.delete()
        if cli_arguments.get("removecity"):
            view_name = "setup"
            location_manager.remove_city(cli_arguments["removecity"], config)
            cache = CacheManager()
            cache.delete()
        if cli_arguments.get("homecity"):
            view_name = "setup"
            location_manager.set_home(cli_arguments["homecity"], config)
            cache = CacheManager()
            cache.delete()

        forecaster: WeatherForecaster = WeatherForecaster(config)
        weather_data: WeatherData = WeatherData()
        forecaster.get_data(weather_data)

        weather_girl: WeatherGirl = WeatherGirl(config, weather_data)
        weather_girl.present(view_name)

        print(f"TUIWEATHERGIRL {APPVERSION} -Your daily terminal weathergirl- by Evgueni Antonov (StrayF) 2026.")
        print("For help: tuiweathergirl --help")
        print("Cast Spells!")

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
