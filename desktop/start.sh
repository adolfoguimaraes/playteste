#!/bin/bash
set -e

mkdir -p ~/.vnc
echo "$VNC_PASSWORD" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

cat > ~/.vnc/xstartup <<'EOF'
#!/bin/bash
chromium --no-sandbox --no-first-run --disable-dev-shm-usage \
  --remote-debugging-port=9222 --user-data-dir=$HOME/chrome-profile \
  about:blank &
exec startxfce4
EOF
chmod +x ~/.vnc/xstartup

# Chromium aceita CDP apenas em 127.0.0.1; o socat expõe para fora do container
socat TCP-LISTEN:9223,fork,reuseaddr TCP:127.0.0.1:9222 &

exec vncserver :1 -fg -localhost no -geometry 1366x768 -depth 24 \
  -rfbauth ~/.vnc/passwd -SecurityTypes VncAuth
