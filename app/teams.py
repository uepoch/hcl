#!/usr/bin/env python3

import logging
import hvac
import os
import yaml
import sys
import hcl
import glob

from helper import *
from main import VAULT_POLICIES_PATH

LDAP_BACKEND_PATH = "ldap/"
LDAP_PATH = "../auth/" + LDAP_BACKEND_PATH

# For now, only support ro/rw keys
ACL_ROLES = ['ro', 'rw']
ACL_GRANTERS = ['users', 'groups']

RO_RIGHTS = {"capabilities": ["read", "list"]}
RW_RIGHTS = {"capabilities": RO_RIGHTS['capabilities'] + ['update', 'create', 'delete']}
NO_RIGHTS = {"capabilities": []}
TEAM_POLICY_PREFIX = "_team_policy"

DEFAULT_ROLES = {"ro": RO_RIGHTS, "rw": RW_RIGHTS}


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
        #No ACL found, go deeper
        return subpaths
    else:
        return [{"roles": parse(acl_files[0]), "path": vaultify_path(_dir),
                 "subpaths": subpaths}]


# Stupid ATM, but here for convenience
def generate_policy_name(path, role):
    return "{}_{}_{}".format(TEAM_POLICY_PREFIX.lower(), path, role).replace('/', '_')


def generate_policies(acl):
    for k, role in acl["roles"].items():
        r = NO_RIGHTS
        if "rights" in role:
            logging.info("Found custom rights for role %s in %s", k, acl["path"])
            if type(role["rights"]) is not dict:
                logging.warning("- Invalid role definition. It's not a dict")
            elif "capabilities" in role["rights"] and type(role["rights"]["capabilities"]) is not list:
                logging.warning("- Capabilities are not a list. Fallbacking to default roles")
            else:
                r = role["rights"]
        elif k in DEFAULT_ROLES:
            r = DEFAULT_ROLES[k]
        main = {"path": {acl["path"]: r}}
        denied_paths = {x["path"] + "/*": NO_RIGHTS for x in acl["subpaths"]}
        main["path"].update(denied_paths)
        yield (generate_policy_name(acl["path"], k), k, main)


# TODO(m.conraux): Add filter for the "rights" subkey in the entity list
def generate_files(ACLs, output_dir, logindent=0):
    ret = []
    for acl in ACLs:
        logging.debug("Creating files for %s", acl)
        for name, role, policy in generate_policies(acl):
            logging.info("%sPolicy: %s", "-" * logindent, name)
            policy_file = "{}/{}/{}.json".format(output_dir, VAULT_POLICIES_PATH, name)
            # client.set_policy(name, hcl.dumps(policy))
            write_file(policy_file, hcl.dumps(policy))
            logging.debug("Created %s", policy_file)
            for entity in ["{}/{}".format(entityType, name) for entityType in acl["roles"][role] for name in
                           acl["roles"][role][entityType]]:
                add_policy_to_ldap_entity_file("{}/auth/ldap/{}.json".format(output_dir, entity), name)
            ret.append(name)
        for x in generate_files(acl["subpaths"], output_dir, logindent + 2):
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
