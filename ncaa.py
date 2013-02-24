# -*- coding: utf8 -*-
'''
$ python ncaa2013/ncaa.py

Library defines ORM database accessor classes and other classes for NCAA.

Includes team name normalization helper functions.

A word on database design.

Most of the mappings in the database are many-to-one / one-to-many. In all of
these cases the relationship is defined just once in the many-end of the
relationship. The corresponding attribute in the one-end is defined using
backref.

There is one many-to-many relationship, the map of Squads to Games, which
is managed by the cross-reference table schedule.

The database is richly interconnected with a set of hierarchical structures
for Teams, Players, and Games. Here's the gist of this network:


> Team
    @ Contains vital info about team (name, etc.)
    + Contains a collection of TeamAliases
    
    + Squad (a Team in a particular year)
        @ Contains descriptive info about Squad: season, RPI, etc.
        ^ references parent Team
        + contains a collection of SquadMembers in `roster`
        + contains a collection of Games in `schedule`


> Player
    @ Contains vital info about player (name, height, etc.)
    
    > SquadMember (a Player in a particular year)
        @ Contains vitalish info about player (jersey #, year in college, etc.)
        ^ references parent Player
        + contains a reference to Squad
        + contains a collection of PlayerStatSheets

        > PlayerStatSheet (a Player in a particular game)
            @ Contains performance statistics for a particular Game
            ^ references parent SquadMember
            + references particular Game
            

> Game
    + contains collection of opponents in Game
    + contains collection of PlayerStatSheets for players in Game
    + contains reference to winner
    + contains reference to loser


> TeamAlias
    ^ references team being aliases
    @ contains alternate name of team (e.g., 'Pitt' instead of 'Pittsburgh')


See class-specific documentation for more information.


Copyright (c) 2013 Joe Nudell.
Freely distributable under the MIT License.
'''


# Third Party Modules
from sqlalchemy import *
from sqlalchemy.orm import relationship, backref, sessionmaker, reconstructor
from sqlalchemy.ext.declarative import declarative_base
from collections import OrderedDict
# Standard Library
import re
import datetime

# Try to load fuzzy text matching libraries, in order of (my) preference
fuzzymatch = None
# Written in C. Standard Levenstein algorithm
try:
    from Levenstein import ratio as fuzzymatch
except ImportError:
    # Written in Python. Levenstein is available in this package, but try
    # jaro_winkler, which I've had better luck with.
    try:
        from jellyfish import jaro_winkler as fuzzymatch
    except ImportError:
        # Default to stdlib difflib, which isn't a really good approach,
        # but it'll do in a pinch.
        from difflib import SequenceMatcher
        fuzzymatch = lambda a,b: SequenceMatcher(None, a,b).ratio()



## ---- CLASSES ---- //



Base = declarative_base()



# - Schedule -- /
'''Schedule is the cross-reference table for establishing the many-to-many
map from Squads to Games.'''
schedule = Table('schedule', Base.metadata,
    Column('game_id', Integer, ForeignKey('game.id')),
    Column('squad_id', Integer, ForeignKey('squad.id')),
    Column('type', Enum('home', 'away'))
)
    



# - Game -- /
class Game(Base):
    '''Game holds references to two Squads. Holds a collection of references
    to SquadMembers (from both Squads). Allow for specification of Winner.
    Also hold vital statistics such as where and when.

    Many-to-many map to Squads via Schedule, one-to-many map to
    PlayerStatSheets.'''
    __tablename__ = 'game'
    
    id = Column(Integer, primary_key=True)

    location = Column(String)
    date = Column(Date)
    
    # Map squads playing via schedule cross-reference Table
    opponents = relationship('Squad',
                             secondary=schedule,
                             backref=backref('schedule', order_by=date))

    winner_id = Column(Integer, ForeignKey('squad.id'))
    winner = relationship('Squad', foreign_keys=[winner_id],
                          backref=backref('wins', order_by=date))
    winner_score = Column(Integer)

    loser_id = Column(Integer, ForeignKey('squad.id'))
    loser = relationship('Squad', foreign_keys=[loser_id],
                         backref=backref('losses', order_by=date))
    loser_score = Column(Integer)
    
    # Post season
    postseason = Column(Boolean)

    arena = Column(String)
    # NOTE boxscore = one-to-many map to PlayerStatSheets.

    def __init__(self, first_team, second_team, date, location=None,
                 loser=None, winner=None,
                 winner_score=None, loser_score=None, postseason=False):
        # First and 2nd Teams and date are mandatory. Location is optional. If
        # the location is specified, make it equal to one of the Team's names,
        # if that team was the home team. Sometimes (especially in the
        # Tournament) the concept of home vs. away teams is essentially
        # meaningless, so this isn't actually that important. Specify loser
        # and winner optionally; if one is missing, the other will be inferred.
        # Future games' winners and losers don't have to sbe specified at all.
        self.opponents.append(first_team)
        self.opponents.append(second_team)
        self.date = date
        self.arena = location
        
        self.postseason = postseason
        
        self.winner_score = winner_score
        self.loser_score = loser_score

        if loser is not None:
            self.loser = loser
            if winner is None:
                if self.loser.id==self.home_id:
                    # Away team was winner
                    self.winner = away_team
                else:
                    # Home team was winner
                    self.winner = home_team

        if winner is not None:
            self.winner = winner
            if loser is None:
                if self.winner.id==self.home_id:
                    # Away team was loser
                    self.loser = away_team
                else:
                    # Home team was loser
                    self.winner = home_team
    
    def __repr__(self):
        teams = "%s vs. %s" % (self.opponents[0].team.name,
                                self.opponents[1].team.name)
        date = self.date.strftime('%h %d, %Y')
        return "<Game('%s', '%s')>" % (teams, date)




# - Player -- /
class Player(Base):
    '''Players hold vital statistics like height, number, position, etc.
    They do NOT themselves contain and performance statistics or team
    affiliation. Instead, they possess a one-to-many mapping to SquadMembers,
    which are essentially chrono-sensitive versions of the Player. For
    example, a Player's corresponding SquadMember from 2010-11 will not
    have access to that Player's statistics from 2011-12, nor will these
    latest statistics be incorporated into the earlier SquadMember's record.
    This allows for more realistic simulations.'''
    __tablename__ = "player"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    middle_name = Column(String)
    last_name = Column(String, nullable=False)
    name_suffix = Column(String)

    height = Column(Integer)        # Inches
    weight = Column(Integer)        # Pounds
    position = Column(String)

    # NOTE career = one-to-many mapping to SquadMembers

    def __init__(self, first_name, last_name, middle_name=None,
                 name_suffix=None, id=None, height=None,
                 position=None):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.name_suffix = name_suffix

        if id is not None: self.id = id
        if height is not None: self.height = height
        if position is not None: self.position = position
        
    @reconstructor
    def _reconstruct(self):
        # Implement this to calculate transient properties of object
        pass
    
    def __repr__(self):
        return "<Player('%s %s')>" % (self.first_name, self.last_name)



# - SquadMember -- /
class SquadMember(Base):
    '''This is the class that holds individual game statistics for a Player.
    Many-to-one maps to Player, Squad, and Game'''
    __tablename__ = 'squadmember'

    id = Column(Integer, primary_key=True)
    
    player_id = Column(Integer, ForeignKey('player.id'))
    player = relationship('Player', backref=backref('career', order_by=id))

    squad_id = Column(Integer, ForeignKey('squad.id'))
    squad = relationship('Squad', backref=backref('roster', order_by=id)) 

    # NOTE statsheets = one-to-many mapping to PlayerStatSheets

    # Vital-ish stats
    jersey = Column(Integer)
    year = Column(String)       # i.e., year in college (Freshman, etc.)

    def __init__(self, player, squad, jersey=None, year=None):
        self.player = player
        self.squad = squad
        if jersey is not None:
            self.jersey = jersey
        if year is not None:
            self.year = year

    @reconstructor
    def _reconstruct(self):
        # Calculate transient stats here
        return

    def __repr__(self):
        return "<SquadMember('%s %s', '%s', '%s')>" % \
                (self.player.first_name, self.player.last_name,
                 self.squad.team.name, self.squad.season)




# - PlayerStatSheet -- /
class PlayerStatSheet(Base):
    '''Contains the stats of one SquadMember in one Game'''
    __tablename__ = 'playerstatsheet'

    id = Column(Integer, primary_key=True)

    squadmember_id = Column(Integer, ForeignKey('squadmember.id'))
    squadmember = relationship('SquadMember',
                               backref=backref('statsheets', order_by=id))

    game_id = Column(Integer, ForeignKey('game.id'))
    game = relationship('Game', backref=backref('boxscore', order_by=id))

    # Individual Game Statistics
    # TODO Lazy or eager calculation of career statistics?
    #games_played = Column(Integer)
    minutes_played = Column(Float)
    field_goals_made = Column(Integer)
    field_goals_attempted = Column(Integer)
    #field_goal_percentage = Column(Float)
    threes_made = Column(Integer)
    threes_attempted = Column(Integer)
    #three_percentage = Column(Float)
    free_throws_made = Column(Integer)
    free_throws_attempted = Column(Integer)
    #free_throw_percentage = Columns(Float)
    points = Column(Integer)
    #points_per_game = Column(Float)
    offensive_rebounds = Column(Integer)
    defensive_rebounds = Column(Integer)
    rebounds = Column(Integer)
    #rebounds_per_game = Column(Float)
    assists = Column(Integer)
    turnovers = Column(Integer)
    steals = Column(Integer)
    blocks = Column(Integer)
    fouls = Column(Integer)
    #double_doubles = Column(Integer)
    #triple_doubles = Column(Integer)

    def __repr__(self):
        name = "%s %s" % (self.squadmember.player.first_name,
                          self.squadmember.player.last_name)
        game = "%s vs. %s" % (self.game.opponents[0].team.name,
                              self.game.opponents[1].team.name)
        date = self.game.date.strftime('%h %d, %Y')
        return "<PlayerStatSheet('%s', '%s', '%s')>" % (name, game, date)
    



# - Squad -- /
class Squad(Base):
    '''Squads contain the roster and regular season record of a Team in
    a given season.

    One-to-many maps to SquadMembers, Games. Many-to-one map to Team.'''
    __tablename__ = 'squad'

    id = Column(Integer, primary_key=True)
    season = Column(String, nullable=False)

    team_id = Column(Integer, ForeignKey('team.id'))
    team = relationship("Team", backref=backref('squads', order_by=id))

    # NOTE roster = one-to-many map to SquadMembers
    # NOTE schedule = many-to-many map to Games
    # NOTE wins = one-to-many map to Games
    # NOTE losses = one-to-many map to Games

    # TODO Is it worth storing stats about the whole team?
    # Am I going to scrape stats that can't be calculated from indivual
    # Player records and the schedule?
    # Am I going to _use_ such stats?
    rpi = Column(Float)
    seed = Column(Integer)
    conference = Column(String)
    rank = Column(Integer)

    def __init__(self, season, team=None):
        self.season = season
        if team is not None:
            self.team = team

    def __repr__(self):
        return "<Squad('%s', '%s')>" % (self.team.name, self.season)



# - Team -- /
class Team(Base):
    '''Teams contain a relationship to Squads for any available years.
    Also contain relationships to alternate team names.

    Note that IDs have been assigned explicitly to match those used by
    NCAA.com to make record linkage easier. The alternate team names
    and fuzzy matching capabilities are just in case another source is
    used.

    One-to-many maps to Squads and TeamAliases.'''
    __tablename__ = 'team'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    # NOTE squads = one-to-many map to Squads
    # NOTE aliases = one-to-many map to TeamAliases

    def __init__(self, name, id=None):
        self.name = name
        if id is not None:
            self.id = id

    def __repr__(self):
        return "<Team('%s')>" % self.name



# - TeamAlias -- /
class TeamAlias(Base):
    '''TeamAlias is used for record linkage. When querying the database for a
    Team by name it is not necessarily (read: usually) the case that there is
    a standardized way of referring to the Team. Different sources abbreviate
    teams in different ways, e.g. 'Pitt' versus 'Pittsburgh.' This class helps
    mitigate this problem by keeping track of different ways of referring to
    a team. Names in this class are normalized by entirely removing all
    non-alpha-numeric characters and transforming to upper case.

    TeamAliases are in a many-to-one relationship with Teams'''
    __tablename__ = 'teamalias'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    team_id = Column(Integer, ForeignKey('team.id'))
    team = relationship("Team", backref=backref('aliases', order_by=id))

    def __init__(self, name):
        self.name = normalize_name(name)

    def __repr__(self):
        return "<TeamAlias('%s', '%s')>" % (self.team.name, self.name)




#class Tournament(Base):
#    '''Tournament is a binary tree, made up of TournamentNodes.'''
    




# -- HELPER FUNCTIONS -- //
def normalize_name(name):
    '''Normalize team name to upper case and with no non-alpha-numeric chars.'''
    return re.sub(r'[^\w\d]', '', name.upper())



def get_team_by_name(session, name):
    '''Convenience function for searching teams by name. Returns a Team
    if one is found, otherwise returns None.'''
    normalized_name = normalize_name(name)
    ta = session.query(TeamAlias).filter_by(name=normalized_name).first()
    if ta is None:
        return None
    return ta.team



def fuzzy_match_team(session, name, threshold=.9, matcher=fuzzymatch):
    '''Convenience function that tries to fuzzily match the given name to
    Teams in database. Returns a list of (unique) teams that are above a
    certain threshold. Note that this module tries to load any one of several
    fuzzy matching libraries in order of quality (subjective) and interfaces
    with the first one it finds. Last choice is standard library difflib,
    which isn't great for this task but it'll work in a pinch.
    
    Returns OrderedDict of IDs of Teams hwose name (any variation of it)
    matches the provided `name` above a certain threshold. Keys are IDs,
    values are match percentile.'''
    normalized_name = normalize_name(name)

    match_func = lambda s: matcher(normalized_name, s)

    # Create a function for the SQL to use
    c = session.bind.connect()
    c.connection.create_function('distance', 1, match_func)

    # Execute query
    query = "SELECT `team_id`, distance(name) \
             FROM `teamalias` \
             WHERE distance(name)>=:threshold"
    res = c.execute(query, dict(threshold=threshold))

    if res is None:
        return None

    unique_results = OrderedDict()
    for row in res:
        # Compact results into ordered dict by referenced Team name and store
        # highest score
        if unique_results.has_key(row[0]) and \
           unique_results[row[0]]>row[1]:
            # Stored match is higher
            continue
        unique_results[row[0]] = row[1]

    # Sort results and return
    return OrderedDict(sorted(unique_results.items(), key=lambda d: d[1]))




def load_db(path):
    '''Convenience function to make an engine and create a session. Returns
    new session.'''
    engine = create_engine('sqlite:///%s'%path)
    Session = sessionmaker(bind=engine)
    return Session()



if __name__=='__main__':
    # Might be useful to run in interactive mode and create session.
    from sys import argv, stderr, exit
    if len(argv)!=2:
        print >>stderr, "Need to specify path to DB"
        exit(1)
    engine = create_engine('sqlite:///%s'%argv[1])
    Session = sessionmaker(bind=engine)
    session = Session()

    print >>stderr, "\033[92mSession stored in `session` variable.\033[0m"
