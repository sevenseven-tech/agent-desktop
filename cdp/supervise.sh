#!/bin/bash
rm -f /root/browser-profile/Singleton*
python3 /usr/local/bin/cdp_forward.py &
exec /start.sh
