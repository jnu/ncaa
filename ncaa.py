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
# Standard Library
import re
import json
import datetime
import operator
from collections import OrderedDict, defaultdict
from random import randint, seed
seed(datetime.datetime.now())


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

# Optional 3rd-party libraries
try:
    import numpy as np
except ImportError:
    # There's some type checking that involves numpy, so just fudge it
    # if numpy is not available
    class NPFake(object):
        pass
    np = NPFake()
    np.ndarray = type(list)



## ---- CLASSES ---- //




Base = declarative_base()




# - Schedule -- /
'''Schedule is the cross-reference table for establishing the many-to-many
map from Squads to Games.'''
schedule = Table('schedule', Base.metadata,
    Column('game_id', Integer, ForeignKey('game.id', onupdate='cascade')),
    Column('squad_id', Integer, ForeignKey('squad.id', onupdate='cascade')),
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
    
    discriminator = Column(String)
    __mapper_args__ = {'polymorphic_on' : discriminator}
    
    id = Column(Integer, primary_key=True)

    date = Column(Date)
    
    # Map squads playing via schedule cross-reference Table
    opponents = relationship('Squad',
                             secondary=schedule,
                             backref=backref('schedule', order_by=date))

    winner_id = Column(Integer, ForeignKey('squad.id', onupdate='cascade'))
    winner = relationship('Squad', foreign_keys=[winner_id],
                          backref=backref('wins', order_by=date))
    winner_score = Column(Integer)

    loser_id = Column(Integer, ForeignKey('squad.id', onupdate='cascade'))
    loser = relationship('Squad', foreign_keys=[loser_id],
                         backref=backref('losses', order_by=date))
    loser_score = Column(Integer)
    
    # Post season
    postseason = Column(Boolean)
    overtime = Column(Integer)

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
        # Future games' winners and losers don't have to be specified at all.
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

    @staticmethod
    def get_games_with_data(session, limit=None, random=True):
        '''Query the database only for Games that have stats for both
        teams. Optionally specify whether random sample should be obtained
        (by default, yes) and how many Games to return (by default, all).'''
        q_incomplete = session.query(Game)\
                              .join(Game.opponents)\
                              .filter(Game.opponents.any(Squad.roster==None))
        q_tournament = session.query(Game).filter(Game.postseason==True)
        q_nowinner = session.query(Game).filter(Game.winner==None)
        
        q2 = session.query(Game).except_(q_incomplete,
                                         q_tournament,
                                         q_nowinner)
        
        if random:
            q2 = q2.order_by(func.random())
        
        if limit is not None:
            q2 = q2.limit(limit)
        
        return q2.all()
        
    
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
        
    def __repr__(self):
        return "<Player('%s %s')>" % (self.first_name, self.last_name)




# - SquadMember -- /
class SquadMember(Base):
    '''This is the class that holds individual game statistics for a Player.
    Many-to-one maps to Player, Squad, and Game'''
    __tablename__ = 'squadmember'

    id = Column(Integer, primary_key=True)
    
    player_id = Column(Integer, ForeignKey('player.id', onupdate='cascade'))
    player = relationship('Player', backref=backref('career', order_by=id))

    squad_id = Column(Integer, ForeignKey('squad.id', onupdate='cascade'))
    squad = relationship('Squad', backref=backref('roster', order_by=id))
    
    stats_id = Column(Integer, ForeignKey('statscache.id', onupdate='cascade'))
    stats = relationship('SquadMemberDerivedStats', backref=backref('referent',
                                                               uselist=False,
                                                               order_by=id))

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
        if self.stats is None:
            self.derive_stats()

    def derive_stats(self):
        '''Calculate and cache derived statistics'''
        derived_stats = defaultdict(float)
        
        for statsheet in self.statsheets:
            # Sum statsheets
            minutes_played = statsheet.minutes_played
            
            if minutes_played:
                derived_stats['games_played'] += 1.0
            else:
                # Played 0 minutes in this game, move on
                continue
                
            for stat in statsheet.stats:
                val = getattr(statsheet, stat)
                if val is None:
                    # Data is N/A. Interpret as 0.
                    continue
                derived_stats[stat] += val
    
        # Calculate percentages and averages
        for newfield, rat in DerivedStats.pctfields.items():
            num, den = rat
            if type(den) is str:
                den = derived_stats[den]
            if den == 0.0:
                # Denominator is 0, interpret error as 0.
                derived_stats[newfield] = 0.0
            else:
                derived_stats[newfield] = derived_stats[num] / den

        # Store the derived stats
        if self.stats is not None:
            # Update old entry
            for stat, val in derived_stats.items():
                self.stats[stat] = val
        else:
            # Create new entry
            self.stats = SquadMemberDerivedStats(derived_stats)

    def __repr__(self):
        return "<SquadMember('%s %s', '%s', '%s')>" % \
                (self.player.first_name, self.player.last_name,
                 self.squad.team.name, self.squad.season)




# - PlayerStatSheet -- /
class PlayerStatSheet(Base):
    '''Contains the stats of one SquadMember in one Game'''
    __tablename__ = 'playerstatsheet'

    id = Column(Integer, primary_key=True)

    squadmember_id = Column(Integer, ForeignKey('squadmember.id',
                                                onupdate='cascade'))
    squadmember = relationship('SquadMember',
                               backref=backref('statsheets', order_by=id))

    game_id = Column(Integer, ForeignKey('game.id', onupdate='cascade'))
    game = relationship('Game', backref=backref('boxscore', order_by=id))

    # Individual Game Statistics
    minutes_played = Column(Float)
    field_goals_made = Column(Integer)
    field_goals_attempted = Column(Integer)
    threes_made = Column(Integer)
    threes_attempted = Column(Integer)
    free_throws_made = Column(Integer)
    free_throws_attempted = Column(Integer)
    points = Column(Integer)
    offensive_rebounds = Column(Integer)
    defensive_rebounds = Column(Integer)
    rebounds = Column(Integer)
    assists = Column(Integer)
    turnovers = Column(Integer)
    steals = Column(Integer)
    blocks = Column(Integer)
    fouls = Column(Integer)
    
    stats = [
        'minutes_played',
        'field_goals_made',
        'field_goals_attempted',
        'threes_made',
        'threes_attempted',
        'free_throws_made',
        'free_throws_attempted',
        'points',
        'offensive_rebounds',
        'defensive_rebounds',
        'rebounds',
        'assists',
        'turnovers',
        'steals',
        'blocks',
        'fouls',
    ]

    def __repr__(self):
        name = "%s %s" % (self.squadmember.player.first_name,
                          self.squadmember.player.last_name)
        game = "%s vs. %s" % (self.game.opponents[0].team.name,
                              self.game.opponents[1].team.name)
        date = self.game.date.strftime('%h %d, %Y')
        return "<PlayerStatSheet('%s', '%s', '%s')>" % (name, game, date)
    



class DerivedStats(Base):
    __tablename__ = 'statscache'
    id = Column(Integer, primary_key=True)
    
    # Polymorphic: DerivedStatsPlayer, DerivedStatsSquad
    type = Column(String)
    __mapper_args__ = {'polymorphic_on' : type}
    
    # One-to-One relationship with Squad / SquadMember

    # Derived statistics -- all calculated on load, stored in self.stats
    sumfields = [
        # Sums
        'minutes_played',
        'field_goals_made',
        'field_goals_attempted',
        'threes_made',
        'threes_attempted',
        'free_throws_made',
        'free_throws_attempted',
        'points',
        'offensive_rebounds',
        'defensive_rebounds',
        'rebounds',
        'assists',
        'turnovers',
        'steals',
        'blocks',
        'fouls',
    ]
    
    pctfields = {
        # Ratios
        'fg_pct'     : ('field_goals_made', 'field_goals_attempted'),
        'threes_pct' : ('threes_made', 'threes_attempted'),
        'ft_pct'     : ('free_throws_made', 'free_throws_attempted'),
        'ppm'        : ('points', 'minutes_played'),
        'lpm'        : ('field_goals_attempted', 'minutes_played'),
        # Averages
        'field_goal_avg' : ('field_goals_made', 'games_played'),
        'looks_avg'      : ('field_goals_attempted', 'games_played'),
        'threes_avg'     : ('threes_made', 'games_played'),
        'free_throws_avg': ('free_throws_made', 'games_played'),
        'points_avg'     : ('points', 'games_played'),
        'rebounds_avg'   : ('rebounds', 'games_played'),
        'steals_avg'     : ('steals', 'games_played'),
        'assists_avg'    : ('assists', 'games_played'),
        'blocks_avg'     : ('blocks', 'games_played'),
        'fouls_avg'      : ('fouls', 'games_played'),
        'turnovers_avg'  : ('turnovers', 'games_played'),
    }
    
    # Sums
    games_played = Column(Float)
    minutes_played = Column(Float)
    field_goals_made = Column(Float)
    field_goals_attempted = Column(Float)
    threes_made = Column(Float)
    threes_attempted = Column(Float)
    free_throws_made = Column(Float)
    free_throws_attempted = Column(Float)
    points = Column(Float)
    offensive_rebounds = Column(Float)
    defensive_rebounds = Column(Float)
    rebounds = Column(Float)
    assists = Column(Float)
    turnovers = Column(Float)
    steals = Column(Float)
    blocks = Column(Float)
    fouls = Column(Float)

    # Ratios
    fg_pct = Column(Float)
    threes_pct = Column(Float)
    ft_pct = Column(Float)
    ppm = Column(Float)
    lpm = Column(Float)
    
    # Averages
    field_goal_avg = Column(Float)
    looks_avg = Column(Float)
    threes_avg = Column(Float)
    free_throws_avg = Column(Float)
    points_avg = Column(Float)
    rebounds_avg = Column(Float)
    steals_avg = Column(Float)
    assists_avg = Column(Float)
    blocks_avg = Column(Float)
    fouls_avg = Column(Float)
    turnovers_avg = Column(Float)

    def __init__(self, stats):
        '''Load stats into object'''
        for stat, val in stats.items():
            setattr(self, stat, val)

    def __getitem__(self, item):
        '''Alias of getattr'''
        return getattr(self, item)

    def __setitem__(self, item, val):
        '''Alias of setattr'''
        return setattr(self, item, val)

    def items(self):
        '''For iteration'''
        keys = self.sumfields + self.pctfields.keys()
        return [(key, getattr(self, key)) for key in keys]

    def __repr__(self):
        items = ["'%s': %f" % (k, v) for k, v in self.items()]
        return "<DerivedStats(%s)>" % ', '.join(items)


class SquadMemberDerivedStats(DerivedStats):
    __mapper_args__ = {'polymorphic_identity' : 'squadmember'}
    # Note referent is one-to-one mapping to SquadMember


class SquadDerivedStats(DerivedStats):
    __mapper_args__ = {'polymorphic_identity' : 'squad'}
    # NOTE referent is one-to-one mapping to Squad
    



# - Squad -- /
class Squad(Base):
    '''Squads contain the roster and regular season record of a Team in
    a given season.

    One-to-many maps to SquadMembers, Games. Many-to-one map to Team.'''
    __tablename__ = 'squad'

    id = Column(Integer, primary_key=True)
    season = Column(String, nullable=False)

    team_id = Column(Integer, ForeignKey('team.id', onupdate='cascade'))
    team = relationship("Team", backref=backref('squads', order_by=id))

    stats_id = Column(Integer, ForeignKey('statscache.id', onupdate='cascade'))
    stats = relationship('SquadDerivedStats', backref=backref('referent',
                                                              uselist=False,
                                                              order_by=id))

    # NOTE roster = one-to-many map to SquadMembers
    # NOTE schedule = many-to-many map to Games
    # NOTE wins = one-to-many map to Games
    # NOTE losses = one-to-many map to Games

    rpi = Column(Float)
    seed = Column(Integer)
    conference = Column(String)
    rank = Column(Integer)

    def __init__(self, season, team=None):
        self.season = season
        if team is not None:
            self.team = team
    
    @reconstructor
    def _reconstruct(self):
        if self.stats is None:
            self.derive_stats()
    
    def derive_stats(self):
        '''Derive statistics'''
        derived_stats = defaultdict(float)
        
        # Calculate sums
        for member in self.roster:
            member.derive_stats()
            for stat, val in member.stats.items():
                if val is None:
                    # No value here. Player wasn't prolific in this area.
                    continue
                derived_stats[stat] += val
    
        # Overwrite some aggregate stats with more useful values
        derived_stats['games_played'] = float(len(self.schedule))
    
        # Calculate percentages and averages        
        for newfield, rat in DerivedStats.pctfields.items():
            num, den = rat
            if type(den) is str:
                den = derived_stats[den]
            if den == 0:
                derived_stats[newfield] = 0
                continue
            derived_stats[newfield] = derived_stats[num] / den

        # Store derived stats in cache
        if self.stats is not None:
            # Update existing record
            for stat, val in derived_stats.items():
                self.stats[stat] = val
        else:
            # Create new record
            self.stats = SquadDerivedStats(derived_stats)

    @staticmethod
    def get(session, name, season):
        '''Get Squad in Season in DB (session) using a more forigiving
        search (through TeamAliases)'''
        tid = Team.get(session, name).id
        return session.query(Squad).filter(Squad.team_id==tid,
                                           Squad.season==season).one()

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
    
    @staticmethod
    def get(session, name):
        '''Convenience function for getting teams by name.'''
        normalized_name = normalize_name(name)
        ta = session.query(TeamAlias).filter_by(name=normalized_name).one()
        return ta.team
    
    @staticmethod
    def search(session, name, threshold=.9, method=fuzzymatch):
        '''Convenience function that tries to fuzzily match the given name to
        Teams in database. Returns a list of (unique) teams that are above a
        certain threshold. Note that this module tries to load any one of
        several fuzzy matching libraries in order of quality (subjective) and
        interfaces with the first one it finds. Last choice is standard library
        difflib, which isn't great for this task but it'll work in a pinch.
    
        Returns OrderedDict of IDs of Teams hwose name (any variation of it)
        matches the provided `name` above a certain threshold. Keys are IDs,
        values are match percentile.'''
        normalized_name = normalize_name(name)

        match_func = lambda s: method(normalized_name, s)

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
            # Compact results into ordered dict by referenced Team name and
            # store highest score
            if unique_results.has_key(row[0]) and \
            unique_results[row[0]]>row[1]:
                # Stored match is higher
                continue
            unique_results[row[0]] = row[1]

        # Sort results and return
        s = OrderedDict(sorted(unique_results.items(), key=lambda d: d[1]))
        return [(session.query(Team).get(k), v) for k,v in s.items()]

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

    team_id = Column(Integer, ForeignKey('team.id', onupdate='cascade'))
    team = relationship("Team", backref=backref('aliases', order_by=id))

    def __init__(self, name):
        self.name = normalize_name(name)

    def __repr__(self):
        return "<TeamAlias('%s', '%s')>" % (self.team.name, self.name)




# - TournamentGame -- /
class TournamentGame(Game):
    '''Subclass of Game. Polymorphic: TournamentGame can stand in for Game.'''
    __tablename__ = 'tournygame'
    __mapper_args__ = {'polymorphic_identity' : 'tourneygame'}
    id = Column(Integer, ForeignKey('game.id'), primary_key=True)
    
    index = Column(Integer)

    tournament_id = Column(Integer, ForeignKey('tournament.id',
                                               onupdate='cascade'))
    tournament = relationship('Tournament',
                              backref=backref('games', order_by=index))
        
    def __init__(self, tournament, index):
        self.index = index
        self.tournament = tournament
        self.accurate = None
        self.postseason = True

    def next(self):
        next_idx = ((self.index+1) / 2) - 1
        if next_idx < 0:
            return None
        return self.tournament.get_by_id(next_idx)

    def __iter__(self):
        return self

    def __repr__(self):
        round, region, n = self.tournament.lookup(self.index)
        return "<TournamentGame('%s', '%s', '%s', '%s')>" \
                % (self.tournament.season, round, region, n)




# - Tournament -- /
class Tournament(Base):
    '''Tournament is an iterable binary heap, which is accessible using
    common names for rounds and regions. These names are configurable on
    initialization. Games are stored as TournamentGames. Neither of the
    Tournament data structures are stored in the stats DB.'''
    __tablename__ = 'tournament'

    id = Column(Integer, primary_key=True)

    regions_store = Column(String)
    rounds_store = Column(String) 
    delim = Column(String)
    season = Column(String)
    
    # Transient default scores for pointsmap - not saved in DB
    # Converted to pointsmap based on round names in _reconstruct().
    # Ordered from Championship (0th element) to 1st round (5th element).
    # This is the default value; it's the system used by ESPN.
    roundpoints = [320, 160, 80, 40, 20, 10]

    # Note: games = many-to-one relationship to Tournament.games

    def __init__(self, season,
                 regions=['North', 'East', 'South', 'West'],
                 rounds=None, delim='/'):

        self.season = season
        self.regions_store = '|'.join(regions)
        self.regions = regions # transient
        
        self.delim = delim

        if rounds is not None:
            self.rounds_store = '|'.join(rounds)

        self._reconstruct()

    @reconstructor
    def _reconstruct(self):
        '''Reconstruct transient attributes from DB values'''
        if self.rounds_store is None:
            self.rounds = ['finals', 'finalfour',
                            'elite8', 'sweet16', '2nd', '1st']
        else:
            self.rounds = self.rounds_store.split('|')

        if not hasattr(self, 'regions'):
            self.regions = self.regions_store.split('|')

        if self.games is None or not len(self.games):
            self.games = [TournamentGame(self, i)
                            for i in range((1<<len(self.rounds))-1)]

        # Pair default round points with round labels from DB
        self.pointsmap = dict(zip(self.rounds, self.roundpoints))
        self.points = None

    def lookup(self, n):
        # Find depth in tree
        n += 1
        round_id = log2(n)

        # Find horizontal offset in tree
        k = n - (1<<round_id)

        # Calculate number of elements in each region in this level of tree
        gsize = (1<<round_id) / len(self.regions)

        # If gsize is 0, special case.
        if gsize==0:
            if round_id==0:
                return (self.rounds[round_id], None, None,)
            else:
                tname = ""
                if n<=2:
                    # First two regions coincide in FinalFour
                    tname = self.delim.join(self.regions[:2])
                else:
                    # Second two regions coincide in FinalFour
                    tname = self.delim.join(self.regions[-2:])
                return (self.rounds[round_id], tname, None)

        # Find regional ID
        region_id = k / gsize

        # And position within region
        num = k % gsize

        return (self.rounds[round_id], self.regions[region_id], num)

    def set(self, data, round_, region=0, n=0):
        idx = self.index(round_, region, n)
        self.games[idx] = data
         
    def index(self, round_, region=0, n=0):
        if type(region) is not int:
            if region is None:
                region = 0
            else:
                if self.delim in region:
                    region = region.partition(self.delim)[0]
                region = self.regions.index(region)
        
        if type(round_) is not int:
            round_ = self.rounds.index(round_)

        # Translate depth to row-initial index
        rowinitid = (1<<round_) - 1

        # Get number of games in each region
        gsize = (1<<round_) / 4
        
        # Special case if finalfour or finals
        if not gsize:
            if not round_:
                # Finals
                return 0
            else:
                # Final four
                return (region/2)+1

        # Find horizontal offset in row
        return rowinitid + (region*gsize) + n
        
    def get(self, round_, region=0, n=0):
        idx = self.index(round_, region, n)
        return self.games[idx]

    def get_by_id(self, n):
        return self.games[n]

    def set_by_id(self, n, data):
        self.games[n] = data

    def __getitem__(self, n):
        return self.games[n]

    def __setitem__(self, n, data):
        self.games[n] = data

    def simulate(self, decide):
        '''Simulate tournament with given decision function. Decision fn must
        return either Game (with 'winner' attribute filled out), a tuple of
        Squads in the form [winner, loser], the Squad that won, or the index
        in Game.opponents of the given Game of the winner.'''
        for tgame in self:
            if len(tgame.opponents)!=2:
                raise IndexError
            r = decide(tgame)
            if type(r) is Game:
                tgame = r
            elif type(r) is tuple or type(r) is list:
                tgame.winner = r[0]
                tgame.loser = r[1]
            elif type(r) is Squad:
                tgame.winner = r
                lid = (tgame.opponents.index(r)+1)%2
                tgame.loser = tgame.opponents[lid]
            elif type(r) is int:
                tgame.winner = tgame.opponents[r]
                tgame.loser = tgame.opponents[(r+1)%2]
            elif type(r) is np.ndarray or type(r) is list:
                i = int(r[0])
                tgame.winner = tgame.opponents[i]
                tgame.loser = tgame.opponents[(i+1)%2]
            else:
                raise NotImplementedError("Unsupported return type %s"\
                                            % type(r))

            nextroundgame = tgame.next()
            
            if nextroundgame:
                nextroundgame.opponents.append(tgame.winner)

    def __iter__(self):
        class TournamentIterator(object):
            def __init__(self, m):
                self.__o = m
                self.index = len(m)

            def next(self):
                if self.index==0:
                    raise StopIteration
                self.index -= 1
                return self.__o.get_by_id(self.index)
        return TournamentIterator(self)

    def __len__(self):
        return len(self.games)

    def __repr__(self):
        return "<Tournament('%s')>" % self.season
    
    def empty_bracket(self, name=None):
        '''Return a clone of this Tournament that has not been filled out,
        except for the first round. Designate its moniker.'''
        if name is None:
            name = "%s-empty-%d" % (self.season, randint(0,1000000))
        
        newtourny = Tournament(name, rounds=self.rounds, regions=self.regions,
                               delim='/')
        # Get index - start of first round
        fr_start = self.index('1st')
        # Iterate to end of Tournament, copy TournamentGame opponents
        for i in range(fr_start, len(self)):
            newtourny[i].opponents = [t for t in self[i].opponents]
    
        # Return new Tournament
        return newtourny
        

    def export(self, format='heap'):
        '''Serialize tournament. Supports to methods of serialization. First
        is essentially a copy of the heap. Second is a nested tree. By default
        outputs heap.'''
        formats = ['heap', 'nested']
        format = format.lower()
        if format not in formats:
            raise NotImplementedError("Format %s not implemented." % format)
        
        # Create object wrapper for output
        output = {
            'regions' : self.regions,
            'rounds' : self.rounds,
            'season' : self.season,
            'nodes' : []
        }
        
        def _createNode(id_, squad, score, children=None):
            # Used to specify consistent structure of nodes.
            node = {
                'id' : id_,
                'name' : squad.team.name,
                'data' : {
                    'sid' : squad.id,
                    'seed' : squad.seed,
                    'points' : score
                },
            }
            if children is not None:
                node['children'] = children
            return node
        
        ## Output algorithms
        
        if format=='heap':
            # Default format: Heap-list with some extra info. JSON.
            # Nodes are WINNERS (or opponents) of each game, not whole games
            heap = []
            for i in range(len(self)):
                # Iterate through games and store winners / scores / seeds
                # in heap
                heap.append(_createNode(i, self[i].winner,
                                        self[i].winner_score))

            first_round_id = log2(len(self))-1
            for i in range(first_round_id, len(self)):
                # Iterate through 1st round games and add opponents (and their
                # scores and stuff) to heap. Order by seed.
                ops = sorted(self[i].opponents,
                             key=lambda a: a.seed,
                             reverse=True);
                scores = [self[i].winner_score, self[i].loser_score]
                if ops[1] is self[i].winner:
                    # Make sure scores associate correctly with winner/loser
                    scores.reverse();
                for x in [0,1]:
                    heap.append(_createNode((i<<1)+1+x, ops[x], scores[x]))
            
            # Set nodes attribute of output structure
            output['nodes'] = heap
            
        ###
        
        elif format=='nested':
            # Javascript Infovis Toolkit (JSON)
            # Root at Champion.

            def _maketree(n=0, prev=None):
                # Build tree recursively
                currentsquad = None
                children = []
                score = None
                
                if n >= len(self):
                    # Leaf node - order by Seed. Use higher one when n is odd.
                    ops = sorted(self[prev].opponents,
                                 key=lambda a: a.seed, reverse=True)
                    currentsquad = ops[n%2]
                else:
                    # Intermediate node (winner of game at self[n])
                    currentsquad = self[n].winner
                    children = [_maketree(2*n+1, n),
                                _maketree(2*n+2, n)]
            
                if prev is not None:
                    # Get points scored in game
                    if currentsquad is self[prev].winner:
                        score = self[prev].winner_score
                    elif currentsquad is self[prev].loser:
                        score = self[prev].loser_score
                    
                # Construct node and return
                return _createNode(n, currentsquad, score, children)
            
            # Create the structure, store in output object
            output['nodes'] = _maketree()
            ###
            
        # Serialize output
        return json.dumps(output)

    def score(self, realtourny, pointsmap=None):
        '''Score this Tournament based on the actual results. By default
        uses the scoring system used by ESPN. Optionally pass a dictionary
        mapping round labels to points for correct games in that round. Also
        may pass a list with such values, listing points for each round in
        order starting from the Championship and ending with the 1st round.
        If you pass a value here, it is saved as the default for this session,
        though it will never be persisted in the database. Returns score.
        Score is also preserved in self.score, though it is never persisted.'''
        if type(pointsmap) is list:
            # Given list - pair with round labels in order, championship first.
            pointsmap = dict(zip(self.rounds, pointsmap))
            self.pointsmap = pointsmap
        elif type(pointsmap) is dict:
            # Given dictionary mapping round labels to points. Make sure there
            # is a bijection between its keys and self.rounds. If not, raise
            # an error.
            for key, val in pointsmap.items():
                if key not in self.rounds:
                    raise NameError("Tried to map value %d \
to unknown round %s" % (val, key))
                else:
                    self.pointsmap[key] = val
        elif pointsmap is not None:
            # Give something that isn't None, a list, or a dict
            raise ValueError("pointsmap something other than list or dict")

        # Correct Tournament
        self.correct(realtourny)

        # Score Tournament (sum everywhere TournamentGame is accurate),
        # multiplied by the points awarded for that round.
        self.points = 0
        for game in self.games:
            if game.accurate:
                # log2 of index in heap gives round number
                roundlbl = self.rounds[log2(game.index+1)]
                self.points += self.pointsmap[roundlbl]

        return self.points
        
    

    def correct(self, realtourny):
        '''Correct this Tournament based on actual results Tournament.
        Sets the 'accurate' attribute on TournamentGames to True if correct,
        False if incorrect, and None if unavailable (e.g., when the game
        hasn't been played yet).'''
        for i in range(len(realtourny)):
            if realtourny[i].winner is None:
                self[i].accurate = None
            else:
                self[i].accurate = realtourny[i].winner == self[i].winner




# -- HELPER FUNCTIONS -- //
def normalize_name(name):
    '''Normalize team name to upper case and with no non-alpha-numeric chars.'''
    return re.sub(r'[^\w\d]', '', name.upper())




def log2(x):
    t = 0
    while x > 1:
        x >>= 1
        t += 1
    return t




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
