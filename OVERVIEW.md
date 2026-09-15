# TUIWEATHERGIRL: RUNNING FOR THE FIRST TIME - APPLICATION OVERVIEW

## CONTENTS

- [Dashboard View - Overview](#dashboard-view-overview)
- [Home Location](#home-location)
- [Currently](#currently)
- [Air & Conditions](#air-conditions)
- [7-day Forecast](#7dayforecast)
- [Warnings](#warnings)
- [Healthy Living](#healthy-living)
- [Celestial](#celestial)
- [Misc](#misc)
- [Followed Cities](#followed-cities)
- [Status](#status)

## DASHBOARD VIEW - OVERVIEW

This application have several views. While most of them show the same information, each one of them is designed with specific focus or terminal size in mind. For this reason not all view display all the information.

Let's start with the default view. It is called "dashboard" view. Here is how it looks.

[![Dashboard View 001](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard001.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard001.jpg)

Now let me clarify what do you see. The screen is divided into several areas which I call "windows". Please note I put yellow numbers over the different windows of the screen. Here is what they are:

0. The ABOUT window. From left to right: Application name, version, description and author.
1. Currently set home location (your home city) (city name, province name, country name)
2. Today's date, time, DST, day/night and season
3. Current sky situation (explained below)
4. Current air situation (explained below)
5. 7-day weather forecast
6. Warnings window
7. Healthy living window
8. Celestial information
9. Miscelaneous window
10. Followed cities (cities of interest) window
11. Last data refresh time and date
12. Auto-refresh interval and QUIT-key information

Now let's go over each window in detail.

## HOME LOCATION

> [!TIP]
> If your home location was incorrectly detected or you are simply behind a VPN you can fix it.
> See the TROUBLESHOOTING section in the [README.md](../README.md).

[![Dashboard View 002](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard002.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard002.jpg)

## CURRENTLY

The "Currently" window displays current sky situation as follows:

- "Sky": Current sky situation
- "Temp": Current temperature
- "Range": Forecasted minimum and maximum temperatures for today
- "Humidt": Current humidity

> The temperature units will be defaulted to the current country units. You can change this in the config file.

[![Currently](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/currently.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/currently.jpg)

## AIR & CONDITIONS

This window shows the current air situation as follows:

- "Wind": Current wind type, direction and speed
- "Air Q": Current air quality and air quality index (AQI) in brackets
- "Precip": Precipitation percentage indicators and forecasted Precipitation sum for today
- "Humidt": Forecasted humidity for today

> The wind speed units will be defaulted to the current country units. You can change this in the config file.

> The precipitation will indicate snowfall in winter.

[![AirConditions](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/airconditions.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/airconditions.jpg)

## 7DAY FORECAST

This window shows the weather forecast for the next 7 days. I put letters to clarify the information:

A. Forecasted minimum and maximum temperatures
B. Forecasted precipitation percentage
C. Forecasted precipitation sum

> The temperature units will be defaulted to the current country units. You can change this in the config file.

> The precipitation will indicate snowfall in winter.

[![Forecast7](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/forecast7.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/forecast7.jpg)

## WARNINGS

This window will display warnings of mainly two types - nature disasters and warnings for people with medical conditions.

[![Warnings](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/warnings.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/warnings.jpg)

[![Wildfire Warnings](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard_wildfire.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/dashboard_wildfire.jpg)

## HEALTHY LIVING

This window will display only two things: On the upper line you will see the current seasonal fruits and vegetables for your area and on the lower line you will see a quick daily challenge to improve your health.

[![Healthy](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/healthy.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/healthy.jpg)

## CELESTIAL

This window will display various celestial information. First would be the sunrise and sunset times, then the current zodiac sign, then the current Chinese zodiac sign and finally the current moon phase.

[![Celestial](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/celestial.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/celestial.jpg)

## MISC

This is the "Miscelaneous" window. It will primarily display the current national holiday. However if there is none, it will display random fun facts.

[![Misc](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/misc.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/misc.jpg)

## FOLLOWED CITIES

The "Followed cities" window will be initially empty. Here you can add cities of your interest. Cities where your relatives or your friends live. Up to 10 cities could be added.

Let's see what information is displayed for each city:

A. City name, province, country
B. Current city temperature
C. Current city sky situation
D. Current city time
E. Day/night indicator

Please note - the city of "St.Kliment Ohridski STN, Bulgaria" (circled in red) is displayed in cyan color. This is because this is not an actual city - this is an actual Antarctic Scientific Research Station, operated by Bulgaria. So this spot is located on Antarctica which by international convention is considered a NEUTRAL TERRIRORY. This is why while "Bulgaria" is indicated by location country, it is actually not located in the country of Bulgaria - it is on the Antarctic continent.

Yes, you can add locations of interest located outside any country. Basically you can add 3 types of locations of interest:

- A city (specified by City Name and Country Name)
- An Antarctic Scientific Research Station (specified by a station list number)
- A random spot on the Earth (specified directly by LATITUDE and LONGITUDE)

In case you live and work on an Antarctic station or if you live outside any city, the way to specify this as your home location is:

1. Add it as a "City of Interest"
2. Set it as a "Home location" (See: README or USAGE for details)

> Every Antarctic Scientific Research Station will be displayed in CYAN color.

> Every location of interest added directly by LATITUDE and LONGITUDE will be displayed in RED color (See: "USAGE").

[![Followed Cities](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/cities.jpg)](https://github.com/StrayFeral/tuiweathergirl/blob/main/overview/cities.jpg)

## STATUS

This is the lowest part of the screen. Few things are displayed there:

1. Last data refresh date and time. When you first launch the application there will be none.
2. Data auto-refresh interval - this indicates on how much time the data will be auto-updated.
3. Active keyboard keys - currently only the "Q"-key is active.

> You can quit the application by pressing "Q" or simply closing the terminal.
