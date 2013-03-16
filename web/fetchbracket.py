#!/var/chroot/home/content/41/10223541/html/python/bin/python
# -*- coding: utf8 -*-
'''
$ python ncaa2013/web/fetchbracket.py

MVC-Controller for retrieving brackets from ncaa.db. Returns JSON.

Copyright (c) 2013 Joe Nudell
Freely distributable under the MIT License.
'''

import cgi
import json
import os
from ncaalib.ncaa import *


# Get GET
args = cgi.FieldStorage()

db = args.getvalue('db', True)
method = args.getvalue('method', 'nested')
key = args.getvalue('id', '-1')
filter_ = args.getvalue('f', 'id').lower()

ret = dict()

if key is None:
    ret['error'] = 'key not specified'

else:
    if db=='1' or db=='true':
        # Fetch from db
        session = load_db('../../data/ncaa.db')
        
        try:
            # Try to pull tournament record from database
            t = None
            
            if filter_=='id':
                # Default: pull by ID
                t = session.query(Tournament).get(int(key))
            elif filter_=='season':
                # Alternative: pull by season
                t = session.query(Tournament).filter_by(season=key).one()
            else:
                # No other query filters are supported currently
                ret['error'] = 'unsupported query filter'
                
            if t is not None:
                ret = t.export(method)
        except:
            ret['error'] = 'key not found'

    else:
        # Fetch from local scrap
        spaths = [key+'.js', key+'.json',
                  'brackets/'+key+'.js', 'brackets/'+key+'.json']
        for path in spaths:
            if os.path.exists(path):
                with open(path, 'r') as fh:
                    t = json.loads(fh.read())
                    ret['nodes'] = t
                break
            else:
                ret['error'] = 'record not found'



#### RETURN #####
print "Content-type: application/json;charset=utf-8"
print
## Content ##
if type(ret) is dict:
    print json.dumps(ret)
else:
    # Already JSON-ified
    print ret
