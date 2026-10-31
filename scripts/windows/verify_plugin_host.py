import argparse
from fireblade.validation.plugin_checks import verify

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',required=True);parser.add_argument('--fixture',required=True)
    args=parser.parse_args();print(verify(args.host,args.fixture))
