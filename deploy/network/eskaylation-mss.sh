#!/bin/sh
# Avoid inbound PMTU black holes on client paths with smaller MTUs.
# Only reduce the MSS advertised by this host; do not change access rules.
set -eu

IPTABLES=/usr/sbin/iptables
INTERFACE=eth0
MSS=1360
COMMENT=eskaylation-path-mtu

if [ "$(id -u)" -ne 0 ]; then
    echo 'This network service requires root.' >&2
    exit 1
fi

rule() {
    action=$1
    port=$2
    "$IPTABLES" -w 5 -t mangle "$action" OUTPUT \
        -o "$INTERFACE" -p tcp --sport "$port" \
        --tcp-flags SYN,RST SYN -m tcpmss --mss "$((MSS + 1)):65535" \
        -m comment --comment "$COMMENT" -j TCPMSS --set-mss "$MSS"
}

case "${1:-check}" in
    apply)
        for port in 443; do
            if ! rule -C "$port" 2>/dev/null; then
                rule -I "$port"
            fi
        done
        ;;
    remove)
        for port in 443; do
            while rule -C "$port" 2>/dev/null; do
                rule -D "$port"
            done
        done
        ;;
    check)
        for port in 443; do
            rule -C "$port"
        done
        ;;
    *)
        echo 'Usage: eskaylation-mss {apply|remove|check}' >&2
        exit 2
        ;;
esac
