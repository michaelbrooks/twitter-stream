import ConfigParser
import logging

__all__ = ['Settings']

_logger = logging.getLogger('euromaidan.settings')
if not _logger.handlers:
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
        
def _get_ini_file(ini_path):
    _logger.info("Reading configuration from %s", ini_path)

    import cStringIO as StringIO
    import os

    config = StringIO.StringIO()
    config.write('[root]\n')

    with open(ini_path) as ini:
        config.write(ini.read())

    config.seek(0, os.SEEK_SET)
    return config
    
class Settings(object):
    
    def __init__(self, ini_file='twitter_monitor.ini'):
        
        config = ConfigParser.SafeConfigParser()
        config.readfp(_get_ini_file(ini_file))
        
        class Section:
            pass
        
        for section_name in config.sections():
            section = Section()
            for k, v in config.items(section_name):
                setattr(section, k, v)
            setattr(self, section_name, section)

def connect_to_database(settings):
    import MySQLdb
    _logger.info("Connecting to database")
    try:
        db = MySQLdb.connect(
            host=settings.db.host,
            port=int(settings.db.port),
            user=settings.db.user,
            passwd=settings.db.password,
            db=settings.db.name,
            charset='utf8'
        )
        
    except Exception, e:
        _logger.error(e, exc_info=True)
        return False
        
    # Trick MySQLdb into using 4-byte UTF-8 strings
    db.query('SET NAMES "utf8mb4"')
    
    return db