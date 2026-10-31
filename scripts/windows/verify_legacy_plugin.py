import argparse
from fireblade.validation.legacy_plugin_checks import verify
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--legacy',required=True);p.add_argument('--fixture',required=True);a=p.parse_args();print(verify(a.host,a.legacy,a.fixture))
