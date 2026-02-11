import socket
import asyncio
import sys
import datetime
import os

# --- CONFIGURATION ---
# Add all 10 of your Raspberry Pi MAC addresses here
PI_FLEET = [
    "88:A2:9E:52:5C:E6",
    "88:A2:9E:17:DE:B5",
    "B8:27:EB:C2:43:0A",
    "88:A2:9E:17:DF:55",
    "88:A2:9E:17:DF:98",
    "88:A2:9E:17:DE:B5",
    "88:A2:9E:17:DE:E1",
    "88:A2:9E:17:DF:02",
    "88:A2:9E:17:DE:E4"
]

PI_FLEET = [
#    "88:A2:9E:17:DF:02",
    "88:A2:9E:17:DE:B5"
]
PI_FLEET += [
    "88:A2:9E:17:DF:89"
]

PORT = 1
TIMEOUT = 0.2      # Max time to wait for the Pi to send the file
COOLDOWN_TIME = 0.1  # Time to wait after disconnecting (Critical for BlueZ stability)
CYCLE_DELAY = 0.1    # Time to wait before restarting the round-robin list
CHANNEL = 157
FILTER = None
FILTER = "0x88"
FILTER = "0x80"
MACS = ["10:63:C8:A6:7F:C7","AC:EC:85:54:55:05"]
MACS += ["10:63:C8:A6:7F:17","AC:EC:85:54:55:15"]
SETUP=True
CONCURRENT_LIMIT=4

async def download_from_pi(mac, sequence_lock):
    """
    Connects to a single Pi, requests 'GET_FILE', saves the data, and disconnects.
    """
    # STRICT ROUND ROBIN: The lock ensures we only talk to 1 Pi at a time.
    async with sequence_lock: 
        print(f"------------------------------------------------")
        print(f"[*] Targeting: {mac}")
        
        sock = None
        file_buffer = b""
        
        try:
            # 1. Setup Non-Blocking Socket
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            sock.setblocking(True) 
            loop = asyncio.get_running_loop()

            # 2. CONNECT (With Timeout)
            try:
                await asyncio.wait_for(
                    loop.sock_connect(sock, (mac, PORT)), 
                    timeout=TIMEOUT
                )
                print(f"    [+] Connected.")
            except (asyncio.TimeoutError, OSError) as e:
                print(f"    [!] Connection Failed: {e}")
                return # Skip to next Pi

            # 3. STABILIZE & SEND COMMAND
            # Wait 0.5s to ensure Pi is ready to read. Fixes "Reset by Peer".
            #await asyncio.sleep(0.5) 
            await asyncio.sleep(0.1) 
            if SETUP:
                try:
                    print("It ran")
                    MACS_STR=",".join(MACS) 
                    filterString = str(FILTER) if FILTER else "None"
                    msg  = f"GET_CMD {CHANNEL} {filterString} {MACS_STR}"
                    msg = bytes(msg,'utf-8')
                    print(msg)
                    await loop.sock_sendall(sock, msg)
                except OSError as e:
                    print(f"    [!] Failed to send command: {e}")
                    return
            else:
                try:
                    await loop.sock_sendall(sock, b"GET_FILE")
                except OSError as e:
                    print(f"    [!] Failed to send command: {e}")
                    return

            # 4. DOWNLOAD LOOP
            # Keep reading chunks until the Pi closes the connection
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        loop.sock_recv(sock, 1024), 
                        timeout=TIMEOUT
                    )
                    #print(chunk)
                    if not chunk:
                        break # Normal End of File (Pi closed connection)
                    file_buffer += chunk
                except asyncio.TimeoutError:
                    print(f"    [!] Transfer Stalled (Timeout).")
                    break
                except OSError as e:
                    # Catch the "104 Connection Reset" here so we save what we got
                    if e.errno == 104:
                        print(f"    [!] Connection Reset by Pi (Transfer likely complete).")
                    else:
                        print(f"    [!] Socket Error during receive: {e}")
                    break
            
            # 5. SAVE FILE (With Timestamp)
            if file_buffer and not SETUP:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                safe_mac = mac.replace(":", "-")
                
                # Create 'logs' folder if it doesn't exist
                os.makedirs("logs", exist_ok=True)
                
                filename = f"logs/log_{safe_mac}_{timestamp}.txt"
                filename = f"logs/{safe_mac}.txt"
                
                with open(filename, "wb") as f:
                    f.write(file_buffer)
                print(f"    [OK] Saved {len(file_buffer)} bytes to '{filename}'")
            else:
                print(f"    [!] Warning: Received 0 bytes.")

        except Exception as e:
            print(f"    [!] Critical Error: {e}")
        
        finally:
            if sock: 
                sock.close()
            print(f"    [-] Disconnected.")
            
            # CRITICAL: Let the Bluetooth hardware rest before the next device
            await asyncio.sleep(COOLDOWN_TIME)

async def main():
    print(f"--- Starting Round Robin Collection for {len(PI_FLEET)} Devices ---")
    
    # This Lock creates the queue. Tasks must wait for the Lock to be free.
    #sequence_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)

    global SETUP
    SETUP=True
    while True:
        # Create a task for every Pi in the list
        #tasks = [download_from_pi(mac, sequence_lock) for mac in PI_FLEET]
        tasks = [download_from_pi(mac, semaphore) for mac in PI_FLEET]
        
        # Run through the entire list
        await asyncio.gather(*tasks)
        
        print(f"\n>>> Cycle Complete. Restarting in {CYCLE_DELAY} seconds... <<<\n")
        #read the file and run the algorithim
        #Run the alogorithim
        SETUP=False
        await asyncio.sleep(CYCLE_DELAY)

if __name__ == "__main__":
    # Fix for Windows users (just in case)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by User.")
