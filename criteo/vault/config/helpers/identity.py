from criteo.vault.config.variables import VALID_IDENTITY_TYPES
from criteo.vault.config.helpers import argument_checker


def identity_type_check(f):
    return argument_checker('identity_type', lambda t: t in VALID_IDENTITY_TYPES)(f)


def list_group_alias_from_accessor(client, mount_accessor):
    return list_identity_alias_from_accessor(client, 'group', mount_accessor)


def list_entity_alias_from_accessor(client, mount_accessor):
    return list_identity_alias_from_accessor(client, 'entity', mount_accessor)


@identity_type_check
def list_identity_alias_from_accessor(client, identity_type, mount_accessor):
    keys, data = list_identity_generic(client, identity_type, alias=True)
    ret_keys = []
    ret_info = {}
    for ID in keys:
        if data.get(ID, {}).get('mount_accessor', '') == mount_accessor:
            ret_keys.append(ID)
            ret_info[ID] = data[ID]
    return ret_keys, ret_info


@identity_type_check
def list_identity_generic(client, identity_type, alias=True):
    list_data = client.list('identity/{}/id'.format(identity_type + "-alias" if alias else ""))
    if not list_data:
        return [], {}
    return list_data['data']['keys'], list_data['data']['key_info']


def lookup_entity_by_name(client, name, alias_mount_accessor=""):
    return lookup_identity_generic(client, 'entity', 'name', name, alias_mount_accessor)


def lookup_entity_by_id(client, ID, alias_mount_accessor=""):
    return lookup_identity_generic(client, 'entity', 'id', ID, alias_mount_accessor)


def lookup_group_by_name(client, name, alias_mount_accessor=""):
    return lookup_identity_generic(client, 'group', 'name', name, alias_mount_accessor)


def lookup_group_by_id(client, ID, alias_mount_accessor=""):
    return lookup_identity_generic(client, 'group', 'id', ID, alias_mount_accessor)


@identity_type_check
def lookup_identity_generic(client, identity_type, attribute, value, alias_mount_accessor):
    if identity_type not in VALID_IDENTITY_TYPES:
        raise RuntimeError("Lookup on invalid type {}".format(identity_type))
    req = {}
    if alias_mount_accessor != "":
        attribute = "alias_" + attribute
        req["alias_mount_accessor"] = alias_mount_accessor
    req[attribute] = value
    res = client.write("identity/lookup/{}".format(identity_type), **req)
    if res is None:
        return None, None
    elif res.get('data', {}).get('id', "") == "":
        raise RuntimeError("Invalid data returned. Response is: {}".format(res))
    else:
        return res['data']['id'], res['data']


def create_entity(client, name, policies=None, metadata=None, disabled=False, ID=None):
    return create_identity_generic(client, 'entity', name, policies=policies, metadata=metadata, disabled=disabled,
                                   id=ID)


def create_group(client, name, type, policies=None, metadata=None, member_group_ids=None, member_entity_ids=None,
                 ID=None):
    if type not in ['internal', 'external']:
        raise RuntimeError("Invalid type given for create_group: {}".format(type))
    return create_identity_generic(client, 'group', name, policies=policies, metadata=metadata,
                                   member_group_ids=member_group_ids, member_entity_ids=member_entity_ids, type=type,
                                   id=ID)


@identity_type_check
def create_identity_generic(client, identity_type, name, policies=None, metadata=None, **kwargs):
    additional_args = {k: v for k, v in kwargs.items() if v is not None}
    req = {'name': name, 'policies': policies, 'metadata': metadata or {}, **additional_args}
    res = client.write("identity/{}".format(identity_type), **req)
    if res.get('data', {}).get('id', "") == "":
        raise RuntimeError("Invalid data returned. Response is: {}".format(res))
    else:
        return res['data']['id'], res['data']


def update_entity_alias(client, name, canonical_id, mount_accessor, ID=""):
    return create_identity_alias_generic(client, 'entity', name, canonical_id, mount_accessor, id=ID)


def update_group_alias(client, name, canonical_id, mount_accessor, ID=""):
    return create_identity_alias_generic(client, 'group', name, canonical_id, mount_accessor, id=ID)


@identity_type_check
def create_identity_alias_generic(client, identity_type, name, canonical_id, mount_accessor, **kwargs):
    additional_args = {k: v for k, v in kwargs.items() if v is not None}
    req = {'name': name, 'canonical_id': canonical_id, 'mount_accessor': mount_accessor, **additional_args}
    identity_type = identity_type + "-alias"
    res = client.write("identity/{}".format(identity_type), **req)
    if res.get('data', {}).get('id', "") == "":
        raise RuntimeError("Invalid data returned. Response is: {}".format(res))
    else:
        return res['data']['id'], res['data']


@identity_type_check
def delete_identity_generic(client, identity_type, id, alias=True):
    client.delete('identity/{}/id/{}'.format(identity_type + "-alias" if alias else identity_type, id))
