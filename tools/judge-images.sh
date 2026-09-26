#!/bin/sh
set -eu

case "${DOCKER_HOST:-}" in
  unix:///*) ;;
  *) echo 'Set DOCKER_HOST to the dedicated rootless Unix socket.' >&2; exit 1 ;;
esac

security_options=$(docker info --format '{{json .SecurityOptions}}')
case "$security_options" in
  *'name=rootless'*) ;;
  *) echo 'The judge images must be installed on a rootless Docker daemon.' >&2; exit 1 ;;
esac
if [ "$(docker info --format '{{.CgroupVersion}} {{.CgroupDriver}}')" != '2 systemd' ]; then
  echo 'The judge requires cgroup v2 with the systemd cgroup driver.' >&2
  exit 1
fi

for image in python:3.12-slim node:22-slim golang:1.25-bookworm eclipse-temurin:21-jdk gcc:14 rust:1.90-slim; do
  docker pull "$image"
done

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
docker build -f "$repo_root/backend/judge-kotlin.Dockerfile" -t tsf-judge-kotlin:2.4.20 "$repo_root/backend"
