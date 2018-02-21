#!/usr/bin/env python3

import os
import pprint
import hvac
import hcl
import sys
import shutil

import teams
import logging
import glob
from helper import *

STATIC_CONF_PATH = "../static-configurations"
BUILD_PATH = "../build/"

VAULT_MOUNTS_PATH = "sys/mounts"
VAULT_POLICIES_PATH = "sys/policy"

VAULT_DATA_KEY = "data"


def enable_auth_backends(client, conf_dir):
    backends = client.list_auth_backends()
    for backend in [os.path.basename(x) for x in glob.glob("{}/auth/*".format(conf_dir)) if
                    os.path.isdir(x) and os.path.basename(x) + "/" not in backends]:
        logging.info("Mounted auth backend %s", backend)
        client.enable_auth_backend(backend_type=backend)


def enable_secret_backends(client, conf_dir):
    backends = client.list_secret_backends()
    for backend, conf in [(get_name(os.path.basename(x)), parse(x)) for x in
                          glob.glob("{}/{}/*".format(conf_dir, VAULT_MOUNTS_PATH))]:
        backend_path = backend + "/"
        if backend_path in backends:
            orig = backends[backend_path]
            if orig['type'] is not conf['type']:
                logging.error("%s secret backend have a different type in the configuration and server", backend)
            if orig['description'] is not conf['description']:
                logging.warning("%s secret backend have a different description in the configuration and server",
                                backend)
            logging.info("Updating TTL information for %s", backend)
            client.write("{}/{}/tune".format(VAULT_MOUNTS_PATH, backend),
                         default_lease_ttl=conf.get("config", {}).get("default_lease_ttl", 0),
                         max_lease_ttl=conf.get("config", {}).get("max_lease_ttl", 0))
        else:
            logging.info("Enabling %s secret backend", backend)
            client.write("{}/{}".format(VAULT_MOUNTS_PATH, backend), **conf)


def build_static_config(input_dir, output_dir, template=True, ctx=None):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    elif not os.path.isdir(output_dir):
        raise Exception("Output %s is not a directory")
    else:
        logging.info("Cleaning the build directory")
        shutil.rmtree(output_dir)
        os.mkdir(output_dir)

    def build_file(file=""):
        outfile = file.replace(input_dir, output_dir)
        content = ""
        if os.path.isdir(file):
            if not os.path.exists(outfile):
                os.mkdir(outfile)
            return
        elif get_extension(file) is ".template" and template is True:
            content = render_template(file, ctx)
            logging.info("Rendering %s", file)
        else:
            content = read_file(file)
        logging.debug("Writing %s", outfile)
        write_file(outfile, content)

    crawl_map(build_file, input_dir + "/**", input_dir + "/**/.*")


def apply_configuration(client, conf_dir, cleanup=True):
    def apply_then_cleanup(dir):
        all = glob.glob(dir + "/*")
        dirs = [x for x in all if os.path.isdir(x)]
        configs = [(vaultify_path(get_name(x)), parse(x)) for x in all if x not in dirs]
        old_configs = client.list(vaultify_path(dir)) or []
        if not os.path.exists(dir + "/.noupdate"):
            if VAULT_DATA_KEY in old_configs:
                old_configs = [vaultify_path(dir + "/" + x) for x in old_configs[VAULT_DATA_KEY]["keys"]]
                logging.debug("Existing configs in vault: %s", old_configs)
                # We can't touch it, it's hardcoded, it sucks.
                if vaultify_path(dir) == VAULT_POLICIES_PATH:
                    old_configs.remove(vaultify_path(dir + "/root"))
            for path, config in configs:
                logging.info("Updating %s", path)
                if path.startswith(VAULT_POLICIES_PATH):
                    client.write(path, policy=hcl.dumps(config))
                else:
                    client.write(path, **config)
                if path in old_configs:
                    old_configs.remove(path)
            if cleanup is True and not os.path.exists(dir + "/.nocleanup"):
                for config in old_configs:
                    logging.info("Deleting %s", config)
                    client.delete(config)
        for subdir in dirs:
            logging.debug("Entering %s", subdir)
            apply_then_cleanup(subdir)

    crawl_map(apply_then_cleanup, conf_dir + "sys/*", conf_dir + "/*")


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    default_path = os.path.dirname(__file__)
    if default_path:
        os.chdir(default_path)

    VAULT_ADDR = os.getenv('VAULT_ADDR', "http://127.0.0.1:8200")
    VAULT_TOKEN = os.environ['VAULT_TOKEN']
    ENV = os.getenv('CRITEO_ENV', 'dev')

    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    assert_valid_client(client)

    build_static_config(STATIC_CONF_PATH, BUILD_PATH, ctx={"env": ENV})

    teams.generate_team_storage("../configurations/teams", BUILD_PATH)
    enable_auth_backends(client, BUILD_PATH)
    enable_secret_backends(client, BUILD_PATH)
    apply_configuration(client, BUILD_PATH, cleanup=True)


if __name__ == '__main__':
    main()
