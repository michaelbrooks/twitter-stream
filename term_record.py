from twitter_monitor.checker import FileTermChecker
import sys
import argparse
import settings
import logging

logger = logging.getLogger('euromaidan.term_record')

CREATE_TABLE_STMT = """CREATE TABLE IF NOT EXISTS `tracking_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `term` varchar(250) NOT NULL,
  `active_on` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM  DEFAULT CHARSET=utf8mb4"""

TERM_INSERT_STMT = """INSERT INTO `tracking_history`
  (term, active_on) 
  VALUES (%s, %s)"""

def record_terms(args):
    config = settings.Settings(args.ini_file)

    if args.date:
        now = args.date
    else:
        from datetime import datetime
        now = datetime.utcnow()
        now = now.strftime('%Y-%m-%d %H:%M:%S')

    ftc = FileTermChecker(args.track_file)
    terms = list(ftc.update_tracking_terms())
    
    rows = [(term, now) for term in terms]

    db = settings.connect_to_database(config)
    if db:
        # Create the table if it doesn't exist
        db.query(CREATE_TABLE_STMT)

        # Get a database cursor
        cursor = db.cursor()

        # insert the things
        inserted = cursor.executemany(TERM_INSERT_STMT, rows)
        
        logger.info("Inserted %d terms", inserted)
    else:
        logger.error("Failed to connect to database")
        exit(1)

        
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('track_file', default="trackfile.txt")
    parser.add_argument('--date', '-d', help="the mysql datetime when the terms became active (defaults to now)")
    parser.add_argument('--ini_file', '-i', help="an ini file containing database settings", default="twitter_monitor.ini")
    args = parser.parse_args()

    record_terms(args)
    

    