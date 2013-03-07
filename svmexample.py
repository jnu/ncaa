'''
$ python ncaa2013/svmexample.py

Train a Support Vector Machine and test run.

Copyright (c) 2013 Joseph Nudell
'''


from ncaa import *
from nltk.classify import accuracy, svm
import random
from output import *



def extract_features(squad1, squad2):
    return {
        'fg_pct' : squad1.stats.fg_pct,
        'rebounds-o' : squad1.stats.rebounds_avg,
        'assists' : squad1.stats.assists_avg,
        'blocks' : squad2.stats.blocks_avg,
        'steals' : squad2.stats.steals_avg,
        'rebounds-d' : squad2.stats.rebounds_avg
    }


def split_sample(sample, rat=.75):
    s = int(round(sample*rat))
    return sample[:s], sample[s:]


def run():
    session = load_db('data/ncaa.db')

    some_games = Game.get_games_with_data(session, limit=20)

    sample = []

    for game in some_games:
        winner1 = 'o'
        winner2 = 'd'
        if game.winner is game.opponents[1]:
            winner1 = 'd'
            winner2 = 'o'
        sample.append((extract_features(*game.opponents), winner1,))

        sample.append((extract_features(game.opponents[1],
                                        game.opponents[0]), winner2,))


    print_info("Splitting sample in test and train sets")
    train_set, test_set = split_sample(sample, .75)

    print_comment("Training size:\t%d" % len(train_set))
    print_comment("Testing size:\t%d" % len(test_set))

    print_info("Training classifier ...")

    classifier = svm.SvmClassifier.train(train_set)

    
    print_comment("Resulting SVM Dimensions: %d" % (len(classifier._svmfeatureindex)))

    print_comment("Label mapping: %s" % classifer.__labelmapping)

    print_info("Testing model accuracy ... ")
    print_comment("Overall classification accuracy: %s" % accuracy(classifier, test_set))    


if __name__=='__main__':
    run()
