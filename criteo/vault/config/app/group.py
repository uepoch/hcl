import glob
import json
import logging
import os
from criteo.vault.config.helpers import get_name


def add_policies_to_user(client, policies, user):
    logging.info("Linking the policies %s to the entity %s", ', '.join(policies), user)

    entity = client.write('identity/lookup/entity', name=user)
    if entity is None or 'data' not in entity or 'id' not in entity['data'] \
            or 'disabled' not in entity['data'] or 'aliases' not in entity['data']:
        logging.warning("The user %s does not exist in Vault or is invalid", user)
        return
    user_id = entity['data']['id']
    disable = entity['data']['disabled']
    alias = entity['data']['aliases']

    client.write('identity/entity/id/{}'.format(user_id), name=user, disabled=disable, aliases=alias, policies=policies)


def link_policies_to_users(client, output_dir):
    for filename in glob.iglob("{}auth/ldap/users/*.json".format(output_dir)):
        with open(filename) as file:
            data = json.load(file)
            if 'policies' not in data:
                logging.critical("The file %s does not have policies", filename)
                exit(1)
        policies = data['policies']
        user_name = get_name(os.path.basename(filename))
        add_policies_to_user(client, policies, user_name)
