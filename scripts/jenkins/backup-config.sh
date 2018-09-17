#!/usr/bin/env bash
set -e

cd "$(git rev-parse --show-toplevel)"
source ./scripts/venv.sh

BACKUP_PATH="$(mktemp -d)"
BRANCH=${BRANCH:-develop}

git clone "ssh://${GITUSER:-qabot}@review.criteois.lan:29418/identity-management/vault-configuration-archives" $BACKUP_PATH

(
    cd $BACKUP_PATH
    git checkout "$BRANCH"
)

echo "Building the configuration"
python app/main.py -d --no-deploy

echo "Updated the configuration"
rm -rvf $BACKUP_PATH/*
cp -r ./build/* "$BACKUP_PATH"

echo "Commiting the new configuration"
cd $BACKUP_PATH

git add .
git commit -m "Configuration updated at $(date -u +'%F %T')"
git push origin "$BRANCH"

echo "Pushed configuration to archive repository $BRANCH branch"

rm -rf "$BACKUP_PATH"
