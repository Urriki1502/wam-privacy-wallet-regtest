#!/usr/bin/env bash
# Ephemeral Ubuntu x86_64 only; exact upstream recipes, no source edits here.
set -euo pipefail
umask 077
test "$(uname -sm)" = 'Linux x86_64'
test "$(git -C linux-upstream rev-parse HEAD)" = 82a1487fd86f7021b1b9fc1524d267fca126f7d4
test -z "$(git -C linux-upstream status --porcelain --untracked-files=no)"
test "$(git -C linux-upstream/build/wam-core rev-parse HEAD)" = 32efe850438ef22e2de39e562af557872a402c31
test "$(git -C linux-upstream/build/randomx rev-parse HEAD)" = 102f8acf90a7649ada410de5499a7ec62e49e1da
# The official patcher expects the v28.1 tag; verify its immutable annotated object.
git -C linux-upstream/build/wam-core fetch origin tag v28.1 --depth=1
test "$(git -C linux-upstream/build/wam-core rev-parse v28.1)" = 0e6ddeca339cef84d862bd8ce4e38f4bf83a8760
export RANDOMX_TAG=102f8acf90a7649ada410de5499a7ec62e49e1da
export WAM_RANDOMX_ARCH=x86-64
bash linux-upstream/scripts/fetch-upstream.sh
test "$(git -C linux-upstream/build/wam-core rev-parse HEAD)" = 32efe850438ef22e2de39e562af557872a402c31
test "$(git -C linux-upstream/build/randomx rev-parse HEAD)" = 102f8acf90a7649ada410de5499a7ec62e49e1da
(
  cd linux-upstream/build/wam-core
  ./autogen.sh
  ./configure --without-gui --disable-zmq --disable-bench --disable-tests-fuzz-binary \
    --with-incompatible-bdb CPPFLAGS="-I$(pwd)/../randomx/src" \
    LIBS="$(pwd)/../randomx/build/librandomx.a -lpthread" CXXFLAGS='-O2 -g0'
  make -j2
  ./src/test/test_bitcoin --run_test=wam_monetary_tests,wam_devfee_tests
)
mkdir linux-core
# Copy/strip developer outputs; record final bytes, never call these signed release bytes.
for name in wamd wam-cli; do
  install -m700 "linux-upstream/build/wam-core/src/$name" "linux-core/$name"
  strip "linux-core/$name"
  readelf -lW "linux-core/$name" | grep GNU_STACK
done
python - <<'PY'
import json
from hashlib import sha256
from pathlib import Path
from wam_regtest.linux_developer_core import build_manifest,SOURCES
root=Path('linux-core').absolute()
raw=(json.dumps(build_manifest(root,SOURCES),sort_keys=True,indent=2)+'\n').encode()
(root/'DEVELOPER_CORE_MANIFEST.json').write_bytes(raw)
Path('LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt').write_text(sha256(raw).hexdigest()+'\n')
print('LINUX_DEVELOPER_CORE_MANIFEST_SHA256='+sha256(raw).hexdigest())
PY
