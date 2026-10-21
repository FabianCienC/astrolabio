#!/usr/bin/env bash
# Sets the image tag of $IMAGE_NAME (astrolabio-api, astrolabio-web) to $GITHUB_SHA in
# homelab-gitops, so Argo CD deploys the image this run just pushed.
# Needs DEPLOY_KEY (write deploy key of homelab-gitops), IMAGE_NAME and GITHUB_SHA.
set -euo pipefail

install -m 700 -d ~/.ssh
printf '%s\n' "$DEPLOY_KEY" > ~/.ssh/gitops && chmod 600 ~/.ssh/gitops
echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" >> ~/.ssh/known_hosts
export GIT_SSH_COMMAND="ssh -i ~/.ssh/gitops -o IdentitiesOnly=yes"

git clone --depth 1 git@github.com:FabianCienC/homelab-gitops.git gitops
cd gitops
file=workloads/astrolabio/kustomization.yaml
# Fails loudly if the image entry is missing, instead of silently not deploying.
yq -e '.images[] | select(.name == strenv(IMAGE_NAME))' "$file" > /dev/null
yq -i '(.images[] | select(.name == strenv(IMAGE_NAME))).newTag = strenv(GITHUB_SHA)' "$file"
if git diff --quiet; then echo "already at ${GITHUB_SHA::7}"; exit 0; fi  # a re-run

git config user.name "astrolabio-ci"
git config user.email "astrolabio-ci@users.noreply.github.com"
git commit -am "$IMAGE_NAME: imagen ${GITHUB_SHA::7}"
# Another job (the other image, another app) may have pushed meanwhile: rebase and retry.
for attempt in 1 2 3; do
  git push && exit 0
  git pull --rebase
done
exit 1
