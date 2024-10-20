#!/bin/bash

LOG_FILE="/root/track_balances.log"

# Navigate to the correct directory
cd /root/ceremonyclient/node || exit 1  # Exit if directory change fails

# Fetch balance and peer ID
PEER_ID=$(./ceremonyclientnode-1.4.21.1-linux-amd64 -peer-id | grep "Peer ID" | awk '{print $3}')
BALANCE=$(/ceremonyclientnode-1.4.21.1-linux-amd64 -balance | grep "Unclaimed balance" | awk '{print $3}')

# Get the current date and time
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Get the hostname of the machine
HOSTNAME=$(hostname)

# Log peer ID, balance, and hostname
echo "[$DATE] Peer ID: $PEER_ID, Balance: $BALANCE, Hostname: $HOSTNAME" >> $LOG_FILE

# Send the data to the Flask server, including the hostname
curl -X POST -H "Content-Type: application/json" \
-d "{\"peer_id\":\"$PEER_ID\", \"balance\":\"$BALANCE\", \"timestamp\":\"$DATE\", \"hostname\":\"$HOSTNAME\"}" \
http://192.168.20.210:5000/update_balance >> $LOG_FILE 2>&1