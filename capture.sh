#!/usr/bin/env bash
#set -e 


# INSTALLATION 

    # sudo apt-get update
    # sudo apt-get install bluez bluez-tools
    # Accept Bluetooth file transfer request on Laptop Settings

# CONFIG

INTERFACE="wlan0"
MON_INTERFACE="mon0"
PCAP="collection_test.pcap"
BT_MAC="80:A9:97:28:46:4A" # obtained using = system_profiler SPBluetoothDataType
PCAP_COUNT=20
ADDR=$2
CHAN=$1

# CSI COLLECTION

echo "Starting CSI Collection Flow..."

echo "Configuring Channel..."
MCP_OUT=$(mcp -C 1 -N 1 -c $CHAN/20 -m $ADDR)

echo "Bringing wlan0 Up..."
sudo ifconfig $INTERFACE up

echo "Configuring Nexmon CSI Params..."
nexutil -I$INTERFACE -s500 -b -l34 -v$MCP_OUT

echo "Creating monitor interface..."
sudo iw dev $INTERFACE interface add $MON_INTERFACE type monitor
sudo ip link set $MON_INTERFACE up

echo "Capturing packets..."
sudo tcpdump -i $INTERFACE dst port 5500 -vv -w $PCAP -c $PCAP_COUNT

echo "Capture complete: $PCAP"
