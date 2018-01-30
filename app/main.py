#!/usr/bin/env python3

import os
import pprint
import hvac

import helper


def enable_auth_backend_ldap(client):
    if "ldap/" not in client.list_auth_backends().keys():
        client.enable_auth_backend(backend_type="ldap")

def write_config_ldap(client):
    config_location = "../configurations/auth/ldap/config/config.json"
    config_content = helper.read_json_file(config_location)
    client.write("/auth/ldap/config", **config_content)

def write_policies(client):
    policy_dir = "../configurations/sys/policy"

    def write_policy(f):
        policy_name = helper.get_name(f)
        print("INFO: writing policy {}...".format(policy_name))
        p = os.path.abspath(os.path.join(policy_dir, f))
        policy_content = helper.read_file(p)
        client.set_policy(policy_name, policy_content)
        print("INFO: wrote policy {}...".format(policy_name))

    helper.browse_folder(policy_dir, write_policy)

def add_policies_for_ldap_groups(client):
    policy_dir = "../configurations/auth/ldap/groups"

    def add_policy_for_ldap_groups(f):
        group_name = helper.get_name(f)
        print("INFO: writing policies for ldap group {}...".format(group_name))
        p = os.path.abspath(os.path.join(policy_dir, f))
        policy_content = helper.read_json_file(p)
        client.write("/auth/ldap/groups/{}".format(group_name), **policy_content)
        print("INFO: wrote policies for ldap group {}...".format(group_name))

    helper.browse_folder(policy_dir, add_policy_for_ldap_groups)

def add_policies_for_ldap_users(client):
    # TODO: for the moment only allow policy from ldap groups
    pass

def main():
    default_path = os.path.dirname(__file__)
    if default_path:
        os.chdir(default_path)

    VAULT_ADDR = os.environ['VAULT_ADDR']
    VAULT_TOKEN = os.environ['VAULT_TOKEN']
    ENV = os.environ.get('CRITEO_ENV', 'dev')

    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    pp = pprint.PrettyPrinter(indent=4)

    # enable auth backend only if disable
    enable_auth_backend_ldap(client)

    # erase existing configuration
    write_config_ldap(client)

    # erase policy if existing
    write_policies(client)
    add_policies_for_ldap_groups(client)

    # print information
    print("INFO: existing auth backends:\n{}".format(client.list_auth_backends().keys()))
    print("INFO: ldap configuration:\n{}".format(client.read("/auth/ldap/config")))
    policies = client.list_policies()
    print("INFO: existing policies:\n{}".format(policies))
    for policy in policies:
        print("INFO: {} policy:\n{}".format(policy, client.get_policy(policy)))


if __name__ == '__main__':
    main()
