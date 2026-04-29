# TUIWEATHERGIRL: Your daily terminal weathergirl

![Screenshot](screenshots/thumbnail.jpg)

## DESCRIPTION

Terminal application to display the daily and weekly weather forecast.

The application was written with the most basic to modern terminals in mind and paying special attention to ease the API calls and prevent the APIs being called too often, thus improving the speed while still being useful to the user.

The application have minimal dependencies (only `python3-babel`) and is portability-centric.

Not vibe-coded.

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
  - DST
  - Day/night
  - Wind type assessment
  - Precipitation type assessment
  - Up to 10 additional cities available to monitor
- Robustness:
  - Several cachine methods to ease the API calls and prevent being banned
- Extensibility:
  - Different views, ranging from simple prints for super basic terminals to colorful views for modern terminals
  - Users could add their own views, assuming they have knowledge of Python programming language
- Flexibility:
  - Application can handle scenario when user is behind VPN and still provide the relevant data
- Accessibility:
  - Convenient for people using screen-reading software
- Portability:
  - The application makes use of only one external Python library (`python3-babel`), everything else used are core libraries
  - The application was written as a single file to simplify the portability
- Usability:
  - Extensive help screen with detailed description of the application

## INSTALLATION

```bash
make install
```

## USAGE

> Please consult the help screen for the most up-to-date command-line options

```bash
tuiweathergirl --help
```

After the very first run, the application would auto-configure itself and will create the configuration file (`~/.tuiweathergirlrc`). You are not required to modify it, as there are command-line options to do it, but you are free to do so if you wish.

If you mess it up and the application start throwing errors, just delete it and run the appliation again. It will create new configuration file, filled with the proper data.

> If you are behind VPN, still let the application detect your location, then add the city you're actually in manually with the `--addcity` option, then use the `--sethome` option to set which city is your actual home.

