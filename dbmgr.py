# -*- coding: utf8 -*-
'''
$ python ncaa2013/dbmgr.py

Command-line utility for adding data to the NCAA database through CSV
and other types of files.


# ABOUT
Written to data scraped as any number of CSV files to the ncaa project DB.
Expected files have generally been scraped using the CasperJS scraper
provided at ncaa2013/scrapers/ncaaPlayerStatScraper.js.

Run `python dbmgr.py -h` to see possible command line arguments.


# DEPENDENCIES
## LOCAL
    + ncaa          Module containing DB schema / ORM
    + output        Output formatting for ncaa project
    
## 3RD PARTY
    + sqlalchemy
    + nameparser    Available via `pip install nameparser`


# LICENSE
Copyright (c) 2013 Joe Nudell.
Freely distributable under the MIT License.
'''
# Local Modules
from ncaa import *
from output import *
# Third Party Modules
from sqlalchemy import create_engine, MetaData, Table, exc
from sqlalchemy.orm import sessionmaker
import sqlalchemy.engine.ddl
import sqlalchemy
from nameparser import HumanName
# Standard Library
from sys import argv, exit, stderr
from random import randint
import csv
import os
import argparse
import re
import datetime




# -- HELPER FUNCTIONS -- //



def is_yes(input):
    return ((input.strip()+'es').lower())[:3]=='yes'


def parse_opponent_name(name):
    '''Determine whether OPPONENT was Home or Away'''
    if '@' in name:
        if name.startswith('@'):
            # opponent was home
            return (name.rpartition('@')[2].strip(), 'home')
        else:
            # Game was played somewhere special, like on a boat.
            np = name.partition('@')
            return (np[0].strip(), np[2].strip())
    else:
        # Opponent was away
        return (name, 'away')


def parse_minutes(mp):
    try:
        return float(mp)
    except ValueError:
        if ':' in mp:
            try:
                min, sec = [float(i) for i in mp.split(':')]
                return min+(sec/60.0)
            except ValueError:
                return None


def get_int(val, empty=0):
    try:
        return int(float(val))
    except ValueError:
        try:
            return int(re.sub(r'[^\d]', '', val))
        except ValueError:
            if len(val)==0:
                return empty
            return None


def get_float(val):
    try:
        return float(val)
    except ValueError:
        return None


def create_new_team_prompt(session, name, yesall=None):
    # Create a new team through the use of prompts
    
    yn = 'yes'
    if not yesall:
        yn = raw_input("Is `%s` the name of the new team (y/n)? " % name)
    
    if not is_yes(yn):
        # Prompt for new team name
        name = raw_input("New team name: ")

    newid = str(randint(1000000, 9999999))
    if not yesall:
        while not newid.isdigit():
            # Get new team ID
            newid = raw_input("New team ID: ").strip()
        newid = int(newid)

    # Make sure Team ID is unique
    if session.query(Team).get(newid) is not None:
        print >>stderr, "Error: key `%d` is taken" % newid
        yn = 'yes'
        if not yesall:
            yn = raw_input("Try again (y/n)?")
        if is_yes(yn):
            return create_new_team_prompt(session, name, yesall)
        else:
            return None
    else:
        # All clear; create new Team (with Alias)
        newteam = Team(name, id=newid)
        newteam.aliases = [TeamAlias(name)]
        session.add(newteam)
        session.commit()
        return newteam



_new_sa_ddl = re.match(r'^0\.(7|8)', sqlalchemy.__version__) is not None

def create_and_upgrade(engine, metadata):
    '''Ensure all tables in DB are in Class and vice versa. Based on solution
    on SO by jon /http://stackoverflow.com/questions/2103274/sqlalchemy-add\
    -new-field-to-class-and-create-corresponding-column-in-table'''
    db_metadata = MetaData()
    db_metadata.bind = engine

    for model_table in metadata.sorted_tables:
        try:
            db_table = Table(model_table.name, db_metadata, autoload=True)
        except exc.NoSuchTableError:
            print_comment('Creating table %s' % model_table.name)
            model_table.create(bind=engine)
        else:
            if _new_sa_ddl:
                ddl_c = engine.dialect.ddl_compiler(engine.dialect, None)
            else:
                # 0.6
                ddl_c = engine.dialect.ddl_compiler(engine.dialect, db_table)
            # else:
                # 0.5
                # ddl_c = engine.dialect.schemagenerator(engine.dialect,
                #               engine.contextual_connect())

            print_info("Table %s exists. Checking for missing columns ..." \
                        % model_table.name)

            model_columns = _column_names(model_table)
            db_columns = _column_names(db_table)

            to_create = model_columns - db_columns
            to_remove = db_columns - model_columns
            to_check = db_columns.intersection(model_columns)

            for c in to_create:
                model_column = getattr(model_table.c, c)
                print_good("Adding column %s.%s" % (model_table.name,
                                                    model_column.name))
                try:
                    assert not model_column.constraints
                except:
                    print_error("Can't add columns to constrained table.")
                    exit(41)

                model_col_spec = ddl_c.get_column_specification(model_column)
                sql = 'ALTER TABLE %s ADD %s' % (model_table.name,
                                                 model_col_spec)
                engine.execute(sql)

            # It's difficult to reliably determine if the model has changed 
            # a column definition. E.g. the default precision of columns
            # is None, which means the database decides. Therefore when I look
            # at the model it may give the SQL for the column as INTEGER but
            # when I look at the database I have a definite precision,
            # therefore the returned type is INTEGER(11)

            for c in to_check:
                model_column = model_table.c[c]
                db_column = db_table.c[c]
                x =  model_column == db_column

                print_comment("Checking column %s.%s" % (model_table.name,
                                                         model_column.name))
                model_col_spec = ddl_c.get_column_specification(model_column)
                db_col_spec = ddl_c.get_column_specification(db_column)

                model_col_spec = re.sub(r'[(][\d ,]+[)]', '', model_col_spec)
                db_col_spec = re.sub(r'[(][\d ,]+[)]', '', db_col_spec)
                db_col_spec = db_col_spec.replace('DECIMAL', 'NUMERIC')
                db_col_spec = db_col_spec.replace('TINYINT', 'BOOL')

                if model_col_spec != db_col_spec:
                    print_warning("Column %s.%s has specification %r in the \
model but %r in the database" % (model_table.name, model_column.name,
                                 model_col_spec, db_col_spec))

                if model_column.constraints or db_column.constraints:
                    # TODO, check constraints
                    print_warning("Contraints not checked (not implemented")

            for c in to_remove:
                model_column = getattr(db_table.c, c)
                print_warning("Column %s.%s in the database is not in \
the model ... leaving be, for now." % (model_table.name, model_column.name))


def _column_names(table):
    # Autoloaded columns return unicode column names
    return set((unicode(i.name) for i in table.c)) 




# -- MAIN -- //


if __name__=='__main__':
    # Parse CLI
    parser = argparse.ArgumentParser(description="Manage NCAA datbase.")
    parser.add_argument('dbname', type=str, metavar='DB',
                        help='path to NCAA database')
    parser.add_argument('-m', '--map', dest='nmap', type=argparse.FileType('r'),
                        metavar='team-names-map', default=None,
                        help='map from team IDs to team name  names')
    parser.add_argument('-a', '--aliases', dest='aliases',
                        metavar='aliases-map',
                        type=argparse.FileType('r'), help='map from team name \
to variations of this team name', default=None)
    parser.add_argument('-p', '--players', dest='players',
                        metavar='players-csv',
                        type=argparse.FileType('r'), help='add players to DB',
                        default=None)
    parser.add_argument('-q', '--quickadd', type=argparse.FileType('r'),
                        metavar='quick-players.csv', help='quickly add players \
to DB.', default=None, dest='quickadd')
    parser.add_argument('-g', '--gamestats', dest='gamestats',
                        metavar='stats-csv',
                        type=argparse.FileType('r'), help='add game stats by \
player to database', default=None)
    parser.add_argument('-r', '--resume', dest='resume', metavar='name',
                        help='Resume entry at given player (last name, first)',
                        default=None)
    parser.add_argument('-y', '--yes', dest='yesall', help="Yes to prompts",
                        action='store_true')
    cli = parser.parse_args()

    # Create database engine
    if not os.path.exists(cli.dbname):
        print_warning("Database `%s` doesn't exist. Creating ..."%cli.dbname)
        if not os.path.exists(os.path.dirname(cli.dbname)):
            os.makedirs(os.path.dirname(cli.dbname))

    engine = create_engine('sqlite:///%s' % cli.dbname)

    # Create tables
    print_comment("Verifying DB structure ...")
    Base.metadata.create_all(engine)
    create_and_upgrade(engine, Base.metadata)

    # Begin a session
    print_info("Beginning session ...")
    Session = sessionmaker(bind=engine)
    session = Session()


    # -- Now do whatever was specified on CLI --
    
    # --------------------------------- //
    if cli.nmap:
        # Provided a map (as csv) from team IDs to names
        reader = csv.reader(cli.nmap)

        print_good("Adding teams and IDs to database ... ")

        for entry in reader:
            old = session.query(Team).get(int(entry[1]))
            if old is not None:
                print_warning("--> Trying to add `%s`" % entry[0])
                print_warning("Conflict: Found previously existing team with \
id=%d: `%s`" % (int(entry[1]), old.name))
                if is_yes(raw_input("replace (y/n)? ", color='cyan')):
                    session.query(Team).filter_by(id=int(entry[1])).delete()
                    session.commit()
                    print_good("Deleted old team at %d." % int(entry[1]))
            team_name, team_id = entry[0], int(entry[1])
            new_team = Team(team_name, id=team_id)
            new_team.aliases = [TeamAlias(team_name)]
            session.add(new_team)
            print_comment("Added %s with ID %d" % (team_name, team_id))

        # Flush pending entries
        print_info("Flushing pending insertions ...")
        session.commit()
        print_success("All finished.")

    # --------------------------------- //
    if cli.aliases:
        # Map team names to aliases
        raise NotImplementedError

    # --------------------------------- //
    if cli.players:
        clear(stream=stderr)
        #print_good("\nAdding players from %s to DB ..." % cli.players)
        # Add players from CSV into DB
        reader = csv.reader(cli.players)
        
        # First entry is header
        headers = reader.next()
        maxlen = len(headers)
        
        entries = [line for line in reader]
        
        print_header("Adding players to DB")
        progbar = ProgressBar(max=len(entries), color='yellow',
                              line=3, stream=stderr)
        
        for entry in entries:
            # Iterate through CSV, adding players to DB
            
            progbar.update(entry[1])
            print >>stderr, ""
            
            changed = False
            
            print_comment("Parsing entry for `%s` ... " % entry[1])
            
            while len(entry) < maxlen:
                # make sure entries are the expected length
                entry.append('')

            # Find if player is already in DB
            player_id = int(float(entry[0]))
            player = session.query(Player).get(player_id)
        
            if player is None:
                # Player not found. Create him.
                changed = True
                print_info("Not found in DB")
                name = HumanName(entry[1])
                player = Player(name.first, name.last,
                                middle_name=name.middle,
                                name_suffix=name.suffix,
                                id=player_id, height=entry[2],
                                position=entry[4])
                session.add(player)
                print_info("Added %s %s to DB ... " % (player.first_name,
                                                       player.last_name))
        
            # see if can add any info
            if player.height is None:
                changed = True
                player.height = entry[2]
                print_comment("Updated player height")
            
            if player.position is None:
                changed = True
                player.position = entry[4]
                print_comment("Updated player position")
            
            # Temporary!
            player.first_name = player.first_name.strip()
            

            # Attempt to find SquadMember of Player in given season.
            squadmember = None
            for sm in player.career:
                if sm.squad.season==entry[6]:
                    squadmember = sm
                    break
                    

            if squadmember is None:
                # Couldn't find SquadMember. Create him.
                changed = True
                print_info("No info yet for player in this season")
                
                # - First find Squad
                # -- Try to find TeamAlias by name
                team = get_team_by_name(session, entry[7])
                
                if team is None:
                    # Couldn't find team name in DB
                    print_error("Couldn't find team `%s` in DB. Check \
team aliases." % (entry[7]))
                    exit(11)

                # -- Determine whether Squad is already defined in Team
                squad = None
                for teamsquad in team.squads:
                    if teamsquad.season==entry[6]:
                        squad = teamsquad
                        break

                if squad is None:
                    print_info("No info yet on team %s in %s" % \
                                    (team.name, entry[6]))
                    # Squad doesn't exist yet. Create it.
                    squad = Squad(entry[6], team=team)

                # - Create SquadMember, attaching to Player and Squad
                jersey = None
                try:
                    jersey = int(entry[3])
                except ValueError:
                    try:
                        jersey = int(re.sub(r'[^\d]', '', entry[3]))
                    except:
                        pass
                
                squadmember = SquadMember(player, squad, jersey=jersey,
                                          year=entry[5])
            if changed:
                # Save additions to DB
                print_good("Successfully added entry to database.")
            else:
                print_warning("Entry already in DB -- nothing changed.")

            if progbar.current%20==0:
                session.commit()
                print_info("Database saved")
        
            clear_below(10, stream=stderr)
            
        print_success("\nAll finished!")
            

    # --------------------------------- //
    if cli.quickadd:
        # Quickly add players to DB
        print_info("Patching players DB")
        reader = csv.reader(cli.quickadd)
        # First line is team / season
        head = reader.next()
        team = session.query(Team).get(int(head[0]))
        if team is None:
            print_error("Error patching DB. Check team ID in patch file.")
            exit(31)
        squad = None
        for s in team.squads:
            if s.season==head[1]:
                squad = s
                break
        if squad is None:
            print_warning("Error finding Squad for given season. Creating one.")
            squad = Squad(team, head[1])
        
        for line in reader:
            # Add players to squad
            id_ = int(float(line[1]))
            last_name, first_name = [t.strip() for t in line[0].split(',')]
            if session.query(Player).get(id_) is None:
                p = Player(first_name, last_name, id=id_)
                sm = SquadMember(p, squad)
                session.add(p)
                print_comment("Added %s %s" % (first_name, last_name))
            else:
                print_warning("%s %s already in DB. Skipping." % (first_name,
                                                                  last_name))
        print_info("Committing changes ...")
        session.commit()
        print_success("All Finished!")
        

    # --------------------------------- //
    if cli.gamestats:
        # Add game stats from file to DB.
        print_info("Processing input file (might take a second) ...")
        reader = csv.reader(cli.gamestats)
        
        # The first entry is the header entry
        headers = reader.next()
        maxlen = len(headers)
        
        resumeat = None
        if cli.resume:
            resumeat = str(cli.resume).lower()

        entries = [line for line in reader]
        
        clear(stream=stderr)
        print_header("Adding game stats to DB")
        progbar = ProgressBar(max=len(entries), color='yellow',
                              line=3, stream=stderr)

        # Map headers onto DB schema
        ## NOTE not really necessary now; assume consistent format
        
        for entry in entries:
            # Iterate through lines, adding and connecting things in db
            # as necessary
            while len(entry) < maxlen:
                # Make sure line is of proper length
                entry.append('')
            
            progbar.update(message=entry[1])
            print >>stderr, ""
            #clear_below(2, stream=stderr, return_=False)
        
            changed = False
        
        
            if resumeat is not None:
                # Resume entry at given player (Last name, first name)
                if entry[1].lower()==resumeat:
                    print_comment("Resuming entry.")
                    resumeat = None
                else:
                    print_comment("Skipping forward ...")
                    continue
                    

            # Attempt to find SquadMember in DB (die if doesn't exist)
            player_id = int(float(entry[0]))
            season = entry[6]
            squadmember = session.query(SquadMember).join(Player).join(Squad)\
                                 .filter(Player.id==player_id)\
                                 .filter(Squad.season==season)\
                                 .first()

            if squadmember is None:
                # Player doesn't exist. This input file cannot properly create
                # a player entry in the database; have to use --players option
                # and input to do that.
                #clear_below(10, start=5, stream=stderr)
                print_warning("Failed to find player `%s` (%s) for season %s \
in the database." % (entry[1], entry[0], season))
                print_comment("Would you like to create a new season for this \
player? (Note this will assume he is still playing for the last team he played \
for.)")
                yn = 'no'
                if cli.yesall:
                    yn = 'yes'
                else:
                    yn = raw_input("Create (y/n)? ", color='yellow')

                if is_yes(yn):
                    changed = True
                    print_info("Creating new season for player ... ")
                    player = session.query(Player).get(player_id)
                    if player is None:
                        print_error("Player doesn't exist in DB at all. Make \
sure that players have all been added to DB and try again.")
                        exit(21)
                    else:
                        # Get last team player played for
                        try:
                            last_team = player.career[-1].squad.team
                        except:
                            print_warning("No record of this player playing \
for anyone ever.")
                            tid = raw_input("Enter team ID:")
                            fail = False
                            try:
                                last_team = session.query(Team).get(int(tid))
                            except:
                                fail = True
                            if fail or last_team is None:
                                print_error("Failed to fix DB. Might have to \
do it by hand.")
                                exit(22)
                        # Get Squad for Team in given season
                        squad = session.query(Squad)\
                                       .filter(Squad.team_id==last_team.id)\
                                       .filter(Squad.season==season)\
                                       .first()
                        if squad is None:
                            print_error("Squad does not exist for %s in the \
season %s! You'll have to fix the DB by hand." \
                            % (last_team.name, season))
                            exit(23)
                        # Made it: add player as SquadMember to this Squad
                        squadmember = SquadMember(player, squad)
                else:
                    print_error("Try to fix database by hand and try again.")
                    exit(24)

            # Try to find Game that stats are being listed for
            # Find the game by matching squadmember's Team with opponent's
            # Team, and the date.
            # -- First find opponent as Team in DB.
            # NOTE: It's possible that the Opponent's team is not listed in
            # the database. Ask the user just in case
            opponent_name, opponent_location = parse_opponent_name(entry[8])
            opponent = get_team_by_name(session, opponent_name)

            if opponent is None:
                # Couldn't find opponent
                if opponent_name.isdigit():
                    print_warning("Skipping invitational (no stats available)")
                    continue
                clear_below(10, start=5, stream=stderr)
                print_warning("Couldn't find team. Trying fuzzy matching ...")

                possible_teams = fuzzy_match_team(session, opponent_name)

                if possible_teams is not None and len(possible_teams)>0:
                    # Display selection of possible teams to match
                    cnt = 1
                    for teamid,score in possible_teams.iteritems():
                        name = session.query(Team).get(teamid).name
                        print_comment("%d) %s" % (cnt, name))
                        cnt += 1

                    # Display prompt for selection
                    selection = None
                    if cli.yesall:
                        selection = 'no'
                    while not selection:
                        input=raw_input("Is `%s` one of the above? \
(# or 'no') " % opponent_name, color='yellow')
    
                        if not is_yes(input):
                            selection = 'no'
                        else:
                            try:
                                selection = int(input)
                                if selection>0 \
                                    and selection<=len(possible_teams):
                                    break
                            except:
                                selection = None

                    # If selection is 'no', prompt to enter Team info to create
                    # new team
                    if selection=='no':
                        opponent = create_new_team_prompt(session,
                                                          opponent_name,
                                                          cli.yesall)
                        if opponent is None:
                            # Can't have None-type opponent. Die.
                            print_error("Unable to create opponent `%s`" %\
                                            opponent_name)
                            exit(13)
                    else:
                        changed = True
                        opponent_id = possible_teams.items()[selection-1][0]
                        opponent = session.query(Team).get(opponent_id)

                else:
                    # No possible teams. Prompt to create new one.
                    opponent = create_new_team_prompt(session,
                                                      opponent_name,
                                                      cli.yesall)
                    if opponent is None:
                        # No opponent created. Die.
                        print_error("Unable to create opponent `%s` " \
                                        % opponent_name)
                        exit(13)
                    changed = True

            # Got opponent. Now get opponents Squad, if possible
            opponent_squad = None
            for osquad in opponent.squads:
                if osquad.season==season:
                    opponent_squad = osquad
                    break
            if opponent_squad is None:
                print_warning("Warning: Creating empty Squad for \
team `%s` in season `%s`!" % (opponent_name, season))
                opponent_squad = Squad(season, opponent)
                opponent.squads.append(opponent_squad)
            
            
            #Back to deciding ID of Game.
            
            # - Parse Date
            month, day, year = [int(p) for p in entry[7].split('/')]
            date = datetime.date(year, month, day)
            
            # Query database for matching Game
            game = session.query(Game)\
                          .filter(Game.opponents.any(id=opponent_squad.id))\
                          .filter(Game.opponents.any(id=squadmember.squad.id))\
                          .filter(Game.date==date)\
                          .first()

            if game is None:
                changed = True
                # Create this game / Doesn't exist yet
                print_info("Creating non-existent game %s vs. %s on \
%d/%d/%d" % (squadmember.squad.team.name, opponent_name,
                             month, day, year))
                
                # Determine respective scores of Game
                winner = None
                loser = None
                score_high = None
                score_low = None
                try:
                    outcome = entry[9]
                
                    score_low, score_high = sorted([int(s.strip())
                                        for s in outcome[1:].split('-')])
                
                    if outcome[:1].lower()=='w':
                        winner = squadmember.squad
                        loser = opponent_squad
                    else:
                        winner = opponent_squad
                        loser = squadmember.squad
                except:
                    pass
                
                game_loc = opponent_location
                if opponent_location=='home':
                    game_loc = opponent.name
                elif opponent_location=='away':
                    game_loc = squadmember.squad.team.name
                game = Game(squadmember.squad, opponent_squad, date,
                            location=game_loc, winner=winner, loser=loser,
                            winner_score=score_high, loser_score=score_low)

                session.add(game)
                print_good("Successfully created game.")

            # Finally, create a statsheet and associate it with the
            # SquadMember and the Game, unless it already exists.
            statsheet = session.query(PlayerStatSheet)\
                    .filter(PlayerStatSheet.game_id==game.id)\
                    .filter(PlayerStatSheet.squadmember_id==squadmember.id)\
                    .first()

            if statsheet is None:
                print_info("Player's record not in DB yet. Entering ...")
                changed = True
                # Create a new statsheet
                statsheet = PlayerStatSheet(squadmember=squadmember, game=game)

                # Map stats from entry into statsheet
                statsheet.minutes_played = parse_minutes(entry[10])

                statsheet.field_goals_made = get_int(entry[11])

                statsheet.field_goals_attempted = get_int(entry[12])

                statsheet.threes_made = get_int(entry[13])

                statsheet.threes_attempted = get_int(entry[14])

                statsheet.free_throws_made = get_int(entry[15])

                statsheet.free_throws_attempted = get_int(entry[16])

                statsheet.points = get_int(entry[17])

                statsheet.offensive_rebounds = get_int(entry[18])

                statsheet.defensive_rebounds = get_int(entry[19])

                statsheet.rebounds = get_int(entry[20])

                statsheet.assists = get_int(entry[21])

                statsheet.turnovers = get_int(entry[22])

                statsheet.steals = get_int(entry[23])

                statsheet.blocks = get_int(entry[24])

                statsheet.fouls = get_int(entry[25])

                print_good("Successfully entered data for player.")

            # Update Database with changes, sporadically
            if progbar.current%20==0 and changed:
                print_info("Saved progress changes to DB")
                session.commit()

            if not changed:
                print_warning("Data is already in DB; nothing added.")

            # Prettify screen
            clear_below(20, stream=stderr)
        print_success("All finished!")
        # Done iterating through entries in GameStats CSV
    # Done processing GameStats CLI

    # --------------------------------- //
                
            

