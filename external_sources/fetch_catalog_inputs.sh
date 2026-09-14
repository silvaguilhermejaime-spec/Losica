#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: fetch_catalog_inputs.sh TARGET_DIRECTORY}
mkdir -p "$target"

fetch_one() {
  name=$1
  url=$2
  revision=$3
  destination="$target/$name"
  if [ -e "$destination" ]; then
    echo "target already exists: $destination" >&2
    return 1
  fi
  git init -q "$destination"
  git -C "$destination" remote add origin "$url"
  git -C "$destination" fetch -q --depth 1 origin "$revision"
  git -C "$destination" checkout -q --detach FETCH_HEAD
  test "$(git -C "$destination" rev-parse HEAD)" = "$revision"
}

fetch_one epic https://github.com/epic-kitchens/epic-kitchens-100-annotations.git ea8b40457a400c3fffa1c7f406ef3dc169cc2522
fetch_one epic_sounds https://github.com/epic-kitchens/epic-sounds-annotations.git 57a922f0d352e9429f1ef8a37eee21758dd3a33c
fetch_one activitynet_entities https://github.com/facebookresearch/ActivityNet-Entities.git eb455f7cdd9847cb6dca9f099c84070e2a85f614
fetch_one talk2car https://github.com/talk2car/Talk2Car.git 3fde52aee3341312196ab9b2f999337eff0693a0
fetch_one aac_datasets https://github.com/Labbeti/aac-datasets.git 631524fb86eef351c1848e42196fbe5cf62442e4

echo "fetched 5 locked repositories into $target"
