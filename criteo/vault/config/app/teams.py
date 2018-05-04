#!/usr/bin/env python3

import glob
import copy
from criteo.vault.config.helpers import *
from criteo.vault.config.variables.vault import VAULT_POLICIES_PATH, VAULT_VERSIONNED_KV_DATA, \
    VAULT_VERSIONNED_KV_METADATA, VAULT_VERSIONNED_KV_DELETE, VAULT_VERSIONNED_KV_DESTROY, VAULT_VERSIONNED_KV_UNDELETE, \
    VAULT_VERSIONNED_KV_KEYWORDS, VAULT_TEAMS_MOUNT

LDAP_BACKEND_PATH = "ldap/"
LDAP_PATH = "../auth/" + LDAP_BACKEND_PATH

# For now, only support ro/rw keys
ACL_ROLES = ['ro', 'rw']
ACL_GRANTERS = ['users', 'groups']

RO_RIGHTS = {"capabilities": ["read", "list"]}
RW_RIGHTS = {"capabilities": RO_RIGHTS['capabilities'] + ['update', 'create', 'delete']}
ADMIN_RIGHTS = {"capabilities": RW_RIGHTS['capabilities'] + ['sudo']}
NO_RIGHTS = {"capabilities": []}
TEAM_POLICY_PREFIX = "__team_policy"

DEFAULT_ROLES = {"ro": RO_RIGHTS, "rw": RW_RIGHTS, "admin": ADMIN_RIGHTS}


# TODO(m.conraux): Other part of the code supports custom role, should adapt the validator
def validate_ACL(acl_object):
    for key in acl_object:
        if key not in ACL_ROLES:
            raise Exception("Unsupported key used: {}".format(key))
        for subkey in acl_object[key]:
            if subkey not in ACL_GRANTERS:
                raise Exception("Unsupported key used: {}".format(subkey))
            if type(subkey) is not list:
                raise Exception("No list passed in {}".format(key + '.' + subkey))
    return True


def compile_ACLs(_dir):
    logging.debug("Entering %s", _dir)
    dir_content = glob.glob(_dir + "/*")
    acl_files = [x for x in dir_content if x.endswith("acl.json") or x.endswith("acl.hcl")]
    dirs = [x for x in dir_content if os.path.isdir(x)]
    subpaths = [acl for acls in [compile_ACLs(subdir) for subdir in dirs] for acl in acls]
    if len(acl_files) > 1:
        raise Exception("You can't have more than one ACL file in {}", _dir)
    elif len(acl_files) == 0:
        # No ACL found, go deeper
        return subpaths
    else:
        try:
            return [{"roles": parse(acl_files[0]), "path": vaultify_path(_dir),
                     "subpaths": subpaths}]
        except Exception as e:
            logging.error("An error occured during the parsing of {}: {}".format(acl_files[0], e))
            exit(2)


# Stupid ATM, but here for convenience
def generate_policy_name(path, role):
    return "{}_{}_{}".format(TEAM_POLICY_PREFIX.lower(), path, role).replace('/', '_')


# Hide complexity for users when dealing with metadatas
def generate_rights(path, rights):
    # Legacy KV
    ret = {path: rights}
    cs = rights["capabilities"]
    mount, *rest = path.split("/")
    fmt = "{mount}/{special}/{rest}/*"
    paths = {}
    for key in VAULT_VERSIONNED_KV_KEYWORDS:
        paths[key] = fmt.format(mount=mount, rest='/'.join(rest), special=key)
        ret[paths[key]] = copy.deepcopy(rights)
        ret[paths[key]]["capabilities"] = []
    if "deny" in cs:
        logging.error("- deny keyword not supported for path: {}".format(path))
        exit(2)
    sudo = "sudo" in cs
    if "list" in cs:
        ret[paths[VAULT_VERSIONNED_KV_METADATA]]["capabilities"].append("list")
    if "read" in cs and sudo:
        ret[paths[VAULT_VERSIONNED_KV_METADATA]]["capabilities"].append("read")
    if "delete" in cs and sudo:
        ret[paths[VAULT_VERSIONNED_KV_METADATA]]["capabilities"].append("delete")
        ret[paths[VAULT_VERSIONNED_KV_DELETE]]["capabilities"].append("update")
        ret[paths[VAULT_VERSIONNED_KV_DESTROY]]["capabilities"].append("update")
        if "read" in cs:
            ret[paths[VAULT_VERSIONNED_KV_UNDELETE]]["capabilities"].append("update")
    for keyword in ("read", "update", "delete", "create", "list"):
        if keyword in cs:
            ret[paths[VAULT_VERSIONNED_KV_DATA]]["capabilities"].append(keyword)
    return ret


def generate_policies(acl):
    for k, role in acl["roles"].items():
        r = NO_RIGHTS
        if k in DEFAULT_ROLES:
            r = DEFAULT_ROLES[k]
        if "rights" in role:
            logging.info("Found custom rights for role %s in %s", k, acl["path"])
            if type(role["rights"]) is not dict:
                logging.warning("- Invalid role definition. It's not a dict")
            elif "capabilities" not in role["rights"]:
                logging.warning("- You have to specify at least one capability. Fallbacking to default roles")
            elif "capabilities" in role["rights"] and type(role["rights"]["capabilities"]) is not list:
                logging.warning("- Capabilities are not a list. Fallbacking to default roles")
            # TODO: Remove when better understanding of versionned KV internals. Advanced feature that shouldn't be used for now
            elif len(role["rights"].keys()) > 1:
                logging.error(
                    "- Only capabilities are supported as of now. If you have a special request, feel free to ping IDM")
                # I'm exiting to preserve secrets in case of misusage in the metadata path
                exit(2)
            else:
                r = role["rights"]

        main = {"path": generate_rights(acl['path'], r)}
        for denied_path in acl["subpaths"]:
            main["path"].update(generate_rights(denied_path["path"], NO_RIGHTS))
        yield (generate_policy_name(acl["path"], k), k, main)


# TODO(m.conraux): Add filter for the "rights" subkey in the entity list
def generate_files(ACLs, output_dir):
    ret = []
    for acl in ACLs:
        logging.debug("Creating files for %s", acl)
        for name, role, policy in generate_policies(acl):
            policy_file = "{}/{}/{}.json".format(output_dir, VAULT_POLICIES_PATH, name)
            write_file(policy_file, hcl.dumps(policy, indent=4))
            logging.info("Generated %s team policy", name)
            logging.debug("With content: %s", policy_file)
            for entity in ["{}/{}".format(entityType, name) for entityType in acl["roles"][role] for name in
                           acl["roles"][role][entityType]]:
                add_policy_to_ldap_entity_file("{}/auth/ldap/{}.json".format(output_dir, entity), name)
            ret.append(name)
        for x in generate_files(acl["subpaths"], output_dir):
            ret.append(x)
    return ret


def generate_team_storage(path, output_dir):
    if not os.path.exists(path):
        raise Exception("Path {} not found.".format(path))
    if not os.path.isdir(path):
        raise Exception("Path {} is not a directory".format(path))
    if not os.path.exists(output_dir):
        raise Exception("Path {} not found.".format(output_dir))
    if not os.path.isdir(output_dir):
        raise Exception("Path {} is not a directory".format(output_dir))
    acls = compile_ACLs(path)
    if len(acls) == 0:
        logging.warning("Empty list of ACL generated for %s", path)
    generate_files(acls, output_dir)
