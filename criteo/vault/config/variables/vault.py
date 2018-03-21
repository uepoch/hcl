from hvac import Client

STATIC_CONF_PATH = "static-configurations"
BUILD_PATH = "build/"

VAULT_MOUNTS_PATH = "sys/mounts"
VAULT_POLICIES_PATH = "sys/policy"

VAULT_DATA_KEY = "data"

VAULT_ROTATE_SUFFIX_UNIT_DAYS = "d"
VAULT_ROTATE_SUFFIX_UNIT_HOURS = "h"
VAULT_ROTATE_SUFFIX_FORMAT = "-{number}{unit}"
