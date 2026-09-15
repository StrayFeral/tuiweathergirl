# TUIWEATHERGIRL: USAGE

## CONTENTS

- [Help](#help)
- [Application files](#application-files)
- [Updating application](#updating-application)
- [Increasing the Request Timeout](#increasing-the-request-timeout)
- [TROUBLESHOOTING](#troubleshooting)
- [VIEWS](#views)
- [Setup View](#setup-view)
- [DASHBOARD VIEW](#dashboard-view)
- [TTYDashboard View](#ttydashboard-view)
- [Basic View](#basic-view)
- [Seasonal View](#seasonal-view)
- [Motivate View](#motivate-view)
- [THEMES](#themes)
- [CITIES OF INTEREST](#cities-of-interest)
- [Adding a city](#adding-a-city)
- [Adding an Antarctic Scientific Research Station](#adding-an-antarctic-scientific-research-station)
- [Adding a random spot](#adding-a-random-spot)
- [Removing a city](#removing-a-city)
- [Sorting cities](#sorting-cities)
- [Setting a home location](#setting-a-home-location)
- [QUESTIONS](#questions)

## HELP

> [!TIP]
> Please consult the help screen for the most up-to-date command-line options

```bash
tuiweathergirl --help
tuiweathergirl -h
```

Getting the application version:

```bash
tuiweathergirl --version
tuiweathergirl -ver
```

> [!TIP]
> Please note: On near every command-line example I actually give two commands, one being longer, one being shorter, which do absolutely the same thing. So type whichever you find comfortable to type. For example `--version` and `-ver` do absolutely the same thing.

## APPLICATION FILES

For a full list of the application files with full path, you can run:

```bash
tuiweathergirl --listfiles
tuiweathergirl -ls
```

Application uses few files:

- Config: The application configuration file (INI)
- Warnings: The warnings log file (CSV)
- Cache: The application cache file (not human-readable)
- LOG: The application log file (TXT)

After the very first run, the application would auto-configure itself and will create the configuration, then the warnings the cache and the log files. You are not required to modify the configuration file, as there are command-line options to do it, but you are free to do so if you wish.

> [!TIP]
> If you edit the config file and you mess it up and the application start throwing errors, just delete it and run the appliation again. It will create new configuration file, filled with the proper data.

If anything else got messed up, _before_ a new application run you might want to

```bash
tuiweathergirl --clearcache
tuiweathergirl -clr
```

But beware - on the next launch the application would gather fresh data from all APIs, so if you do this too often you may choke the APIs and may get banned.

## UPDATING APPLICATION

In general you do not need to do anything. By default the application will auto-update each Wednesday when you launch it. In case you launch the application and you do not close it for many days, all you need to do is to close it and open it again. Even if it is not Wednesday, if the application detects it hasn't been updated for more than 7 days, it will check for updates imediatelly.

You could always turn the auto-update OFF:

```bash
tuiweathergirl --autoupdateapp off
tuiweathergirl -au off
```

In this case the applicaiton will never check for updates and you must manually update it. You could always turn the auto-update back `ON` by simply typing:

```bash
tuiweathergirl --autoupdateapp on
tuiweathergirl -au on
```

Even if the autoupdate is `ON`, you can always manually force the application to check for updates:

```bash
tuiweathergirl --utoupdateapp
tuiweathergirl -u
```

In this case the application will quietly check for updates and if an update is found, the application qill quietly download it and install it for you behind the scenes. After the update is complete, the application will continue the launch and if successful you will see the new version being displayed at the top of the application.

The application will never show a message that it has been updated, but you will always be able to see in the log file if an update has been installed.

## INCREASING THE REQUEST TIMEOUT

Normally when the application sends a request to any API, it will wait for a certain amount of time for the API to respond. This is the Request Timeout. If the API does not respond by the given time, the application will assume error. Depending on precisely which API was queried and when it was queried, the application will react differently.

Open-Meteo is considered the most important API as it provides the main meteorological data.

Very generally speaking, the application performs data collection upon every launch. If Open-Meteo fails to respond upon application launch, the application will throw an exception and will exit. However if upon start-up Open-Meteo responds, the application will start normally. Then it will query few more APIs. If any of them fails to respond, the application will simply continue the launch and will wait until the data auto-refresh time to collect data again. Default data-refresh interval is set to `30` minutes. This cannot be changed.

This will happen only for the `"dashboard"` and the `"ttydashboard"` views. All other views will collect data only upon application start.

Once the application has been started normally and data refresh time has been reaches, even if Open-Meteo fails to respond, the application will not throw exception and will not exit. It will simply retry few times in 3 minutes and if this fails, will increase the retry interval again to 30 minutes. Then will print an error message in the `"Warnings" window`, but will not exit. Will simply wait for the next data-refresh interval.

In case your internet is slow, you might experience problems with the application - it might throw exceptions with `"REQUEST TIMEOUT"` message. If this happens, simply increase the request timeout like this:

```bash
tuiweathergirl --requesttimeout <XX>
tuiweathergirl -reqt <XX>
```

Where `XX` is a number (seconds). As I said - when you first install the application, the default will be `5`. I personally set this value to `7` for me and this solves any problems. This is the number I recommend. There is no point to make this number super large. So while you could set it like `15` for example, there is no point to set it to `300`. And the application will also not allow such a large number.

> [!TIP]
> Use this if your internet connection is slow for any reason.

Example:
```bash
tuiweathergirl --requesttimeout 7
```

> [!TIP]
> You do not need to specify the request timeout each time you run the application. It will be saved in the config file, so next time you run the application it will be run with the last used value.

## TROUBLESHOOTING

As I wrote in the [README.md](README.md), the first two things you can do in case of problems are:

1. Look at the log file
2. Clear the cache
3. Enable DEBUG MODE (and still check the logfile)

To clear the cache, do:

```bash
tuiweathergirl --clearcache
tuiweathergirl -clr
```

This will do 3 things at once:

1. Delete the cache file
2. Delete the warnings logfile
3. Delete the logfile

You might want to clear the cache if you change home cities or experiment otherwise with the app. If you simply launch it, add few cities and later change nothing you won't need to do this.

To enable `DEBUG MODE`:

```bash
tuiweathergirl --debug
tuiweathergirl -d
```

Yes - just add the `--debug` or (`-d`) at the end of your command-line. This will enable the debug mode. The application will start printing a lot more to the log file. You will see precisely what queries has been sent to which APIs, so you could manually debug yourself, if you want to do that and you could investigate precisely what fails when.

> [!TIP]
> If for some reason your home location was not properly detected or if you are behing VPN, use `--addcity` and `--sethome`. See below.

## VIEWS

This application have several views. Most of them show the same information, but not all views show all information. Each view have a different focus.

To change a view, type:

```bash
tuiweathergirl --view <VIEWNAME>
```

You can see what are the currently available view names by just invoking the `help`. At present these are:

1. `setup` - Just displays the home location and added cities setup.
2. `basic` - Basic prints to the terminal, but will display almost everything.
3. `motivate` - Very cool view! Especially for D&D or LOTR fans!
4. `dashboard` - `THE MAIN VIEW`
5. `ttydashboard` - View specifically designed for barebone terminals.
6. `seasonal` - Display the seasonal fruits and vegetables for the home location and all cities of interest.

> [!TIP]
> In future I might develop more views, so be sure to check the help!

> [!TIP]
> You do not need to specify the view name each time you run the application. It will be saved in the config file, so next time you run the application it will be run with the last used view.

## SETUP VIEW

This view shows only the current city setup. It will only display the currently set home location and all added cities of interest.

```bash
tuiweathergirl --view setup
```

> [!TIP]
> Please note! The home location will be listed simply by its name (city name, country etc), however all cities of interest will be listed by an assigned number! You will reference to this number later, when you will be adding cities, removing cities or setting a new home location.

## DASHBOARD VIEW

This is the `default view`. When you first install the application, it will try to start this view.

This view is considered the main view and will try to display all available information.

I already wrote a detailed description of this view with screenshots. See: [OVERVIEW.md](OVERVIEW.md)

> [!TIP]
> Dashboard view uses ncurses and requires a terminal size of minimum 146x38.

Yes. If you try to launch the view in a smaller terminal, it will throw an exception and will exit. But in the error message it will tell you precisely what is your current terminal size, so you can resize it to the required size.

> [!TIP]
> If you have a smaller terminal or you simply don't want to enlarge your terminal, just use any of the other views.

## TTYDASHBOARD VIEW

This view is specifically designed for barebone terminals. So if you like to have linux installed without any desktop environment, this view is for you.

The only thing this view will not display are the cities of interest.

> [!TIP]
> TTYDashboard view uses ncurses and requires a terminal size of minimum 106x33.

## BASIC VIEW

This view will display absolutely everything with simple prints to `STDOUT`. It is the only view which will display `absolutely all warning messages`.

> [!TIP]
> The application in reality collects warning messages from the midnight of the previous day, but will display only the last set of messages which fit in the `"Warnings"` window for the `"dashboard"` and `"ttydashboard"` views. This is why if you want to see absolutely all messages, use the `"basic"` view. Keep in mind that every time you use `--clearcache` it will delete the collected warning messages.

## SEASONAL VIEW

This view will display all current seasonal fruits and vegetables for the home location and all cities of interest (normally other views will show seasonal veggies only for the home location). So if you want to recommend your friends what to eat, check this view.

## MOTIVATE VIEW

This view started as a joke to test the application, but I decided to keep it. It will show the weather information in a bit bardic way - so if you're a fan of `D&D` or `LOTR` you might enjoy it a lot.

## THEMES

All `ncurses` views support color themes. You can change a theme using:

```bash
tuiweathergirl --theme <THEMENAME>
```

Currently available color themes are:

1. `main`
2. `mono`
3. `lemon`
4. `arctic`

> [!TIP]
> You do not need to specify the theme name each time you run the application. It will be saved in the config file, so next time you run the application it will be run with the last used theme.

## CITIES OF INTEREST

The cities of interest (also shown as `"Followed Cities"`) are cities of which you are interested to monitor the current weather situation of.

These are cities where you might have friends or relatives living or just cities which you are curious of.

Initially it was only possible to add known settlements - cities, towns, villages - but now it's also possible to add also Antarctic Scientific Research Stations (Antarctica by international convention is a `neutral zone`) and just any spot on Planet Earth, regardless where is it, even if it's in the middle of the Sahara Desert or in the middle of the Atlantic Ocean.

For details - see below!

## ADDING A CITY

To add a known settlement (no need to be a city, could be a village too), you must also specify the country name like this:

```bash
tuiweathergirl --addcity <CITYNAME> --country <COUNTRYNAME>
```

For example, to add the city of New York as a city of interest, do this:

```bash
tuiweathergirl --addcity "new york" --country usa
```

> [!TIP]
> To add a city name or country name consisting of more than one word - use `quotes`!

## ADDING AN ANTARCTIC SCIENTIFIC RESEARCH STATION

To add an Antarctiv Scientific Research Station you will use a little hack into the city syntax:

```bash
tuiweathergirl --addcity <STATIONNUMBER> --country polarstation
```

Currently there are a total of 46 known Antarctic stations. Here is how to get a list of them all:

```bash
tuiweathergirl --listpolarstations
tuiweathergirl -lsps
```

This will list all stations with an assigned number. Use this number to add the station to your places of interest.

For example, to add Concordia Station, you should do this:

```bash
tuiweathergirl --addcity 2 --country polarstation
```

We used the number `2` as Concordia is listed as number two in the list of stations.

## ADDING A RANDOM SPOT

You can add just any spot on Planet Earth as a location of interest. Here's how:

```bash
tuiweathergirl --addcity <SOMETHING> --country <SOMETHINGELSE> --latitude <XX> --longitude <XX>
tuiweathergirl --addcity <SOMETHING> --country <SOMETHINGELSE> -lat <XX> -lon <XX>
```

The important here are the `--latitude` and `--longitude` parameters. In this syntax, the "city name" and "country name" serve only as a descriptor. Something which would mean something just for you. Sure, you can type existing city and country name, but these would `NEVER` be actually checked, so you can really type anything you like.

For example let's imagine you are now living in a hut in the Lybian part of the Sahara desert. Let's add it:

```bash
tuiweathergirl --addcity "My hut" --country "Sahara" --latitude 27.490153722109945 --longitude 12.118631915829864
```

> [!TIP]
> You can check the exact latitude and longitude of any spot on Earth by just right-clicking anywhere on Google Maps.

## REMOVING A CITY

Let's say you previously added a city by mistake or you previously added a city, but you are no longer interested in this city. It could be any settlement - city, town, village, Antarctic Station or just any spot on Earth.

Here's how:

First check the setup. Any added location have an assigned number. So you need to see which number is this:

```bash
tuiweathergirl --view setup
```

> [!TIP]
> Always check the setup and get the location number from there! Do not rely on the number shown in the Dashboard or TTYDashboard view, as the locations shown there could be sorted and shown in a different order!

After you've seen the actual location number, the second thing to do is:

```bash
tuiweathergirl --removecity <LOCATIONNUMBER>
```

This will permanently remove the location from your "Cities of interest".

## SORTING CITIES

The locations of interest could be sorted by:

1. `unsorted` (DEFAULT)
2. `city`
3. `country`

Here's how:

```bash
tuiweathergirl --citiessorting <FIELDNAME>
tuiweathergirl -csort <FIELDNAME>
```

> [!TIP]
> When you sort by `city` or `country`, the cities of interest located in the home country (if any) will always be shown first.

## SETTING A HOME LOCATION

Finally the last thing to show about cities of interest is how to set a home location.

Suppose you launch the application for the first time and your home location was incorrectly detected. It will be incorrectly detected also if you're behind a VPN. Or you are just located in an Antarctic Station or you are located in some weird spot on the map.

So here is how to solve the problem:

First you must add your actual location using one of the above methods - either as a city, as an Antarctic Station or as a random spot.

Second you must view the setup. As I already mentioned, each added location have an assigned number. You must see which this number is:

```bash
tuiweathergirl --view setup
```

And finally you must specify this number as the new home location:

```bash
tuiweathergirl --sethome <LOCATIONNUMBER>
```

What this will do is it will swap the two locations. So the specified location number will become the new home location, while the existing home location will become the new city of interest with the specified number.

Lastly - if you do not need the old home location (which now will be moved to the Cities of Interest list) you can simply remove it, using the above-mentioned method.

## QUESTIONS

Questions? Something is not clear? Here's how to contact me:

1. Write me a comment under any of my Youtube videos. My channel is [SKATECODE](https://www.youtube.com/@SkateCode)
2. Write me on GitHub (but I rarely check messages there)
3. Write me on [Reddit](https://www.reddit.com/user/StrayFeral/)
