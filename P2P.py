from threading import Thread, Lock
import tkinter as tk
import socket
import json
import os
import select
from queue import Queue, Empty
import time
import google.generativeai as genai

class Peer:
    listSocket = {}  
    address = socket.gethostname()
    allThreads = []
    endAllThread = False
    ports = []  
    centralServerPort = 8000
    listFriend = ""
    socket_lock = Lock()  
    ui_queue = Queue()  
    file_queue = Queue()  

    def __init__(self, name, port, text):
        self.port = port
        self.name = name
        self.text = text
        self.filename_lock = Lock()  
        self._filename = "" 

        if not isinstance(self.text, tk.Text):
            raise ValueError("Parameter 'text' must be a tk.Text widget")

        self.root = text.master

       
        try:
            os.makedirs(self.name, exist_ok=True)
            if not os.access(self.name, os.W_OK):
                raise PermissionError(f"Cannot write to directory {self.name}")
            self.log_event(f"Created/Verified user folder: {self.name}")
        except Exception as e:
            self.log_to_ui(f"Error creating user folder {self.name}: {str(e)}\n")
            self.log_event(f"Error creating user folder {self.name}: {str(e)}")
            raise  

        self.save_user_config()
        
   
        try:
            genai.configure(api_key="Your key API")
            self.gemini_model = genai.GenerativeModel(model_name="models/gemini-1.5-flash-latest")
            self.log_event("Gemini API configured successfully")
        except Exception as e:
            self.log_to_ui(f"Failed to configure Gemini API: {str(e)}\n")
            self.log_event(f"Failed to configure Gemini API: {str(e)}")
            self.gemini_model = None  

        self.load_history()
        self.process_ui_updates()

    @property
    def filename(self):
        with self.filename_lock:
            return self._filename

    @filename.setter
    def filename(self, value):
        with self.filename_lock:
            self._filename = value

    def process_ui_updates(self):
        try:
            while True:
                message, tag = self.ui_queue.get_nowait()
                self.text.configure(state='normal')
                self.text.insert(tk.END, message, tag)
                self.text.see(tk.END)
                self.text.configure(state='disable')
        except Empty:
            pass
        self.root.after(100, self.process_ui_updates)

    def log_to_ui(self, message, tag=None):
        self.ui_queue.put((message, tag))

    def log_event(self, message):
        log_line = f"[{self.name}:{self.port}] {message}"
        print(log_line)
        self.rotate_log_if_needed()
        try:
            with open("log.txt", "a", encoding="utf-8") as log_file:
                log_file.write(log_line + '\n')
        except Exception as e:
            print(f"Failed to write to log: {str(e)}")

    def rotate_log_if_needed(self):
        log_file = "log.txt"
        if os.path.exists(log_file) and os.path.getsize(log_file) > 10 * 1024 * 1024: 
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.rename(log_file, f"log_{timestamp}.txt")
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"[{self.name}:{self.port}] Log rotated.\n")
            except Exception as e:
                self.log_to_ui(f"Error rotating log: {str(e)}\n")
                self.log_event(f"Error rotating log: {str(e)}")

    def save_user_config(self):
        config = {"name": self.name, "port": self.port}
        try:
            with open(os.path.join(self.name, "user_config.json"), "w") as f:
                json.dump(config, f)
        except Exception as e:
            self.log_to_ui(f"Error saving config: {str(e)}\n")
            self.log_event(f"Error saving config: {str(e)}")

    @staticmethod
    def load_user_config(user_name):
        try:
            with open(os.path.join(user_name, "user_config.json"), "r") as f:
                config = json.load(f)
                return config.get("name"), config.get("port")
        except:
            return None, None

    def processBotMessage(self, message):
        self.log_event(f"Processing bot message: {message}")
        if self.gemini_model is None:
            self.log_event("Gemini model is None")
            return "Bot unavailable: Gemini API not configured"
        try:
            response = self.gemini_model.generate_content(message)
            self.log_event(f"Bot response: {response.text}")
            return response.text
        except Exception as e:
            self.log_event(f"Bot error: {str(e)}")
            return f"Bot error: {str(e)}"

    def save_history(self, sender, message):
        filename = os.path.join(self.name, f"history_{self.name}_{self.port}.txt")
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(f"<{sender}> : {message}\n")
        except Exception as e:
            self.log_to_ui(f"Error saving history: {str(e)}\n")
            self.log_event(f"Error saving history: {str(e)}")

    def load_history(self):
        filename = os.path.join(self.name, f"history_{self.name}_{self.port}.txt")
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    self.text.configure(state='normal')
                    for line in lines:
                        self.text.insert(tk.END, line)
                    self.text.see(tk.END)
                    self.text.configure(state='disable')
            except Exception as e:
                self.log_to_ui(f"Error loading history: {str(e)}\n")
                self.log_event(f"Error loading history: {str(e)}")

    def recv_input_stream(self, connection, address):
        self.log_event(f"Starting recv_input_stream for {address}")
        buffer = ""
        connection.setblocking(False)
        while not self.endAllThread:
            try:
                readable, _, _ = select.select([connection], [], [], 5)
                if not readable:
                    continue
                data = connection.recv(2048)
                if not data:
                    self.log_event(f"Connection closed from {address}")
                    break
                try:
                    buffer += data.decode("utf-8")
                    self.log_event(f"Raw data received from {address}: {buffer}")
                    while buffer:
                        try:
                            jsonMessage, index = json.JSONDecoder().raw_decode(buffer)
                            self.log_event(f"Parsed JSON from {address}: {jsonMessage}")
                            buffer = buffer[index:].lstrip()
                            if jsonMessage["type"] == "connect":
                                self.log_to_ui(
                                    f"<🕭{jsonMessage['name']}> wants to connect to your channel\n",
                                    "connect"
                                )
                                self.text.tag_configure("connect", foreground="blue", font=("Georgia", 12, "bold"))
                                self.log_event(f"Peer {jsonMessage['name']} requested connection")
                            elif jsonMessage["type"] == "chat":
                                self.log_to_ui(f"<{jsonMessage['name']}> : {jsonMessage['message']}\n")
                                self.save_history(jsonMessage["name"], jsonMessage["message"])
                                self.log_event(f"Received chat from {jsonMessage['name']}: {jsonMessage['message']}")
                            elif jsonMessage["type"] == "file":
                                file_socket = socket.socket()
                                file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                file_socket.bind((self.address, 0)) 
                                file_socket.listen(1)
                                file_port = file_socket.getsockname()[1]
                                self.file_queue.put((jsonMessage["filename"], jsonMessage["name"], file_socket))
                                connection.send(json.dumps({"type": "file_port", "port": file_port}).encode('utf-8'))
                                file_thread = Thread(
                                    target=self.handleReceiveFile,
                                    args=(file_socket, jsonMessage["filename"], jsonMessage["name"])
                                )
                                file_thread.start()
                                self.allThreads.append(file_thread)
                                self.log_event(f"Queued file: {jsonMessage['filename']} from {jsonMessage['name']} on port {file_port}")
                            elif jsonMessage["type"] == "central":
                                self.listFriend = jsonMessage["listFriend"]
                                self.log_event(f"Received friend list: {self.listFriend}")
                            elif jsonMessage["type"] == "fetch":
                                filename = os.path.join(self.name, f"history_{self.name}_{self.port}.txt")
                                if os.path.exists(filename):
                                    with open(filename, "r", encoding="utf-8") as f:
                                        lines = f.readlines()
                                        if lines:
                                            last_line = lines[-1].strip()
                                            fetch_response = json.dumps({
                                                "type": "chat",
                                                "name": self.name,
                                                "message": f"[Repeat] {last_line}"
                                            }) + "\n"
                                            connection.send(fetch_response.encode('utf-8'))
                                            self.log_event(f"Responded to fetch request from {jsonMessage['name']}")
                        except json.JSONDecodeError:
                            if buffer.count("{") > buffer.count("}"):
                                break  
                            buffer = buffer[buffer.find("{"):] if "{" in buffer else ""
                            continue
                        except Exception as e:
                            self.log_to_ui(f"Error processing JSON from {address}: {str(e)}\n")
                            self.log_event(f"Error processing JSON from {address}: {str(e)}")
                            break
                except UnicodeDecodeError:
                    self.log_event(f"Ignoring non-text data from {address}, likely file data")
                    continue
            except (ConnectionResetError, BrokenPipeError):
                self.log_event(f"Connection to {address} closed by peer")
                break
            except Exception as e:
                self.log_to_ui(f"Error processing data from {address}: {str(e)}\n")
                self.log_event(f"Error processing data from {address}: {str(e)}")
                break
        try:
            connection.close()
        except:
            pass

    def handleReceiveFile(self, file_socket, filename, sender):
        base_dir = self.name
        file_path = os.path.join(base_dir, filename)
        self.log_to_ui(f"<{sender}> : Sent you {filename}\n")
        self.log_event(f"Start receiving file: {filename} to {file_path}")
        try:
            conn, addr = file_socket.accept()
            conn.setblocking(False)
            conn.send("ACK".encode('utf-8'))  
            with open(file_path, 'wb') as f:
                while not self.endAllThread:
                    readable, _, _ = select.select([conn], [], [], 5)
                    if not readable:
                        continue
                    try:
                        chunk = conn.recv(4096) 
                        if not chunk:
                            break
                        f.write(chunk)
                    except socket.error as e:
                        if e.errno == 10035:  
                            self.log_event(f"Non-blocking receive not ready for {filename}, retrying")
                            continue
                        raise
            self.log_event(f"File received successfully: {filename} to {file_path}")
            with self.filename_lock:
                self.filename = ""
        except Exception as e:
            self.log_to_ui(f"Error receiving file {filename}: {str(e)}\n")
            self.log_event(f"Error receiving file {filename}: {str(e)}")
        finally:
            try:
                conn.close()
            except:
                pass
            try:
                file_socket.close()
            except:
                pass

    def accept_connection(self, connection, address):
        self.log_event(f"New connection from {address}")
        try:
            connection.setblocking(False)
            time.sleep(0.3)
            self.log_event(f"Connection stabilized for {address}")
        except Exception as e:
            self.log_to_ui(f"Error setting up connection from {address}: {str(e)}\n")
            self.log_event(f"Error setting up connection from {address}: {str(e)}")
            connection.close()
            return
        input_stream = Thread(target=self.recv_input_stream, args=(connection, address))
        input_stream.start()
        self.allThreads.append(input_stream)

    def registerPort(self, address, port):
        serverSocket = socket.socket()
        serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                serverSocket.bind((address, port))
                serverSocket.listen(5)
                for retry in range(3):
                    try:
                        centralSocket = socket.socket()
                        centralSocket.connect((self.address, self.centralServerPort))
                        data = json.dumps({"name": self.name, "port": str(self.port)})
                        centralSocket.send(data.encode('utf-8'))
                        centralSocket.close()
                        self.log_event(f"Peer registered with central server on port {port}")
                        break
                    except Exception as e:
                        self.log_to_ui(f"Attempt {retry + 1}/3 to connect to central server failed: {str(e)}\n")
                        self.log_event(f"Attempt {retry + 1}/3 to connect to central server failed: {str(e)}")
                        if retry == 2:
                            self.log_to_ui("Cannot connect to central server\n")
                        time.sleep(2)
                self.log_event(f"Peer started on port {port}")
                break
            except Exception as e:
                self.log_to_ui(f"Attempt {attempt + 1}/{max_retries} failed to start server on port {port}: {str(e)}\n")
                self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to start server on port {port}: {str(e)}")
                if attempt == max_retries - 1:
                    self.log_to_ui(f"Failed to start server on port {port} after {max_retries} attempts\n")
                    self.log_event(f"Failed to start server on port {port} after {max_retries} attempts")
                    return
                time.sleep(1)
        while not self.endAllThread:
            try:
                serverSocket.settimeout(10)
                conn, addr = serverSocket.accept()
                acceptThread = Thread(target=self.accept_connection, args=(conn, addr))
                acceptThread.start()
                self.allThreads.append(acceptThread)
            except socket.timeout:
                continue
            except Exception as e:
                self.log_to_ui(f"Error accepting connection: {str(e)}\n")
                self.log_event(f"Error accepting connection: {str(e)}")
                continue
        try:
            serverSocket.close()
        except:
            pass

    def cleanup_sockets(self):
        with self.socket_lock:
            for port, sock in list(self.listSocket.items()):
                try:
                    sock.send(b"")
                except:
                    sock.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)
                        self.log_event(f"Cleaned up disconnected socket for {port}")

    def sendMessage(self, message):
        if message.lower() == "showfriends":
            friends = self.listFriend.split(";")
            self.log_to_ui("From Server: Online user list:\n")
            for friend in friends:
                if friend:
                    name_port = friend.split(":")
                    self.log_to_ui(f"\t{name_port[0]} : {name_port[1]}\n")
            return

        self.log_to_ui(f"<{self.name}> : {message}\n")
        self.save_history(self.name, message)
        self.log_event(f"Sent message: {message}")

        data = json.dumps({"name": self.name, "type": "chat", "message": message}) + "\n"
        self.cleanup_sockets()
        with self.socket_lock:
            for port, client in list(self.listSocket.items()):
                try:
                    client.send(data.encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError):
                    self.log_to_ui(f"Connection to port {port} closed\n")
                    self.log_event(f"Connection to port {port} closed")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)
                except Exception as e:
                    self.log_to_ui(f"Error sending message to port {port}: {str(e)}\n")
                    self.log_event(f"Error sending message to port {port}: {str(e)}")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)

        if "@bot" in message.lower() or "bot:" in message.lower():
            bot_response = self.processBotMessage(message)
            self.log_to_ui(f"<Bot🤖> : {bot_response}\n")
            self.save_history("Bot", bot_response)
            self.log_event(f"Bot responded: {bot_response}")

    def sendFile(self, filePath):
        if not os.path.exists(filePath):
            self.log_to_ui(f"File {filePath} does not exist\n")
            self.log_event(f"File {filePath} does not exist")
            return
        filename = os.path.basename(filePath)
        self.log_to_ui(f"<You> : Sending {filename} to your friend\n")
        self.log_event(f"Preparing to send file: {filename}")
        data = json.dumps({"name": self.name, "type": "file", "filename": filename}) + "\n"
        
        self.cleanup_sockets()
        with self.socket_lock:
            for port, client in list(self.listSocket.items()):
                try:
                    client.send(data.encode('utf-8'))
                    client.settimeout(5)
                    response = client.recv(1024).decode("utf-8")
                    file_port = json.loads(response).get("port")
                    if not file_port:
                        self.log_to_ui(f"Peer at port {port} did not provide file port\n")
                        self.log_event(f"Peer at port {port} did not provide file port")
                        continue
                    file_socket = socket.socket()
                    file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    file_socket.connect((self.address, file_port))
                    file_socket.recv(1024)  
                    with open(filePath, 'rb') as f:
                        while True:
                            chunk = f.read(4096) 
                            if not chunk:
                                break
                            file_socket.send(chunk)
                    file_socket.shutdown(socket.SHUT_WR)
                    self.log_event(f"Successfully sent file: {filename} to port {port}")
                    file_socket.close()
                except socket.timeout:
                    self.log_to_ui(f"Peer at port {port} did not respond to file transfer\n")
                    self.log_event(f"Peer at port {port} did not respond to file transfer")
                except (ConnectionResetError, BrokenPipeError):
                    self.log_to_ui(f"Connection to port {port} closed during file transfer\n")
                    self.log_event(f"Connection to port {port} closed during file transfer")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)
                except Exception as e:
                    self.log_to_ui(f"Error sending {filename} to port {port}: {str(e)}\n")
                    self.log_event(f"Error sending file {filename} to port {port}: {str(e)}")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)

    def setUpSendMessage(self, address, port):
        with self.socket_lock:
            if port in self.listSocket:
                client = self.listSocket[port]
                try:
                    client.send(b"")
                    self.log_event(f"Existing connection to port {port} is still active, sending connect request")
                    connect_request = json.dumps({"type": "connect", "name": self.name}) + "\n"
                    client.send(connect_request.encode('utf-8'))
                    self.log_event(f"Sent connect request to port {port}: {connect_request}")
                    return
                except:
                    self.log_event(f"Existing connection to port {port} is closed, removing")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)

        clientSocket = socket.socket()
        clientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        clientSocket.settimeout(5)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.socket_lock:
                    clientSocket.connect((address, int(port)))
                    self.listSocket[port] = clientSocket
                    if port not in self.ports:
                        self.ports.append(port)
                self.log_event(f"Connected to peer at port {port}")
                connect_request = json.dumps({"type": "connect", "name": self.name}) + "\n"
                clientSocket.send(connect_request.encode('utf-8'))
                self.log_event(f"Sent connect request to port {port}: {connect_request}")
                fetch_request = json.dumps({"type": "fetch", "name": self.name}) + "\n"
                clientSocket.send(fetch_request.encode('utf-8'))
                self.log_event(f"Sent fetch request to port {port}: {fetch_request}")
                return
            except socket.error as e:
                if e.errno == 10056:  
                    self.log_event(f"Socket to port {port} already connected, reusing")
                    with self.socket_lock:
                        if port in self.listSocket:
                            client = self.listSocket[port]
                            try:
                                client.send(b"")
                                connect_request = json.dumps({"type": "connect", "name": self.name}) + "\n"
                                client.send(connect_request.encode('utf-8'))
                                self.log_event(f"Sent connect request to port {port}: {connect_request}")
                                return
                            except:
                                client.close()
                                del self.listSocket[port]
                                if port in self.ports:
                                    self.ports.remove(port)
                    clientSocket.close()
                    continue
                self.log_to_ui(f"Attempt {attempt + 1}/{max_retries} failed to connect to port {port}: {str(e)}\n")
                self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to connect to port {port}: {str(e)}")
                if attempt == max_retries - 1:
                    self.log_to_ui(f"Failed to connect to peer at port {port} after {max_retries} attempts\n")
                    self.log_event(f"Failed to connect to peer at port {port} after {max_retries} attempts")
                    clientSocket.close()
                    with self.socket_lock:
                        if port in self.ports:
                            self.ports.remove(port)
                    return
                time.sleep(1)
        clientSocket.close()

    def startServer(self):
        binder = Thread(target=self.registerPort, args=(self.address, self.port))
        self.allThreads.append(binder)
        binder.start()

    def startClient(self, port):
        sender = Thread(target=self.setUpSendMessage, args=(self.address, port))
        self.allThreads.append(sender)
        sender.start()

    def endSystem(self):
        self.log_event("Peer shutting down.")
        self.endAllThread = True
        with self.socket_lock:
            for port, sock in list(self.listSocket.items()):
                try:
                    sock.close()
                except:
                    pass
                del self.listSocket[port]
            self.listSocket.clear()
            self.ports.clear()
        for thread in self.allThreads:
            try:
                thread.join(timeout=1)
            except:
                pass
        self.allThreads.clear()
