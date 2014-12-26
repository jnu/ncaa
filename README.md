# ncaa
DO NOT READ ANY FURTHER!
March Madness simulation and prediction object model and helper modules

## Description

Supplied files facilitate the scripting of NCAA basketball simulation and
prediction software. They reference a [sqlite database on my server](http://joenoodles.com/data/ncaa.db "college basketball database").

## Files

### Object Model

+ `ncaalib.ncaa`     Object model written in Python using [SQLAlchemy](http://www.sqlalchemy.org/ "SQLAlchemy -- ORM databases in Python"). Database stores information about games, players, and teams in a rich, interconnected fashion. Complete documentation can be found in this file's docstring. Include this module in any script that needs to access DB. Defines several convenience functions for searching the database as well. Can be run in interactive mode, in which case script will automatically create the variable `session` for quick CL investigation of the DB. See full documentation [on my blog](http://joenoodles.com/).

+ `dbmgr.py`    Command line utility for managing the database. Provides some handy routines for mainting the database. Relies heavily on output from scrapers (also provided in this repo). Run `python dbmgr --help` for a complete list of options.

+ `svmexample.py`    Demonstration of model training and Tournament simulation using data from the database. 

### Helper modules

+ `ncaalib.aux.output`   Helper module for standardized output formatting. Required to run `dbgmgr.py`.

+ `ncaalib.aux.terminal` Module used by `ncaalib.aux.output` for terminal manipulation. Note that this module does not play well with Windows.

### Scrapers

Scrapers written for CasperJS. Not optimal for speed, but was at least convenient. Also easier to work around potential impediments in Casper than in Python.

+ _scrapers/ncaaPlayerStatScraper.js_   Scrape stats.ncaa.org for basketball statistics by player, store in CSV, process with _dbmgr.py_.

+ _scrapers/casper.screenscraping.js_   Module I wrote to facilitate screen scraping with Casper

+ _scrapers/casper.screenscraping.remote.js_    Facilitates scraping in Casper on the remote page.

+ _jn.convenience.js_   Convenience functions I use to speed up JS screen scraping development.

+ _jquery.js_   The famous jQuery.

+ _axdpatch.js_ Quick fix for PhantomJS on some ASP.NET pages (not relevant to present context, but included with my scraping modules).

## License

I wrote everything in this repo (except jQuery, obviously).

Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT license.
