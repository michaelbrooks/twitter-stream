#! /usr/bin/env python
"""
Imports tweets from stdin (json-format, one tweet per line)
into a MySQL table (schema shown below).
If the table does not exist, it will be created automatically.
"""

import sys
import time
import json
import argparse
import logging
import HTMLParser
import ConfigParser
from email.utils import parsedate
from datetime import datetime, timedelta
import settings

CREATE_TABLE_TEMPLATE = """CREATE TABLE IF NOT EXISTS `{table}` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tweet_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  `text` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `lat` float DEFAULT NULL,
  `lon` float DEFAULT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `user_screen_name` varchar(100) NOT NULL,
  `user_name` varchar(100) NOT NULL,
  `user_location` varchar(150) DEFAULT NULL,
  `user_tz` varchar(150) DEFAULT NULL,
  `user_utc_offset` int(11) DEFAULT NULL,
  `user_geo_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `user_followers_count` int(11) DEFAULT NULL,
  `user_friends_count` int(11) DEFAULT NULL,
  `user_statuses_count` int(11) DEFAULT NULL,
  `retweet_of_status_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `created_at` (`created_at`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;"""

TWEET_INSERT_TEMPLATE = """INSERT INTO `{table}`
(tweet_id, created_at, text, 
 lat, lon, 
 user_id, user_screen_name, user_name, 
 user_location, user_tz, user_utc_offset, user_geo_enabled, 
 user_followers_count, user_friends_count, user_statuses_count,
 retweet_of_status_id)
VALUES 
(%s, %s, %s, 
 %s, %s, 
 %s, %s, %s, 
 %s, %s, %s, %s, 
 %s, %s, %s, 
 %s)"""

BUFFER_SIZE = 100
REPORT_EVERY = 30  # time in seconds

logger = logging.getLogger('euromaidan.dbimport')

def _configure_logger():
    if not logger.handlers:
        from logging.config import dictConfig
        dictConfig({
            'version': 1,
            'disable_existing_loggers': True,
            'formatters': {
                'simple': {
                    'format': '%(asctime)s %(levelname)s %(message)s',
                    'datefmt': '%m/%d %I:%M:%S%p',
                },
            },
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                    'stream': 'ext://sys.stderr',
                },
            },
            'loggers': {
                'euromaidan': {
                    'handlers': ['console'],
                    'propagate': False,
                    'level': 'INFO',
                },
            }
        })
        
def parse_datetime(str):
    return datetime(*(parsedate(str)[:6]))

class DbImport(object):

    def __init__(self, config):
        self.config = config
        self.dbtable = self.config.db.table
        
        self.hp = HTMLParser.HTMLParser()
        self.tweet_buffer = []
        self.inserted = 0
        self.last_report = time.time() - REPORT_EVERY - 1
        
    def setup_queries(self):
        self.TWEET_INSERT_STMT = TWEET_INSERT_TEMPLATE.format(table=self.dbtable)
        self.TWEET_SELECT_STMT = 'SELECT id FROM `{table}` WHERE id = (%s)'.format(table=self.dbtable)
        self.CREATE_TABLE_STMT = CREATE_TABLE_TEMPLATE.format(table=self.dbtable)
        
    def setup(self):
        self.setup_queries()
        
        self.db = settings.connect_to_database(self.config)
        
        # Create the table if it doesn't exist
        self.db.query(self.CREATE_TABLE_STMT)
        
        # Get a database cursor
        self.cursor = self.db.cursor()
        
        return True
        
    def read_loop(self):
        logger.info("Reading tweets from stdin")
        for line in sys.stdin:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    tweet = json.loads(line)
                    self.process(tweet)
                except ValueError, e:
                    logger.error(e, exc_info=True)
                    sys.stderr.flush()
                except KeyError, e:
                    logger.error(e, exc_info=True)
                    sys.stderr.flush()
            else:
                logger.warn("Unrecognized input: %s", line)
                sys.stderr.flush()
        
        self.flush_tweet_buffer(report=True)
        logger.info("Finished")
        
    def process(self, tweet):
        tweet_id = tweet['id']
        tweet_created_at = parse_datetime(tweet['created_at'])
        tweet_text = self.hp.unescape(tweet['text'])

        retweet_id = None
        if tweet.get('retweeted_status') is not None:
            retweet_id = tweet['retweeted_status']['id']
            
        user = tweet['user']
        user_id = user['id']
        user_screen_name = user['screen_name']
        user_name = user['name']
        user_location = user['location']
        user_time_zone = user['time_zone']
        user_utc_offset = user['utc_offset']
        user_geo_enabled = user['geo_enabled']
        
        counts = {
            'user_statuses_count': user.get('statuses_count'),
            'user_followers_count': user.get('followers_count'),
            'user_friends_count': user.get('friends_count'),
        }
        for key in counts:
            if counts[key] is not None and counts[key] < 0:
                counts[key] = None
                
        tweet_lat = None
        tweet_lon = None
        coordinates = tweet.get('coordinates')
        if coordinates:
            tweet_lon = coordinates['coordinates'][0]
            tweet_lat = coordinates['coordinates'][1]
            
        tweet_params = (
            tweet_id,
            tweet_created_at,
            tweet_text,
            tweet_lat,
            tweet_lon,
            user_id,
            user_screen_name,
            user_name,
            user_location,
            user_time_zone,
            user_utc_offset,
            user_geo_enabled,
            counts['user_followers_count'],
            counts['user_friends_count'],
            counts['user_statuses_count'],
            retweet_id,
        )
        
        # Insert the tweet
        self.buffer_tweet(tweet_params)
        
    def buffer_tweet(self, tweet_data):
        self.tweet_buffer.append(tweet_data)

        if len(self.tweet_buffer) >= BUFFER_SIZE:
            self.flush_tweet_buffer()
    
    def flush_tweet_buffer(self, report=False):
        reported = False
        
        if len(self.tweet_buffer) > 0:
            try:
                self.cursor.executemany(self.TWEET_INSERT_STMT, self.tweet_buffer)
                self.inserted += len(self.tweet_buffer)
                self.tweet_buffer = []
                
                now = time.time()
                if report or now - self.last_report >= REPORT_EVERY:
                    logger.info("Inserted {:15,} tweets".format(self.inserted))
                    self.last_report = now
                    reported = True

            except Exception, e:
                logger.error(e, exc_info=True)
                
        if report and not reported:
            now = time.time()
            if report or now - self.last_report >= REPORT_EVERY:
                logger.info("Inserted {:15,} tweets".format(self.inserted))
                self.last_report = now
                
if __name__ == '__main__':

    parser = argparse.ArgumentParser("Stream tweets from stdin into a database")
    parser.add_argument("ini_file", type=str, help="name of the ini file containing db connection info")
    args = parser.parse_args()
    
    config = settings.Settings(args.ini_file)
    
    importer = DbImport(config)
    
    if not importer.setup():
        logger.error("Failed to initialize. Stopping.")
        exit(1)
        
    importer.read_loop()
    