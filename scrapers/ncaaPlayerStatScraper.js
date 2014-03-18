/**
 * $ casperjs ncaaPlayerStatScraper.js
 *
 *
 * Copyright (c) 2013 Joseph Nudell
 * Freely distributable under MIT license.
 */


// Create CasperJS object
var casper = require('casper').create({
    logLevel: 'debug',
    verbose: false,
    onError: function(self, m) {
        console.log('WARNING: ' + m);
    },
    pageSettings: {
        loadImages: false
    }
});

// Imports. fs and utils are from PhantomJS
var ss = require('./casper.screenscraping.js');
var fs = require('fs');
var utils = require('utils');

// xpath selectors.
var x = require('casper').selectXPath;

// Global parameters
var resume = casper.cli.get('resume') || null,
	year = casper.cli.get('year') || 2014,
	index = "http://stats.ncaa.org/team/inst_team_list?academic_year=" + year + "&conf_id=-1&division=1&sport_code=MBB",
	playerDBName = "players-"+casper.today()+(resume?"-resumedAt_"+resume:"")+".csv",
	gameDBName = "gameByPlayers-"+casper.today()+(resume?"-resumedAt_"+resume:"")+".csv",
	errorLogName = "errors-"+casper.today()+(resume?"-resumedAt_"+resume:"")+".csv",
	playerDB = {}, // file will be opened later
	gameDB = {}, // file will be opened later
	errorLog = {}, // ditto
	data = {}; // local cache



// Print error message
casper.on('remote.message', function(msg) {
    if( msg.startsWith('casper:') ) {
        msg = msg.substring(7);
        casper.echo(msg, "PARAMETER");
    }else{
        casper.echo("remote> "+msg, "WARNING");
    }
});





// Begin casper routine
casper.start(function() {
	casper.echo("Starting scraper ...");
});


casper.then(function() {
	// Open ouput files
	casper.echo("Opening player database at `"+ playerDBName +"` ... ");
	playerDB = fs.open(playerDBName, 'w');

	casper.echo("Opening games database at `"+ gameDBName +"` ... ");
	gameDB = fs.open(gameDBName, 'w');

	// Open error log silently.
	errorLog = fs.open(errorLogName, 'w');
});


casper.thenOpen(index, function() {
	casper.echo("Navigating to NCAA stats index ...");
});


casper.then(function() {
	// Find all the teams!
	data.teamLinks = casper.evaluate(function() {
		return $j.selectAll('a[href^="/team/index"]').map(function(teamLink) {
			return {name: teamLink.innerText.strip(), href: teamLink.href};
		});
	});

	if(data.teamLinks===null) {
		casper.echo("Failed to find any team links to scrape. Quitting.", "ERROR").exit();
	}

	data.indexPage = casper.getCurrentUrl();


	// User might have specified "resume", in which case shift the teamLinks array
	// until the requested "start" team is matched.

	if(resume) {
		var lcResume = resume.toLowerCase();

		var locTL = data.teamLinks.map(function(c) { return c; });

		while(locTL.length>1) {
			if(locTL[0].name.toLowerCase()==lcResume) break;
			locTL.shift();
		}

		data.teamLinks = locTL;


		if(data.teamLinks[0].name.toLowerCase()!=lcResume) {
			casper.echo("Failed to find `"+ resume +"` in index. Can't resume scraping at this team. Quitting.", "ERROR").exit();
		}
	}

	casper.echo("Found "+ data.teamLinks.length +" teams to scrape.", "PARAMETER");

});

/// End of boilerplate / main index parsing



// convenience functions
function getCurrentYear() {
	return this.evaluate(function() {
		// Get current year
		var season = $j.selectFirst('div.appTitle').innerText.split(' ')[0].strip();
		return season;
	});
}


function getYearLinks() {
	return this.evaluate(function() {
		return $j.selectAll('//a[starts-with(., "201")][@href] | //a[starts-with(., "200")][@href]').map(function(me) {
			return {text: me.innerText, href: me.href};
		});
	});
}



// Page parsers
parser = {};

parser.playerPage = function(player) {
	// Parse the player's page.
	var that = this;
	data.statsRetrieved = data.statsRetrieved || {};

	// First store the player info in the local data cache.
	data.players[player.id] = player.href;

	// Use to get current grade level, insofar as this is possible
	var gradeMap = ['Sr', 'Jr', 'So', 'Fr'],
	origYear = gradeMap.indexOf(player.year);

	// This data is not cached, but will be written to the output file.
	var d = new Date();
		scrapeTime = d.getTime() + d.getTimezoneOffset()*60*1000;

	this.then(function() { this.echo("    >> Opening player info for "+ player.name +" ...", "PARAMETER") });


	var _getStats = function() {
		// This is the real parser. Get data here and write it to a file.
		var currentSeason = getCurrentYear.call(this);

		// First -- Career stats.
		var needHeaders = data.careerStatHeaders===undefined,
			needStats = data.statsRetrieved[player.id]===undefined;

		if(needStats) {
			this.echo("      + Getting career stats for player "+ player.name +" ("+ player.id +")", "COMMENT");
			// Career stats are contained in TR.text rows
			var cstats = this.evaluate(function(needHeaders) {
				// Get the rows and parse them. Get headers as very first row if necessary.
				try{
					var rows = $j.selectAll('tr.text').map(function(row) {
						var stats = [];
						Array.prototype.forEach.call(row.querySelectorAll('td'), function(cell) {
							stats.push(cell.innerText.strip());
						});
						console.log("casper:debug> Career Stats: "+ stats.toCSVEntry());
						return stats;
					});

					var headers = null;
					if(needHeaders) {
						var headerCellsList = $j.selectFirst('tr.grey_heading').querySelectorAll('td');
						headers = [];
						Array.prototype.forEach.call(headerCellsList, function(cell) {
							headers.push(cell.innerText.strip());
						});
					}

					return {rows: rows, headers: headers};
				}catch(e) {
					console.log(e.message);
					return {};
				}
			}, needHeaders);

			// Append data to players database, headers first (if applicable)
			if(cstats) {
				if(cstats.headers) {
					// Extend with name, ID, and href fields
					data.careerStatHeaders = ['ID', 'Name', 'Height (in.)',
											  'Number', 'Position', 'Grade']
											 .concat(cstats.headers, ['Date Retrieved', 'Source']);
					playerDB.writeLine(data.careerStatHeaders.toCSVEntry());
				}
				if(cstats.rows) {
					cstats.rows.forEach(function(me, i) {
						// Extend with relevant player information (ID and Name and URL)
						var thisYear = (origYear>=0 && origYear+i<gradeMap.length)? gradeMap[origYear+i] : "";
						var entryList = [player.id, player.name, player.height,
										 player.number, player.position, thisYear]
										.concat(me, [scrapeTime, player.href]);
						playerDB.writeLine(entryList.toCSVEntry());
					});
					data.statsRetrieved[player.id] = true;
				}else{
					this.echo("Error getting career stats for player "+ player.id +" ("+player.name+"). Got headers though?", "WARNING");
					errorLog.writeLine(['player-season-h', player.id, player.href, 'missing'].toCSVEntry());
					errorLog.flush();
				}
			}else{
				// Error getting stats
				this.echo("Error getting career stats for player "+ player.id +" ("+player.name+")", "WARNING");
				errorLog.writeLine(['player-season', player.id, player.href, 'missing'].toCSVEntry());
				errorLog.flush();
			}
		}



		// Now get the individual game statistics.
		this.echo("      + Getting game stats for "+ player.name +" / Season "+currentSeason, "COMMENT");

		needHeaders = data.gameStatHeaders===undefined;

		var gstats = this.evaluate(function(needHeaders) {
			// Get game stats with a fancy xpath query.
			var rows = $j.selectAll('.//div[starts-with(@id, "game")]//tr[@class="grey_heading"]/following-sibling::tr').map(
				function(row) {
					var stats = [];
					Array.prototype.forEach.call(row.querySelectorAll('td'), function(cell) {
						stats.push(cell.innerText.strip());
					});
					return stats;
				}
			);

			// Get headers if so advised
			var headers = null;
			if(needHeaders) {
				headers = $j.selectAll('.//div[starts-with(@id, "game")]//tr[@class="grey_heading"]//td').map(
					function(cell) {
						return cell.innerText.strip();
					}
				);
			}

			return {rows: rows, headers: headers};
		}, needHeaders);


		// Finally, write to gameDB.
		if(gstats) {
			if(gstats.headers) {
				// Extend with name, ID, and href fields
				data.gameStatHeaders = ['ID', 'Name', 'Height (in.)',
									    'Number', 'Position', 'Grade', 'Season']
									   .concat(gstats.headers, ['Date Retrieved', 'Source']);
				gameDB.writeLine(data.gameStatHeaders.toCSVEntry());
			}

			if(gstats.rows) {
				gstats.rows.forEach(function(me, i) {
					var thisYear = (origYear>=0 && origYear+i<gradeMap.length)? gradeMap[origYear+i] : "";
					// Extend with relevant player information (ID and Name and URL)
					var entryList = [player.id, player.name, player.height,
									 player.number, player.position, thisYear, currentSeason]
									.concat(me, [scrapeTime, player.href]);
					gameDB.writeLine(entryList.toCSVEntry());
				});
			}else{
				this.echo("Error getting game stats for player "+ player.id +" ("+player.name+"). Got headers though?", "WARNING");
				errorLog.writeLine(['player-game-h', player.id, player.href, 'missing'].toCSVEntry());
				errorLog.flush();
			}
		}else{
			// Error getting stats
			this.echo("Error getting stats for games / player "+ player.id +" ("+player.name+")", "WARNING");
			errorLog.writeLine(['player-game', player.id, player.href, 'missing'].toCSVEntry());
			errorLog.flush();
		}

		// Done!
		this.echo("      - Got stats!", "TRACE");

	};

	this.thenOpen(player.href, function() {
		// Parse the player stats pages. (for all years.)
		// Includes summarial data as well as individual game data. Get it ALL.
		var ppc = this;

		var years = getYearLinks.call(this).map(function(me){ return me.text; });

		var currentYear = getCurrentYear.call(this);

		// Translate season link texts in YEARS to IDs
		years = years.map(function(me){
			if(!Object.keys(data.yearIDs).contains(me)) {
				// Year ID not found.
				that.echo("Year ID not found: `"+ me +"`", "WARNING");
				return [me, null];
			}
			return [me, data.yearIDs[me]];
		});
		years.unshift([currentYear, undefined]);

		// Iterate through years and download player stats for each year.
		years.forEach(function(me) {
			if(me[1]===undefined) {
				// dispatch parser on current page
				_getStats.call(ppc);
			}else if(me[1]===null) {
				// try to dispatch parser by clicking. Uses AJAX, waits for
				// Loading screen to disappear.
				ppc.echo(" -- Resorting to AJAX click on season link "+ me[0], "WARNING");
				ppc.thenClick(x('//a[.="'+ me[0] +'"]'), function() {
					this.waitWhileVisible(x('//div[.="Loading..."]'), _getStats);
				});
			}else{
				// A year ID was given, so use it.
				var newURL = ppc.getCurrentUrl().replace(/game_sport_year_ctl_id=\d+/, "game_sport_year_ctl_id="+me[1]);
				ppc.thenOpen(newURL, _getStats);
			}
		});

		gameDB.flush();
		playerDB.flush();
	});

}


// Parse Team Stats Page
parser.teamPage = function(teamLink) {
	data.teams = data.teams || {};
	data.players = data.players || {};
	data.yearIDs = data.yearIDs || {};

	var that = this;

	var _getRoster = function() {
		var grc = this;

		var currentYear = getCurrentYear.call(this);

		this.echo("   :: Getting team roster for "+ currentYear +" season ...", "PARAMETER");

		// Get the roster of team as displayed on current page.
		var players = this.evaluate(function() {
			console.log("casper:   * Entering remote page context (team page)");
			return $j.selectAll('a[href^="/player?"]').map(function(me) {
				var playerID = me.href.match(/stats_player_seq=(\d+(?:\.\d+)?)/i);
				if(playerID && playerID.length>1) {
					playerID = playerID[1];
				}else{
					console.log("Error determining player ID in link: "+ me.href);
					playerID = -1;
				}

				// Get adjacent fields
				try{
					var linkCell = '//a[contains(@href, "stats_player_seq='+playerID+'")]/parent::td',
						number = $j.selectFirst(linkCell + "/preceding-sibling::td").innerText,
						position = $j.selectFirst(linkCell + "/following-sibling::td").innerText,
						height = $j.selectFirst(linkCell + "/following-sibling::td/following-sibling::td").innerText,
						year = $j.selectFirst(linkCell + "/following-sibling::td/following-sibling::td/following-sibling::td").innerText;

						// convert height to inches
						if(height) {
							try{
								var feet = parseInt(height.split("-")[0]),
									inches = parseInt(height.split("-")[1]);
								height = feet*12 + inches;
							}catch(e){
								height = height;
							}
						}
				}catch(e){
					console.log("Error:" + e.message);
				}



				return {
					id: playerID,
					href: me.href,
					name: me.innerText.strip(),
					number: number,
					position: position,
					height: height,
					year: year
				};
			});
		});

		// Any player that is already in the data store has
		// been retrieved already. Only add new entries.
		players.forEach(function(player) {
			if(!Object.keys(data.players).contains(player.id)) {
				// This is a new player. Dispatch player scraper.
				parser.playerPage.call(grc, player);
			}
		});
	};

	// Open link to the stats page for a given team.
	this.start(teamLink, function() {
		// Parse Team page.

		var teamName = this.evaluate(function() {
			return $j.selectFirst('h1').innerText.replace(/\(.+\)/g, '').strip();
		});

		// - Get Team ID
		var teamID = this.getCurrentUrl().split('=')[1];
		data.teams[teamID] = data.teams[teamID] || {};

		this.echo("  * Getting data for team "+teamID+" ("+ teamName +") ...", "TRACE");

		// - Get other years of stats for team.
		data.teams[teamID].yearLinks = getYearLinks.call(this);

		// - Get team rosters (for every year)
		// Starting with current year
		_getRoster.call(this);

		// figure out what the current year is
		var currentYear = getCurrentYear.call(this);

		if(!Object.keys(data.yearIDs).contains(currentYear)) {
			// Get and add currentYear ID to local data cache if necessary
			var cyid = this.getCurrentUrl().match(/\/(\d+)\?/);
			if(cyid) {
				data.yearIDs[currentYear] = cyid[1];
				that.echo("> Mapped season "+currentYear+" to ID "+ cyid[1], "COMMENT");
			}else{
				that.echo("Unable to get year ID for current year "+ currentYear +" from URL "+ this.getCurrentUrl(), "WARNING");
				errorLog.writeLine(['yearID', me.innerText, me.href, 'missing'].toCSVEntry());
			}
		}

		// Get team rosters for every other year
		data.teams[teamID].yearLinks.forEach(function(me) {
			if(!Object.keys(data.yearIDs).contains(me.text)) {
				// Map current year text to ID by parsing URL. Useful later on
				// to avoid AJAX links.
				var idM = me.href.match(/\/(\d+)\?/);
				if(idM) {
					that.echo("> Mapped season "+me.text+" to ID "+ idM[1], "COMMENT");
					data.yearIDs[me.text] = idM[1];
				}else{
					that.echo("Unable to get year ID for year "+me.innerText+" from URL "+me.href, "WARNING");
					errorLog.writeLine(['yearID', me.innerText, me.href, 'missing'].toCSVEntry());
				}
			}

			// Grab the team roster and parse it.
			that.thenOpen(me.href, _getRoster);
		});
	});
}


function _scrape() {
	// Begin scraping
	data.teamIndex = data.teamIndex || 0;
	if(data.teamLinks[data.teamIndex]) {
		this.echo(" == Dispatching scraper for `"+
				  data.teamLinks[data.teamIndex].name +
				  "` ("+ (data.teamIndex+1) +" / "+ data.teamLinks.length +") == ",
				  "INFO_BAR");
		parser.teamPage.call(this, data.teamLinks[data.teamIndex].href);
		data.teamIndex++;
		this.run(_scrape);
	}else{
		this.echo("All finished!", "GREEN_BAR").exit();
	}
}


// Call _scrape() when everything else is finished.
casper.run(_scrape);
