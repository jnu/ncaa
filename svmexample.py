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
from sklearn.grid_search import GridSearchCV
from cmath import sqrt
from collections import defaultdict, OrderedDict
import numpy as np
import random



class Decider(object):
    def __init__(self, c, extractor, normalize=None, method=None):
        self.classifier = c
        self.extractor = extractor
        self.normalize = normalize
    
        if method is None:
            if hasattr(c, 'classify'):
                self.method = getattr(c, 'classify')
            elif hasattr(c, 'predict'):
                self.method = getattr(c, 'predict')
            else:
                raise TypeError("Unsure what method to call on classifer")
        else:
            self.method = getattr(c, method)

    def __call__(self, game):
        ft = self.extractor(*game.opponents)
        if self.normalize is not None:
            ft = self.normalize(ft)
        p = self.method(ft)
        return p





class Normalizer(object):
    '''Class for feature normalization. Does mean removal and variance
    scaling. Initialize with a training set and call Normalizer.normalize()
    on a feature map or training/testing set to normalize the data. Can
    alternatively call the instance directly instead of calling the normalize()
    method.'''
    def __init__(self, train_set, method='rescale'):
        '''Initialize with a training set to compute mean and variance from.'''
        self._train_set = train_set
        self._vals = defaultdict(list)
        self.means = OrderedDict()
        self.stdevs = OrderedDict()
        self.maxes = OrderedDict()
        self.mins = OrderedDict()
        self.method = method
    
        if type(train_set) is list:
            # NLTK Format
            for set_ in train_set:
                for k,v in set_[0].items():
                    self._vals[k].append(v)
        
        elif type(train_set) is tuple and type(train_set[0]) is np.matrix:
            # SKL Format (labeled)
            for set_ in train_set[0].getA():
                for i,v in enumerate(set_):
                    self._vals[i].append(v)
    
        elif type(train_set) is np.matrix:
            # SKL Format (unlabeled)
            for set_ in train_set.getA():
                for i,v in enumerate(set_):
                    self._vals[i].append(v)
        
        else:
            # Unsupported Type
            raise TypeError("Don't know how to interpret type %s" \
                                % type(train_set))
    
        for k,v in self._vals.items():
            self.means[k] = self.mean(v)
            self.stdevs[k] = self.stdev(v)
            self.maxes[k] = float(max(v))
            self.mins[k] = float(min(v))

    def __call__(self, data):
        '''Shorthand for calling Normalizer.normalize(data)'''
        return self.normalize(data)

    def normalize(self, data):
        '''Normalize a piece of data by removing the mean and scaling
        variance to unit. Data can be a set (such as training set) or
        a single feature map.'''
        norm = None
        if type(data) is list:
            # Got set of data in NLTK format
            norm = [(self._normalize_fm(fm), lbl,) for fm,lbl in data]
        elif type(data) is dict:
            # Got single featuremap in NLTK format
            norm = self._normalize_fm(data)
        elif type(data) is np.matrix:
            # Got set of data in SKL format
            norm = [self._normalize_fm(row) for row in data.getA()]
            norm = np.matrix(norm)
        elif type(data) is tuple and type(data[0]) is np.matrix:
            # Got labeled set of data in SKL format
            norm = ([self._normalize_fm(row)
                     for row in data[0].getA()], data[1],)
            norm = (np.matrix(norm[0]), norm[1],)
        elif type(data) is np.ndarray:
            # Got single featureset in SKL format
            norm = self._normalize_fm(data)
            norm = np.array(norm)
        elif type(data) is tuple and type(data[0]) is np.ndarray:
            # Got labeled single featureset (not sure why) in SKL format
            norm = (self._normalize_fm(data[0]), data[1],)
            norm = (np.array(norm[0]), norm[1],)
            
        else:
            raise TypeError("Don't know how to normalize for type %s" \
                                % type(data))
        return norm
            
    def _normalize_fm(self, feature_map):
        '''Normalize a feature map. Better not to call this method
        directly, but to call Normalizer.normalize() instead, which
        is polymorphic for featuremaps and sets of feature maps.'''
        norm = feature_map
        items = []
        
        if hasattr(norm, 'items'):
            items = norm.items()
        else:
            items = enumerate(norm)
            
        if self.method=='standardize':
            for k,v in items:
                norm[k] = self._standardize(k, v)
                
        elif self.method=='rescale':
            for k,v in items:
                norm[k] = self._rescale(k, v)
            
        return norm
        
    def _standardize(self, key, val):
        return (val - self.means[key]) / self.stdevs[key]

    def _rescale(self, key, val):
        return (val - self.mins[key]) / (self.maxes[key] - self.mins[key])
    
    def stdev(self, X):
        '''Compute standard deviation of list X. Uses Welford's single pass
        algorithm.'''
        n = 0.
        m = 0.
        m2 = 0.
        
        for x in X:
            n += 1.
            d = x - m
            m = m + d/n
            m2 = m2 + d*(x - m)
        return m2 / (n - 1.)

    def mean(self, data):
        '''Compute mean of list X'''
        X = data
        if hasattr(data, 'values'):
            X = data.values()
        return sum(X, 0.) / float(len(X))




class DataSet(object):
    def __init__(self, data, split=.75, normalizer=Normalizer):
        self._split = split
        self.data = self.convert(data)
        self.train, self.test = [self.convert(v) for v
                                                 in self._split_data(data)]
        self.normalize = normalizer(self.train)
        self.train = self.normalize(self.train)
        self.test = self.normalize(self.test)
    
    def _split_data(self, data):
     '''Splits a sample set into a test and train set with the given ratio'''
     s = int(round(len(data) * self._split))
     return (data[:s], data[s:],)
    
    def convert(self, featuresets):
        '''Convert NLTK style featureset to SciKit-Learn style featureset'''
        features = []
        targets = []
        if type(featuresets) is list:
            for item in featuresets:
                if type(item) is tuple:
                    features.append(self._convert_featureset(item[0]))
                    targets.append(item[1])
                else:
                    features.append(self._convert_featureset(item))
            return (np.matrix(features), np.array(targets))
        else:
            if type(featuresets) is tuple:
                return (self._convert_featureset(featuresets[0]),
                                                 featuresets[1])
            else:
                return self._convert_featureset(featuresets)
            
    def _convert_featureset(self, featureset):
        X = featureset
        if hasattr(featureset, 'values'):
            X = featureset.values()
        return np.array(X)

   





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
    
    some_games = Game.get_games_with_data(session, limit=200)

    sample_a, sample_b = [], []
    
    
    for i, game in enumerate(some_games):
        # Extract features and label the Games. 
        print_comment("Calculating stats for squads in game %s ... " % i)
        
        opponents = [squad for squad in game.opponents]
        winner = opponents.index(game.winner)
    
        # Make one sample with Squad 1's offense and Squad 2's defense
        ft_a = extract_features(*opponents)
        sample_a.append((ft_a, str(winner),))

        # Make another sample with Squad 2's offense and Squad 1's offense
        opponents.reverse()
        ft_b = extract_features(*opponents)
        sample_b.append((ft_b, str(winner),))


    print_good("Commiting calculated stats to db")
    session.commit()



    print_info("Creating and normalizing data set ...")
    data_a = DataSet(sample_a)
    data_b = DataSet(sample_b)



    print_info("Constructing grid for optimizing hyperparameters ...")
    # Create Grid to search
    grid = {
        'kernel' : ('rbf', 'linear', 'sigmoid',),
        'C'      : [2**i for i in range(-15, 15)],
        'gamma'  : [2**i for i in range(-15, 15)],
    }

    classifier_a = GridSearchCV(SVC(probability=True), grid,
                                verbose=3, refit=True, cv=10, n_jobs=4)
    classifier_b = GridSearchCV(SVC(probability=True), grid,
                                verbose=3, refit=True, cv=10, n_jobs=4)

    print_info("Searching for optimal classifier ...")
    # Train the classifier
    classifier_a.fit(*data_a.data)
    classifier_b.fit(*data_b.data)
    

    # Score the classifier
    print_comment("Classifier A accuracy: %.3f" % classifier_a.best_score_)
    print_comment("Classifier B accuracy: %.3f" % classifier_b.best_score_)


    t = session.query(Tournament).filter_by(season="2011-12").one()

    print_info("Simulating 2011-12 tournament with first model ...")
    bracket = t.empty_bracket()
    bracket.simulate(Decider(classifier_a,
                              lambda *g: data_a.convert(extract_features(*g)),
                              data_a.normalize))
    s2 = bracket.score(t)
    print_comment("Scored %d / 1920" % s2)

