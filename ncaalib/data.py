#-*- coding: utf8 -*-
'''
ncaalib.data

Class that provides some data manipulation classes that are useful in
working with NLTK and SciKit-Learn data and the ncaalib.ncaa class.

Provides DataSet container for NLTK / SciKit-Learn data sets, as well
as a Normalizer class to facilitate data normalization on this container.

Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT License.
'''
__author__ = "Joseph Nudell"
__date__ = "March 12, 2013"


from collections import defaultdict, OrderedDict
import numpy as np



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
    '''Container for NLTK / SciKit-Learn data objects. Preference is given to
    SKL classes; this is the internal storage mechanism. Uses numpy. Provides
    simple function to convert from  NLTK to SKL format.'''
    def __init__(self, data, split=.75, normalizer=Normalizer):
        self._split = split
        self.data = self.convert(data)
        
        # NOTE: inefficiency -- should split data after initial convert
        # also after normalization
        self.train, self.test = [self.convert(v) for v
                                                 in self._split_data(data)]
        
        if normalizer is not None:
            # Normalize data if normalizer is specified
            self.normalize = normalizer(self.train)
        
            # Normalize full data set
            self.data = (self.normalize(self.data[0]), self.data[1],)
    
            # Normalize test & train sets
            self.test = (self.normalize(self.test[0]), self.test[1],)
            self.train = (self.normalize(self.train[0]), self.train[1],)
        
    
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