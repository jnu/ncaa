#!/var/chroot/home/content/41/10223541/html/python/bin/python
# -*- coding: utf8 -*-
'''
$ python ncaa2013/web/fetchstats.py

MVC-Controller for retrieving stats (by ID) from ncaa.db. Returns JSON.

Copyright (c) 2013 Joe Nudell
Freely distributable under the MIT License.
'''

import cgi
import json
import os
from ncaa import *


# Get GET
args = cgi.FieldStorage()

type = args.getvalue('type', None)
id_ = args.getvalue('id', None)
er = False

try:
    id_ = int(id_)
except:
    ret['error'] = 'bad ID'
    er = True

ret = dict()

if type is None:
    ret['error'] = 'type not specified'

elif id is None:
    ret['error'] = 'id not specified'

elif not er:
    # Connect to DB
    session = load_db('../../data/ncaa.db')
    
    # Get entity from DB.
    if type.lower() == 'squad':
        e = session.query(Squad).get(id_)
        
        # Place general info about Team in return dict
        ret['name'] = e.team.name
        ret['season'] = e.season
        
        # Place stats object in return dict
        ret['stats'] = dict(e.stats.items())
        ret['stats']['rpi'] = e.rpi
        ret['stats']['wwp'] = e.win_pct(weighted=True)
        ret['wins'] = len(e.wins)
        ret['losses'] = len(e.losses)

    else:
        # Nothing else supported so far
        ret['error'] = 'type not currently supported'


## RETURN ##
## HEADER ##
print "Content-type: application/json;charset=utf-8"
print
## CONTENT ##
print json.dumps(ret)