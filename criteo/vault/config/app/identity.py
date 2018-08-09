import requests
import logging
from os.path import basename
from criteo.vault.config.helpers import *
from criteo.vault.config.variables import BUILD_PATH


def fetch_ldap_groups(environment):
    return requests.get("https://idm.{}.crto.in/tool/ldapUserGroup".format(environment)).json()


def fetch_local_ldap_groups():
    groups = {}

    def load_group_info(file):
        data = parse(file)
        group_name = basename(get_name(file))
        groups[group_name] = data

    crawl_map(load_group_info, BUILD_PATH + "/auth/ldap/groups/*.json")
    return groups  # groups = {'gu-idm': {'policies': ['abc']}}


def update_ldap_group_aliases(client, ctx):
    if 'env' not in ctx:
        raise RuntimeError("You must provide env in context object")
    auth_backends = client.list_auth_backends()
    if 'ldap/' not in auth_backends:
        raise RuntimeError(
            "LDAP Not initialized or not found, "
            "If it's the first run. please make sure a first pass has been made.")
    ldap_accessor = auth_backends['ldap/']['accessor']
    local_groups = fetch_local_ldap_groups()
    groups = fetch_ldap_groups(ctx['env'])
    aliases_to_delete, _ = list_group_alias_from_accessor(client, ldap_accessor)
    for group in groups:
        name = group['name'].lower()
        description = sanitize_murphy_description(group['description'])
        policy_list = local_groups.get(name, {}).get('policies', [])

        metadata = {"description": description, "ldap_type": "UAD"}

        identity_group_id, group_data = lookup_group_by_name(client, name)
        if not identity_group_id:
            logging.info("group {name} is missing, creating it.".format(name=name))
            identity_group_id, _ = create_group(client, name, 'external')
        logging.debug("group {name} has id {id}".format(name=name, id=identity_group_id))
        create_group(client, name, 'external', policies=policy_list, metadata=metadata, ID=identity_group_id)
        if name in local_groups:
            client.delete('auth/ldap/groups/{}'.format(name))
        alias_group_id = None
        if type(group_data) is dict and group_data.get('alias', {}):
            alias_group_id = group_data['alias']['id']

        alias_group_id, _ = update_group_alias(client, name, identity_group_id, ldap_accessor, alias_group_id)
        if alias_group_id in aliases_to_delete:
            # We know him, don't delete it
            aliases_to_delete.remove(alias_group_id)

    for ID in aliases_to_delete:
        delete_identity_generic(client, 'group', ID, alias=True)
