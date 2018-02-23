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

VAULT_ROTATE_SUFFIX_UNIT_DAYS = "d"
VAULT_ROTATE_SUFFIX_UNIT_HOURS = "h"
VAULT_ROTATE_SUFFIX_FORMAT = "-{number}{unit}"


def enable_auth_backends(client, conf_dir):
    backends = client.list_auth_backends()
    for backend in [os.path.basename(x) for x in glob.glob("{}/auth/*".format(conf_dir)) if
                    os.path.isdir(x) and os.path.basename(x) + "/" not in backends]:
        logging.info("Mounted auth backend %s", backend)
        client.enable_auth_backend(backend_type=backend)


def enable_secret_backends(client, conf_dir):
    remote_backends = client.list_secret_backends()
    for local_backend, conf in [(get_name(os.path.basename(x)), parse(x)) for x in
                          glob.glob("{}/{}/*".format(conf_dir, VAULT_MOUNTS_PATH))]:
        backend_path = local_backend + "/"
        if backend_path in remote_backends:
            orig = remote_backends[backend_path]
            if orig['type'] != conf['type']:
                logging.error("%s secret backend have a different type in the configuration and server", local_backend)
                logging.error("Remote: %s", orig)
                logging.error("Local: %s", conf)
            if orig['description'] != conf['description']:
                logging.warning("%s secret backend have a different description in the configuration and server",
                                local_backend)
            logging.info("Updating TTL information for %s", local_backend)
            client.write("{}/{}/tune".format(VAULT_MOUNTS_PATH, local_backend),
                         default_lease_ttl=conf.get("config", {}).get("default_lease_ttl", 0),
                         max_lease_ttl=conf.get("config", {}).get("max_lease_ttl", 0))
        else:
            logging.info("Enabling %s secret backend", local_backend)
            client.write("{}/{}".format(VAULT_MOUNTS_PATH, local_backend), **conf)


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

def generate_versionned_policies(hours=3, days=2):
    pdir = BUILD_PATH + VAULT_POLICIES_PATH
    mdir = BUILD_PATH + VAULT_MOUNTS_PATH
    KVs = []
    for f in glob.glob(mdir+'/*'):
        logging.debug("Checking if %s is a KV mount", f)
        mount = parse(f)
        if mount.get("type", "") == "kv":
            KVs.append(os.path.basename(get_name(f)))
            logging.debug("- Adding it to the list")

    if len(KVs) > 0:
        logging.info("Found some KV mount-point to rotate: %s", KVs)
        def reconfigure_policy(f):
            p = parse(f)
            logging.debug("Searching in %s", f)
            for path, capabilities in list(p.get("path", {}).items()):
                mount_point = path.split('/')[0]
                if mount_point in KVs:
                    for i in  range(1, hours+1):
                        p["path"][path.replace(mount_point, mount_point+VAULT_ROTATE_SUFFIX_FORMAT.format(unit=VAULT_ROTATE_SUFFIX_UNIT_HOURS, number=i))] = capabilities
                    for i in  range(1, days+1):
                        p["path"][path.replace(mount_point, mount_point+VAULT_ROTATE_SUFFIX_FORMAT.format(unit=VAULT_ROTATE_SUFFIX_UNIT_DAYS, number=i))] = capabilities
                    logging.info("Updated %s with %d rotate paths on ", vaultify_path(f), hours+days, path)
            write_file(f, hcl.dumps(p, indent=4))
        crawl_map(reconfigure_policy, pdir+"/*")





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
    generate_versionned_policies(hours=3, days=2)
    apply_configuration(client, BUILD_PATH, cleanup=True)


if __name__ == '__main__':
    main()
