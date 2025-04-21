from tkinter import *
from tkinter.ttk import *
from P2P import Peer
from tkinter import filedialog, simpledialog
from threading import Thread
from PIL import ImageTk, Image
import tkinter as tk
import copy
import socket
import json

peer = None
flag = True
friendList = None
friends = []

def updateFriendList():
    global peer, friendList, friends

    for widget in master.winfo_children():
        if isinstance(widget, Button) and widget.cget('text') not in ['Log in', '➤', 'Browser', 'Channel Online']:
            widget.destroy()
        if isinstance(widget, Label) and widget.cget('text') in ['●']:
            widget.destroy()

    if peer is None:
        print("Debug: Peer is None - Please log in first")
        return

    try:
        if not hasattr(peer, 'listFriend') or not peer.listFriend:
            print("Debug: No friend list available")
            return
        friendList = peer.listFriend.split(';')
        print(f"Debug: Raw friend list: {peer.listFriend}")
        print(f"Debug: Split friend list: {friendList}")
    except Exception as e:
        print(f"Debug: Error accessing friend list: {str(e)}")
        return

    friends.clear()

    if friendList and friendList[0]:
        for i, friend_str in enumerate(friendList):
            if not friend_str:
                continue
            friend = friend_str.split(":")
            if len(friend) >= 2:
                friends.append(copy.deepcopy(friend))
                print(f"Debug: Friend {i}: {friend}")

                is_online = len(friend) >= 3 and friend[2].lower() == "online"
                status_color = "#43B581" if is_online else "black"

                status_dot = Label(master, text="●", foreground=status_color, font=("Arial", 15))
                status_dot.place(x=7, y=(i + 1) * 31 + 100)

                Button(
                    master,
                    text=friends[i][0],
                    command=lambda b=friends[i][1]: RunClient(b),
                    width=13,
                    style='Friend.TButton'
                ).place(x=21, y=(i + 1) * 30 + 100)
            else:
                print(f"Debug: Invalid friend format at index {i}: {friend}")
    else:
        print("Debug: Friend list is empty or invalid")

def RunServer():
    global flag, peer
    print("Starting Server")
    if not flag:
        return

    name = nameEntry.get()
    port = portEntry.get()

    if name and port:
        try:
            nameEntry.configure(state='readonly')
            portEntry.configure(state='readonly')
            peer = Peer(name, int(port), text)
            print("Create Server")
            peer.startServer()
            print("Run Server")
            flag = False
        except Exception as e:
            print(f"Fail Server: {str(e)}")
            nameEntry.configure(state='normal')
            portEntry.configure(state='normal')
    else:
        print("Debug: Name or Port is empty")

def RunClient(port):
    global flag, peer
    print("Starting client")
    if flag or peer is None:
        return
    try:
        peer.startClient(port)
        print("Run client")
    except Exception as e:
        print(f"Fail client: {str(e)}")

def SendMessage():
    global flag, peer
    print("Starting send")
    if flag or peer is None:
        return
    if chatBox.get().strip():
        try:
            peer.sendMessage(chatBox.get().strip())
            chatBox.delete(0, END)
            print("SendMessage")
        except Exception as e:
            print(f"Fail sending message: {str(e)}")

def OpenFile():
    filepath = filedialog.askopenfilename()
    fileBox.configure(state='normal')
    fileBox.delete(0, END)
    fileBox.insert(0, filepath)
    fileBox.configure(state='readonly')

def SendFile():
    global peer
    if peer is None:
        return
    try:
        if fileBox.get():
            peer.sendFile(fileBox.get())
    except Exception as e:
        print(f"Fail sending file: {str(e)}")

def on_closing():
    global peer, flag
    flag = False
    if peer is not None:
        peer.endSystem()
        try:
            offline_socket = socket.socket()
            offline_socket.connect((peer.address, peer.centralServerPort))
            data = json.dumps({"name": peer.name, "port": str(peer.port), "status": "offline"})
            offline_socket.send(data.encode('utf-8'))
            offline_socket.close()
        except Exception as e:
            print(f"Error notifying offline status: {e}")
    master.destroy()

master = Tk()
master.title('Bku Streaming ✿')
master.geometry("600x500")
master.resizable(0, 0)

style = Style()
style.theme_use('default')
style.configure('TButton', font=('Segoe UI', 10), background='white', foreground='black')
style.map('TButton', background=[('active', '#4752C4')])
style.configure('Friend.TButton', font=('Segoe UI', 10), background='#999bad', foreground='black')
style.map('Friend.TButton', background=[('active', 'white')])

# Server inputs
Label(master, text="Name:", width=10).place(x=10, y=10)
Label(master, text="Port:", width=10).place(x=10, y=40)
nameEntry = Entry(master, width=33)
portEntry = Entry(master, width=20)
nameEntry.place(x=50, y=10)
portEntry.place(x=50, y=40)
Button(master, text="Log in", command=RunServer).place(x=180, y=40)

# App title
Label(master, text="Bku Channel✿", width=15, font=("Helvetica", 25, "bold"), background="#82CAFA", foreground="black", anchor="center").place(x=290, y=15)

# Chat area
chatArea = Frame(master, width=50, height=50)
scroll = Scrollbar(chatArea)
text = Text(chatArea, font=("Georgia", 12), yscrollcommand=scroll.set, width=44, height=17, bg="white", fg="black")
chatArea.place(x=130, y=100)
scroll.pack(side=RIGHT, fill=Y)
text.pack(side=LEFT)
text.configure(state='disable')

# Send message
Label(master, text="Message:", width=10).place(x=125, y=460)
chatBox = Entry(master, width=50)
chatBox.place(x=190, y=460)
Button(master, text="➤", command=SendMessage).place(x=500, y=460)
master.bind('<Return>', lambda event: SendMessage())

# Send file
Label(master, text="File:", width=10).place(x=125, y=420)
fileBox = Entry(master, width=37)
fileBox.place(x=190, y=420)
fileBox.configure(state='readonly')
Button(master, text="Browser", command=OpenFile).place(x=420, y=420)
Button(master, text="➤", command=SendFile).place(x=500, y=420)

style.configure('Channel.TButton', background='#7289DA', foreground='white')
style.map('Channel.TButton',
          background=[('active', '#444477')],
          foreground=[('active', 'white')])
Button(
    master,
    text="Channel Online",
    command=updateFriendList,
    style='Channel.TButton'
).place(x=5, y=100, width=120, height=30)


master.protocol("WM_DELETE_WINDOW", on_closing)
mainloop()
