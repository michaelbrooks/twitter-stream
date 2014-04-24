import argparse
import bottle
from bottle import jinja2_template, request
import json

import settings

bottle.TEMPLATE_PATH.insert(0,'templates/')

app = bottle.Bottle()


class StripPathMiddleware(object):
  def __init__(self, app):
    self.app = app
  def __call__(self, e, h):
    e['PATH_INFO'] = e['PATH_INFO'].rstrip('/')
    return self.app(e,h)

class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the 
    front-end server to add these headers, to let you quietly bind 
    this to a URL other than / and to an HTTP scheme that is 
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)
    
@app.route('/')
def visualization(db):
    data = {
        'initial_data': json.dumps(update_data(db)),
        'urls': json.dumps({
            'update': app.get_url('update')
        })
    }
    return jinja2_template('visualization', data)
    
@app.route('/update', name='update')
def update(db):
    return update_data(db)
    
def update_data(db):
    table = config.db.table
    db.execute("select count(*) as count from %s" % table)
    count = db.fetchone()['count']
    
    db.execute("select * from %s order by created_at desc LIMIT 10" % table)
    latest = db.fetchall()
    for tweet in latest:
        tweet['created_at'] = tweet['created_at'].isoformat()
        
    return {
        'count': count,
        'latest': latest
    }

def setup_database(config):
    import bottle_mysql
    # dbhost is optional, default is localhost
    mysql = bottle_mysql.Plugin(dbhost=config.db.host,
                                dbport=int(config.db.port),
                                dbuser=config.db.user, 
                                dbpass=config.db.password,
                                dbname=config.db.name,
                                charset='utf8')
    app.install(mysql)
    
if __name__ == '__main__':

    parser = argparse.ArgumentParser("Stream tweets from stdin into a database")
    parser.add_argument("ini_file", type=str, help="name of the ini file containing db connection info")
    args = parser.parse_args()
    
    config = settings.Settings(args.ini_file)
    
    setup_database(config)
    
    bottle.run(ReverseProxied(StripPathMiddleware(app)),
               host=config.web.host, port=config.web.port, debug=True)

