#!/usr/bin/env python3

import hvac
from hvac.exceptions import UnexpectedError
import sys
import shutil

import argparse
import shutil
import sys

from criteo.vault.config.app.teams import *
from criteo.vault.config.app.group import *
from criteo.vault.config.app.identity import *
from criteo.vault.config.variables.vault import *


def enable_mounts(client, conf_dir, path):
    remote_mounts = client.read(path)['data']
    plugins = client.list('sys/plugins/catalog').get('data', {}).get('keys', [])

    for local_mount, conf in [(get_name(os.path.basename(x)), parse(x)) for x in
                              glob.glob("{}/{}/*.json".format(conf_dir, path))]:
        mount_path = local_mount + "/"
        if conf['type'] == "plugin":
            if conf['plugin_name'] == "":
                logging.error("You must provide a valid plugin_name in %s", local_mount)
                exit(1)
            elif conf['plugin_name'] not in plugins:
                logging.warning("Plugin based mount detected in %s that is not in the deployed plugins of the vault server. Skipping..", local_mount)
                shutil.rmtree("{}/{}/{}/".format(conf_dir, "sys/auth", local_mount), True)
                shutil.rmtree("{}/{}/{}".format(conf_dir, "auth", local_mount))
                continue
        if mount_path in remote_mounts:
            orig = remote_mounts[mount_path]
            if orig['type'] != conf['type']:
                logging.error("%s/%s mount have a different type in the configuration and server", path,  local_mount)
                logging.error("Remote: %s", orig)
                logging.error("Local: %s", conf)
        else:
            logging.info("Enabling %s mount", local_mount)
            client.write("{}/{}".format(path, local_mount), **conf)


def enable_auth_backends(client, conf_dir):
    enable_mounts(client, conf_dir, VAULT_AUTH_MOUNTS_PATH)


def enable_secret_backends(client, conf_dir):
    enable_mounts(client, conf_dir, VAULT_MOUNTS_PATH)


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


def apply_configuration(client, conf_dir, cleanup=False):
    def apply_then_cleanup(folder):
        resources = glob.glob(folder + "/*")
        dirs = []
        configs = []
        for r in resources:
            if os.path.isdir(r):
                dirs.append(r)
            else:
                configs.append((vaultify_path(r), parse(r)))
        do_cleanup = cleanup and not os.path.exists(folder + '/.nocleanup')
        api_path = vaultify_path(folder)
        old_configs = []
        try:
            old_configs = ["{}/{}".format(api_path, x) for x in client.list(api_path)['data']['keys'] if
                           not x.endswith('/')]
            if api_path == VAULT_POLICIES_PATH:
                old_configs.remove(api_path + "/root")
            logging.debug("Existing configs in vault:")
            for x in old_configs:
                logging.debug("- {}".format(x))
        except UnexpectedError as e:
            if e.errors is not None:
                raise e
            if do_cleanup:
                logging.error("{} doesn't support listing. Add .nocleanup in the directory".format(api_path))
                exit(1)
            else:
                logging.warning(
                    "{} doesn't support listing. No information can be given on already present configurations".format(
                        api_path))
        except (TypeError, KeyError):
            old_configs = []
        if not os.path.exists(folder + "/.noupdate"):
            for path, config in configs:
                logging.info("Updating %s", path)
                if path.startswith(VAULT_POLICIES_PATH):
                    # Policies needs to be encoded in policy field
                    client.write(path, policy=hcl.dumps(config))
                else:
                    client.write(path, **config)
                if path in old_configs:
                    old_configs.remove(path)
            for config in old_configs:
                if do_cleanup:
                    logging.info("Deleting {}".format(config))
                    client.delete(config)
                else:
                    logging.info("{} is not deleted".format(config))
        for subdir in dirs:
            logging.debug("Entering %s", subdir)
            apply_then_cleanup(subdir)

    crawl_map(apply_then_cleanup, conf_dir + "sys/*", conf_dir + "/*")


def main():
    parser = argparse.ArgumentParser(description="Vault Deployer")
    parser.add_argument("-t", "--token", help="The vault token you want to use", default=os.getenv("VAULT_TOKEN", ""))
    parser.add_argument("-E", "--criteo-env", help="Criteo ENV to substitute in strings", dest="env",
                        default=os.getenv("CRITEO_ENV", "preprod"))
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
    parser.add_argument('-C', "--no-cleanup", help="Prevent the configuration to be cleared on deploy",
                        dest='nocleanup',
                        action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, stream=sys.stdout)

    go_vcs_root(os.getcwd(), default=os.getcwd())

    ctx = {"env": args.env}

    if not args.nobuild:
        build_static_config(STATIC_CONF_PATH, BUILD_PATH, ctx=ctx)
        generate_team_storage("configurations/teams", BUILD_PATH)
    if not args.nodeploy:
        if not args.token:
            logging.error("You need to provide a VAULT_TOKEN.")
        client = hvac.Client(url=args.addr, token=args.token)
        assert_valid_client(client)
        # Apply a first time jenkins policy, to make sure changes are passed before actually touching any other endpoint
        client.set_policy("jenkins-update", rules=parse("{}/{}/jenkins-update.hcl".format(BUILD_PATH, VAULT_POLICIES_PATH)))
        enable_auth_backends(client, BUILD_PATH)
        enable_secret_backends(client, BUILD_PATH)
        apply_configuration(client, BUILD_PATH, cleanup=not args.nocleanup)

        update_ldap_group_aliases(client, ctx=ctx)
        update_ldap_entity_aliases(client, ctx=ctx)
        link_policies_to_users(client, BUILD_PATH)


if __name__ == '__main__':
    main()
