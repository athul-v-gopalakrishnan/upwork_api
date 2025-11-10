#!/bin/bash
set -e

rm -f /root/.config/chrome-profile/SingletonLock
rm -f /root/.config/chrome-profile/SingletonCookie
rm -f /root/.config/chrome-profile/SingletonSocket

echo "✅ Starting Chrome in Xvfb..."

# Start Chrome inside Xvfb
xvfb-run -a google-chrome \
    --user-data-dir=/root/.config/chrome-profile \
    --no-sandbox \
    --disable-dev-shm-usage \
    --remote-debugging-address=0.0.0.0 \
    --remote-debugging-port=9222 \
    --disable-blink-features=AutomationControlled \
    --disable-gpu \
    --start-maximized \
    --no-first-run \
    --no-default-browser-check \
    --disable-infobars \
    > /dev/null 2>&1 &


CHROME_PID=$!

echo "✅ Chrome started with PID: $CHROME_PID"
echo "⏳ Waiting for Chrome CDP to become ready..."

# Wait for CDP to respond
until curl -s http://127.0.0.1:9222/json/version > /dev/null; do
  echo "⏳ Chrome not ready yet…"
  sleep 1
done

echo "✅ Chrome CDP is available!"

echo "✅ Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000