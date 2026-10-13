FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_PASSWORD=guacdesktop

RUN apt-get update && apt-get install -y --no-install-recommends \
        tigervnc-standalone-server tigervnc-tools \
        xfce4 xfce4-terminal dbus-x11 \
        chromium socat fonts-liberation procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash user
COPY start.sh /start.sh
RUN sed -i 's/\r$//' /start.sh && chmod +x /start.sh

USER user
WORKDIR /home/user
EXPOSE 5901 9223
CMD ["/start.sh"]
