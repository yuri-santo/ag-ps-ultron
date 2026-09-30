#!/bin/sh
# Run as root in the local WSL Debian distribution. No service is started.
set -eu

revision=1cdc0d963641d517f5deb687adb37332cf844e70
destination=/opt/phoneharness-1cdc0d9
source_directory=${1:?Pass the existing local PhoneHarness git checkout}
script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

test "$(id -u)" = 0 || { echo 'Run within WSL Debian as root.' >&2; exit 1; }
test ! -e "$destination" || { echo 'Destination already exists; refusing overwrite.' >&2; exit 1; }
git -c "safe.directory=$source_directory" -C "$source_directory" cat-file -e "$revision^{commit}"

umask 077
archive=$(mktemp /tmp/phoneharness-source.XXXXXX.tar)
trap 'rm -f -- "$archive"' EXIT HUP INT TERM
git -c "safe.directory=$source_directory" -C "$source_directory" archive --format=tar --output="$archive" "$revision"
mkdir "$destination"
tar -xf "$archive" -C "$destination" --exclude='.env' --exclude='.env.*'
python3 -m venv "$destination/.venv"
"$destination/.venv/bin/python" -m pip --isolated install --disable-pip-version-check --only-binary=:all: 'PyYAML==6.0.2'
mkdir "$destination/offline-home"
install -m 0755 "$script_directory/phoneharness_local.py" "$destination/phoneharness-local"
echo 'Installed offline-only launcher: /opt/phoneharness-1cdc0d9/phoneharness-local'
