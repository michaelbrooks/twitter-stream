import os, sys
from fabric.state import env
from fabric.api import local, warn_only, sudo
from fabric.contrib import files
from fabric.contrib.console import confirm
from fabric.context_managers import lcd, hide

root_dir = os.path.dirname(os.path.realpath(__file__))
trackfile = os.path.join(root_dir, 'trackfile.txt')
ini_file = os.path.join(root_dir, 'twitter_monitor.ini')
supervisord_conf = os.path.join(root_dir, 'supervisord.conf')
python_exe = sys.executable

def _jinja_render(template_path, values):
    """Render a template. Expects path relative to root_dir."""
    from jinja2 import Template, Environment, FileSystemLoader
    environment = Environment(loader=FileSystemLoader(root_dir))

    template = environment.get_template(template_path)
    return template.render(values)

def _save_template(target_path, template_path, values):
    result = _jinja_render(template_path, values)
    
    if os.path.isfile(target_path):
        if confirm("Do you want to regenerate %s? A backup would be created." % target_path, default=False):
            # Back up first
            with warn_only():
                local('cp %s %s~ 2> /dev/null || :' % (target_path, target_path))
        else:
            return
    
    with open(target_path, 'w') as outfile:
        outfile.write(result)
    
def _supervisor(command, *args, **kwargs):
    capture = kwargs.get('capture', False)

    with lcd(root_dir):
        if args:
            args = list(args)
            return local('supervisorctl %s %s' % (command, ' '.join(args)), capture=capture)
        elif command == 'status':
            return local('supervisorctl %s' % command, capture=capture)
        else:
            return local('supervisorctl %s all' % command, capture=capture)

def setup():
    with lcd(root_dir):
        app_name = os.path.basename(root_dir)
        run_files = os.path.join('/var/run', app_name)
        username = env.user
        
        
        local('touch %s' % trackfile)
        
        _save_template(supervisord_conf, 'templates/supervisord.conf', {
            'project_dir': root_dir,
            'run_files': run_files,
            'username': username,
            'path': os.environ.get('PATH', ''),
            'ini_file': ini_file,
            'python_exe': python_exe
        })
        
        _save_template(ini_file, 'templates/twitter_monitor.ini', {
            'trackfile': trackfile
        })
        
        _save_template('upstart.conf', 'templates/upstart.conf', {
            'project_dir': root_dir,
            'username': username,
            'supervisord_conf': supervisord_conf
        })
        
        # Hide this, it has passwords
        local('chmod 660 %s' % ini_file)
        
        print "Final steps:"
        print "1. Create the run directory: mkdir -p %s" % run_files
        print "2. Sudo copy upstart.conf to /etc/init/%s.conf or whatever." % app_name
        print "3. Create a MySQL database and user for storing tweets."
        print "4. Add your Twitter API info and database info to %s" % ini_file
        print "5. Edit the tracking terms in %s" % trackfile
        print "6. Start the stream with 'fab start'."

def stop(*args):
    """Stop one or more supervisor processes"""
    if len(args) == 0:
        if not confirm("Are you sure you want to stop ALL processes?", False):
            abort("Nevermind then.")

    _supervisor('stop', *args)

def start(*args):
    """Start one or more supervisor processes"""
    _supervisor('start', *args)

def restart(*args):
    """Restart one or more supervisor processes"""
    _supervisor('restart', *args)
        
def status(*args):
    """Get status of supervisor processes"""
    status = _supervisor('status', *args, capture=True)
    print status
    
    if len(args) == 1 and "RUNNING" in status:
        with hide('running'):
            pid = _supervisor('pid', *args, capture=True)
            local('pstree -p %s' % pid)
            