#-*- coding: utf8 -*-
'''
ncaalib.grid_search

Custom scoring object for scikit-learn model evaluation.

Parts that I wrote:
Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT license.

The GridSearch class and fit_grid_point function are hacky modifications
of sklearn.grid_search.GridSearchCV and sklearn.grid_search.fit_grid_point.
The attribution of that code is:

# Author: Alexandre Gramfort <alexandre.gramfort@inria.fr>,
#         Gael Varoquaux <gael.varoquaux@normalesup.org>
# License: BSD Style.

I took it from

https://github.com/scikit-learn/scikit-learn/blob/master/sklearn/grid_search.py

on March 17. 2013.
'''
__author__="Joseph Nudell"
__date__="March 18, 2013"


from ncaa import *
from aux.output import print_warning
try:
    from sklearn.grid_search import ParameterGrid
except ImportError:
    from sklearn.grid_search import IterGrid as ParameterGrid
from sklearn.utils.validation import _num_samples, check_arrays
from sklearn.externals.joblib import Parallel, delayed, logger
from sklearn.base import clone
import copy
import numbers
import time
import numpy as np





class ExtractedSquad(object):
    '''Analogous to Squad in ncaa module but not connected to DB. Only copies
    the bare minimum for simulation.'''
    def __init__(self, squad):
        self.id = squad.id
        self.stats = copy.deepcopy(squad.stats)
        self.lsalpha = squad.lsalpha
        self.rpi = squad.rpi
        self.wp = squad.win_pct(weighted=False)
        self.wwp = squad.win_pct(weighted=True)






class ExtractedTournamentGame(object):
    '''Analogous to TournamentGame in the ncaa module, but not connected
    to database at all and optimized for multiple simulations and scorings.'''
    def __init__(self, game):
        if game.opponents is None:
            self.opponents = None
        else:
            self.opponents = [ExtractedSquad(s) for s in game.opponents]

        self.winner = ExtractedSquad(game.winner)
        self.loser = ExtractedSquad(game.loser)
        





class ExtractedTournament(object):
    '''Analogous to Tournament in ncaa module, but not connected to database.
    Optimized for repeatedly performing simulations. Used in grid searches
    for maximizing expected Tournament score.'''
    def __init__(self, tournament, scoring=None):
        self.games = [ExtractedTournamentGame(tg) for tg in tournament.games]
        self.key = [tg.winner.id for tg in self.games]
        
        if scoring is None:
            self.scoremap = tournament.roundpoints
        else:
            self.scoremap = scoring
            
        self._gtype = type(self.games[0])
        self._stype = type(self.games[0].opponents[0])
        self._predicted_ids = None
    
    def __iter__(self):
        return TournamentIterator(self)
    
    def score(self):
        pkey = []
        s = 0
        for i, game in enumerate(self.games):
            id_ = game.winner.id
            if self.key[i]==id_:
                round_ = log2(i+1)
                s += self.scoremap[round_]
            pkey.append(id_)
        self._predicted_ids = pkey
        return s

    def clear_bracket(self):
        sr_id = len(self.games)>>1
        for i in range(sr_id):
            self.games[i].opponents = []
            self.games[i].winner = self.games[i].loser = None
        for i in range(len(self.games)-1, sr_id-1, -1):
            self.games[i].winner = None
            self.games[i].loser = None

    def correct_in_round(self, k):
        '''Return % correctly predicted winners in round k'''
        game_ids = range((1<<k)-1, (1<<(k+1))-1)
        den = float(len(game_ids))
        key = self.key
        
        if self._predicted_ids is None:
            self.score()
        
        pids = self._predicted_ids
        
        return sum([key[i]==pids[i] for i in game_ids], 0.) / den
    
    def test(self, decider):
        self.clear_bracket()
        len_ = len(self.games) - 1
        for _x_, tgame in enumerate(self):
            _i_ = len_ - _x_
            if len(tgame.opponents)!=2:
                raise IndexError("%d opponents in game %d" \
                                    % (len(tgame.opponents), _i_))
            r = decider(tgame)
            if type(r) is self._gtype:
                tgame = r
                if tgame.winner is None or tgame.loser is None:
                    raise ValueError("Winner / loser not set on returned Game.")
            elif type(r) is tuple or type(r) is list:
                tgame.winner = r[0]
                tgame.loser = r[1]
            elif type(r) is self._stype:
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

            next_id = ((_i_+1) >> 1) - 1
            if next_id < 0:
                next_id = None
            
            if next_id is not None:
                self.games[next_id].opponents.append(tgame.winner)

        return self.score()










def fit_grid_point(X, y, base_clf, clf_params, scorer,
                   verbose, loss_func=None, **fit_params):
    '''Modified version of sklearn.grid_search.fit_grid_point that trains
    on entire input set. Note that if test set is not ignored by scorer,
    the resulting accuracy will be meaningless (you will have fit the data
    to the test set). The scorer should have its own testing routine that
    does not use data provided as inputs here.
    
    TODO: clean up this function. Right now it's just a hack of the original.
    '''
    if verbose > 1:
        start_time = time.time()
        msg = '%s' % (', '.join('%s=%s' % (k, v)
                      for k, v in clf_params.items()))
        print("[GridSearch] %s %s" % (msg, (64 - len(msg)) * '.'))

    # update parameters of the classifier after a copy of its base structure
    clf = clone(base_clf)
    clf.set_params(**clf_params)

    if hasattr(base_clf, 'kernel') and callable(base_clf.kernel):
        # cannot compute the kernel values with custom function
        raise ValueError("Cannot use a custom kernel function. "
                         "Precompute the kernel matrix instead.")

    if not hasattr(X, "shape"):
        if getattr(base_clf, "_pairwise", False):
            raise ValueError("Precomputed kernels or affinity matrices have "
                             "to be passed as arrays or sparse matrices.")
        X_train = X
        X_test = X
    else:
        if getattr(base_clf, "_pairwise", False):
            # X is a precomputed square kernel matrix
            if X.shape[0] != X.shape[1]:
                raise ValueError("X should be a square kernel matrix")
            X_train = X
            X_test = X
        else:
            X_train = X
            X_test = X

    if y is not None:
        y_test = y
        y_train = y
        clf.fit(X_train, y_train, **fit_params)

        if scorer is not None:
            this_score = scorer(clf, X_test, y_test)
        else:
            this_score = clf.score(X_test, y_test)
    else:
        clf.fit(X_train, **fit_params)
        if scorer is not None:
            this_score = scorer(clf, X_test)
        else:
            this_score = clf.score(X_test)

    if not isinstance(this_score, numbers.Number):
        raise ValueError("scoring must return a number, got %s (%s)"
                         " instead." % (str(this_score), type(this_score)))

    if verbose > 2:
        msg += ", score=%f" % this_score
    if verbose > 1:
        end_msg = "%s -%s" % (msg,
                              logger.short_format_time(time.time() -
                                                       start_time))
        print("[GridSearch] %s %s" % ((64 - len(end_msg)) * '.', end_msg))
    return this_score, clf_params, _num_samples(X_test)








class GridSearch(object):
    '''Perform a grid search with specified grid, searching for highest score
    on specified scorer. Adapted from GridSearchCV, but does no folding.
    It makes sense to use this when optimizing on a fixed testing set that is
    not in an array format, such as the Tournament simulations.'''
    def __init__(self, classifier, grid,
                       seasons=['2009-10', '2010-11', '2011-12'], verbose=1,
                       refit=False, pre_dispatch='2*n_jobs',
                       n_jobs=1, scoring=None, fit_params=None, **kwargs):
        self.verbose = verbose
        self.refit = refit
        self.seasons = seasons
        self.classifier = classifier
        self.grid = ParameterGrid(grid)
        self.pre_dispatch = pre_dispatch
        self.n_jobs = n_jobs
        if scoring is None:
            raise ArgumentError("You have to specify `scoring` parameter")
        self.scoring = scoring
        self.fit_params = fit_params if fit_params is not None else {}
    
    def _set_methods(self):
        '''Create predict and predict_proba if present in best estimator.'''
        if hasattr(self.best_estimator_, 'predict'):
            self.predict = self.best_estimator_.predict
        if hasattr(self.best_estimator_, 'predict_proba'):
            self.predict_proba = self.best_estimator_.predict_proba

    def fit(self, X, y):
        '''Run the grid search.
        
        TODO: Clean up this method. Right now it's an ugly hack of the
        original that removes CV.
        '''
        grid = self.grid
        base_clf = clone(self.classifier)
        scorer = self.scoring
        
        n_samples = _num_samples(X)
        X, y = check_arrays(X, y, allow_lists=True, sparse_format='csr')

        pre_dispatch = self.pre_dispatch

        # Dispatch grid search
        out = Parallel(
            n_jobs=self.n_jobs, verbose=self.verbose,
            pre_dispatch=pre_dispatch)(
                delayed(fit_grid_point)(
                    X, y, base_clf, clf_params, scorer,
                    self.verbose, **self.fit_params) for clf_params in grid)

        # Out is a list of triplet: score, estimator, n_test_samples
        n_param_points = len(list(grid))
        n_fits = len(out)

        scores = list()

        for grid_start in range(0, n_fits):
            n_test_samples = 0
            score = 0
            these_points = list()
            
            for this_score, clf_params, this_n_test_samples in \
                    out[grid_start:grid_start + 1]:
                these_points.append(this_score)
                score += this_score
                
            scores.append((score, clf_params))

        # Get comparison direction
        if scorer is not None:
            greater_is_better = scorer.greater_is_better
        else:
            greater_is_better = True

        if greater_is_better:
            best_score = -np.inf
        else:
            best_score = np.inf

        for score, params in scores:
            if ((score > best_score and greater_is_better)
                    or (score < best_score and not greater_is_better)):
                best_score = score
                best_params = params

        self.best_params_ = best_params
        self.best_score_ = best_score

        if self.refit:
            # fit the best estimator using the entire dataset
            # clone first to work around broken estimators
            best_estimator = clone(base_clf).set_params(**best_params)
            if y is not None:
                best_estimator.fit(X, y, **self.fit_params)
            else:
                best_estimator.fit(X, **self.fit_params)
            self.best_estimator_ = best_estimator
            self._set_methods()

        return self

        







class TournamentScorer(object):
    '''Scorer object that validates a model based on its performance in
    predicting past tournaments. By default it evaluates the model's overall
    score in a past tournament. Can also specify round_ parameter to maximize
    accuracy on a particular round or, by passing an iterable, set of rounds.
    Rounds must be specified by an integer, with 0 being Championship and 5
    being the First Round. Accuracy is evaluated by number of winners correctly
    predicted divided by games played. This means for example if you want to
    maximize the number of Final Fourists correctly predicted, you need to
    set round_ to 2, which is actually the ID of the Elite 8.
    
    In maximizing overall bracket score, you can specify the scoring parameter
    to provide a specific number of points to rounds (again, with the 0th item
    being the Championship and 5th being the Round of 64). By default the
    ESPN scoring system which assigns 320 max points to each round is used.'''
    def __init__(self, session,
                       extractor,
                       round_ = None,
                       scoring = None,
                       seasons=['2009-10', '2010-11', '2011-12'],
                       normalize=None, method=None,
                       greater_is_better=True):
        
        self.seasons = seasons
        self._session = session
        self.extractor = extractor
        self.normalize = normalize
        
        try:
            # Is round_ iterable?
            it = iter(round_)
        except TypeError:
            # Nope, not iterable
            if type(round_) is int:
                # Make a list from the int
                self.round_ = [round_]
            else:
                raise TypeError("Unknown round_ type: %s (%s)" \
                                    % (str(round_), type(round_)))
        else:
            # round_ is iterable
            self.round_ = round_
        
        if round_ is not None:
            self._rounds_frac = 1. / float(len(self.round_))
        
        self.method = method
        self.greater_is_better = greater_is_better
        tournaments = session.query(Tournament)\
                             .filter(Tournament.season.in_(seasons))\
                             .all()
        self.tournaments = [ExtractedTournament(t,scoring) for t in tournaments]
        self._len = float(len(self.tournaments))
        self._frac = 1. / self._len

    def __call__(self, estimator, *args):
        '''To implement the scorer protocol __call__ must accept X, y as 
        the testing set. The whole point of this scorer is to bring a
        specialized test set, though, so whatever is provided for X and y
        should just be ignored.'''
        decider = GameDecider(estimator, self.extractor,
                              normalize=self.normalize, method=self.method)
        round_ = self.round_
        trns = self.tournaments
        f = self._frac
        rf = self._rounds_frac
        
        s = sum([f * t.test(decider) for t in trns])

        if round_ is None:
            return s
        else:
            return sum([f * rf * t.correct_in_round(r)
                                                    for t in trns
                                                            for r in round_])
            







if __name__=='__main__':
    from sys import argv, exit
    from aux.output import print_error, print_info, print_success, print_comment
    if len(argv)!=2:
        print_error("Specify database to connect to in interactive mode.")
        exit(32)

    print_info("Loading database ... ")
    session = load_db(argv[1])

    print_comment("Loading 2011-12 tournament for example ... ")
    t12 = session.query(Tournament).filter_by(season='2011-12').one()

    print_comment("Extracting 2011-12 tournament ... ")
    et12 = ExtractedTournament(t12)

    print_comment("Running simulation ... ")
    et12.test(lambda x: x.opponents[0])

    print_success("Finished example.")


