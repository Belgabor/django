import django
from django.core.management.base import BaseCommand, CommandError, handle_default_options 
from optparse import OptionParser
import os
import sys
from imp import find_module

# For backwards compatibility: get_version() used to be in this module.
get_version = django.get_version

# A cache of loaded commands, so that call_command 
# doesn't have to reload every time it is called
_commands = None

def find_commands(management_dir):
    """
    Given a path to a management directory, return a list of all the command names 
    that are available. Returns an empty list if no commands are defined.
    """
    command_dir = os.path.join(management_dir,'commands')
    try:
        return [f[:-3] for f in os.listdir(command_dir) if not f.startswith('_') and f.endswith('.py')]
    except OSError:
        return []

def find_management_module(app_name):
    """
    Determine the path to the management module for the application named,
    without acutally importing the application or the management module.

    Raises ImportError if the management module cannot be found for any reason.
    """
    parts = app_name.split('.')
    parts.append('management')
    parts.reverse()
    path = None
    while parts:
        part = parts.pop()
        f,path,descr = find_module(part, path and [path] or None)
    return path
    
def load_command_class(app_name, name):
    """
    Given a command name and an application name, returns the Command 
    class instance. All errors raised by the importation process
    (ImportError, AttributeError) are allowed to propagate.
    """
    return getattr(__import__('%s.management.commands.%s' % (app_name, name), 
                   {}, {}, ['Command']), 'Command')()

def get_commands(load_user_commands=True, project_directory=None):
    """
    Returns a dictionary of commands against the application in which
    those commands can be found. This works by looking for a 
    management.commands package in django.core, and in each installed 
    application -- if a commands package exists, all commands in that
    package are registered.

    Core commands are always included; user-defined commands will also
    be included if ``load_user_commands`` is True. If a project directory
    is provided, the startproject command will be disabled, and the
    startapp command will be modified to use that directory.

    The dictionary is in the format {command_name: app_name}. Key-value
    pairs from this dictionary can then be used in calls to 
    load_command_class(app_name, command_name)
    
    If a specific version of a command must be loaded (e.g., with the
    startapp command), the instantiated module can be placed in the
    dictionary in place of the application name.
    
    The dictionary is cached on the first call, and reused on subsequent
    calls.
    """
    global _commands
    if _commands is None:
        _commands = dict([(name, 'django.core') 
                          for name in find_commands(__path__[0])])
        if load_user_commands:
            # Get commands from all installed apps
            from django.conf import settings
            for app_name in settings.INSTALLED_APPS:
                try:
                    path = find_management_module(app_name)
                    _commands.update(dict([(name, app_name) 
                                           for name in find_commands(path)]))
                except ImportError:
                    pass # No management module - ignore this app
                    
        if project_directory:
            # Remove the "startproject" command from self.commands, because
            # that's a django-admin.py command, not a manage.py command.
            del _commands['startproject']

            # Override the startapp command so that it always uses the
            # project_directory, not the current working directory 
            # (which is default).
            from django.core.management.commands.startapp import ProjectCommand
            _commands['startapp'] = ProjectCommand(project_directory)

    return _commands

def call_command(name, *args, **options):
    """
    Calls the given command, with the given options and args/kwargs.

    This is the primary API you should use for calling specific commands.

    Some examples:
        call_command('syncdb')
        call_command('shell', plain=True)
        call_command('sqlall', 'myapp')
    """
    try:
        app_name = get_commands()[name]
        if isinstance(app_name, BaseCommand): 
            # If the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, subcommand)
    except KeyError:
        raise CommandError, "Unknown command: %r" % name
    return klass.execute(*args, **options)
    
class LaxOptionParser(OptionParser): 
    """
    An option parser that doesn't raise any errors on unknown options.
    
    This is needed because the --settings and --pythonpath options affect
    the commands (and thus the options) that are available to the user. 
    """
    def error(self, msg): 
 	    pass

class ManagementUtility(object):
    """
    Encapsulates the logic of the django-admin.py and manage.py utilities.

    A ManagementUtility has a number of commands, which can be manipulated
    by editing the self.commands dictionary.
    """
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]
        self.prog_name = os.path.basename(self.argv[0])
        self.project_directory = None
        self.user_commands = False
        
    def main_help_text(self):
        """
        Returns the script's main help text, as a string.
        """
        usage = ['%s <subcommand> [options] [args]' % self.prog_name]
        usage.append('Django command line tool, version %s' % django.get_version())
        usage.append("Type '%s help <subcommand>' for help on a specific subcommand." % self.prog_name)
        usage.append('Available subcommands:')
        commands = get_commands(self.user_commands, self.project_directory).keys()
        commands.sort()
        for cmd in commands:
            usage.append('  %s' % cmd)
        return '\n'.join(usage)

    def fetch_command(self, subcommand):
        """
        Tries to fetch the given subcommand, printing a message with the
        appropriate command called from the command line (usually
        django-admin.py or manage.py) if it can't be found.
        """
        try:
            app_name = get_commands(self.user_commands, self.project_directory)[subcommand]
            if isinstance(app_name, BaseCommand): 
                # If the command is already loaded, use it directly.
                klass = app_name
            else:
                klass = load_command_class(app_name, subcommand)
        except KeyError:
            sys.stderr.write("Unknown command: %r\nType '%s help' for usage.\n" % (subcommand, self.prog_name))
            sys.exit(1)
        return klass
        
    def execute(self):
        """
        Given the command-line arguments, this figures out which subcommand is
        being run, creates a parser appropriate to that command, and runs it.
        """
        # Preprocess options to extract --settings and --pythonpath. These options
        # could affect the commands that are available, so they must be processed
        # early
        parser = LaxOptionParser(version=get_version(), 
                                 option_list=BaseCommand.option_list) 
        try:
            options, args = parser.parse_args(self.argv) 
            handle_default_options(options)
        except: 
            pass # Ignore any option errors at this point.
         
        try:
            subcommand = self.argv[1]
        except IndexError:
            sys.stderr.write("Type '%s help' for usage.\n" % self.prog_name)
            sys.exit(1)

        if subcommand == 'help':
            if len(args) > 2:
                self.fetch_command(args[2]).print_help(self.prog_name, args[2])
            else:
                sys.stderr.write(self.main_help_text() + '\n')
                sys.exit(1)
        # Special-cases: We want 'django-admin.py --version' and
        # 'django-admin.py --help' to work, for backwards compatibility.
        elif self.argv[1:] == ['--version']:
            print django.get_version()
        elif self.argv[1:] == ['--help']:
            sys.stderr.write(self.main_help_text() + '\n')
        else:
            self.fetch_command(subcommand).run_from_argv(self.argv)

class ProjectManagementUtility(ManagementUtility):
    """
    A ManagementUtility that is specific to a particular Django project.
    As such, its commands are slightly different than those of its parent
    class.

    In practice, this class represents manage.py, whereas ManagementUtility
    represents django-admin.py.
    """
    def __init__(self, argv, project_directory):
        super(ProjectManagementUtility, self).__init__(argv)
        self.project_directory = project_directory
        self.user_commands = True
                
def setup_environ(settings_mod):
    """
    Configure the runtime environment. This can also be used by external
    scripts wanting to set up a similar environment to manage.py.
    """
    # Add this project to sys.path so that it's importable in the conventional
    # way. For example, if this file (manage.py) lives in a directory
    # "myproject", this code would add "/path/to/myproject" to sys.path.
    project_directory, settings_filename = os.path.split(settings_mod.__file__)
    project_name = os.path.basename(project_directory)
    settings_name = os.path.splitext(settings_filename)[0]
    sys.path.append(os.path.join(project_directory, '..'))
    project_module = __import__(project_name, {}, {}, [''])
    sys.path.pop()

    # Set DJANGO_SETTINGS_MODULE appropriately.
    os.environ['DJANGO_SETTINGS_MODULE'] = '%s.%s' % (project_name, settings_name)
    return project_directory

def execute_from_command_line(argv=None):
    """
    A simple method that runs a ManagementUtility.
    """
    utility = ManagementUtility(argv)
    utility.execute()

def execute_manager(settings_mod, argv=None):
    """
    Like execute_from_command_line(), but for use by manage.py, a
    project-specific django-admin.py utility.
    """
    project_directory = setup_environ(settings_mod)
    utility = ProjectManagementUtility(argv, project_directory)
    utility.execute()
