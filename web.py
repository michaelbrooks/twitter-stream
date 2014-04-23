import bottle
from bottle import Bottle, run, template, view
import argparse
import settings

app = Bottle()

bottle.TEMPLATE_PATH.insert(0,'templates/')

@app.route('/')
@view('visualization')
def visualization():
    return {}
    
@app.route('/update')
def update():
    return { "some": "data" }

if __name__ == '__main__':

    parser = argparse.ArgumentParser("Stream tweets from stdin into a database")
    parser.add_argument("ini_file", type=str, help="name of the ini file containing db connection info")
    args = parser.parse_args()
    
    config = settings.Settings(args.ini_file)
    
    run(app, host=config.web.host, port=config.web.port)

