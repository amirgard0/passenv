#!/usr/bin/env bash
# Build the passenv Debian binary package.
#
# Usage: scripts/build-deb.sh [output-dir]
#
# Needs only dpkg-deb and coreutils, so it runs on any Debian/Ubuntu host
# and on GitHub Actions runners without debhelper.
#
# The package installs:
#   /usr/lib/python3/dist-packages/passenv/   the Python module
#   /usr/bin/passenv, /usr/bin/passmanager    the two entry points
#
# DEB_VERSION can be set to override the revision part (default: <ver>-1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' pyproject.toml | head -1)"
DEB_VERSION="${DEB_VERSION:-$VERSION-1}"
OUT_DIR="${1:-dist}"
STAGE="build/deb-stage"

if [[ -z "$VERSION" ]]; then
    echo "error: could not parse version from pyproject.toml" >&2
    exit 1
fi

DEB="$OUT_DIR/passenv_${DEB_VERSION}_all.deb"
echo "==> Building $DEB"

rm -rf "$STAGE"
mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/lib/python3/dist-packages/passenv" \
    "$STAGE/usr/share/doc/passenv"

cp passenv/*.py "$STAGE/usr/lib/python3/dist-packages/passenv/"

cat > "$STAGE/usr/bin/passenv" <<'EOF'
#!/usr/bin/python3
from passenv.cli import cli

if __name__ == "__main__":
    cli()
EOF

cat > "$STAGE/usr/bin/passmanager" <<'EOF'
#!/usr/bin/python3
from passenv.cli import passmanager

if __name__ == "__main__":
    passmanager()
EOF
chmod 755 "$STAGE/usr/bin/passenv" "$STAGE/usr/bin/passmanager"

YEAR="$(date +%Y)"
cat > "$STAGE/usr/share/doc/passenv/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: passenv
Source: https://github.com/amirgard0/passenv

Files: *
Copyright: $YEAR Amir Hossain Zare <amirgard0@gmail.com>
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
EOF

cat > "$STAGE/usr/share/doc/passenv/changelog" <<EOF
passenv ($DEB_VERSION) stable; urgency=medium

  * Package of upstream passenv $VERSION.

 -- Amir Hossain Zare <amirgard0@gmail.com>  $(date -R)
EOF
gzip -9n "$STAGE/usr/share/doc/passenv/changelog"

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

if [ -x /usr/bin/py3compile ]; then
    py3compile -p passenv /usr/lib/python3/dist-packages/passenv
fi

exit 0
EOF

cat > "$STAGE/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e

if [ -x /usr/bin/py3clean ]; then
    py3clean -p passenv
fi

exit 0
EOF

cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e

if [ "$1" = "purge" ] && [ -x /usr/bin/py3clean ]; then
    py3clean -p passenv
fi

exit 0
EOF

chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

INSTALLED_SIZE="$(du -sk "$STAGE/usr" | cut -f1)"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: passenv
Version: $DEB_VERSION
Architecture: all
Multi-Arch: foreign
Maintainer: Amir Hossain Zare <amirgard0@gmail.com>
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.10), python3-click (>= 8.0)
Section: utils
Priority: optional
Homepage: https://github.com/amirgard0/passenv
Description: manage multiple pass(1) password-store environments
 passenv lets you switch between several independent pass(1)
 password stores (work, personal, clients) from any shell, while
 leaving the default ~/.password-store untouched. It wraps pass(1)
 via PASSWORD_STORE_DIR and provides the passenv and passmanager
 commands.
EOF

mkdir -p "$OUT_DIR"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB"

echo "==> OK: $DEB"
