#!/usr/bin/env python3

import hvac
import sys
import shutil

import argparse
import shutil
import sys

from criteo.vault.config.app.teams import *
from criteo.vault.config.variables.vault import *


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
        outfile = file.replace(input_dir, output_dir).lower()
        content = ""
        if os.path.isdir(file):
            if not os.path.exists(outfile):
                os.mkdir(outfile)
            return
        elif get_extension(file) == ".template" and template is True:
            content = render_template(file, ctx)
            outfile = outfile.replace(".template", "")
            logging.info("Rendering %s", file)
        else:
            content = read_file(file)
        logging.debug("Writing %s", outfile)
        write_file(outfile, content)

    crawl_map(build_file, input_dir + "/**", input_dir + "/**/.*")


def apply_configuration(client, conf_dir, cleanup=True):
    def apply_then_cleanup(folder):
        resources = glob.glob(folder + "/*")
        dirs = [x for x in resources if os.path.isdir(x)]
        configs = [(vaultify_path(get_name(x)), parse(x)) for x in resources if x not in dirs]
        old_configs = client.list(vaultify_path(folder)) or []
        if not os.path.exists(folder + "/.noupdate"):
            if VAULT_DATA_KEY in old_configs:
                old_configs = [vaultify_path(folder + "/" + x) for x in old_configs[VAULT_DATA_KEY]["keys"]]
                logging.debug("Existing configs in vault: %s", old_configs)
                # We can't touch it, it's hardcoded, it sucks.
                if vaultify_path(folder) == VAULT_POLICIES_PATH:
                    old_configs.remove(vaultify_path(folder + "/root"))
            for path, config in configs:
                logging.info("Updating %s", path)
                if path.startswith(VAULT_POLICIES_PATH):
                    client.write(path, policy=hcl.dumps(config))
                else:
                    client.write(path, **config)
                if path in old_configs:
                    old_configs.remove(path)
            if cleanup is True and not os.path.exists(folder + "/.nocleanup"):
                for config in old_configs:
                    logging.info("Deleting %s", config)
                    client.delete(config)
        for subdir in dirs:
            logging.debug("Entering %s", subdir)
            apply_then_cleanup(subdir)
    crawl_map(apply_then_cleanup, conf_dir + "sys/*", conf_dir + "/*")


def main():
    parser = argparse.ArgumentParser(description="Vault Deployer")
    parser.add_argument("-t", "--token", help="The vault token you want to use", default=os.getenv("VAULT_TOKEN", ""))
    parser.add_argument("-E", "--criteo-env", help="Criteo ENV to substitute in strings", dest="env", default=os.getenv("CRITEO_ENV", "preprod"))
    parser.add_argument("-H", "--vault-addr", help="The vault server address", dest='addr',
                        default=os.getenv("VAULT_ADDR", "https://127.0.0.1:8200"))
    parser.add_argument("-d", "--debug", help="Enable debug logging", dest='loglevel', action="store_const",
                        const=logging.DEBUG, default=logging.WARNING)
    parser.add_argument("-v", "--verbose", help="Enable verbose logging", dest='loglevel', action="store_const",
                        const=logging.INFO)
    parser.add_argument('-B', "--no-build", help="Prevent the configuration to be builded", dest='nobuild',
                        action="store_true")
    parser.add_argument('-D', "--no-deploy", help="Prevent the configuration to be deployed", dest='nodeploy',
                        action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, stream=sys.stdout)

    go_vcs_root(os.getcwd(), default=os.getcwd())

    if not args.nobuild:
        build_static_config(STATIC_CONF_PATH, BUILD_PATH, ctx={"env": args.env})
        generate_team_storage("configurations/teams", BUILD_PATH)
    if not args.nodeploy:
        if not args.token:
            logging.error("You need to provide a VAULT_TOKEN.")
        client = hvac.Client(url=args.addr, token=args.token)
        assert_valid_client(client)
        enable_auth_backends(client, BUILD_PATH)
        enable_secret_backends(client, BUILD_PATH)
        apply_configuration(client, BUILD_PATH, cleanup=True)


if __name__ == '__main__':
    main()
