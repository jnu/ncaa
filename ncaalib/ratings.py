#-*-coding: utf8 -*-
'''
ncaalib.ratings

Module that implements additional rating / ranking methods for Squads.

Some third-party modules are required. They are as follows:

====================================================================
* PyDEC: A Python library for Discretization of Exterior Calculus
    Authors:    Anil Hirani and Nathan Bell
    Note:       Software available through Google Code
    Url:        http://code.google.com/p/pydec
    Urldate:    2008
    
Note: See also lecture given by Dr. Anil Hirani at NCSU on Applied Topology
in which he demonstrates the NCAA Men's Basketball ranking system used here:

    - http://www.ece.ncsu.edu/news/interdisciplinary/speakers/90

Additionally, this ranking system and a more detailed explanation of the
methodology is available online at http://basketball.cs.illinois.edu/.

======================================================================


Implemented by Joe Nudell in 2013, but uses ideas and methods developed by
others. See third-party module descriptions for details.
'''
# Load from standard library
from sys import exit

# Load intramodule classes
from aux.output import *
from ncaa import *

# Try to load third-party (but common) libraries
try:
    from scipy.sparse.linalg import lsqr
except ImportError:
    print_warning("Module scipy is missing. Can't do any algebra.")

try:
    import numpy as np
except ImportError:
    print_warning("Module numpy is missing! This is required for ncaalib.")
    exit(1)

# Try to load third-party (but uncommon) libraries
try:
    from pydec import abstract_simplicial_complex
except ImportError:
    print_warning("Module PyDEC not installed! Can't do least squares ranking.")







class SquadRater(object):
    def __init__(self, session, season):
        self.season = season
        self._session = session
        self.squads = self._get_squads()

    def _get_squads(self):
        squads = self._session.query(Squad)\
                     .filter(Squad.season==self.season)\
                     .all()
        return squads

    def rate(self):
        '''Subclasses must implement this method.'''
        return None




class LeastSquaresRater(SquadRater):
    def __init__(self, session, season, dist=None):
        super(LeastSquaresRater, self).__init__(session, season)

        self.dist = dist
        if self.dist is None:
            # No distance function specified. By default use score margin.
            self.dist = self._score_diff

        self._squadmap = self._enumerate_squads()
        self.distances = self._reduce_schedule()

    def _enumerate_squads(self):
        '''Enumerate squads by ID. The enumerated ID allows interfacing with
        the PyDEC methods.'''
        map_ = {
            'eid2sid' : dict(),
            'sid2eid' : dict()
        }
        
        for i, squad in enumerate(self.squads):
            sid = squad.id
            map_['eid2sid'][i] = sid
            map_['sid2eid'][sid] = i

        return map_

    def _reduce_schedule(self):
        '''Convert games played in season to a matrix (np.ndarray) in the form
        SquadOneEID, SquadTwoEID, Score Difference. The magnitude of the score
        differential is in favor of SquadOne.'''
        distances = list()
    
        for squad in self.squads:
            games = squad.get_games(postseason=False, played=True, cache=True)
    
            for game in games:
                if game.winner is None or game.loser is None:
                    # Shouldn't be any unplayed games in set, but it's possible.
                    continue
                
                if hasattr(game, "_analyzed") and game._analyzed:
                    # Skip games which have already been added to graph. This
                    # will be half of them.
                    continue
                else:
                    # Mark game as analyzed
                    game._analyzed = True

                distances.append(list(self.dist(game)))
        return np.array(distances)
            
    def _score_diff(self, game):
        '''Standard distance between two squads is the score of the winner
        minus the score of the loser.'''
        delta = game.winner_score - game.loser_score
        w_eid = self._squadmap['sid2eid'][game.winner.id]
        l_eid = self._squadmap['sid2eid'][game.loser.id]
        return (w_eid, l_eid, delta,)

    def rate(self, mutate=True):
        '''Least squares ranking on graphs. This method is adapted from the
        example given by Hirani et al. Set mutate to False to prevent the
        calculation from being saved on each Squad instance. No commits
        are performed.
        See also
            * A. N. Hirani, K. Kalyanaraman, S. Watts
            arXiv:1011.1716v1 [cs.NA] on http://arxiv.org/abs/1011.1716'''
        data = self.distances
        
        # Find edges
        edges = data[:, :2]

        # Create abstract simplicial complex from edges
        asc = abstract_simplicial_complex([edges])

        # Pairwise comparisons
        omega = data[:, -1]

        # Find boundary matrix of abs. simplicial complex
        B = asc.chain_complex()[1]

        # Solve least squares problem
        alpha = lsqr(B.T, omega)[0]

        # Normalize minimum
        alpha = alpha - alpha.min()

        # Convert enumerated IDs back into SIDs
        ret = {}
        for eid, aval in enumerate(alpha):
            ret[self._squadmap['eid2sid'][eid]] = aval
        
        if mutate:
            for squad in self.squads:
                squad.lsalpha = ret[squad.id]

        return ret




if __name__=='__main__':
    from sys import argv
    if len(argv)!=2:
        print_error("Have to specify database to connect to!")
        exit(54)
    # Test
    session = load_db(argv[1])

    # Load least squares rater
    print_info("Loading test of LeastSquaresRater on 2011-12")
    lsrater = LeastSquaresRater(session, '2011-12')
    print_comment("Rating & mutating... ")
    lsrater.rate(mutate=True)

    print_comment("Same for 2009-10")
    ls10 = LeastSquaresRater(session, '2009-10')
    lsrater.rate(mutate=True)

    print_comment("Same for 2010-11")
    ls11 = LeastSquaresRater(session, '2010-11')
    ls11.rate(mutate=True)

    print_comment("Same for current season")
    ls13 = LeastSquaresRater(session, '2012-13')
    ls13.rate(mutate=True)

    print_success("Graphed and rated all teams in all available season.")
    print_comment("Saving changes to database ... ")
    session.commit()
    print_success("Done!")



