#!/bin/bash
# Spustí CDP Chrome s ČISTÝM profilem a hned na to sondu.
#
# PROČ: vložení PDF do noty-app dokáže „otrávit" profil — indexedDB.open()
# zůstane navždy pending a KAŽDÝ upload pak visí na „Nahrávám noty… 0 / 1"
# (sonda spadne na falešný timeout „PDF upload"). Druhý běh na stejném profilu
# proto selže i když je kód v pořádku. Řešení: kill + smazat --user-data-dir
# + nastartovat na NOVÉM portu (reload stránky nestačí).
#
# Použití:  scripts/run-probe-fresh.sh scripts/probe-annot-nav-wedge.py
set -u
PORT="${NOTY_CDP_PORT:-9226}"
PROFILE="/tmp/chrome-noty-fresh"
PROBE="${1:-scripts/probe-annot-nav-wedge.py}"

pkill -f "remote-debugging-port=${PORT}" 2>/dev/null
pkill -f "user-data-dir=${PROFILE}" 2>/dev/null
sleep 2
rm -rf "$PROFILE"

cat > /tmp/start-chrome-fresh.sh <<EOF
export LD_LIBRARY_PATH="\$HOME/.agent-browser/lib:\$LD_LIBRARY_PATH"
CHROME_BIN=\$(ls -d "\$HOME"/.agent-browser/browsers/chrome-*/chrome | head -1)
exec "\$CHROME_BIN" --headless=new --disable-gpu --no-sandbox \\
  --remote-debugging-port=${PORT} --user-data-dir=${PROFILE} about:blank
EOF
chmod +x /tmp/start-chrome-fresh.sh
nohup bash /tmp/start-chrome-fresh.sh >/tmp/chrome-fresh.log 2>&1 &

for i in $(seq 1 40); do
  sleep 1
  if curl -s -m 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then break; fi
done
curl -s -m 3 "http://127.0.0.1:${PORT}/json/version" | head -2 || { echo "Chrome se nezvedl"; exit 1; }

cd "$(dirname "$0")/.."
NOTY_CDP="http://127.0.0.1:${PORT}" timeout 400 python3 -u "$PROBE"
