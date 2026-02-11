#!/usr/bin/env python3

import bluetooth
import os
import time
import subprocess
import signal
import sys

# --- CONFIGURATION ---
PORT = 1
FILE_TO_SEND = "collection_test.pcap"  # The file you want to send to the client

"""
CHANGE THIS
"""
CAPTURE_SCRIPT = "/home/jay/capture.sh" # <----------- Change This
"""
CHANGE THIS
"""

#CAPTURE_CHANNEL = 120
#CAPTURE_MAC = "10:63:C8:A6:7F:C7"

CAPTURE_CHANNEL = 153
CAPTURE_MAC = ["10:63:C8:A6:7F:C7"]
FILTER = ""

# --- HELPER FUNCTIONS ---

def start_capture():
    """
    Starts the capture script in a new process group.
    Returns the process object.
    """
    print(f"[*] Starting Capture Script on CH {CAPTURE_CHANNEL}...")
    try:
        # start_new_session=True creates a new process group.
        # This allows us to kill the script AND tcpdump together later.
        MACS=",".join(CAPTURE_MAC)
        proc = subprocess.Popen(
            ["/bin/bash", CAPTURE_SCRIPT, str(CAPTURE_CHANNEL), MACS, FILTER],
            stdout=subprocess.DEVNULL, # Hide output to keep console clean
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return proc
    except Exception as e:
        print(f"[!] Failed to start capture: {e}")
        return None

def stop_capture(proc):
    """
    Stops the capture script and cleans up the monitor interface.
    """
    if proc:
        print("[*] Stopping Capture Script...")
        try:
            # Send SIGTERM to the process group (kills bash script + tcpdump)
            #os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=2)
        except ProcessLookupError:
            print("    Process already dead.")
        except subprocess.TimeoutExpired:
            print("    Forcing kill...")
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

        # CLEANUP: Remove mon0 so the script doesn't fail next time it tries to create it
        #print("    Cleaning up mon0 interface...")
        #subprocess.run(["iw", "dev", "mon0", "del"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("    Capture stopped.")
    else:
        print("[!] No capture process to stop.")

# --- MAIN SETUP ---

# Ensure the file exists for testing
if not os.path.exists(FILE_TO_SEND):
    with open(FILE_TO_SEND, "w") as f:
        f.write("Log Entry 1: System Start\nLog Entry 2: Sensor OK\n")

server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
server_sock.bind(("", PORT))
server_sock.listen(1)

print(f"[*] Pi Server listening on Port {PORT}...")

# 1. START CAPTURE INITIALLY
capture_process = start_capture()

try:
    while True:
        client_sock = None
        try:
            # 2. Accept Connection
            # The capture is running in the background while we wait here.
            client_sock, client_info = server_sock.accept()
            print(f"[+] Connection from {client_info}")

            # 3. Robust Receive
            command = ""
            attempts = 0
            while not command and attempts < 10:
                raw_data = client_sock.recv(1024)
                if raw_data:
                    command = raw_data.decode('utf-8').strip()
                else:
                    time.sleep(0.1)
                    attempts += 1

            if not command:
                print("    [!] Warning: Client connected but sent no command.")

            elif command == "GET_FILE":
                # --- STOP CAPTURE ---
                # We stop it to free up resources and ensure file integrity if needed
                stop_capture(capture_process)
                capture_process = None # Mark as stopped

                if os.path.exists(FILE_TO_SEND):
                    print(f"    Sending {FILE_TO_SEND}...")
                    with open(FILE_TO_SEND, "rb") as f:
                        while True:
                            chunk = f.read(1024)
                            if not chunk:
                                break
                            client_sock.send(chunk)
                    print("    File Sent.")
                else:
                    client_sock.send(b"ERROR: File missing")

                # --- RESTART CAPTURE ---
                # We restart it immediately after the file is sent
                subprocess.call(['rm', 'collection_test.pcap','-f'])
                #time.sleep(1.0) # Short buffer
                time.sleep(0.1) # Short buffer
                capture_process = start_capture()
            elif "GET_CMD" in command:
                stop_capture(capture_process)
                capture_process = None # Mark as stopped
                
                arr = command.split(" ")
                arr.pop(0)
                CAPTURE_CHANNEL = arr[0]
                arr.pop(0)
                FILTER = f"-b {arr[0]}" if arr[0] != "None" else ""
                arr.pop(0)
                CAPTURE_MAC = arr
                msg_received = f"Receivted with vals {CAPTURE_CHANNEL} {FILTER} {CAPTURE_MAC}"
                msg_received = bytes(msg_received,"utf-8")

                client_sock.send(msg_received)

                # --- RESTART CAPTURE ---
                # We restart it immediately after the file is sent
                subprocess.call(['rm', 'collection_test.pcap','-f'])
                #time.sleep(1.0) # Short buffer
                time.sleep(0.1) # Short buffer
                capture_process = start_capture()


#ooo
            else:
                print(f"    [!] Unknown Command: {command}")
                client_sock.send(b"ERROR: Unknown Command")

            # 4. Sync Sleep
            #time.sleep(1.0)
            time.sleep(0.1)


        except Exception as e:
            print(f"[!] Error in loop: {e}")

        finally:
            if client_sock:
                client_sock.close()
            print("[-] Connection closed. Ready for next.\n")

except KeyboardInterrupt:
    print("\n[!] User stopped script.")

finally:
    # Final cleanup if the python script is killed
    print("[*] Shutting down...")
    if capture_process:
        stop_capture(capture_process)
    server_sock.close()
