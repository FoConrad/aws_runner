#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import sys
import json
import code
import argparse
import IPython
from tarfile import is_tarfile


class AwsWorker(object):
    def __init__(self, args):
        pass

def run_main(args: argparse.Namespace, arg_dict: dict=None):
    if arg_dict is not None:
        base_set = arg_dict # Type: dict
    else:
        base_set = json.load(args.config_file)
        if args.update:
            for upd in args.update:
                base_set[upd] = vars(args)[upd]

    if isinstance(base_set['files'], str):
        base_set['files'] = open(base_set['files'], 'rb')
    if isinstance(base_set['read_key'], str):
        base_set['read_key'] = open(base_set['read_key'], 'rb')

def build_config(args: argparse.Namespace):
    if args.command_str is None:
        raise ValueError('Must set value for --command_str in config mode')
    # Can use Namespace directly to make dict, and then to json
    arg_dict = {key: value.name if hasattr(value, 'name') else value
                for key, value in vars(args).items()}
    arg_dict = {k: v for k, v in arg_dict.items() if  is_json_serializable(v)}
    if args.save is not None:
        json.dump(arg_dict, args.save)
    if args.run:
        run_main(args, arg_dict=arg_dict)
        
def is_json_serializable(x):
    try:
        json.dumps(x)
        return True
    except TypeError:
        return False

class FileAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not is_tarfile(values.name):
            raise ValueError('File {} is not at tar archive'.format(values))
        setattr(namespace, self.dest, values)

class CaptureArgv(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        vs = [arg.replace('-', '_') for arg in 
              ['num-clients', 'base-dir', 'branch', 'files', 'pull', 
               'read-key', 'command-str'] if ('--'+arg) in sys.argv]
        setattr(namespace, self.dest, vs)

def extension_file_type(name, extension, mode):
    return argparse.FileType(mode)(
        name if name.endswith(extension) else name + extension)

def parse_args():
    """
    Program entrance and command-line argument parsing.
    """
    # Is this annoying? Replace with: lambda _: []
    _prefixes = lambda string: [string[:end] for end in range(1, len(string))]

    def_help = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(
        prog='./aws_runner.py', formatter_class=def_help)

    subparsers = parser.add_subparsers(
        help='execution or configuration modes (one of the two is required!)')
    subparsers.required = True

    # Rub sub command solely takes a configuration file and runs the experiment
    # while allowing values from the config file to be overridden with fresh
    # command line arguments
    run_parser = subparsers.add_parser(
        'run', aliases=_prefixes('run'), formatter_class=def_help,
        help='actual run from config file noting that additional command line '
        'arguments will override those found in the configuration file')
    run_parser.add_argument(
        'config_file', nargs='?', default='config.json',
        type=lambda name: extension_file_type(name, '.json', 'r'),
        help='configuration file describing execution to take place')
    run_parser.add_argument(
        '--update', action=CaptureArgv, nargs=0,
        help='update the configuration file with command line arguments '
        'provided to main parser')
    run_parser.set_defaults(main=run_main)

    # Allows building up of command line arguments by emitting choices back
    # to terminal. When user is satisfied, they may either: 
    #   1) save the configuration with --save <output>.json
    #   2) run with the arguments with --run.
    # The options are not mutually exclusive, lastly.
    config_parser = subparsers.add_parser(
        'config', aliases=_prefixes('config'), formatter_class=def_help,
        help='build configuration file, dry run showing values passed, or '
        'directly run')
    config_parser.add_argument(
        '--save', type=lambda name: extension_file_type(name, '.json', 'w'), 
        const='config.json', nargs='?', help='save run configuration described '
        'in the arguments')
    config_parser.add_argument(
        '--run', action='store_true', help='execute the current configuration')
    config_parser.set_defaults(main=build_config)

    # Finally the set of arguments excepted for either subcommand to both
    # allow 'config' to build up configuration, and 'run' to override select
    # configuration values.
    parser.add_argument('--num-clients', type=int, default=1, metavar='N',
                        help='number of AWS clients to start and run on')
    parser.add_argument('--base-dir', type=str, default='~',
                        help='base directory to enter on AWS machines')
    parser.add_argument('--branch', type=str, default=None,
                        help='branch to checkout, if base-dir is git repo')
    parser.add_argument('--files', type=argparse.FileType('rb'), default=None,
                        action=FileAction, metavar='FILES.tar', 
                        help='TAR archive to send and extract in base-dir on '
                        'each AWS worker')
    parser.add_argument('--pull', action='store_true',
                        help='used for pulling new '
                        'changes to branch listed above. Use with --read-key'
                        'read-only key if needed')
    parser.add_argument('--read-key', type=argparse.FileType('rb'),
                        default=None, metavar='READ_ONLY_KEY', 
                        help='a read only key if git repository is protected')
                        #metavar='READ_KEY.gpg', help='used for pulling new '
    parser.add_argument('--command-str', type=str,
                        help='command to run on each machine. NOTE: will be '
                        'formatted with clients index [0, N-1], replacing '
                        'every {} encountered (you may need to quote)')



    # Error for omitting a subcommand is, unfortunately, not very informative
    # and not clearly the desired behavior. Instead better to print help
    try:
        return parser.parse_args()
    except TypeError as te:
        if 'sequence item 0' in te.args[0]:
            print('Must chose a subcommand')
            return parser.parse_args(['-h'])
        raise

# Main function is an attribute set by each sub-parser and hence callable. To
# avoid more globals, just close main invocation in lambda
if __name__ == '__main__':
    (lambda args: args.main(args))(parse_args())
