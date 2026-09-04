# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-09-05
### Added
- EMSC earthquake query logic

### Fixed
- Some strings tried to print variables, but weren't declared as f-strings.
- The USGS earthquake query logic

## [1.2.20] - 2026-08-31
### Added
- CHANGELOG.md (this file): Now all release notes are written here, to keep the `README.md` clean.
- `README.md` now contains link to `CHANGELOG.md`

### Fixed
- Code fixed to be fully Python 3.9 compatible. Tested on the official `python:3.9-bookworm` Docker image.

## [1.2.19] - 2026-08-30
### Added
- Some comand-line parameters now have shorter versions.

### Changed
- TimeZoneDB API KEY NO LONGER NEEDED! Thanks to Reddit user `recycledcoder`.
- Code optimized a bit.

## [1.2.18] - 2026-08-25
### Added
- Followed Random Earth Points as cities, now appear in white in the Cities window.
- Sorting for the followed cities.

### Changed
- Help changed.

### Fixed
- Improper forecasted humidity assessment and color coding.

## [1.2.17] - 2026-08-25
### Fixed
- Crasher bug when a random Earth point is set as home location.
- Crasher in the auto-update.

## Non-Version Updates - 2026-08-25
### Added
- New video tutorials for Windows 10 and Linux has been created and uploaded to Youtube.

### Changed
- Readme is updated with the new URLs.

## [1.2.16] - 2026-08-24
### Fixed
- Crasher URL issue.

## [1.2.15] - 2026-08-24
### Added
- Basic view extended to show all warnings and a bit more info.

### Changed
- Help reformatted.
- Small terminal exception message wording changed.

## [1.2.14] - 2026-08-23
### Added
- Added recent Windows 10 screenshot.
- Added directories for screenshots of known bugs.

### Changed
- Terminal no longer force-maximized.

### Fixed
- Windows 10 installation issues.

## [1.2.13] - 2026-08-22
### Changed
- Application update is now fully working.

## [1.2.6] - 2026-08-22
### Fixed
- Bugs with the application updates.

## [1.2.0] - 2026-08-21
### Added
- Implemented application auto-update and force-update.

## [1.1.6] - 2026-08-21
### Changed
- Abbreviation "ppl." expanded back to "people.".

## [1.1.5] - 2026-08-20
### Fixed
- Fixed duplicate wildfire warnings.

## [1.1.4] - 2026-08-20
### Changed
- Electrostatic warning texts shortened to better fit the screen.

## [1.1.3] - 2026-08-17
### Fixed
- Sky condition overlap in cities of interest.

## [1.1.2] - 2026-08-17
### Fixed
- Abbreviation in cities of interest sky condition.

## [1.1.1] - 2026-08-16
### Fixed
- Too long city/province names for cities of interest.
- Bug in holidays update.

## [1.1.0] - 2026-08-16
### Changed
- Code refactored.

### Fixed
- Bug in right-aligned text.
- Bug in TTYDashboard view.
- Bug in NASA Fireballs query.

## [1.0.13] - 2026-08-13
### Added
- Now Polar Stations could be followed too.

### Fixed
- Temperature assessments now takes Fahrenheit into account too.

## [1.0.12] - 2026-08-13
### Changed
- Shortened the names of cities, countries and provinces.

### Fixed
- Fixed small bug in showing the current home time.

## [1.0.11] - 2026-08-08
### Fixed
- Now application could be closed with capital "Q" too.

## [1.0.10] - 2026-08-08
### Changed
- Maximum cities of interest increased to 10.
- One error message changed.

## [1.0.9] - 2026-08-08
### Added
- Makefile now supports all major linux distros.

## [1.0.8] - 2026-08-07
### Added
- Terminal close and Ctrl-C now intercepted.

### Fixed
- Fixed minor bugs.
- Makefile fixed.

## [1.0.6] - 2026-08-03
### Changed
- More defensive parsing of the NASA FIRMS response.

## [1.0.5] - 2026-08-03
### Fixed
- Now the "setup" view is not saved in the config, so your actual default view is preserved.

## [1.0.4] - 2026-08-03
### Fixed
- Fixed how the exception stacktrace is being printed.

## [1.0.3] - 2026-08-03
### Added
- Exception stacktrace is now always logged in the log file, so in case of found bug, just paste me the log.
