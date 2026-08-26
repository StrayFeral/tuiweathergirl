# TUIWEATHERGIRL: Weather and Disaster Station

![Screenshot](screenshots/thumbnail.gif)

## CONTENTS

- [Download](#download)
- [Description](#description)
- [What's new (Changelog)](#whats-new-changelog)
- [Tested on](#tested-on)
- [Features](#features)
- [Dependencies](#dependencies)
- [Installation prerequisites](#installation-prerequisites)
- [Installing on Linux/Unix](#installing-on-linuxunix)
- [Installing on Windows10](#installing-on-windows10)
- [Installing on MacOS](#installing-on-macos)
- [Updating](#updating)
- [Usage](#usage)
- [Changing the setup](#changing-the-setup)
- [Troubleshooting](#troubleshooting)
- [VIDEO TUTORIALS - installation, in-depth app overview](#video-tutorials-installation-in-depth-app-overview)
- [Screenshots](#screenshots)

## DOWNLOAD

> [!TIP]
> LINUX: **Download the LINUX installer** (no need to download anything else)  
> 📥 RIGHT-CLICK and "SAVE AS" to Download: [linux_install.sh](https://raw.githubusercontent.com/StrayFeral/tuiweathergirl/main/linux_install.sh)

> [!TIP]
> ANY operating system: **Download the Latest Release**  
> 📥 Download: [tuiweathergirl.zip](https://github.com/StrayFeral/tuiweathergirl/releases/latest/download/tuiweathergirl.zip)

## DESCRIPTION

Personal weather and disaster terminal application for everyday use.

This application was designed with maximum inclusivity for individuals with health sensitivities, including photosensitivity (sun allergies), respiratory conditions (such as asthma), geomagnetic sensitivities etc. Its goal is to assist users by providing warnings for dangerous or risky weather conditions.

It features alerts for regional disasters, space weather, and various other public safety events.

Built to run on everything from basic legacy terminals to modern terminal emulators, the application prioritizes performance by optimizing API calls and preventing rate-limit issues, resulting in a low-overhead experience.

The application has minimal dependencies and is designed with a strong focus on portability.

> [!NOTE]
> Not vibe-coded.

> [!TIP]
> This application was created to become part of my [**DEWLINUX** Project (Debian Terminal-Only Remix)](https://github.com/StrayFeral/dewlinux). You might want to check it out.

> [!NOTE]
> There was a minimal use of AI during the development of this app, mainly for the interpretation of the data for the different medical conditions.

## WHAT'S NEW (CHANGELOG)

- 2026-08-25: New video tutorials for Windows10 and Linux has been created and uploaded to Youtube. Readme is updated with the new URLs.
- 2026-08-25 v.1.2.17: Fixed: Crasher bug when a random Earth point is set as home location. Crasher in the auto-update.
- 2026-08-24 v.1.2.16: Fixed: Crasher URL issue.
- 2026-08-24 v.1.2.15: Basic view extended to show all warnings and a bit more info. Help reformatted. Small terminal exception message wording changed.
- 2026-08-23 v.1.2.14: Fixed: Windows10 installation issues. Terminal no longer force-maximized. Added recent Win10 screenshot. Added directories for screenshots of known bugs.
- 2026-08-22 v.1.2.13: Application update is now fully working.
- 2026-08-22 v.1.2.6: Fixed: Bugs with the application updates.
- 2026-08-21 v.1.2.0: Implemented application auto-update and force-update.
- 2026-08-21 v.1.1.6: Abbreviation "ppl." expanded back to "people.".
- 2026-08-20 v.1.1.5: Fixed duplicate wildfire warnings.
- 2026-08-20 v.1.1.4: Electrostatic warning texts shortened to better fit the screen.
- 2026-08-17 v.1.1.3: Fixed: Sky condition overlap in cities of interest.
- 2026-08-17 v.1.1.2: Fixed: Abbreviation in cities of interest sky condition.
- 2026-08-16 v.1.1.1: Fixed: Too long city/province names for cities of interest. Bug in holidays update.
- 2026-08-16 v.1.1.0: Code refactored. Fixed: Bug in right-aligned text. Bug in TTYDashboard view. Bug in NASA Fireballs query. Optimized the 
- 2026-08-13 v.1.0.13: Fixed: Temperature assessments now takes Fahrenheit into account too. Now Polar Stations could be followed too.
- 2026-08-13 v.1.0.12: Fixed small bug in showing the current home time. Shortened the names of cities, countries and provinces.
- 2026-08-08 v.1.0.11: Fixed bug: Now application could be closed with capital "Q" too.
- 2026-08-08 v.1.0.10: Maximum cities of interest increased to 10. One error message changed.
- 2026-08-08 v.1.0.9: Makefile now supports all major linux distros.
- 2026-08-07 v.1.0.8: Terminal close and Ctrl-C now intercepted. Fixed minor bugs. Makefile fixed.
- 2026-08-03 v.1.0.6: More defensive parsing of the NASA FIRMS response.
- 2026-08-03 v.1.0.5: Now the "setup" view is not saved in the config, so your actual default view is preserved.
- 2026-08-03 v.1.0.4: Fixed how the exception stacktrace is being printed.
- 2026-08-03 v.1.0.3: Exception stacktrace is now always logged in the log file, so in case of found bug, just paste me the log.

## TESTED ON

1. Lubuntu 24.04.4 LTS x86_64 linux, 256 color terminal
2. Windows 10
3. Debian 13.3.0, 8 color terminal

> [!WARNING]
> The application was never tested on MacOS. I am providing installation instructions, but please do let me know if you had any installation issues and how you solved them. Thanks!

## FEATURES

> Features marked with an asterisk (*) are automatically converted to the appropriate format and units for the current location. Therefore supported temperature units are Celsius and Fahrenheit, as well as speed units will be displayed in MpH and KpH accordingly.

> Not all metrics are displayed on each view

- Display:
  - Location
  - Time and date*
  - Current sky condition
  - Current temperature*
  - Today's minimum and maximum temperatures*
  - Current wind speed and wind direction*
  - Current Air Quality Index (AQI)
  - Today's precipitation probability
  - 7 day weather forecast with minimum/maximum temperatures and precipitation probability
  - Dangerous weather condition warnings
  - Health hazard warnings
  - DST
  - Day/night
  - Wind type assessment
  - Precipitation type assessment
  - Up to 10 additional cities available to monitor for time and temperature
- Robustness:
  - Several cache methods to ease the API calls and prevent being banned
- Extensibility:
  - Different views, ranging from simple prints for super basic terminals to colorful views for modern terminals
  - Color themes
- Flexibility:
  - Application can handle scenario when user is behind VPN and still provide the relevant data for their home location
- Accessibility:
  - Convenient for people using screen-reading software
- Portability:
  - The application makes use of few external libraries, everything else used are core libraries
  - The application was written as a single file to simplify the portability
- Usability:
  - Extensive help screen with detailed description of the application

## DEPENDENCIES

1. Python 3
2. `python3-babel`
3. `python3-requests`
4. `libncurses6`
5. `tzdata`
6. `python3-packaging`

## INSTALLATION PREREQUISITES

In case of difficulties, please see [VIDEO TUTORIALS - installation, in-depth app overview](#video-tutorials-installation-in-depth-app-overview)

### MANDATORY COMPONENTS AND DATA

1. PYTHON3: Please get the latest: https://www.python.org/downloads/
2. TIMEZONEDB API KEY (*FREE*):

- Create an account on https://timezonedb.com/
- Get a *FREE* API key
- Create an environment variable called TIMEZONEAPIKEY and set the API key as a value. See the examples below.

> [!WARNING]
> The application will NOT WORK without this API key set in the environment.

> [!WARNING]
> FOR WINDOWS 10 DO NOT USE THE OLD CMD.EXE: USE "WINDOWS TERMINAL" INSTEAD! You can install it from the Microsoft Store. See my Windows 10 video below for details.

### OPTIONAL DATA

If you want detailed wildfire information provided, please consider getting a *FREE* API key from NASA FIRMS:
1. Go to https://firms.modaps.eosdis.nasa.gov/api/map_key and follow the steps to get the *FREE* API key
2. Create an environment variable called NASAFIRMSAPIKEY and set the API key as a value

### INSTALLING ON LINUX/UNIX

> [!TIP]
> **Download the Linux INSTALLER** (no need to download anything else)  
> 📥 RIGHT-CLICK TO Download: [linux_install.sh](https://raw.githubusercontent.com/StrayFeral/tuiweathergirl/main/linux_install.sh)

```bash
printf "export TIMEZONEAPIKEY=PUT_YOUR_API_KEY_HERE\n" >> ~/.profile
source ~/.profile
linux_install.sh
```

> [!CAUTION]
> DISCLAIMER: Since the application was tested on Debian and Lubuntu, my Makefile was created for a Debian or derivative distro. If you are a linux user on another distro (SUSE, Fedora etc), please inspect it and install the required packages manually with your provided distro package manager. I don't know what the package names would be on another distro, so would be grateful if you tell me what was your distro, the version and if you paste me the lines of how you installed it.

### INSTALLING ON WINDOWS10

> [!TIP]
> Any operating system: **Download the Latest Release**  
> 📥 Download: [tuiweathergirl.zip](https://github.com/StrayFeral/tuiweathergirl/releases/latest/download/tuiweathergirl.zip)

```batch
windows_install.bat
```

> [!TIP]
> After `windows_install.bat` finishes running, it will create an application shortcut, which you may copy around and use to run the app.

### INSTALLING ON MACOS

> [!TIP]
> Any operating system: **Download the Latest Release**  
> 📥 Download: [tuiweathergirl.zip](https://github.com/StrayFeral/tuiweathergirl/releases/latest/download/tuiweathergirl.zip)

> [!WARNING]
> Please keep in mind this app was never tested on MacOS. Please do let me know if you had any installation issues and how you solved them. Thanks!

If you already have `homebrew` installed:

```bash
brew install python ncurses && pip3 install requests babel
```

If not:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python ncurses
pip3 install requests babel
```

## UPDATING

Once installed, application will quietly auto-update each Wednesday by default (or if you didn't ran it more than 8 days), unless you turn the auto-update OFF with:

```bash
tuiweathergirl --autoupdateapp off
```

(later you could always turn it back ON, by simply running the same command with: --autoupdateapp on)

You could also manually force-update it by running:

```bash
tuiweathergirl --updateapp
```

## USAGE

> [!TIP]
> Please consult the help screen for the most up-to-date command-line options

```bash
tuiweathergirl --help
```

For a full list of the application files with full path, you can run:

```bash
tuiweathergirl --listfiles
```

After the very first run, the application would auto-configure itself and will create the configuration file. You are not required to modify it, as there are command-line options to do it, but you are free to do so if you wish.

If you mess it up and the application start throwing errors, just delete it and run the appliation again. It will create new configuration file, filled with the proper data.

If anything else got messed up, _before_ a new application run you might want to

```bash
tuiweathergirl --clearcache
```

But beware - this would gather fresh data from all APIs, so if you do this too often you may choke the APIs and may get banned.

> [!TIP]
> If you are behind VPN, still let the application detect your location, then add the city you're actually in manually with the `--addcity` option, then use the `--sethome` option to set which city is your actual home and optional you may then remove the fake city using `--removecity`.

> [!TIP]
> If your internet connection is slow for any reason, you may want to increase the API call request timeout, using `--requesttimeout`

### CHANGING THE SETUP

Some of the things could be changed command-line. For example if you run the app just with 

```bash
tuiweathergirl
```

It will run using the default view, default theme, default request timeout and other defaults. But the moment you run using either:

1. `--view`
2. `--theme`
3. `--requesttimeout`

Any of these parameters would also change the default choice saves in the application config file. This is why for these options you do not need to edit the config file manually. So for example, if you run

```bash
tuiweathergirl --view basic
```

The next time you run just `tuiweathergirl` it will assume that `basic` view is now your default view and will use it from now on, unless you run again with `--view` parameter to change the default view to something else. `--theme` and `--requesttimeout` work the same way - if you run the app with any of these set, they would change their defaults in the config file.

You may take a look what's in the config file under `[PREFERENCES]`, in case you want to change the metric/imperial system or temperature units or 24 to 12 hours time format. You may also want to change the language there, but beware - I never tested this. For now I prefer to keep all data in plain English format.

## TROUBLESHOOTING

### FOR ANY HELP - READ THE HELP

```bash
tuiweathergirl --help
```

### INSPECT THE LOGFILE

If anything goes wrong: Inspect the log file. Where is the log file? This command will tell you:

```bash
tuiweathergirl --listfiles
```

### TERMINAL IS NOT LARGE ENOUGH

Just resize your terminal, make it larger to fit the application view or just maximize it. Or maybe you want to try another view? The "basic" and the "motivate" views would work in absolutely any terminal.

### IN CASE OF INCORRECTLY DETECTED HOME LOCATION OR IF YOU'RE BEHIND A VPN

```bash
tuiweathergirl --addcity <YOURCITYNAME> --country <YOURCOUNTRYNAME>
tuiweathergirl --view setup
# Each added new city is recorded with some number and this will tell you 
# under what number the city was recorded. The very first added city is 1.
tuiweathergirl --sethome <CITYNUMBER>
tuiweathergirl --removecity <CITYNUMBER>
tuiweathergirl --clearcache  # Just in case
```

EXAMPLE:

Scenario: You just downloaded and installed TUIWEATHERGIRL. You run it for the very first time.

```bash
tuiweathergirl
```

You are behing a VPN and you realize your home location was incorrectly set to "Whitby, ON, Canada", while you live in New York, USA. Let's fix this:

```bash
# This is the very first added city, so it will be as number 1
tuiweathergirl --addcity "new york" --country usa
tuiweathergirl --sethome 1
tuiweathergirl --removecity 1
tuiweathergirl --clearcache
```

Next time you run the application you would notice your home location is now set to New York and the old location of Whitby has been deleted.

## VIDEO TUTORIALS (INSTALLATION, IN-DEPTH APP OVERVIEW)

[![Detailed overview, Linux installation and setup](https://img.youtube.com/vi/HMTAQ0rKRpM/0.jpg)](https://www.youtube.com/watch?v=HMTAQ0rKRpM)
[![Windows 10 installation, setup and overview](https://img.youtube.com/vi/kSYME9Z-FQs/0.jpg)](https://www.youtube.com/watch?v=kSYME9Z-FQs)

## SCREENSHOTS

Click to enlarge.

[![Dashboard View: Linux](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_view_1.1.5.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_view_1.1.5.jpg)
[![TTYDashboard View](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/ttydashboard_view.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/ttydashboard_view.jpg)
[![Basic View](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/basic_view.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/basic_view.jpg)
[![Motivate View](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/motivate_view.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/motivate_view.jpg)
[![Motivate View](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_view_win10.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_view_win10.jpg)
[![Motivate View](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_wildfire.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/screenshots/dashboard_wildfire.jpg)
