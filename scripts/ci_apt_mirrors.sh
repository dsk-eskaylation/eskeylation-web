#!/usr/bin/env bash
# GitHub's Azure mirror can stall package downloads until CI times out.
# Keep Ubuntu's signed package sources; only change the mirror transport/host.
set -euo pipefail

for mirror_list in /etc/apt/apt-mirrors.txt /etc/apt/apt-mirrors-security.txt; do
    if [ -f "$mirror_list" ]; then
        sudo sed -i \
            -e 's|http://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
            -e 's|https://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
            "$mirror_list"
    fi
done
