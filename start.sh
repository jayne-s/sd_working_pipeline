#!/bin/bash


sleep 5
export PATH=$PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/jay/nexmon/utilities # CHANGE THIS <-----
bluetoothctl discoverable on
bluetoothctl pairable on
bluetoothctl power on


python3 pi_server_test.py
