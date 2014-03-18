# -*- coding: utf8 -*-
'''
export squads table to csv
'''

from sys import argv, stderr, stdout, exit, path
import os
lib_path = os.path.abspath('..')
path.append(lib_path)

import csv
from ncaalib.ncaa import *


if __name__=='__main__':

    if len(argv)!=2:
        print >>stderr, "Need to specify path to DB"
        exit(1)
    session = load_db(argv[1])

    print >>stderr, "\033[92mLoaded DB ... loading squads ...\033[0m"


    records = session.query(Squad).all()

    print >>stderr, "Done loading squads. Writing ..."

    writer = csv.writer(stdout)

    title = [
        'team_id',
        'team-year_id',
        'team_name',
        'season',
        'tournament_seed',
        'tournament_conference',
        'tournament_rank',
        'win_pct',
        'weighted_win_pct',
        'wins',
        'losses',
        'games_played',
        'rpi',
        'lsalpha',

        # derived sums
        'total_minutes_played',
        'total_field_goals_made',
        'total_field_goals_attempted',
        'total_threes_made',
        'total_threes_attempted',
        'total_free_throws_made',
        'total_free_throws_attempted',
        'total_points',
        'total_offensive_rebounds',
        'total_defensive_rebounds',
        'total_rebounds',
        'total_assists',
        'total_turnovers',
        'total_steals',
        'total_blocks',
        'total_fouls',

        # derived ratios
        'fg_pct',
        'threes_pct',
        'ft_pct',
        'avg_points_per_minute',
        'avg_shots_per_minute',

        # Averages
        'avg_field_goals_per_game',
        'avg_shots_per_game',
        'avg_threes_per_game',
        'avg_free_throws_per_game',
        'avg_points_per_game',
        'avg_rebounds_per_game',
        'avg_steals_per_game',
        'avg_assists_per_game',
        'avg_blocks_per_game',
        'avg_fouls_per_game',
        'avg_turnovers_per_game'
    ]

    writer.writerow(title)

    n = len(records)

    for i, record in enumerate(records):
        print >>stderr, "%d / %d\t%s ... " % (i, n, record.team.name)
        record.derive_stats()
        row = [
            record.team.id,
            record.id,
            record.team.name,
            record.season,
            record.seed,
            record.conference,
            record.rank,
            record.win_pct(),
            record.win_pct(True),
            len(record.get_wins()),
            len(record.get_losses()),
            len(record.schedule),
            record.get_rpi(),
            record.lsalpha,

            # derived sums
            record.stats.minutes_played,
            record.stats.field_goals_made,
            record.stats.field_goals_attempted,
            record.stats.threes_made,
            record.stats.threes_attempted,
            record.stats.free_throws_made,
            record.stats.free_throws_attempted,
            record.stats.points,
            record.stats.offensive_rebounds,
            record.stats.defensive_rebounds,
            record.stats.rebounds,
            record.stats.assists,
            record.stats.turnovers,
            record.stats.steals,
            record.stats.blocks,
            record.stats.fouls,

            # derived ratios
            record.stats.fg_pct,
            record.stats.threes_pct,
            record.stats.ft_pct,
            record.stats.ppm,
            record.stats.lpm,

            # Averages
            record.stats.field_goal_avg,
            record.stats.looks_avg,
            record.stats.threes_avg,
            record.stats.free_throws_avg,
            record.stats.points_avg,
            record.stats.rebounds_avg,
            record.stats.steals_avg,
            record.stats.assists_avg,
            record.stats.blocks_avg,
            record.stats.fouls_avg,
            record.stats.turnovers_avg,
        ]

        writer.writerow(row)


