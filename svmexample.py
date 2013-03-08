#-*-coding:utf8-*-
'''
$ python ncaa2013/svmexample.py

Demonstrates how to train a Support Vector Machine using a random
sample of Games from the database.

Copyright (c) 2013 Joseph Nudell
'''

from ncaa import *
from output import *
from sklearn.svm import SVC
import random
import nltk
from nltk.classify.scikitlearn import SklearnClassifier



def split_sample(sample, rat=.75):
     '''Splits a sample set into a test and train set with the given ratio'''
     s = int(round(len(sample)*rat))
     return (sample[:s], sample[s:],)



def extract_features(squad1, squad2):
    '''What to give to SVM for classification? This example gives some
    offensive statistics from the first squad and some defensive stats from
    the second squad.'''
    return {
        'fga' : squad1.stats.field_goal_avg,
        'reba' : squad1.stats.rebounds_avg,
        'rebb' : squad2.stats.rebounds_avg,
        'assa' : squad1.stats.assists_avg,
        'ppma' : squad1.stats.ppm,
        'stlsa' : squad1.stats.steals_avg,
        'toa' : squad1.stats.turnovers_avg,
        'blksb' : squad2.stats.blocks_avg,
        'ptsa' : squad1.stats.points_avg
    }



if __name__=='__main__':
    '''Run a demo that trains two classifiers on a random sample of games from
    the database. The first classifier uses the 1st Squad's offense against
    the 2nd Squad's defense, and the second classifier is trained on the
    reverse of that. A final prediction is made by taking the classifier
    that is maximally confident in its prediction. (Note, would be better to
    use Bayes Optimal Classifier.)'''
    
    # Load a new session
    session = load_db('data/ncaa.db')

    # Get a random sample of 20 games from the Database. This function
    # ensures that both Squds in the Games it returns have stats associated
    # with them. (There are some games in the database in which one or both
    # of the squads do not have stats available at this time.)
    print_info("Creating sample from games in DB")
    
    some_games = Game.get_games_with_data(session, limit=60)

    sample_a, sample_b = [], []
    
    i=1
    for game in some_games:
        # Extract features and label the Games. 
        print_comment("Calculating stats for squads in game %d ... " % i)
        i+=1
        
        opponents = game.opponents
        winner = opponents.index(game.winner)
    
        # Make one sample with Squad 1's offense and Squad 2's defense
        sample_a.append((extract_features(*opponents), str(winner),))

        # Make another sample with Squad 2's offense and Squad 1's offense
        opponents.reverse()
        sample_b.append((extract_features(*opponents), str(winner),))

    print_good("Commiting calculated stats to db")
    session.commit()

    print_info("Splitting samples in test and train sets")
    train_set_a, test_set_a = split_sample(sample_a, .75)
    train_set_b, test_set_b = split_sample(sample_b, .75)


    print_info("Creating classifier ...")
    # Create classifier
    classifier_a = SklearnClassifier(SVC(probability=True))
    classifier_b = SklearnClassifier(SVC(probability=True))


    print_info("Training classifier ...")
    # Train the classifier
    classifier_a.train(train_set_a)
    classifier_b.train(train_set_b)

    # Test the accuracy of the model
    print_info("Testing model accuracy ... ")
    print_comment("Overall classification accuracy")
    print_comment("A = %s" % nltk.classify.accuracy(classifier_a, test_set_a))
    print_comment("B = %s" % nltk.classify.accuracy(classifier_b, test_set_b))


    print_info("Testing combined accuracy ...")
    c = 0
    for i in range(len(test_set_a)):
        # Evaluate ensemble model prediction
        a = classifier_a.prob_classify(test_set_a[i][0])
        b = classifier_b.prob_classify(test_set_b[i][0])

        # Create a dictionary of labels vs. probabilities
        m = [(0, a.prob('0')), (1, a.prob('1')),
             (0, b.prob('0')), (1, b.prob('1'))]
        
        # Select label with maximum probability
        winner = max(m, key=lambda x: x[1])

        # Print results to screen
        print_comment(" * %s vs. %s. Projecting %s wins with %d%% confidence."\
                        % (some_games[i].opponents[0].team.name,
                           some_games[i].opponents[1].team.name,
                           some_games[i].opponents[winner[0]].team.name,
                           int(100 * winner[1])))
        print_comment("    - A: %d (%f), %d (%f)" \
                        % (m[0][0], m[0][1], m[1][0], m[1][1]))
        print_comment("    - B: %d (%f), %d (%f)" \
                        % (m[2][0], m[2][1], m[3][0], m[3][1]))
        
        # Evaluate prediction
        if str(winner[0]) == str(test_set_a[i][1]):
            print_good("      Correct")
            c += 1
        else:
            print_warning("       Incorrect")

    print_info("Model was correct in %d out of %d cases (%f)" \
                % (c, len(test_set_a), c/float(len(test_set_a))))

