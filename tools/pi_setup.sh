#!/bin/sh
# Turn a Raspberry Pi (Zero 2 W or newer, Raspberry Pi OS Bookworm 64-bit) into a portable Vanguard demo box:
#   * its own Wi-Fi network (no internet needed) at http://vanguard.lan  (or http://10.42.0.1)
#   * Vanguard starts by itself whenever the Pi powers on (a USB power bank is enough)
#   * demo mode: library answers only (no AI), a "demo unit" note, and the Vanguard installer to download
#
# Run once, ON THE PI, while it still has internet (to install one package):
#     sudo sh /path/to/Vanguard/tools/pi_setup.sh
# The Wi-Fi name and password come from demo/vanguard-demo.conf next to the Vanguard folder (tools/make_demo_kit.py
# writes it), or are asked for. At the end the Pi switches to its own Wi-Fi network, so an SSH session over Wi-Fi
# ends -- reconnect by joining the Vanguard network:  ssh <user>@10.42.0.1
#
# Back on your home Wi-Fi later:   sudo nmcli connection down vanguard-hotspot
# Demo network again:              sudo nmcli connection up vanguard-hotspot
set -e

if [ "$(id -u)" != "0" ]; then
  echo "Run it with sudo:  sudo sh $0"
  exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)"          # the Vanguard folder this script came with
APP=/opt/vanguard
DATA=/var/lib/vanguard
ADDR=10.42.0.1
SSID=Vanguard
PASSWORD=""
CONF="$SRC/../demo/vanguard-demo.conf"
[ -f "$CONF" ] && . "$CONF"

if [ ! -f "$SRC/run.py" ] || [ ! -d "$SRC/vanguard" ]; then
  echo "Can't find Vanguard next to this script ($SRC)."
  exit 1
fi
if [ -z "$PASSWORD" ]; then
  printf "Wi-Fi password for the '%s' network (8+ characters): " "$SSID"
  read -r PASSWORD
fi
if [ "${#PASSWORD}" -lt 8 ]; then
  echo "The Wi-Fi password needs at least 8 characters."
  exit 1
fi
if ! command -v nmcli >/dev/null 2>&1; then
  echo "This needs NetworkManager (Raspberry Pi OS Bookworm or newer)."
  exit 1
fi

echo "1/6  Python and its encryption package"
if ! python3 -c "import cryptography" 2>/dev/null; then
  apt-get update -q
  apt-get install -y -q python3 python3-cryptography
fi

echo "2/6  Copying Vanguard to $APP"
id vanguard >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin vanguard
mkdir -p "$APP" "$DATA"
for item in vanguard web tools library books faith downloads run.py README.md LIBRARY.md SECURITY.md \
            install-vanguard.sh start-vanguard.sh; do
  rm -rf "$APP/$item"
  if [ -e "$SRC/$item" ]; then cp -R "$SRC/$item" "$APP/$item"; fi
done
chown -R root:root "$APP"
chmod -R a+rX "$APP"
chown -R vanguard:vanguard "$DATA"
chmod 700 "$DATA"

echo "3/6  Demo settings (library answers only, demo note)"
cd "$APP"
runuser -u vanguard -- env VANGUARD_DATA="$DATA" VANGUARD_NO_WARMUP=1 python3 -c \
  "from vanguard import store; store.save_config({'demo': True, 'ai_mode': 'off'})"

echo "4/6  Instructor PIN"
if runuser -u vanguard -- env VANGUARD_DATA="$DATA" python3 -c "from vanguard import security; raise SystemExit(0 if security.admin_set() else 1)"; then
  echo "     already set — keeping it."
else
  while :; do
    printf "     Choose the Instructor PIN (6-12 digits; needed to open class records and add instructors): "
    stty -echo 2>/dev/null || true; read -r PIN; stty echo 2>/dev/null || true; echo
    if runuser -u vanguard -- env VANGUARD_DATA="$DATA" PIN="$PIN" python3 -c \
        "import os,sys; from vanguard import security; e = security.set_admin_pin(os.environ['PIN']); print('     ' + e) if e else None; sys.exit(1 if e else 0)"; then
      break
    fi
  done
fi

echo "5/6  Start Vanguard on every boot"
cat > /etc/systemd/system/vanguard.service <<EOF
[Unit]
Description=Vanguard (demo box)
After=network.target

[Service]
User=vanguard
WorkingDirectory=$APP
Environment=VANGUARD_DATA=$DATA
Environment=VANGUARD_NO_WARMUP=1
ExecStart=/usr/bin/python3 $APP/run.py --lan --no-browser --port 80
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vanguard >/dev/null
systemctl restart vanguard

echo "6/6  The '$SSID' Wi-Fi network"
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
echo "address=/vanguard.lan/$ADDR" > /etc/NetworkManager/dnsmasq-shared.d/vanguard.conf
nmcli connection delete vanguard-hotspot >/dev/null 2>&1 || true
nmcli connection add type wifi ifname wlan0 con-name vanguard-hotspot autoconnect yes \
  connection.autoconnect-priority 100 ssid "$SSID" 802-11-wireless.mode ap 802-11-wireless.band bg \
  802-11-wireless.powersave 2 ipv4.method shared ipv4.addresses "$ADDR/24" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD" >/dev/null

echo
echo "Done. Vanguard starts by itself on every boot."
echo "  Wi-Fi:    $SSID"
echo "  Address:  http://vanguard.lan   (or http://$ADDR)"
echo "  First:    on a phone or laptop, join the Wi-Fi, open the address, tap '+ New profile', choose instructor,"
echo "            and enter the Instructor PIN you just set."
echo
echo "Switching to the '$SSID' network now — this ends an SSH session over Wi-Fi (rejoin: ssh <user>@$ADDR)."
sleep 2
nmcli connection up vanguard-hotspot >/dev/null 2>&1 || echo "Couldn't start the network now; it starts on the next boot (sudo reboot)."
