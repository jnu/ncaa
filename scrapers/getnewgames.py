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
from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
import datetime
import csv
import urlparse
from sys import exit, stderr


game_stats_fn = "../data/sourcedocs/playerGame-stats_%s" \
                     % datetime.datetime.now().strftime("%Y-%h-%d")

fh = open(game_stats_fn, 'w')
player_writer = csv.writer(fh)

fields = [
    'player_id',
    'name',
    'height',
    'number',
    'position',
    'grade',
    'season',
    'date',
    'opponent',
    'result',
    'mp',
    'fgm',
    'fga',
    'threefg',
    'threefga',
    'ft',
    'fta',
    'pts',
    'oreb',
    'dreb',
    'treb',
    'ast',
    'to',
    'stl',
    'blk',
    'fouls',
    'dateret',
    'source',
]



class MBBScraper(BaseSpider):
    name = "mbbscraper"
    start_urls = ["http://stats.ncaa.org/team/inst_team_list?sport_code=MBB&division=1"]
    allowed_domains = ["ncaa.org"]
    
    def parse(self, response):
        print >>stderr, "Navigated to Index"
    
        x = HtmlXPathSelector(response)
        
        links = x.select('//a[starts-with(@href, "/team/index")]/@href').extract()

        for link in links:
            # Iterate through links to team stats and yield requests to there
            team_link = urlparse.urljoin(response.url, link)
            yield Request(team_link, callback=self.parse_team_page)

    def parse_team_page(self, response):
        # Parse page containing team season stats
        print >>stderr, "Parsing team page @ %s" % response.url
        
        x = HtmlXPathSelector(response)

        # Extract player links from page and yield requests to each of them.
        player_links = x.select('//a[contains(@href, "player?")]/@href').extract()

        for link in player_links:
            player_link = urlparse.urljoin(response.url, link)
            yield Request(player_link, callback=self.parse_player_page)

    def parse_player_page(self, response):
        # Parse page containing player season stats
        print >>stderr, "   Parsing player page at %s" % response.url

        x = HtmlXPathSelector(response)

        # Extract player statistics starting at the date specified in
        # initialization.

        rows = x.select('//div[starts-with(@id, "game")]//tr[@class="grey_heading"]/following-sibling::tr')
                
        title = x.select('//div[@class="appTitle"]/text()').extract()[0].strip()
        season = title.partition(' ')[0]

        pid = int(float(response.url.rpartition('=')[2]))

        for row in rows:
            entry = ['' for f in fields]
            entry[0] = pid
            entry[6] = season
            
            # Get all cells in this row
            for k in range(7, len(fields)):
                entry[k] = (''.join(row.select('td[position()=%d]//text()'%(k-6)).extract())).strip()

            entry[-2] = str(datetime.datetime.now())
            entry[-1] = response.url

            player_writer.writerow(entry)
            fh.flush()
        
        



SPIDER = MBBScraper()
        
        
        