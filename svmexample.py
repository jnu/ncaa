#-*-coding:utf8-*-
'''
$ python ncaa2013/svmexample.py

Demonstrates how to train a Support Vector Machine using a random
sample of Games from the database.

Copyright (c) 2013 Joseph Nudell
'''

from ncaalib.ncaa import *
from ncaalib.data import *
from ncaalib.grid_search import GridSearch, TournamentScorer
from ncaalib.aux.output import *
from sklearn.svm import SVC



# Define a feature extractor
def extract_features(squad1, squad2):
    '''What to give to SVM for classification? This example gives some
    offensive statistics from the first squad and some defensive stats from
    the second squad.'''
    if squad1.rpi is None: squad1.get_rpi()
    if squad2.rpi is None: squad2.get_rpi()
    
    r = {
        'fga' : squad1.stats.field_goal_avg,
        'fgb'  : squad2.stats.field_goal_avg,
        'rpia' : squad1.rpi,
        'rpib' : squad2.rpi,
        'lsa'  : squad1.lsalpha,
        'lsb'  : squad2.lsalpha,
        'reba' : squad1.stats.rebounds_avg,
        'rebb' : squad2.stats.rebounds_avg,
        'assa' : squad1.stats.assists_avg,
        'assb' : squad2.stats.assists_avg,
        'stlsa' : squad1.stats.steals_avg,
        'stlsb' : squad2.stats.steals_avg,
        'toa' : squad1.stats.turnovers_avg,
        'tob' : squad2.stats.turnovers_avg,
        'blksa' : squad1.stats.blocks_avg,
        'blksb' : squad2.stats.blocks_avg,
        'ptsa' : squad1.stats.points_avg,
        'ptsb' : squad2.stats.points_avg,
    }
    if r['lsa'] is None or r['lsb'] is None:
        r['lsa'] = r['lsb'] = 100.
    return {
        'fg' : r['fga'] - r['fgb'],
        'ls' : r['lsa'] - r['lsb'],
        'rpi': r['rpia'] - r['rpib'],
        'reb': r['reba'] - r['rebb'],
        'ass': r['assa'] - r['assb'],
        'stl': r['stlsa'] - r['stlsb'],
        'to' : r['toa'] - r['tob'],
        'blk': r['blksa'] - r['blksb'],
        'pts': r['ptsa'] - r['ptsb'],
    }
    #return r




if __name__=='__main__':
    '''Run a demo that trains two classifiers on a random sample of games from
    the database. The first classifier uses the 1st Squad's offense against
    the 2nd Squad's defense, and the second classifier is trained on the
    reverse of that. A final prediction is made by taking the classifier
    that is maximally confident in its prediction. (Note, would be better to
    use Bayes Optimal Classifier.)'''
    
    # Connect to database
    session = load_db('data/ncaa.db')

    # Get a random sample of games from the DB.
    print_info("Creating sample from games in DB")
    some_games = Game.get_games_with_data(session, limit=500)
    sample = []
    
    for i, game in enumerate(some_games):
        # Extract features and label the Games. 
        print_comment("Calculating stats for squads in game %s ... " % i)
        
        opponents = [squad for squad in game.opponents]
        winner = opponents.index(game.winner)
    
        # Extract features and compile sample
        ft = extract_features(*opponents)
        sample.append((ft, str(winner),))
    

    print_info("Creating and normalizing data set ...")
    # Create DataSet
    data = DataSet(sample, split=1)

    print_info("Constructing grid for optimizing hyperparameters ...")
    # Create Grid to search
    grid = [
        {
            'kernel' : ['rbf'],
            'C'      : [2**i for i in np.arange(-5., 15., 1.)],
            'gamma'  : [2**i for i in np.arange(-15., 3., 1.)],
        },
        {
            'kernel' : ['poly'],
            'C'      : [2**i for i in np.arange(-5., 3., .5)],
            'degree' : [2,3],
        }
    ]

    tourny_years = ['2009-10', '2010-11', '2011-12']
    scorer = TournamentScorer(session,
                              lambda *g: data.convert(extract_features(*g)),
                              seasons=tourny_years,
                              normalize=data.normalize)

    classifier = GridSearch(SVC(probability=True), grid, scoring=scorer,
                            verbose=3, refit=True, n_jobs=1)

    # Train classifier
    print_info("Searching for optimal classifier ...")
    classifier.fit(*data.data)

    print_comment("Classifier accuracy: %.3f" % classifier.best_score_)


    # Create decision function from classifier
    decider = GameDecider(classifier,
                          lambda *g: data.convert(extract_features(*g)),
                          data.normalize)


    # REAL WORLD TESTS: Simulate tournaments.
    simdata = dict()

    for season in tourny_years:
        # Simulate some tournaments and print how well the model performed.
        print_info("Simulating %s tournament ... " % season)
        
        # Pull tournament of given year from the database.
        t = session.query(Tournament).filter_by(season=season).one()
        
        # Create an empty bracket from this real tournament
        b = t.empty_bracket()
        
        # Simulate tournament using empty bracket
        b.simulate(decider)
        
        # Score bracket predictions
        s = b.score(t)
        
        # Calculate some detailed performance statistics
        ff_right = len(set(t[1].opponents + t[2].opponents)\
                     & set(b[1].opponents + b[2].opponents))
        cr_right = len(set(t[0].opponents) & set(b[0].opponents))
        c_right = t[0].winner == b[0].winner

        # Print simulation results
        print_comment(" * Scored %d out of 1920" % s)
        print_comment("   - Picked %d Final Four teams" % ff_right)
        print_comment("   - Picked %d Championship teams" % c_right)
        
        if c_right:
            print_comment("   - Correctly picked %s as champion." \
                                % t[0].winner.team.name)
        else:
            print_comment("   - Incorrectly picked %s as champion, not %s" \
                                % (b[0].winner.team.name,
                                   t[0].winner.team.name))

        # Store data in variable simdata, for interactive mode exploration
        simdata[season] = {
            't' : t,
            'b' : b,
            's' : s,
        }


    print_success("Demo finished successfully.")
