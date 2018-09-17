import requests
import logging
from os.path import basename
from criteo.vault.config.helpers import *
from criteo.vault.config.variables import BUILD_PATH


def fetch_ldap_groups(environment):
    try:
        res = requests.get("https://idm.{}.crto.in/tool/ldapUserGroup".format(environment))
        groups = res.json()
        logging.debug("Fetched groups:")
        logging.debug(groups)
        return groups
    except Exception as e:
        logging.error("Error while getting the remote groups from idm.crto.in, response was:")
        logging.error(res)
        raise e


def fetch_ldap_users(environment):
    try:
        res = requests.get("https://idm.{}.crto.in/tool/ldapGroupMembersInfo/gu-rnd".format(environment))
        users = res.json()
        logging.debug("Fetched users:")
        logging.debug(users)
        return [user["name"] for user in users]
    except Exception as e:
        logging.error("Error while getting the remote users from idm.crto.in, response was:")
        logging.error(res)
        raise e


def fetch_local_ldap_groups():
    groups = {}

    def load_group_info(file):
        data = parse(file)
        group_name = basename(get_name(file))
        groups[group_name] = data

    crawl_map(load_group_info, BUILD_PATH + "/auth/ldap/groups/*.json")
    return groups  # groups = {'gu-idm': {'policies': ['abc']}}


def fetch_local_ldap_users():
    entities = {}

    def load_entity_info(file):
        data = parse(file)
        entity_name = basename(get_name(file))
        entities[entity_name] = data

    crawl_map(load_entity_info, BUILD_PATH + "/auth/ldap/users/*.json")
    return entities  # entity = {'t.jacquart': {'policies': ['abc']}}


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


def update_ldap_entity_aliases(client, ctx):
    if 'env' not in ctx:
        raise RuntimeError("You must provide env in context object")
    auth_backends = client.list_auth_backends()
    if 'ldap/' not in auth_backends:
        raise RuntimeError(
            "LDAP Not initialized or not found, "
            "If it's the first run. please make sure a first pass has been made.")
    ldap_accessor = auth_backends['ldap/']['accessor']
    local_entities = fetch_local_ldap_users()
    entities = fetch_ldap_users(ctx['env'])
    aliases_to_delete, _ = list_entity_alias_from_accessor(client, ldap_accessor)
    for entity in entities:
        policy_list = local_entities.get(entity, {}).get('policies', [])

        metadata = {"ldap_type": "UAD"}

        identity_entity_id, entity_data = lookup_entity_by_name(client, entity)
        if not identity_entity_id:
            logging.info("entity {name} is missing, creating it.".format(name=entity))
            identity_entity_id, entity_data = create_entity(client, entity)
        logging.debug("entity {name} has id {id}".format(name=entity, id=identity_entity_id))
        identity_entity_alias_id, entity_alias_data = lookup_entity_by_name(client, entity, ldap_accessor)
        if identity_entity_alias_id and identity_entity_alias_id != identity_entity_id:
            delete_identity_generic(client, 'entity', identity_entity_id, alias=False)
            identity_entity_id = identity_entity_alias_id
            entity_data = entity_alias_data
        create_entity(client, entity, policies=policy_list, metadata=metadata, ID=identity_entity_id)
        if entity in local_entities:
            client.delete('auth/ldap/users/{}'.format(entity))
        alias_entity_id = None
        if type(entity_data) is dict and entity_data.get('aliases', {}) \
                and entity_data['aliases'][-1]['mount_accessor'] == ldap_accessor:
            alias_entity_id = entity_data['aliases'][-1]['id']
        else:
            alias_entity_id, _ = update_entity_alias(client, entity, identity_entity_id, ldap_accessor, alias_entity_id)
        if alias_entity_id in aliases_to_delete:
            # We know him, don't delete it
            aliases_to_delete.remove(alias_entity_id)

    for ID in aliases_to_delete:
        delete_identity_generic(client, 'entity', ID, alias=True)
