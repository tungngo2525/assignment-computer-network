import tkinter as tk
from tkinter.ttk import Style, Button
from P2P import Peer
from threading import Thread
from PIL import ImageTk, Image
import copy
import socket
import json
import cv2

peer = None
flag = True
friendList = None
friends = []
video_label = None
cap = None
is_streaming_locally = False

class MainWindow:
    def __init__(self, root, name, port):
        self.root = root
        self.name = name
        self.port = port
        self.root.title('Bku Streaming ✿')
        self.root.geometry("1080x600")
        self.root.configure(bg='#2C2F33')
        self.root.resizable(0, 0)

        # Style setup
        self.style = Style()
        self.style.theme_use('default')
        self.style.configure('TButton', font=('Segoe UI', 10), background='#7289DA', foreground='white')
        self.style.map('TButton', background=[('active', '#5b6eae')])
        self.style.configure('Friend.TButton', background='#99aab5', foreground='black')
        self.style.map('Friend.TButton', background=[('active', '#ffffff')])
        # Bỏ style Video.TButton, sử dụng Channel.TButton cho cả ba nút
        self.style.configure('Channel.TButton', background='#7289DA', foreground='white')
        self.style.map('Channel.TButton', background=[('active', '#5865F2')])
        self.style.configure('Send.TButton', font=('Segoe UI', 10, 'bold'), background='#5865F2', foreground='white', padding=3)
        self.style.map('Send.TButton', background=[('active', '#4752C4')])

        # Title label
        tk.Label(self.root, text="Bku Channel✿", font=("Helvetica", 25, "bold"), bg="#2C2F33", fg="white").place(x=430, y=15)

        # Video area
        global video_label
        video_label = tk.Label(self.root, bg="#23272A", bd=2, relief="groove")
        video_label.place(x=150, y=100, width=615, height=420)

        # Chat area
        chatArea = tk.Frame(self.root, bg="#2C2F33")
        scroll = tk.Scrollbar(chatArea)
        self.text = tk.Text(chatArea, font=("Georgia", 11), yscrollcommand=scroll.set, width=30, height=21.5, bg="#23272A", fg="white", insertbackground="white", bd=2, relief="solid", padx=5)
        chatArea.place(x=775, y=100)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT)
        self.text.configure(state='disable')

        # Định nghĩa các tag màu sắc
        self.text.tag_configure("username", foreground="#00FF00")
        self.text.tag_configure("message", foreground="white")
        self.text.tag_configure("connect", foreground="blue", font=("Georgia", 12, "bold"))
        self.text.tag_configure("error", foreground="red")

        # Chat input frame
        chatFrame = tk.Frame(self.root, bg="#2C2F33")
        chatFrame.place(x=775, y=490)
        self.chatBox = tk.Entry(chatFrame, width=31, font=("Segoe UI", 10), bg="#99aab5", fg="black")
        self.chatBox.pack(side=tk.LEFT, padx=(0, 5), pady=5, ipady=2)
        sendButton = Button(chatFrame, text="➤", command=self.SendMessage, style='Send.TButton')
        sendButton.pack(side=tk.LEFT, ipadx=2)

        # Bind keys
        self.root.bind('<Shift-Return>', lambda event: self.chatBox.insert(tk.END, '\n'))
        self.root.bind('<Return>', self.SendMessage)

        # Buttons - Sử dụng Channel.TButton cho cả Start Stream, Stop Stream và Channel Online
        Button(self.root, text="Start Stream", command=self.StartVideoStream, style='Channel.TButton').place(x=150, y=525, width=120, height=30)
        Button(self.root, text="Stop Stream", command=self.StopVideoStream, style='Channel.TButton').place(x=270, y=525, width=120, height=30)
        Button(self.root, text="Channel Online", command=self.updateFriendList, style='Channel.TButton').place(x=18, y=100, width=130, height=30)

        # Khởi tạo Peer sau khi các widget đã được tạo
        self.initialize_peer()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def initialize_peer(self):
        global peer, flag
        try:
            peer = Peer(self.name, self.port, self.text, video_label)
            peer.startServer()
            flag = False
        except Exception as e:
            self.log_to_ui(f"Failed to start server: {str(e)}\n", "error")
            print(f"Fail Server: {str(e)}")
            self.root.destroy()

    def log_to_ui(self, message, tag=None):
        self.text.configure(state='normal')
        self.text.insert(tk.END, message, tag)
        self.text.see(tk.END)
        self.text.configure(state='disable')

    def updateFriendList(self):
        global peer, friendList, friends
        if peer is None:
            self.log_to_ui("Error: Peer not initialized\n", "error")
            return

        for widget in self.root.winfo_children():
            if isinstance(widget, Button) and widget.cget('text') not in ['Log in', '➤', 'Browser', 'Channel Online', 'Start Stream', 'Stop Stream']:
                widget.destroy()
            if isinstance(widget, tk.Label) and widget.cget('text') == '●':
                widget.destroy()

        if not hasattr(peer, 'listFriend') or not peer.listFriend:
            self.log_to_ui("No friends online\n", "message")
            return

        friendList = peer.listFriend.split(';')
        friends.clear()
        if friendList and friendList[0]:
            for i, friend_str in enumerate(friendList):
                if not friend_str:
                    continue
                friend = friend_str.split(":")
                if len(friend) >= 2:
                    friends.append(copy.deepcopy(friend))
                    is_online = len(friend) >= 3 and friend[2].lower() == "online"
                    status_color = "#43B581" if is_online else "gray"

                    tk.Label(self.root, text="●", fg=status_color, bg="#2C2F33", font=("Arial", 14)).place(x=15, y=(i + 1) * 35 + 100)
                    Button(self.root, text=friends[i][0], command=lambda b=friends[i][1]: self.RunClient(b), width=15, style='Friend.TButton').place(x=30, y=(i + 1) * 35 + 100)

    def RunClient(self, port):
        global flag, peer
        if flag or peer is None:
            self.log_to_ui("Error: Peer not initialized\n", "error")
            return
        try:
            peer.startClient(port)
        except Exception as e:
            self.log_to_ui(f"Failed to connect to peer at port {port}: {str(e)}\n", "error")
            print(f"Fail client: {str(e)}")

    def SendMessage(self, event=None):
        global flag, peer
        if flag or peer is None:
            self.log_to_ui("Error: Peer not initialized\n", "error")
            return
        if self.chatBox.get().strip():
            try:
                peer.sendMessage(self.chatBox.get().strip())
                self.chatBox.delete(0, tk.END)
            except Exception as e:
                self.log_to_ui(f"Failed to send message: {str(e)}\n", "error")
                print(f"Fail sending message: {str(e)}")

    def StartVideoStream(self):
        global peer, cap, is_streaming_locally
        if peer is None:
            self.log_to_ui("Error: Peer not initialized\n", "error")
            print("Peer not initialized.")
            return

        try:
            peer.startVideoStream()
            self.log_to_ui("Video stream started\n", "message")
            print("Video stream started.")
        except Exception as e:
            self.log_to_ui(f"Error starting video stream: {str(e)}\n", "error")
            print(f"Error starting video stream: {str(e)}")
            return

        # Chỉ chạy local stream nếu không nhận video từ peer khác
        if not peer.receiving_video and not is_streaming_locally:
            is_streaming_locally = True
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.log_to_ui("Error: Could not open video stream\n", "error")
                print("Error: Could not open video stream.")
                is_streaming_locally = False
                return

            def update_frame():
                global cap, is_streaming_locally
                if not is_streaming_locally or peer.receiving_video or not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                        cap = None
                    video_label.configure(image='')
                    return

                ret, frame = cap.read()
                if ret:
                    # Resize frame để khớp với video_label
                    height, width = frame.shape[:2]
                    target_width, target_height = 615, 420
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

                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    img_tk = ImageTk.PhotoImage(img)
                    video_label.img_tk = img_tk
                    video_label.configure(image=img_tk)
                    video_label.after(33, update_frame)  # 30 FPS
                else:
                    
                
                    if cap:
                        cap.release()
                        cap = None
                    video_label.configure(image='')
                    is_streaming_locally = False

            video_label.after(0, update_frame)

    def StopVideoStream(self):
        global peer, cap, is_streaming_locally
        if peer is None:
            self.log_to_ui("Error: Peer not initialized\n", "error")
            print("Peer not initialized.")
            return

        try:
            peer.stopVideoStream()
            is_streaming_locally = False
            print("Video stream stopped.")
        except Exception as e:
            self.log_to_ui(f"Error stopping video stream: {str(e)}\n", "error")
            print(f"Error stopping video stream: {str(e)}")

        if cap:
            cap.release()
            cap = None
        video_label.configure(image='')

    def on_closing(self):
        global peer, flag, cap
        flag = False
        if cap:
            cap.release()
            cap = None
        if peer:
            peer.endSystem()
            try:
                offline_socket = socket.socket()
                offline_socket.connect((peer.address, peer.centralServerPort))
                data = json.dumps({"name": peer.name, "port": str(peer.port), "status": "offline"})
                offline_socket.send(data.encode('utf-8'))
                offline_socket.close()
            except Exception as e:
                self.log_to_ui(f"Error notifying offline status: {str(e)}\n", "error")
                print(f"Error notifying offline status: {e}")
        self.root.destroy()

class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title('Login - Bku Streaming ✿')
        self.root.geometry("400x300")
        self.root.configure(bg='#2C2F33')
        self.root.resizable(0, 0)

        # Style setup
        self.style = Style()
        self.style.theme_use('default')
        self.style.configure('Login.TButton', font=('Segoe UI', 12, 'bold'), background='#5865F2', foreground='white', padding=8)
        self.style.map('Login.TButton', background=[('active', '#4752C4')])
        self.style.configure('TEntry', fieldbackground='#40444B', foreground='white', font=('Segoe UI', 12))
        self.style.map('TEntry', fieldbackground=[('focus', '#4A4F56')])

        # Title label
        tk.Label(self.root, text="Bku Streaming ✿ Login", font=("Helvetica", 18, "bold"), bg="#2C2F33", fg="white").place(relx=0.5, y=40, anchor="center")

        # Name frame
        nameFrame = tk.Frame(self.root, bg="#2C2F33")
        nameFrame.place(relx=0.48, y=90, anchor="center")
        tk.Label(nameFrame, text="Name:", font=('Segoe UI', 12), fg="white", bg="#2C2F33").pack(side=tk.LEFT, padx=5)
        self.nameEntry = tk.Entry(nameFrame, width=20, font=('Segoe UI', 12), bg="#40444B", fg="white", insertbackground="white", bd=2, relief="flat")
        self.nameEntry.pack(side=tk.LEFT)

        # Port frame
        portFrame = tk.Frame(self.root, bg="#2C2F33")
        portFrame.place(relx=0.5, y=130, anchor="center")
        tk.Label(portFrame, text="Port:", font=('Segoe UI', 12), fg="white", bg="#2C2F33").pack(side=tk.LEFT, padx=5)
        self.portEntry = tk.Entry(portFrame, width=20, font=('Segoe UI', 12), bg="#40444B", fg="white", insertbackground="white", bd=2, relief="flat")
        self.portEntry.pack(side=tk.LEFT)

        # Error label
        self.errorLabel = tk.Label(self.root, text="", font=('Segoe UI', 10), fg="red", bg="#2C2F33", wraplength=350)
        self.errorLabel.place(relx=0.5, y=170, anchor="center")

        # Login button
        Button(self.root, text="Log in", style='Login.TButton', command=self.RunServer).place(relx=0.5, y=220, anchor="center")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def RunServer(self):
        global flag
        if not flag:
            return
        name = self.nameEntry.get()
        port = self.portEntry.get()
        if name and port:
            try:
                port = int(port)
                self.nameEntry.configure(state='readonly')
                self.portEntry.configure(state='readonly')
                self.root.destroy()
                main_root = tk.Tk()
                app = MainWindow(main_root, name, port)
                main_root.mainloop()
            except ValueError:
                self.errorLabel.config(text="Port must be a valid integer")
                self.nameEntry.configure(state='normal')
                self.portEntry.configure(state='normal')
            except Exception as e:
                self.errorLabel.config(text=f"Login failed: {str(e)}")
                self.nameEntry.configure(state='normal')
                self.portEntry.configure(state='normal')
        else:
            self.errorLabel.config(text="Please enter both Name and Port")
            self.nameEntry.configure(state='normal')
            self.portEntry.configure(state='normal')

    def on_closing(self):
        self.root.destroy()

# Khởi tạo cửa sổ đăng nhập
if __name__ == "__main__":
    login_root = tk.Tk()
    login_app = LoginWindow(login_root)
    login_root.mainloop()
