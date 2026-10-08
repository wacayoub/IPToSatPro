#!/bin/sh
set -eu
wget -q -O /tmp/iptosatpro-r62.b64 https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r62.b64
base64 -d /tmp/iptosatpro-r62.b64 > /tmp/iptosatpro-r62.ipk
echo "633eada879209286b89d61acbfb57a40e39379e722e2ac7961467c1da01681d9  /tmp/iptosatpro-r62.ipk" | sha256sum -c -
test "$(wc -c < /tmp/iptosatpro-r62.ipk | tr -d ' ')" = "270048"
opkg install --force-reinstall /tmp/iptosatpro-r62.ipk
