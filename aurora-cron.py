# Aurora cron job definition of mesos-scheduled-hello scheduled task
# Launch vault-rotate-kv task every minute
import os
from collections import namedtuple

artifact_id = 'rotate-kv'
group_id = 'com.criteo.vault'
user = 'vault'
# Run at 1AM local time every day
cron_schedule = '0 1 * * *'
rotate_tuple = namedtuple('rotate_params', ['unit', 'keep_number'])
# Same for now
rotate_params = [rotate_tuple(unit='h', keep_number=3), rotate_tuple(unit='d', keep_number=3)]

# Prod targets
# Preprod targets
dcs = ['PAR']

ENCRYPTED_SECRET_ID = "IBrmzX4KqGc6JlObQAygGx/e5YcyJXnlup31fSAN4+Uw8py3fHblHK1yGn+5/JFhlvYX8Yb9ErFuTOlkKVVmEc90IkPOBFLXh6h66VtEzFaymxEEupmM1YNYwbbNRD24DFtMc2HpGucvWgg4IRZlaXkVjYeRnCQpBsRVfzLEVpCZ3PM9Wei8aX+LUrhxSTwIy/fdkxKl6LvliLrqV7EwUS0/4vRVLIO/gLj0+/y5EvDill0rKWhZ2Tw8fggUm0XTAUEhE5mTklRIQgBbrmLwTssyqxFrCUCwE5yCV7PKHqB1ZF/QM2rML36VTQZFrIIt96FXmc9bPjhlGeAJBwmDzA=="

group_id_path = group_id.replace('.', '/')
# Get MOAB_ID to deploy from the environment
MOAB_ID = os.getenv("MOAB_ID")
if not MOAB_ID:
    raise Exception("MOAB_ID not found is the environment")

# Building (cluster, environment) targets
targets = []

# Prod targets
for dc in dcs:
    url = "http://nexus-{dc}.criteo.prod/service/local/repo_groups/criteo/content/{group_id_path}/{artifact_id}/{MOAB_ID}/{artifact_id}-{MOAB_ID}-uber.jar".format(
        **vars())
    targets.append((url, "Criteo {}-PROD Cluster".format(dc), 'prod'))

# Preprod targets
for dc in dcs:
    url = "http://nexus-{dc}.criteo.prod/service/local/repo_groups/criteo/content/{group_id_path}/{artifact_id}/{MOAB_ID}/{artifact_id}-{MOAB_ID}-uber.jar".format(
        **vars())
    targets.append((url, "Criteo {}-PREPROD Cluster".format(dc), 'devel'))

# This is common to all environments
execFmt = " && ".join([
    "export SECRET_SECRET_ID=\"{secret_id}\"".format(secret_id=ENCRYPTED_SECRET_ID),
    "source decryptme.sh /usr/share/mesos/users/{user}/keys/{user}.pem".format(user=user),
    "export VAULT_ADDR=http://vault-vault.marathon-par.central.criteo.{env}:80",
    """export VAULT_TOKEN=$(curl -q -s -XPOST -d '{"role_id": "admin-tasks", "secret_id": "'"$SECRET_ID"'"}' "$VAULT_ADDR/v1/auth/approle/login" | jq -r '.auth.client_token')""",
    "./rotate_kv -u '{unit}' -k '{keep}'"])

# Populating jobs list
jobs = []
for url, cluster, environment in targets:
    inst = Process(name='fetch_package', cmdline="curl -L -o rotate_kv '{}'".format(url))
    for unit, keep in rotate_params:
        proc = Process(name='run_process',
                       cmdline=execFmt.format(env="prod" if environment == "prod" else "devel", unit=unit, keep=keep))
        sequ = SequentialTask(processes=[inst, proc], resources=Resources(cpu=1, ram=64 * MB, disk=128 * MB))
        jobs.append(Job(
            cluster=cluster,
            role=user,
            environment=environment,
            name='vault-rotate-kv-{unit}'.format(unit=unit),
            cron_schedule=cron_schedule,
            task=sequ,
        ))
