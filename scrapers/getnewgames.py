#-*- coding: utf8 -*-
'''
$ ncaa2013/scrapers/getnewgames.py

Scrape the NCAA Men's basketball website for stats. Outputs to CSV in a format
that can be used by dbmgr.py to insert data into the database (and ensure
uniqueness and so on).

Built using scrapy.

Copyright (c) 2013 Joseph Nudell
Freely distributable under the MIT License.
'''
__author__='Joseph Nudell'
__date__='March 14, 2013'


from scrapy.item import Item, Field
from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector
import datetime
import csv
import urlparse
import os
import errno
from sys import exit, stderr
from pprint import pprint

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

game_stats_fn = "../data/sourcedocs/playerGame-stats_%s" \
                     % datetime.datetime.now().strftime("%Y-%h-%d")

mkdir_p(game_stats_fn)

fh = open(game_stats_fn, 'w')
player_writer = csv.writer(fh)

efh = open('errorfix.lst', 'w')

fields = [
    'ID',
    'Name',
    'Height (in.)',
    'Number',
    'Position',
    'Grade',
    'Season',
    'Date',
    'Opponent',
    'Result',
    'MP',
    'FGM',
    'FGA',
    '3FG',
    '3FGA',
    'FT',
    'FTA',
    'PTS',
    'Off Reb',
    'Def Reb',
    'Tot Reb',
    'AST',
    'TO',
    'STL',
    'BLK',
    'Fouls',
    'Team ID',
    'Team Name',
    'Date Retrieved',
    'Source'
]

player_writer.writerow(fields)


class MBBScraper(Spider):
    name = "mbbscraper"
    start_urls = ["http://stats.ncaa.org/team/inst_team_list?sport_code=MBB&division=1"]
    allowed_domains = ["ncaa.org"]

    def __init__(self, retry=None, rosters=None):
        self._rosters = rosters is not None
        self._retrylist = retry is not None
        if retry is not None:
            self.start_urls = []
            roster_links = []
            player_links = []

            with open(retry, 'r') as fh:
                for line in fh.readlines():
                    link = line.strip()
                    cb = lambda x: x
                    if 'stats_player_seq' in link:
                        self.start_urls.append(link)
                    elif '/team/roster/' in link:
                        #cb = self.parse_roster_page
                        print >>efh, link
                        continue
                    else:
                        raise NotImplemented

        if rosters is not None:
            with open(rosters, 'r') as fh:
                links = list(set([r.strip() for r in fh.readlines()]))

                print >>stderr, "starting with ... ", links

                self.start_urls = links

    def start_requests(self):
        req = list()

        for link in self.start_urls:
            if '/team/roster' in link:
                req.append(Request(link, callback=self.parse_roster_page))
            elif 'stats_player_seq' in link:
                raise NotImplemented
            else:
                req.append(Request(link))

        return req

    def get_roster_from_player_page(self, response):
        s = Selector(response)

        link = s.xpath('//a[starts-with(@href, "/team/roster")]/@href').extract()[0].strip()
        roster_link = urlparse.urljoin(response.url, link)

        print >>efh, roster_link


    def parse(self, response):
        print >>stderr, "Navigated to Index"

        if self._retrylist:
            yield self.get_roster_from_player_page(response)

        else:
            s = Selector(response)

            links = s.xpath('//a[starts-with(@href, "/team/index")]/@href').extract()

            for link in links:
                # change index page to roster page
                link = link.replace('/team/index/', '/team/roster/')

                # Iterate through links to team stats and yield requests to there
                team_link = urlparse.urljoin(response.url, link)

                print >>stderr, " - Changed team link to %s" % team_link

                yield Request(team_link, callback=self.parse_roster_page)

    def parse_roster_page(self, response):
        # Parse page containing team season stats
        print >>stderr, "Parsing roster page @ %s" % response.url

        s = Selector(response)

        # Extract player links from page and yield requests to each of them.
        # player_links = x.select('//a[contains(@href, "player?")]/@href').extract()

        rows = s.css('table#stat_grid tbody tr')
        links = s.xpath('//a[contains(@href, "player?")]/@href').extract()

        stuff = zip(rows, links)

        def get_text(r, i):
            t = ''
            try:
                t = r.xpath('td[position()=%d]//text()' % i).extract()[0].strip()
            except:
                try:
                    t = r.xpath('td[position()=%d]//text()' % i).extract().strip()
                except:
                    pass
            finally:
                return t

        for row, link in stuff:
            player_info = ['' for i in range(5)]
            team_info = ['', '']

            # get name
            player_info[0] = get_text(row, 2)

            # get height (in inches)
            height = get_text(row, 4) or ''
            p = map(lambda x: int(x or 0), height.split('-')) or [0, 0]
            height = p[0] * 12 + (p[1] if len(p) is 2 else 0)
            player_info[1] = str(height or '')

            # get jersey number
            player_info[2] = get_text(row, 1)

            # get position
            player_info[3] = get_text(row, 3)

            # get grade
            player_info[4] = get_text(row, 5)

            # team info
            # get id
            team_info[0] = response.url.split('=')[-1]

            # get name
            tname = ''
            try:
                tname = s.xpath('//h1/text()').extract()[0].rpartition('(')[0].strip()
            except:
                pass
            team_info[1] = tname


            # get player link
            player_link = urlparse.urljoin(response.url, link)

            print >>stderr, "Found player stat link at %s ..." % player_link

            yield Request(url=player_link,
                          callback=self.parse_player_page,
                          meta={
                            'player_info' : player_info,
                            'team_info' : team_info
                          })

    def parse_player_page(self, response):
        # Parse page containing player season stats
        print >>stderr, "   Parsing player page at %s" % response.url

        s = Selector(response)

        # Extract player statistics starting at the date specified in
        # initialization.

        rows = s.xpath('//div[starts-with(@id, "game")]//tr[@class="grey_heading"]/following-sibling::tr')

        title = s.xpath('//div[@class="appTitle"]/text()').extract()[0].strip()
        season = title.partition(' ')[0]

        player_info = response.meta['player_info']
        team_info = response.meta['team_info']

        pid = int(float(response.url.rpartition('=')[2]))

        for row in rows:
            entry = ['' for f in fields]
            entry[0] = pid
            for i, item in enumerate(player_info):
                entry[i + 1] = item
            entry[6] = season

            # Get all cells in this row
            for k in range(7, len(fields)):
                entry[k] = (''.join(row.select('td[position()=%d]//text()'%(k-6)).extract())).strip()

            entry[-4] = team_info[0]
            entry[-3] = team_info[1]

            entry[-2] = str(datetime.datetime.now())
            entry[-1] = response.url

            player_writer.writerow(entry)
            fh.flush()





SPIDER = MBBScraper()


