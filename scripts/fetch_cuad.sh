#!/usr/bin/env bash
# Download CUAD v1 (The Atticus Project, CC BY 4.0) into data/.
# Source: data.zip in github.com/TheAtticusProject/cuad (18 MB). It has the same CUADv1.json
# as CUAD_v1.zip on Zenodo record 4595826, which is 106 MB and often slow.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data
if [ ! -f data/cuad-data.zip ]; then
  curl -fsSL --retry 3 -o data/cuad-data.zip "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
fi
unzip -oq data/cuad-data.zip -d data
find data -name "*.json" -maxdepth 2 -print
