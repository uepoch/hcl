#!/usr/bin/python


import os
from datetime import datetime
import argparse
import hvac
import logging
import re

args = None
client = None
match_re = None


def vault_dump(source, dest):
    source += '/' if not source.endswith('/') else ''
    dest += "/" if not dest.endswith('/') else ''
    for path in client.list(source)['data']['keys']:
        if path.endswith("/"):
            logging.debug("Found a nested directory under %s", source + path)
            vault_dump(source + path, dest + path)
        else:
            logging.debug("Found a value in %s", source + path)
            client.write(dest + path, **client.read(source + path)['data'])


def rotateBackends(backends=None):
    if not backends:
        return
    length = max([int(re.findall('[0-9]+', x)[0]) for x in backends])
    for i in range(length, 0, -1):
        old = args.format.format(path=args.path.strip('/'), index=i, unit=args.unit)
        new = args.format.format(path=args.path.strip('/'), index=i + 1, unit=args.unit)
        if i >= args.keep_last:
            try:
                logging.info("Destroying %s", old)
                client.disable_secret_backend(old)
            except Exception:
                logging.warning("Failed to destroy %s", old)
        else:
            try:
                logging.info("Rotating %s to %s", old, new)
                client.remount_secret_backend(old, new)
            except Exception:
                logging.warning("Failed to rotate %s", old)


def main():
    parser = argparse.ArgumentParser(description="Simple script to rotate a vault kv backend")
    parser.add_argument("path", help="The path you want to rotate")
    parser.add_argument("-t", "--token", help="The vault token you want to use", default=os.getenv("VAULT_TOKEN"))
    parser.add_argument("-H", "--vault-addr", help="The vault server address", dest='addr',
                        default=os.getenv("VAULT_ADDR", "https://127.0.0.1:8200"))
    parser.add_argument("-d", "--debug", help="Enable debug logging", dest='loglevel', action="store_const",
                        const=logging.DEBUG, default=logging.WARNING)
    parser.add_argument("-v", "--verbose", help="Enable verbose logging", dest='loglevel', action="store_const",
                        const=logging.INFO)
    parser.add_argument("-k", "--keep-last", help="How much copy should we keep", default=3, type=int)
    parser.add_argument("-u", "--unit", help="Allow to configure a suffix for generated backends", default="")
    parser.add_argument("-f", "--format", help="Format used to create rotated backends", default="{path}-{index}{unit}")
    args = parser.parse_args()

    args.path = args.path.strip('/') + '/'  # Sanitize path used
    logging.basicConfig(level=args.loglevel)
    token = args.token or input("Enter Token: ")
    logging.debug("Authenticating to %s with token: %s", args.addr, token)
    client = hvac.Client(url=args.addr, token=token)

    match_re = re.compile(args.format.format(path=args.path.strip('/'), index="[0-9]+", unit=args.unit))
    if not client.is_authenticated():
        logging.error("Token isn't valid.")
        exit(2)
    backends = client.list_secret_backends()['data']
    logging.debug("All Backends:      %s", list(backends.keys()))

    if args.path not in backends.keys():
        logging.error("Backend %s not found", args.path)
        exit(2)
    elif backends[args.path]['type'] != 'kv':
        logging.error("Backend %s invalid type: %s", args.path, backends[args.path]['type'])
        exit(2)
    addBackends = {k: v for k, v in backends.items() if match_re.match(k)}
    logging.info("Matching backends:  %s", list(addBackends.keys()) + [args.path])

    invalidBackend = False
    for k, v in addBackends.items():
        if v['type'] != 'kv':
            invalidBackend = True
            logging.error("Backend %s invalid type: %s", k, v['type'])
    if invalidBackend:
        exit(2)
    rotateBackends(list(addBackends.keys()))
    newBackend = args.format.format(path=args.path.strip('/'), index=1, unit=args.unit)
    client.enable_secret_backend('kv', "Created at {}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                                 newBackend)
    vault_dump(args.path, newBackend)


if __name__ == '__main__':
    main()
