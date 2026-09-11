#!/usr/bin/env bash
# Build a signed APT repository from the .debs in a source directory.
#
# Usage: scripts/build-apt-repo.sh <repo-dir> <key-id>
#
# <repo-dir>  receives: pool/…, dists/stable/{Packages*,Release*},
#             PASSENV-GPG-KEY  (exportable public key block)
# <key-id>    signing key id; gpg must be able to use it non-interactively
#
# Debs must be named <name>_<version>_all.deb and are placed into
# pool/main/<prefix>/<name>/ to match the standard APT layout.
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <repo-dir> <key-id>" >&2
    exit 1
fi

REPO_DIR="$1"
KEY_ID="$2"
SUITE="stable"
COMPONENT="main"
ARCH="all"

mkdir -p "$REPO_DIR/pool/$COMPONENT/p/passenv" "$REPO_DIR/dists/$SUITE/$COMPONENT"

shopt -s nullglob
DEBS=( "$REPO_DIR"/*.deb )
shopt -u nullglob

if [[ ${#DEBS[@]} -eq 0 ]]; then
    echo "error: no .deb files found in $REPO_DIR" >&2
    exit 1
fi

for deb in "${DEBS[@]}"; do
    echo "==> pooling $(basename "$deb")"
    cp "$deb" "$REPO_DIR/pool/$COMPONENT/p/passenv/"
done

cd "$REPO_DIR"

echo "==> generating Packages indices"
mkdir -p "dists/$SUITE/$COMPONENT/binary-all"
dpkg-scanpackages --arch "$ARCH" "pool/$COMPONENT" \
    > "dists/$SUITE/$COMPONENT/binary-all/Packages"
gzip -9n -k "dists/$SUITE/$COMPONENT/binary-all/Packages"

echo "==> generating Release"
# Extra checksums make apt trust the repository more reliably across
# downstream mirrors, and it is what apt-ftparchive emits by default.
apt-ftparchive \
    -o APT::FTPArchive::Release::Suite="$SUITE" \
    -o APT::FTPArchive::Release::Codename="$SUITE" \
    -o APT::FTPArchive::Release::Architectures="$ARCH" \
    -o APT::FTPArchive::Release::Components="$COMPONENT" \
    -o APT::FTPArchive::Release::Origin="passenv" \
    -o APT::FTPArchive::Release::Label="passenv apt repository" \
    -o APT::FTPArchive::Release::Description="APT repository for passenv" \
    release "dists/$SUITE" > "dists/$SUITE/Release"

echo "==> signing Release as $KEY_ID"
GPG_ARGS=(--batch --yes --local-user "$KEY_ID")
if [[ -n "${GPG_PASSPHRASE:-}" ]]; then
    GPG_ARGS+=(--pinentry-mode loopback --passphrase "$GPG_PASSPHRASE")
fi

gpg "${GPG_ARGS[@]}" --armor --detach-sign --output "dists/$SUITE/Release.gpg" \
    "dists/$SUITE/Release"
gpg "${GPG_ARGS[@]}" --armor --clearsign --output "dists/$SUITE/InRelease" \
    "dists/$SUITE/Release"

gpg --armor --export "$KEY_ID" > PASSENV-GPG-KEY

echo "==> repo layout:"
find . -type f | sort | sed 's/^/    /'
echo "==> OK: signed APT repo in $REPO_DIR"
