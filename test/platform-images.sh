#!/bin/bash
#
# Copyright (c) 2026 IndustryFusion Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Moves the images build-local-platform.sh built from one runner to others:
# the K8s e2e builds them once and every shard loads them.
#
#   platform-images.sh save <file>  the built ibn40 images -> zstd archive
#   platform-images.sh load <file>  archive -> docker -> local registry
set -euo pipefail

cd "$(dirname "$0")"
# shellcheck disable=SC1091
. ../.env
# shellcheck disable=SC1091
. ../helm/env.sh

images() {
    docker images --format '{{.Repository}}:{{.Tag}}' \
        | grep "^${LOCAL_REGISTRY}/ibn40/" | grep ":${DOCKER_TAG}\$" | sort -u
}

case "${1:-}" in
    save)
        mapfile -t list < <(images)
        [ "${#list[@]}" -gt 0 ] || { echo "no ${LOCAL_REGISTRY}/ibn40/*:${DOCKER_TAG} images" >&2; exit 1; }
        printf 'saving %s\n' "${list[@]}"
        docker save "${list[@]}" | zstd -q -T0 -3 -o "${2:?file missing}"
        ls -lh "$2"
        ;;
    load)
        zstd -q -dc "${2:?file missing}" | docker load
        mapfile -t list < <(images)
        for image in "${list[@]}"; do
            docker push -q "$image"
        done
        echo "pushed ${#list[@]} images to ${LOCAL_REGISTRY}"
        ;;
    *) echo "usage: $0 save|load <file>" >&2; exit 2 ;;
esac
