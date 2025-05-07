import socket
import json

PORT = 8000
address = socket.gethostname()
user_list = []  # List of dicts with keys: name, port, status

def sendListUser():
    global user_list
    data_list = [f"{u['name']}:{u['port']}:{u['status']}" for u in user_list]
    data = {
        "name": "HCMUT",
        "type": "central",
        "listFriend": ";".join(data_list) + ";"
    }
    json_data = json.dumps(data)
    print(json_data)
    for u in user_list:
        if u["status"] == "online":
            try:
                clientSocket = socket.socket()
                clientSocket.connect((address, int(u["port"])))
                clientSocket.send(json_data.encode('utf8'))
                clientSocket.close()
                print("Send success to", u["name"])
            except:
                print(f"Failed to send to {u['name']}:{u['port']}")

def update_user_status(name, port, status):
    global user_list
    for user in user_list:
        if user["name"] == name and user["port"] == port:
            user["status"] = status
            return
    user_list.append({"name": name, "port": port, "status": status})

def handle_webrtc_signal(data):
    # Forward WebRTC signaling data to the target peer
    target_name = data.get("target_name")
    signal_data = data.get("signal_data")
    for user in user_list:
        if user["name"] == target_name and user["status"] == "online":
            try:
                clientSocket = socket.socket()
                clientSocket.connect((address, int(user["port"])))
                signal_message = json.dumps({
                    "type": "webrtc_signal",
                    "name": data["sender_name"],
                    "data": signal_data
                })
                clientSocket.send(signal_message.encode('utf-8'))
                clientSocket.close()
                print(f"Forwarded WebRTC signal to {target_name}")
            except Exception as e:
                print(f"Failed to forward WebRTC signal to {target_name}: {e}")

# Server setup
serverSocket = socket.socket()
serverSocket.bind((address, PORT))
serverSocket.listen()
print("Central Server is running...")

while True:
    sendListUser()
    conn, addr = serverSocket.accept()
    if conn:
        print("Have a user connected")
        try:
            data = conn.recv(1024).decode('utf-8')
            jsonData = json.loads(data)
            if jsonData.get("type") == "webrtc_signal":
                handle_webrtc_signal(jsonData)
            else:
                name = jsonData.get("name")
                port = jsonData.get("port")
                status = jsonData.get("status", "online")
                update_user_status(name, port, status)
        except Exception as e:
            print(f"Error processing user data: {e}")
        finally:
            conn.close()
