import requests
import logging
from functools import lru_cache
from os.path import basename
from criteo.vault.config.helpers import *
from criteo.vault.config.variables import BUILD_PATH


@lru_cache(1)
def fetch_ldap_groups(environment):
    groups = []
    for endpoint in ["ldapUserGroup", "ldapServiceGroup"]:
        try:
            url = "https://idm.{}.crto.in/tool/{}".format(environment, endpoint)
            res = requests.get(url)
            assert(res.status_code in [200, 204])
            _g = res.json()
            logging.debug("Fetched groups from %s:", url)
            logging.debug(_g)
            groups += _g
        except Exception as e:
            logging.error("Error while getting the remote groups from %s, response was:", url)
            logging.error(res.content)
            raise e
    return groups


@lru_cache(1)
def fetch_ldap_users(environment):
    try:
        res = requests.get("https://idm.{}.crto.in/tool/ldapGroupMembersInfo/gu-rnd".format(environment))
        assert(res.status_code in [200, 204])
        users = res.json()
        logging.debug("Fetched users:")
        logging.debug(users)
        return [user["name"] for user in users]
    except Exception as e:
        logging.error("Error while getting the remote users from idm.%s.crto.in, response was:", environment)
        logging.error(res.content)
        raise e


@lru_cache(1)
def fetch_ldap_services(environment):
    try:
        res = requests.get("https://idm.{}.crto.in/tool/ldapServiceAccount".format(environment))
        assert(res.status_code in [200, 204])
        users = res.json()
        logging.debug("Fetched services:")
        logging.debug(users)
        return [user["name"] for user in users if user["name"].startswith("svc-")]
    except Exception as e:
        logging.error("Error while getting the remote users from idm.%s.crto.in, response was:", environment)
        logging.error(res.content)
        raise e


@lru_cache(3)
def _fetch_local_ldap_generic(type):
    r = {}

    def load_info(file):
        data = parse(file)
        name = basename(get_name(file))
        r[name] = data

    crawl_map(load_info, BUILD_PATH + "/auth/ldap/{}/*.json".format(type))
    return r  # r = {'gu-idm': {'policies': ['abc']}}


def fetch_local_ldap_groups():
    return _fetch_local_ldap_generic("groups")


def fetch_local_ldap_users():
    return _fetch_local_ldap_generic("users")


def attach_aliases_from_backends(client, ctx, backends):
    for backend in backends:
        attach_aliases_from_backend(client, ctx, backend)


def attach_aliases_from_backend(client, ctx, backend):
    if 'env' not in ctx:
        raise RuntimeError("You must provide env in context object")
    env = ctx['env']
    auth_backends = client.list_auth_backends()
    if backend + '/' not in auth_backends:
        raise RuntimeError(
            "Auth Backend {} Not initialized or not found, \n".format(type) +
            "If it's the first run. please make sure a first pass has been made.")
    backend_accessor = auth_backends[backend + '/']['accessor']
    humans = fetch_ldap_users(env)
    # Trim the prefix
    # TODO: Make this behavior configurable if we ever step on a backend relying on LDAP names
    services = [service[len('svc-'):] for service in fetch_ldap_services(env)]
    ldap_entities = humans + services

    # Get entities from Vault
    # We should only act on present ldap users entities to avoid uncontrolled behavior
    # Waiting for next release of vault for endpoint to be released
    # present_entities = client.list("identity/entity/name")
    # entities = set(ldap_entities).intersection(present_entities)
    entities = ldap_entities

    aliases_to_delete, _ = list_entity_alias_from_accessor(client, backend_accessor)
    for entity in entities:
        # Fetch the ID from the Name
        identity_entity_id, entity_data = lookup_entity_by_name(client, entity)

        # Raise if we find that a listed entity is not lookup-able. This should not be possible
        if not identity_entity_id:
            raise RuntimeError("entity {name} is missing, potential race condition.".format(name=entity))

        logging.debug("entity {name} has id {id}".format(name=entity, id=identity_entity_id))

        # Search for an entity with an already attached alias with this name
        identity_entity_alias_id, entity_alias_data = lookup_entity_by_name(client, entity, backend_accessor)

        # We are the source of truth, if alias entity_id is not the right one, we override it
        # This usually mean someone logged in with a method before we actually mapped him to its virtual entity
        if identity_entity_alias_id and identity_entity_alias_id != identity_entity_id:
            delete_identity_generic(client, 'entity', identity_entity_id, alias=False)
            identity_entity_id = identity_entity_alias_id
            entity_data = entity_alias_data

        alias_entity_id = None
        assert (type(entity_data) is dict)
        entity_aliases = entity_data.get("aliases", None) or []
        relevant_alias = [x for x in entity_aliases if x['mount_accessor'] == backend_accessor]

        if len(relevant_alias) > 0:
            alias_entity_id = relevant_alias[0]['id']
        else:
            alias_entity_id, _ = update_entity_alias(client, entity, identity_entity_id, backend_accessor,
                                                     alias_entity_id)
        if alias_entity_id in aliases_to_delete:
            # We know him, don't delete it
            aliases_to_delete.remove(alias_entity_id)
    for ID in aliases_to_delete:
        delete_identity_generic(client, 'entity', ID, alias=True)


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
    env = ctx['env']
    auth_backends = client.list_auth_backends()
    if 'ldap/' not in auth_backends:
        raise RuntimeError(
            "LDAP Not initialized or not found, "
            "If it's the first run. please make sure a first pass has been made.")
    ldap_accessor = auth_backends['ldap/']['accessor']
    local_entities = fetch_local_ldap_users()

    humans = fetch_ldap_users(env)
    services = fetch_ldap_services(env)
    entities = humans + services
    aliases_to_delete, _ = list_entity_alias_from_accessor(client, ldap_accessor)
    for entity_name in entities:
        alias_name = entity_name

        policy_list = local_entities.get(entity_name, {}).get('policies', [])

        if entity_name.startswith('svc-'):
            entity_name = entity_name[len('svc-'):]
            policy_list.append('service-self-ro')

        metadata = {"ldap_type": "UAD"}

        identity_entity_id, entity_data = lookup_entity_by_name(client, entity_name)
        if not identity_entity_id:
            logging.info("entity {name} is missing, creating it.".format(name=entity_name))
            identity_entity_id, entity_data = create_entity(client, entity_name)
        logging.debug("entity {name} has id {id}".format(name=entity_name, id=identity_entity_id))
        identity_entity_alias_id, entity_alias_data = lookup_entity_by_name(client, alias_name, ldap_accessor)
        if identity_entity_alias_id and identity_entity_alias_id != identity_entity_id:
            delete_identity_generic(client, 'entity', identity_entity_id, alias=False)
            identity_entity_id = identity_entity_alias_id
            entity_data = entity_alias_data
        create_entity(client, entity_name, policies=policy_list, metadata=metadata, ID=identity_entity_id)
        if entity_name in local_entities:
            client.delete('auth/ldap/users/{}'.format(entity_name))
        alias_entity_id = None
        assert (type(entity_data) is dict)
        logging.debug("entity %s data: %s", entity_name, entity_data)
        entity_aliases = entity_data.get("aliases", None) or []
        relevant_alias = [x for x in entity_aliases if x['mount_accessor'] == ldap_accessor]

        if len(relevant_alias) > 0:
            alias_entity_id = relevant_alias[0]['id']
        else:
            alias_entity_id, _ = update_entity_alias(client, alias_name, identity_entity_id, ldap_accessor,
                                                     alias_entity_id)
        if alias_entity_id in aliases_to_delete:
            # We know him, don't delete it
            aliases_to_delete.remove(alias_entity_id)

    for ID in aliases_to_delete:
        delete_identity_generic(client, 'entity', ID, alias=True)
