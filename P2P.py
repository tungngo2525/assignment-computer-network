from threading import Thread, Lock
import tkinter as tk
import socket
import json
import os
import select
from queue import Queue, Empty
import time
import google.generativeai as genai
import cv2
import numpy as np
from PIL import Image, ImageTk

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
    video_queue = Queue()
    video_stream_active = False
    video_port = None

    def __init__(self, name, port, text, video_label):
        self.port = port
        self.name = name
        self.text = text
        self.video_label = video_label
        self.filename_lock = Lock()
        self._filename = ""
        self.video_socket = None
        self.cap = None
        self.receiving_video = False  # Thêm biến trạng thái nhận video

        if not isinstance(self.text, tk.Text):
            raise ValueError("Parameter 'text' must be a tk.Text widget")

        self.root = text.master

        try:
            os.makedirs(self.name, exist_ok=True)
            if not os.access(self.name, os.W_OK):
                raise PermissionError(f"Cannot write to directory {self.name}")
            self.log_event(f"Created/Verified user folder: {self.name}")
        except Exception as e:
            self.log_to_ui(f"Error creating user folder {self.name}: {str(e)}\n", "message")
            self.log_event(f"Error creating user folder {self.name}: {str(e)}")
            raise

        self.save_user_config()

        try:
            genai.configure(api_key="your Key API ")
            self.gemini_model = genai.GenerativeModel(model_name="models/gemini-1.5-flash-latest")
            self.log_event("Gemini API configured successfully")
        except Exception as e:
            self.log_to_ui(f"Failed to configure Gemini API: {str(e)}\n", "message")
            self.log_event(f"Failed to configure Gemini API: {str(e)}")
            self.gemini_model = None

        self.load_history()
        self.process_ui_updates()
        Thread(target=self.receive_video_stream).start()

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
                self.log_to_ui(f"Error rotating log: {str(e)}\n", "message")
                self.log_event(f"Error rotating log: {str(e)}")

    def save_user_config(self):
        config = {"name": self.name, "port": self.port}
        try:
            with open(os.path.join(self.name, "user_config.json"), "w") as f:
                json.dump(config, f)
        except Exception as e:
            self.log_to_ui(f"Error saving config: {str(e)}\n", "message")
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
                f.write(f"{sender} : {message}\n")
        except Exception as e:
            self.log_to_ui(f"Error saving history: {str(e)}\n", "message")
            self.log_event(f"Error saving history: {str(e)}")

    def load_history(self):
        filename = os.path.join(self.name, f"history_{self.name}_{self.port}.txt")
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    self.text.configure(state='normal')
                    for line in lines:
                        if " : " in line:
                            if line.startswith("<"):
                                username_end = line.find(">")
                                if username_end != -1:
                                    username_part = line[1:username_end]
                                    message_part = line[username_end + 1:]
                            else:
                                parts = line.split(" : ", 1)
                                username_part = parts[0]
                                message_part = f" : {parts[1]}" if len(parts) > 1 else " : \n"
                            self.text.insert(tk.END, username_part, "username")
                            self.text.insert(tk.END, message_part, "message")
                        else:
                            self.text.insert(tk.END, line, "message")
                    self.text.see(tk.END)
                    self.text.configure(state='disable')
            except Exception as e:
                self.log_to_ui(f"Error loading history: {str(e)}\n", "message")
                self.log_event(f"Error loading history: {str(e)}")

    def resize_frame(self, frame, target_width, target_height):
        height, width = frame.shape[:2]
        target_ratio = target_width / target_height
        frame_ratio = width / height

        if frame_ratio > target_ratio:
            new_height = target_height
            new_width = int(new_height * frame_ratio)
        else:
            new_width = target_width
            new_height = int(new_width / frame_ratio)

        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

        x_offset = (new_width - target_width) // 2
        y_offset = (new_height - target_height) // 2
        frame = frame[y_offset:y_offset + target_height, x_offset:x_offset + target_width]
        return frame

    def startVideoStream(self):
        if self.video_stream_active:
            self.log_to_ui("Video stream already active\n", "message")
            self.log_event("Video stream already active")
            return

        max_retries = 3
        for attempt in range(max_retries):
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                self.log_event("Webcam opened successfully")
                break
            self.log_to_ui(f"Attempt {attempt + 1}/{max_retries} failed to open webcam\n", "message")
            self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to open webcam")
            if attempt < max_retries - 1:
                time.sleep(1)
        else:
            self.log_to_ui("Error: Cannot open webcam after all retries\n", "message")
            self.log_event("Error: Cannot open webcam after all retries")
            return

        ret, frame = self.cap.read()
        if not ret:
            self.log_to_ui("Error: Cannot capture frame from webcam\n", "message")
            self.log_event("Error: Cannot capture frame from webcam")
            self.cap.release()
            self.cap = None
            return

        self.video_stream_active = True
        video_socket = socket.socket()
        video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                video_socket.bind((self.address, self.port + 1000))
                self.video_port = self.port + 1000
                video_socket.listen(5)
                self.video_socket = video_socket
                self.log_event(f"Video socket created on {self.address}:{self.video_port}")
                time.sleep(1)
                break
            except Exception as e:
                self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to bind video socket: {str(e)}")
                if attempt == max_retries - 1:
                    self.log_to_ui("Failed to create video socket\n", "message")
                    self.log_event("Failed to create video socket")
                    video_socket.close()
                    self.cap.release()
                    self.cap = None
                    self.video_stream_active = False
                    return
                time.sleep(1)

        Thread(target=self.send_video_stream, args=(self.video_port,)).start()
        Thread(target=self.test_local_video).start()

    def test_local_video(self):
        self.log_event("Starting local video display")
        displayed_once = False
        target_width, target_height = 615, 420
        while self.video_stream_active and not self.endAllThread and not self.receiving_video:
            if self.cap is None or not self.cap.isOpened():
                self.log_event("Webcam closed or not opened, attempting to reopen")
                self.cap = cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    self.log_event("Failed to reopen webcam")
                    time.sleep(1)
                    continue
            ret, frame = self.cap.read()
            if ret:
                frame = self.resize_frame(frame, target_width, target_height)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(img)
                self.video_label.configure(image=photo)
                self.video_label.image = photo
                if not displayed_once:
                    self.log_event("Local video frame displayed")
                    self.log_event(f"video_label size: {self.video_label.winfo_width()}x{self.video_label.winfo_height()}")
                    displayed_once = True
            else:
                self.log_event("Failed to capture local video frame, retrying")
                if self.cap:
                    self.cap.release()
                    self.cap = None
                time.sleep(0.03)
                continue
            time.sleep(0.03)

    def stopVideoStream(self):
        if not self.video_stream_active:
            self.log_to_ui("No video stream to stop\n", "message")
            self.log_event("No video stream to stop")
            return

        self.log_event("Stopping video stream")
        self.video_stream_active = False
        self.receiving_video = False  # Dừng nhận video
        self.video_port = None
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
            self.video_socket = None
        # Thông báo cho các peer khác dừng nhận video
        data = json.dumps({"name": self.name, "type": "video_stop"}) + "\n"
        with self.socket_lock:
            for port, client in list(self.listSocket.items()):
                try:
                    client.send(data.encode('utf-8'))
                    self.log_event(f"Notified video stop to port {port}")
                except:
                    self.log_event(f"Failed to notify video stop to port {port}")
        self.log_to_ui("Video stream stopped\n", "message")
        self.video_label.configure(image='')

    def send_video_stream(self, video_port):
        self.log_event(f"Starting video stream server on port {video_port}")
        self.log_event(f"Video socket listening on {self.video_socket.getsockname()}")
        notified_peers = set(self.listSocket.keys())
        target_width, target_height = 615, 420
        conn = None
        while self.video_stream_active and not self.endAllThread:
            data = json.dumps({"name": self.name, "type": "video", "port": video_port}) + "\n"
            self.cleanup_sockets()
            with self.socket_lock:
                current_peers = set(self.listSocket.keys())
                new_peers = current_peers - notified_peers
                self.log_event(f"Current listSocket: {list(self.listSocket.keys())}")
                self.log_event(f"New peers to notify: {list(new_peers)}")
                for port in new_peers:
                    try:
                        client = self.listSocket[port]
                        client.send(data.encode('utf-8'))
                        self.log_event(f"Notified video port {video_port} to port {port}")
                        notified_peers.add(port)
                    except Exception as e:
                        self.log_to_ui(f"Error notifying video port to {port}: {str(e)}\n", "message")
                        self.log_event(f"Error notifying video port to {port}: {str(e)}")
                        client.close()
                        del self.listSocket[port]
                        if port in self.ports:
                            self.ports.remove(port)

            try:
                if not conn:
                    self.video_socket.settimeout(15)
                    conn, addr = self.video_socket.accept()
                    self.log_event(f"Video stream connection from {addr}")
                    conn.setblocking(True)
                if self.cap is None or not self.cap.isOpened():
                    self.log_event("Webcam closed in send_video_stream, attempting to reopen")
                    self.cap = cv2.VideoCapture(0)
                    if not self.cap.isOpened():
                        self.log_event("Failed to reopen webcam in send_video_stream")
                        time.sleep(1)
                        continue
                ret, frame = self.cap.read()
                if not ret:
                    self.log_event("Failed to capture video frame, retrying")
                    if self.cap:
                        self.cap.release()
                        self.cap = None
                    time.sleep(0.03)
                    continue
                frame = self.resize_frame(frame, target_width, target_height)
                self.log_event(f"Captured frame with shape: {frame.shape}")
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                data = buffer.tobytes()
                size = len(data)
                try:
                    conn.send(size.to_bytes(4, byteorder='big'))
                    conn.send(data)
                    self.log_event("Video frame sent")
                except (BrokenPipeError, ConnectionResetError):
                    self.log_event("Connection to peer lost, retrying connection")
                    if conn:
                        conn.close()
                        conn = None
                    continue
                except Exception as e:
                    self.log_event(f"Error sending video frame: {str(e)}, retrying")
                    if conn:
                        conn.close()
                        conn = None
                    continue
                time.sleep(0.03)
            except socket.timeout:
                self.log_event("No peer connected to video stream, waiting")
                continue
            except Exception as e:
                self.log_event(f"Error in send_video_stream: {str(e)}, retrying")
                if conn:
                    conn.close()
                    conn = None
                continue
        if conn:
            try:
                conn.close()
            except:
                pass
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
        if self.cap:
            self.cap.release()
            self.cap = None
        self.log_event("send_video_stream stopped")

    def receive_video_stream(self):
        self.log_event("Starting video stream receiver")
        client_socket = None
        last_port = None
        last_sender = None
        target_width, target_height = 615, 420
        displayed_once = False

        def receive_frame():
            nonlocal client_socket, last_port, last_sender, displayed_once
            if self.endAllThread:
                if client_socket:
                    try:
                        client_socket.close()
                    except:
                        pass
                self.log_event("receive_video_stream stopped due to endAllThread")
                self.receiving_video = False
                return

            if not self.receiving_video and client_socket:
                self.log_event("Stopping receive_video_stream as stream is inactive")
                client_socket.close()
                client_socket = None
                last_port = None
                last_sender = None
                displayed_once = False
                self.video_label.configure(image='')
                self.root.after(100, receive_frame)
                return

            # Thử lấy port video từ queue nếu chưa có
            if not client_socket and not last_port:
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        port, sender = self.video_queue.get_nowait()
                        self.log_event(f"Attempting to connect to video stream at port {port} from {sender} (Attempt {attempt + 1}/{max_retries})")
                        client_socket = socket.socket()
                        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        client_socket.settimeout(60)
                        resolved_address = socket.gethostbyname(self.address)
                        self.log_event(f"Resolved {self.address} to {resolved_address} for video stream")
                        client_socket.connect((resolved_address, port))
                        self.log_event(f"Connected to video stream at port {port} from {sender}")
                        last_port = port
                        last_sender = sender
                        self.receiving_video = True
                        break
                    except Empty:
                        self.root.after(100, receive_frame)
                        return
                    except socket.timeout:
                        self.log_event(f"Timeout connecting to video stream at port {last_port or 'unknown'} (Attempt {attempt + 1}/{max_retries})")
                        if client_socket:
                            client_socket.close()
                            client_socket = None
                        if attempt == max_retries - 1:
                            self.log_event("Failed to connect to video stream after all retries")
                            self.log_to_ui("Error: Failed to connect to video stream after all retries\n", "message")
                        self.root.after(2000, receive_frame)
                        return
                    except Exception as e:
                        self.log_event(f"Error connecting to video stream: {str(e)} (Attempt {attempt + 1}/{max_retries})")
                        if client_socket:
                            client_socket.close()
                            client_socket = None
                        if attempt == max_retries - 1:
                            self.log_event("Failed to connect to video stream after all retries")
                            self.log_to_ui(f"Error: Failed to connect to video stream: {str(e)}\n", "message")
                        self.root.after(2000, receive_frame)
                        return

            # Nếu đã có last_port, thử kết nối lại
            if not client_socket and last_port:
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        self.log_event(f"Reattempting connection to video stream at port {last_port} from {last_sender} (Attempt {attempt + 1}/{max_retries})")
                        client_socket = socket.socket()
                        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        client_socket.settimeout(60)
                        resolved_address = socket.gethostbyname(self.address)
                        self.log_event(f"Resolved {self.address} to {resolved_address} for video stream")
                        client_socket.connect((resolved_address, last_port))
                        self.log_event(f"Reconnected to video stream at port {last_port} from {last_sender}")
                        self.receiving_video = True
                        break
                    except socket.timeout:
                        self.log_event(f"Timeout reconnecting to video stream at port {last_port} (Attempt {attempt + 1}/{max_retries})")
                        if client_socket:
                            client_socket.close()
                            client_socket = None
                        if attempt == max_retries - 1:
                            self.log_event("Failed to reconnect to video stream after all retries")
                            self.log_to_ui("Error: Failed to reconnect to video stream after all retries\n", "message")
                            self.receiving_video = False
                            last_port = None
                            last_sender = None
                            displayed_once = False
                        self.root.after(2000, receive_frame)
                        return
                    except Exception as e:
                        self.log_event(f"Error reconnecting to video stream: {str(e)} (Attempt {attempt + 1}/{max_retries})")
                        if client_socket:
                            client_socket.close()
                            client_socket = None
                        if attempt == max_retries - 1:
                            self.log_event("Failed to reconnect to video stream after all retries")
                            self.log_to_ui(f"Error: Failed to reconnect to video stream: {str(e)}\n", "message")
                            self.receiving_video = False
                            last_port = None
                            last_sender = None
                            displayed_once = False
                        self.root.after(2000, receive_frame)
                        return

            if not client_socket:
                self.root.after(100, receive_frame)
                return

            try:
                size_data = client_socket.recv(4)
                if not size_data:
                    self.log_event("Video stream closed by sender")
                    self.log_to_ui("Video stream closed by sender\n", "message")
                    client_socket.close()
                    client_socket = None
                    # Không đặt lại last_port và last_sender, để thử kết nối lại
                    self.root.after(100, receive_frame)
                    return

                size = int.from_bytes(size_data, byteorder='big')
                data = b""
                while len(data) < size:
                    packet = client_socket.recv(size - len(data))
                    if not packet:
                        self.log_event("Incomplete video frame received")
                        self.log_to_ui("Error: Incomplete video frame received\n", "message")
                        client_socket.close()
                        client_socket = None
                        self.root.after(100, receive_frame)
                        return
                    data += packet

                if len(data) == size:
                    frame = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                    if frame is None:
                        self.log_event("Failed to decode video frame, possibly corrupted data")
                        self.log_to_ui("Error: Failed to decode video frame\n", "message")
                        self.root.after(33, receive_frame)
                        return

                    frame = self.resize_frame(frame, target_width, target_height)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    photo = ImageTk.PhotoImage(img)
                    self.root.after(0, lambda: self.video_label.configure(image=photo))
                    self.video_label.image = photo
                    if not displayed_once:
                        self.log_event(f"Received frame with shape: {frame.shape}")
                        self.log_event("Video frame displayed")
                        self.log_event(f"video_label size: {self.video_label.winfo_width()}x{self.video_label.winfo_height()}")
                        displayed_once = True
                else:
                    self.log_event("Incomplete frame data")
                    self.log_to_ui("Error: Incomplete frame data received\n", "message")
                    client_socket.close()
                    client_socket = None

                self.root.after(30, receive_frame)  # Giảm độ trễ để tăng FPS
            except socket.timeout:
                self.log_event("Receive timeout")
                self.log_to_ui("Error: Receive timeout for video stream\n", "message")
                client_socket.close()
                client_socket = None
                self.root.after(100, receive_frame)
                return
            except (BrokenPipeError, ConnectionResetError):
                self.log_event("Connection to sender lost")
                self.log_to_ui("Error: Connection to video sender lost\n", "message")
                client_socket.close()
                client_socket = None
                self.root.after(100, receive_frame)
                return
            except Exception as e:
                self.log_event(f"Error receiving video frame: {str(e)}")
                self.log_to_ui(f"Error: Failed to receive video frame: {str(e)}\n", "message")
                client_socket.close()
                client_socket = None
                self.root.after(100, receive_frame)
                return

        self.root.after(0, receive_frame)
        self.log_event("receive_video_stream initialized")

    def notify_video_port(self, port):
        if not self.video_stream_active or self.video_port is None:
            return
        data = json.dumps({"name": self.name, "type": "video", "port": self.video_port}) + "\n"
        with self.socket_lock:
            if port in self.listSocket:
                try:
                    client = self.listSocket[port]
                    client.send(data.encode('utf-8'))
                    self.log_event(f"Notified video port {self.video_port} to port {port} (on connect)")
                except Exception as e:
                    self.log_event(f"Error notifying video port to {port} (on connect): {str(e)}")

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
                                    f"🕭{jsonMessage['name']} wants to connect to your channel\n",
                                    "connect"
                                )
                                self.log_event(f"Peer {jsonMessage['name']} requested connection")
                            elif jsonMessage["type"] == "chat":
                                username_part = f"{jsonMessage['name']}"
                                message_part = f" : {jsonMessage['message']}\n"
                                self.log_to_ui(username_part, "username")
                                self.log_to_ui(message_part, "message")
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
                            elif jsonMessage["type"] == "video":
                                self.video_queue.put((jsonMessage["port"], jsonMessage["name"]))
                                self.log_to_ui(f"{jsonMessage['name']} started video stream\n", "message")
                                self.log_event(f"Received video stream port {jsonMessage['port']} from {jsonMessage['name']}")
                            elif jsonMessage["type"] == "video_stop":
                                self.receiving_video = False
                                self.log_to_ui(f"{jsonMessage['name']} stopped video stream\n", "message")
                                self.log_event(f"Video stream stopped by {jsonMessage['name']}")
                        except json.JSONDecodeError:
                            if buffer.count("{") > buffer.count("}"):
                                break
                            buffer = buffer[buffer.find("{"):] if "{" in buffer else ""
                            continue
                        except Exception as e:
                            self.log_to_ui(f"Error processing JSON from {address}: {str(e)}\n", "message")
                            self.log_event(f"Error processing JSON from {address}: {str(e)}")
                            break
                except UnicodeDecodeError:
                    self.log_event(f"Ignoring non-text data from {address}, likely file data")
                    continue
            except (ConnectionResetError, BrokenPipeError):
                self.log_event(f"Connection to {address} closed by peer")
                break
            except Exception as e:
                self.log_to_ui(f"Error processing data from {address}: {str(e)}\n", "message")
                self.log_event(f"Error processing data from {address}: {str(e)}")
                break
        try:
            connection.close()
        except:
            pass

    def handleReceiveFile(self, file_socket, filename, sender):
        base_dir = self.name
        file_path = os.path.join(base_dir, filename)
        self.log_to_ui(f"{sender} : Sent you {filename}\n", "message")
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
            self.log_to_ui(f"Error receiving file {filename}: {str(e)}\n", "message")
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
            self.log_to_ui(f"Error setting up connection from {address}: {str(e)}\n", "message")
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
                        self.log_to_ui(f"Attempt {retry + 1}/3 to connect to central server failed: {str(e)}\n", "message")
                        self.log_event(f"Attempt {retry + 1}/3 to connect to central server failed: {str(e)}")
                        if retry == 2:
                            self.log_to_ui("Cannot connect to central server\n", "message")
                        time.sleep(2)
                self.log_event(f"Peer started on port {port}")
                break
            except Exception as e:
                self.log_to_ui(f"Attempt {attempt + 1}/{max_retries} failed to start server on port {port}: {str(e)}\n", "message")
                self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to start server on port {port}: {str(e)}")
                if attempt == max_retries - 1:
                    self.log_to_ui(f"Failed to start server on port {port} after {max_retries} attempts\n", "message")
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
                self.log_to_ui(f"Error accepting connection: {str(e)}\n", "message")
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
            self.log_to_ui("From Server: Online user list:\n", "message")
            for friend in friends:
                if friend:
                    name_port = friend.split(":")
                    self.log_to_ui(f"\t{name_port[0]} : {name_port[1]}\n", "message")
            return

        username_part = f"{self.name}"
        message_part = f" : {message}\n"
        self.log_to_ui(username_part, "username")
        self.log_to_ui(message_part, "message")
        self.save_history(self.name, message)
        self.log_event(f"Sent message: {message}")

        data = json.dumps({"name": self.name, "type": "chat", "message": message}) + "\n"
        self.cleanup_sockets()
        with self.socket_lock:
            for port, client in list(self.listSocket.items()):
                try:
                    client.send(data.encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError):
                    self.log_to_ui(f"Connection to port {port} closed\n", "message")
                    self.log_event(f"Connection to port {port} closed")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)
                except Exception as e:
                    self.log_to_ui(f"Error sending message to port {port}: {str(e)}\n", "message")
                    self.log_event(f"Error sending message to port {port}: {str(e)}")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)

        if "@bot" in message.lower() or "bot:" in message.lower():
            bot_response = self.processBotMessage(message)
            username_part = "Bot🤖"
            message_part = f" : {bot_response}\n"
            self.log_to_ui(username_part, "username")
            self.log_to_ui(message_part, "message")
            self.save_history("Bot", bot_response)
            self.log_event(f"Bot responded: {bot_response}")

    def sendFile(self, filePath):
        if not os.path.exists(filePath):
            self.log_to_ui(f"File {filePath} does not exist\n", "message")
            self.log_event(f"File {filePath} does not exist")
            return
        filename = os.path.basename(filePath)
        self.log_to_ui(f"You : Sending {filename} to your friend\n", "message")
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
                        self.log_to_ui(f"Peer at port {port} did not provide file port\n", "message")
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
                    self.log_to_ui(f"Peer at port {port} did not respond to file transfer\n", "message")
                    self.log_event(f"Peer at port {port} did not respond to file transfer")
                except (ConnectionResetError, BrokenPipeError):
                    self.log_to_ui(f"Connection to port {port} closed during file transfer\n", "message")
                    self.log_event(f"Connection to port {port} closed during file transfer")
                    client.close()
                    del self.listSocket[port]
                    if port in self.ports:
                        self.ports.remove(port)
                except Exception as e:
                    self.log_to_ui(f"Error sending {filename} to port {port}: {str(e)}\n", "message")
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
                    self.notify_video_port(port)
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
                self.notify_video_port(port)
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
                                self.notify_video_port(port)
                                return
                            except:
                                client.close()
                                del self.listSocket[port]
                                if port in self.ports:
                                    self.ports.remove(port)
                    clientSocket.close()
                    continue
                self.log_to_ui(f"Attempt {attempt + 1}/{max_retries} failed to connect to port {port}: {str(e)}\n", "message")
                self.log_event(f"Attempt {attempt + 1}/{max_retries} failed to connect to port {port}: {str(e)}")
                if attempt == max_retries - 1:
                    self.log_to_ui(f"Failed to connect to peer at port {port} after {max_retries} attempts\n", "message")
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
        self.receiving_video = False
        if self.cap:
            self.cap.release()
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
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
