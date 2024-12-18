import socket
import json
import threading
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QTextEdit, QLineEdit, QDialog,
    QDialogButtonBox, QMessageBox, QApplication, QListWidgetItem,
    QColorDialog, QInputDialog, QGroupBox, QStyle, QComboBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal
import sys

class FriendRequestDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle('Friend Request')
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f'Friend request from {self.username}'))

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes |
            QDialogButtonBox.StandardButton.No
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

class FriendsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.friends = {}  # {username: status}

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel('Friends')
        title.setStyleSheet('font-weight: bold; font-size: 14px;')
        layout.addWidget(title)

        # Friends List
        self.friends_list = QListWidget()
        self.friends_list.itemDoubleClicked.connect(self.friend_clicked)
        layout.addWidget(self.friends_list)

        # Add Friend Button
        add_friend_btn = QPushButton('Add Friend')
        add_friend_btn.clicked.connect(self.add_friend)
        layout.addWidget(add_friend_btn)

    def update_friends(self, friends_data):
        self.friends.clear()
        self.friends_list.clear()
        
        # Handle both list and tuple formats
        for friend_data in friends_data:
            if isinstance(friend_data, (list, tuple)):
                username, status = friend_data
            else:
                username = friend_data
                status = 'offline'  # Default status if not provided
                
            self.friends[username] = status
            item = QListWidgetItem(f'{username} ({status})')
            item.setData(Qt.ItemDataRole.UserRole, username)
            if status == 'online':
                item.setForeground(Qt.GlobalColor.green)
            elif status == 'pending':
                item.setForeground(Qt.GlobalColor.gray)
            self.friends_list.addItem(item)

    def add_friend(self):
        username, ok = QInputDialog.getText(self, 'Add Friend',
                                          'Enter username to add as friend:')
        if ok and username:
            self.parent().send_to_server({
                'type': 'send_friend_request',
                'username': username
            })

    def friend_clicked(self, item):
        username = item.data(Qt.ItemDataRole.UserRole)
        status = self.friends.get(username)
        if status == 'pending':
            # Show accept/reject dialog
            dialog = FriendRequestDialog(username, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.parent().send_to_server({
                    'type': 'accept_friend_request',
                    'username': username
                })
        else:
            # Show friend's profile
            self.parent().show_user_profile(username)

class CreateRoomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle('Create Room')
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        # Room Name
        name_label = QLabel('Room Name:')
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Enter room name...')
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        # Room Type
        type_label = QLabel('Room Type:')
        layout.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(['public', 'private'])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)

        # Password (for private rooms)
        self.password_label = QLabel('Password:')
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('Enter room password...')
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_label.hide()
        self.password_edit.hide()
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_edit)

        # Description
        desc_label = QLabel('Description:')
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText('Enter room description...')
        self.desc_edit.setMaximumHeight(100)
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_edit)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_type_changed(self, room_type):
        if room_type == 'private':
            self.password_label.show()
            self.password_edit.show()
        else:
            self.password_label.hide()
            self.password_edit.hide()

    def get_room_data(self):
        return {
            'room_name': self.name_edit.text(),
            'room_type': self.type_combo.currentText(),
            'password': self.password_edit.text() if self.type_combo.currentText() == 'private' else None,
            'description': self.desc_edit.toPlainText()
        }

class RoomManagementDialog(QDialog):
    def __init__(self, room_id, room_info, current_username, parent=None):
        super().__init__(parent)
        self.room_id = room_id
        self.room_info = room_info
        self.current_username = current_username
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f'Manage Room: {self.room_info["name"]}')
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        # Room Info
        info_group = QGroupBox("Room Information")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f'Name: {self.room_info["name"]}'))
        info_layout.addWidget(QLabel(f'Type: {self.room_info["type"]}'))
        info_layout.addWidget(QLabel(f'Creator: {self.room_info["creator"]}'))
        if self.room_info.get("description"):
            info_layout.addWidget(QLabel(f'Description: {self.room_info["description"]}'))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Moderator Controls
        if self.is_moderator():
            mod_group = QGroupBox("Moderator Controls")
            mod_layout = QVBoxLayout()

            # Add Moderator
            add_mod_layout = QHBoxLayout()
            self.mod_input = QLineEdit()
            self.mod_input.setPlaceholderText('Username to make moderator...')
            add_mod_btn = QPushButton('Add Moderator')
            add_mod_btn.clicked.connect(self.add_moderator)
            add_mod_layout.addWidget(self.mod_input)
            add_mod_layout.addWidget(add_mod_btn)
            mod_layout.addLayout(add_mod_layout)

            # Ban User
            ban_layout = QHBoxLayout()
            self.ban_input = QLineEdit()
            self.ban_input.setPlaceholderText('Username to ban...')
            self.ban_reason = QLineEdit()
            self.ban_reason.setPlaceholderText('Ban reason...')
            ban_btn = QPushButton('Ban User')
            ban_btn.clicked.connect(self.ban_user)
            ban_layout.addWidget(self.ban_input)
            ban_layout.addWidget(self.ban_reason)
            ban_layout.addWidget(ban_btn)
            mod_layout.addLayout(ban_layout)

            mod_group.setLayout(mod_layout)
            layout.addWidget(mod_group)

        # Current Moderators List
        mod_list_group = QGroupBox("Current Moderators")
        mod_list_layout = QVBoxLayout()
        for mod in self.room_info["moderators"]:
            mod_list_layout.addWidget(QLabel(mod))
        mod_list_group.setLayout(mod_list_layout)
        layout.addWidget(mod_list_group)

        # Close Button
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def is_moderator(self):
        return (self.current_username == self.room_info["creator"] or 
                self.current_username in self.room_info["moderators"])

    def add_moderator(self):
        username = self.mod_input.text().strip()
        if username:
            self.parent().send_to_server({
                'type': 'add_moderator',
                'room_id': self.room_id,
                'username': username
            })
            self.mod_input.clear()

    def ban_user(self):
        username = self.ban_input.text().strip()
        reason = self.ban_reason.text().strip()
        if username:
            self.parent().send_to_server({
                'type': 'ban_user',
                'room_id': self.room_id,
                'username': username,
                'reason': reason
            })
            self.ban_input.clear()
            self.ban_reason.clear()

class UserProfileDialog(QDialog):
    def __init__(self, username, is_editable=True, parent=None):
        super().__init__(parent)
        self.username = username
        self.is_editable = is_editable
        self.text_color = '#000000'  # Default color
        self.setup_ui()

    def setup_ui(self):
        # Basic window setup
        self.setWindowTitle(f'Profile - {self.username}')
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        # Username display
        username_label = QLabel(f'Username: {self.username}')
        layout.addWidget(username_label)

        # Bio section
        bio_label = QLabel('Bio:')
        layout.addWidget(bio_label)
        self.bio_edit = QTextEdit()
        self.bio_edit.setPlaceholderText('Write something about yourself...')
        self.bio_edit.setReadOnly(not self.is_editable)
        self.bio_edit.setMaximumHeight(100)
        layout.addWidget(self.bio_edit)

        # Pronouns section
        pronouns_label = QLabel('Pronouns:')
        layout.addWidget(pronouns_label)
        self.pronouns_edit = QLineEdit()
        self.pronouns_edit.setPlaceholderText('Your pronouns')
        self.pronouns_edit.setReadOnly(not self.is_editable)
        layout.addWidget(self.pronouns_edit)

        # Text Color button (only for editable profiles)
        if self.is_editable:
            self.color_btn = QPushButton('Choose Text Color')
            self.color_btn.clicked.connect(self.choose_color)
            self.color_btn.setStyleSheet(f'background-color: {self.text_color}')
            layout.addWidget(self.color_btn)

        # Add save/cancel buttons for editable profiles
        if self.is_editable:
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | 
                QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            layout.addWidget(button_box)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()
            self.color_btn.setStyleSheet(f'background-color: {self.text_color}')

class ChatClient(QMainWindow):
    message_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.socket = None
        self.connected = False
        self.username = None
        self.current_room = None
        
        self.init_ui()
        self.message_received.connect(self.handle_server_message)
        self.connection_status.connect(self.handle_connection_status)

    def init_ui(self):
        self.setWindowTitle('Chat Client')
        self.setGeometry(100, 100, 1000, 600)  # Made window wider for friends panel

        # Create status bar
        self.statusBar = self.statusBar()
        self.update_status_bar()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Left panel for rooms and online users
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Rooms list
        rooms_group = QGroupBox("Rooms")
        rooms_layout = QVBoxLayout()
        self.rooms_list = QListWidget()
        self.rooms_list.itemClicked.connect(self.room_selected)
        rooms_layout.addWidget(self.rooms_list)
        
        # Room controls
        room_controls = QHBoxLayout()
        create_room_btn = QPushButton('Create Room')
        create_room_btn.clicked.connect(self.create_room_dialog)
        manage_room_btn = QPushButton('Manage Room')
        manage_room_btn.clicked.connect(self.show_room_management)
        room_controls.addWidget(create_room_btn)
        room_controls.addWidget(manage_room_btn)
        rooms_layout.addLayout(room_controls)
        
        rooms_group.setLayout(rooms_layout)
        left_layout.addWidget(rooms_group)
        
        # Online users list
        users_group = QGroupBox("Online Users")
        users_layout = QVBoxLayout()
        self.users_list = QListWidget()
        self.users_list.itemClicked.connect(self.user_clicked)
        users_layout.addWidget(self.users_list)
        users_group.setLayout(users_layout)
        left_layout.addWidget(users_group)

        # Right panel for chat
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display)
        
        # Message input
        self.message_input = QLineEdit()
        self.message_input.returnPressed.connect(self.send_message)
        right_layout.addWidget(self.message_input)

        # Friends panel
        self.friends_panel = FriendsPanel(self)

        # Add panels to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        layout.addWidget(self.friends_panel, 1)

        # Create menu bar
        menubar = self.menuBar()
        account_menu = menubar.addMenu('Account')
        
        login_action = QAction('Login', self)
        login_action.triggered.connect(self.show_login_dialog)
        account_menu.addAction(login_action)
        
        register_action = QAction('Register', self)
        register_action.triggered.connect(self.show_register_dialog)
        account_menu.addAction(register_action)
        
        profile_action = QAction('My Profile', self)
        profile_action.triggered.connect(self.show_my_profile)
        account_menu.addAction(profile_action)
        
        # Initially disable chat functionality
        self.message_input.setEnabled(False)
        self.rooms_list.setEnabled(False)

    def update_status_bar(self):
        if self.connected:
            if self.username:
                self.statusBar.showMessage(f'Connected | Logged in as: {self.username}')
                self.statusBar.setStyleSheet("background-color: #90EE90;")  # Light green
            else:
                self.statusBar.showMessage('Connected | Not logged in')
                self.statusBar.setStyleSheet("background-color: #FFB6C1;")  # Light red
        else:
            self.statusBar.showMessage('Not connected to server')
            self.statusBar.setStyleSheet("background-color: #FFB6C1;")  # Light red

    def connect_to_server(self):
        try:
            print("Attempting to connect to server...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect(('98.237.241.248', 5000))
            self.socket.settimeout(None)
            self.connected = True
            self.update_status_bar()  # Update status after connection
            
            print("Connected successfully")
            
            # Start listening for server messages
            thread = threading.Thread(target=self.receive_messages)
            thread.daemon = True
            thread.start()
            
            return True
        except socket.timeout:
            QMessageBox.critical(self, 'Error', 'Connection timed out. Server might be offline.')
            return False
        except ConnectionRefusedError:
            QMessageBox.critical(self, 'Error', 'Connection refused. Make sure the server is running and port is open.')
            return False
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Could not connect to server: {str(e)}')
            return False

    def receive_messages(self):
        while self.connected:
            try:
                # First receive the message length
                length_header = self.socket.recv(10)
                if not length_header:
                    raise ConnectionError("Server closed connection")
                
                message_length = int(length_header.decode().strip())
                
                # Initialize buffer for receiving data
                data_buffer = bytearray()
                bytes_received = 0
                
                # Receive the full message
                while bytes_received < message_length:
                    chunk_size = min(8192, message_length - bytes_received)
                    chunk = self.socket.recv(chunk_size)
                    if not chunk:
                        raise ConnectionError("Connection closed while receiving message")
                    data_buffer.extend(chunk)
                    bytes_received += len(chunk)
                
                # Decode and parse the complete message
                message = data_buffer.decode()
                data = json.loads(message)
                self.message_received.emit(data)
                
            except Exception as e:
                print(f"Error receiving message: {e}")
                self.connected = False
                self.connection_status.emit(False)
                break

    def handle_server_message(self, data):
        try:
            print(f"Received message from server: {data['type']}")
            print(f"Message data: {data}")  # Add debug logging
            if data['type'] == 'message':
                self.display_message(data['username'], data['content'], data.get('text_color', '#000000'))
            elif data['type'] == 'room_state':
                print(f"Updating rooms with: {data['rooms']}")  # Add debug logging
                print(f"Rooms list enabled state before update: {self.rooms_list.isEnabled()}")  # Add debug logging
                self.update_rooms(data['rooms'])
                print(f"Room list now has {self.rooms_list.count()} items")  # Add debug logging
                print(f"Rooms list enabled state after update: {self.rooms_list.isEnabled()}")  # Add debug logging
            elif data['type'] == 'online_users':
                self.update_online_users(data['users'])
            elif data['type'] == 'login_response':
                if data.get('success'):
                    print("Login successful, enabling rooms list")  # Add debug logging
                    self.username = data.get('username')
                    self.message_input.setEnabled(True)
                    self.rooms_list.setEnabled(True)
                    print(f"Rooms list enabled state after login: {self.rooms_list.isEnabled()}")  # Add debug logging
                    self.update_status_bar()
                    # Request friends list after login
                    self.send_to_server({'type': 'get_friends'})
                    QMessageBox.information(self, 'Success', 'Logged in successfully!')
                else:
                    QMessageBox.warning(self, 'Error', 'Login failed')
            elif data['type'] == 'friends_list':
                self.friends_panel.update_friends(data['friends'])
            elif data['type'] == 'friend_request':
                dialog = FriendRequestDialog(data['from_user'], self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.send_to_server({
                        'type': 'accept_friend_request',
                        'username': data['from_user']
                    })
            elif data['type'] == 'friend_added':
                QMessageBox.information(self, 'Success', 
                                      f'You are now friends with {data["username"]}')
                self.send_to_server({'type': 'get_friends'})
            elif data['type'] == 'banned':
                QMessageBox.warning(self, 'Banned', 
                                  f'You have been banned from room {data["room_id"]}\nReason: {data.get("reason", "No reason provided")}')
                if self.current_room == data['room_id']:
                    self.current_room = None
                    self.message_input.setEnabled(False)
                    self.chat_display.clear()
            elif data['type'] == 'register_response':
                if data.get('success'):
                    QMessageBox.information(self, 'Success', 'Registration successful! You can now login.')
                else:
                    QMessageBox.warning(self, 'Error', data.get('message', 'Registration failed'))
            elif data['type'] == 'room_created':
                room_id = data.get('room_id')
                if room_id is not None:
                    # Automatically select and join the new room
                    self.current_room = room_id
                    self.chat_display.clear()
                    self.message_input.setEnabled(True)
                    print(f"Automatically joined room {room_id}")
                QMessageBox.information(self, 'Success', 
                                      f'Room "{data["room_name"]}" created successfully!')
            elif data['type'] == 'profile_data':
                # Update profile dialog with received data
                for dialog in self.findChildren(UserProfileDialog):
                    if dialog.username == data['username']:
                        dialog.bio_edit.setText(data.get('bio', ''))
                        dialog.pronouns_edit.setText(data.get('pronouns', ''))
                        if data.get('text_color'):
                            dialog.text_color = data['text_color']
                            if hasattr(dialog, 'color_btn'):
                                dialog.color_btn.setStyleSheet(f'background-color: {data["text_color"]}')
            elif data['type'] == 'profile_updated':
                if data.get('success'):
                    QMessageBox.information(self, 'Success', 'Profile updated successfully!')
                else:
                    QMessageBox.warning(self, 'Error', data.get('message', 'Failed to update profile'))
            elif data['type'] == 'error':
                QMessageBox.warning(self, 'Error', data['message'])
        except Exception as e:
            print(f"Error handling server message: {e}")
            print(f"Message data: {data}")

    def handle_connection_status(self, connected):
        if not connected:
            self.connected = False
            self.username = None
            self.message_input.setEnabled(False)
            self.rooms_list.setEnabled(False)
            self.update_status_bar()  # Update status on disconnect
            QMessageBox.warning(self, 'Disconnected', 'Lost connection to server')

    def send_to_server(self, message_dict):
        if not self.connected:
            print("Not connected to server")
            return False
            
        try:
            # Validate message format
            if not isinstance(message_dict, dict) or 'type' not in message_dict:
                print("Invalid message format")
                return False
            
            # Log message size if it's a profile update
            if message_dict.get('type') == 'update_profile':
                print(f"Sending profile update...")
                if 'profile_pic' in message_dict:
                    pic_size = len(message_dict['profile_pic']) if message_dict['profile_pic'] else 0
                    print(f"Profile picture data size: {pic_size} bytes")
            
            # Convert to JSON and encode
            json_str = json.dumps(message_dict)
            message_bytes = json_str.encode()
            
            # First send the message length
            message_length = len(message_bytes)
            length_header = str(message_length).zfill(10).encode()
            self.socket.send(length_header)
            
            # Then send the actual message in chunks
            chunk_size = 8192
            for i in range(0, len(message_bytes), chunk_size):
                chunk = message_bytes[i:i + chunk_size]
                self.socket.send(chunk)
            
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            self.connected = False
            self.connection_status.emit(False)
            return False

    def send_message(self):
        if not self.current_room:
            print("No room selected")
            return
            
        message_text = self.message_input.text().strip()
        if not message_text:
            return
            
        print(f"Sending message in room {self.current_room}: {message_text}")
        message = {
            'type': 'message',
            'room_id': self.current_room,
            'content': message_text
        }
        if self.send_to_server(message):
            self.message_input.clear()
            # Remove local message display - server will broadcast it back
        else:
            QMessageBox.warning(self, 'Error', 'Failed to send message')

    def create_room_dialog(self):
        if not self.connected or not self.username:
            QMessageBox.warning(self, 'Error', 'Please login first')
            return
            
        try:
            dialog = CreateRoomDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                room_data = dialog.get_room_data()
                if room_data['room_name']:
                    print(f"Creating room: {room_data}")
                    self.send_to_server({
                        'type': 'create_room',
                        **room_data
                    })
                else:
                    QMessageBox.warning(self, 'Error', 'Room name is required')
        except Exception as e:
            print(f"Error in create_room_dialog: {e}")
            QMessageBox.critical(self, 'Error', 
                               f'Error creating room: {str(e)}')

    def show_login_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Login')
        layout = QVBoxLayout(dialog)
        
        username_input = QLineEdit()
        username_input.setPlaceholderText('Username')
        layout.addWidget(username_input)
        
        password_input = QLineEdit()
        password_input.setPlaceholderText('Password')
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_input)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.login(username_input.text(), password_input.text())

    def login(self, username, password):
        if not self.connected and not self.connect_to_server():
            return
            
        message = {
            'type': 'login',
            'username': username,
            'password': password
        }
        self.send_to_server(message)

    def show_register_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Register')
        layout = QVBoxLayout(dialog)
        
        username_input = QLineEdit()
        username_input.setPlaceholderText('Username')
        layout.addWidget(username_input)
        
        password_input = QLineEdit()
        password_input.setPlaceholderText('Password')
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_input)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.register(username_input.text(), password_input.text())

    def register(self, username, password):
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Username and password are required')
            return
            
        if not self.connected and not self.connect_to_server():
            return
            
        try:
            print(f"Attempting to register user: {username}")
            message = {
                'type': 'register',
                'username': username,
                'password': password
            }
            if not self.send_to_server(message):
                QMessageBox.critical(self, 'Error', 'Failed to send registration request')
        except Exception as e:
            print(f"Error sending registration request: {e}")
            QMessageBox.critical(self, 'Error', 
                               f'Failed to send registration request: {str(e)}')

    def update_rooms(self, rooms):
        print(f"Updating rooms list with {len(rooms)} rooms")  # Add debug logging
        self.rooms_list.clear()
        for room in rooms:
            print(f"Processing room: {room}")  # Add debug logging
            # For private rooms, don't show user count
            if room['type'] == 'private':
                item = QListWidgetItem(f"{room['name']} (Private)")
            else:
                item = QListWidgetItem(f"{room['name']} ({room.get('user_count', 0)} users)")
            # Store full room info in item data
            item.setData(Qt.ItemDataRole.UserRole, room)
            if room['type'] == 'private':
                item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
            self.rooms_list.addItem(item)
        print(f"Room list updated, now has {self.rooms_list.count()} items")  # Add debug logging

    def update_online_users(self, users):
        self.users_list.clear()
        for username in users:
            self.users_list.addItem(username)

    def display_message(self, username, content, text_color='#000000'):
        message = f'<span style="color: {text_color}">{username}: {content}</span>'
        self.chat_display.append(message)

    def room_selected(self, item):
        room_data = item.data(Qt.ItemDataRole.UserRole)
        room_id = room_data['id']  # Get room_id from the room data dictionary
        if room_id != self.current_room:
            self.current_room = room_id
            self.chat_display.clear()  # Clear previous chat messages
            
            # Check if room is private and prompt for password
            message = {
                'type': 'join_room',
                'room_id': room_id
            }
            
            if room_data['type'] == 'private':
                password, ok = QInputDialog.getText(
                    self, 'Private Room',
                    'Enter room password:',
                    QLineEdit.EchoMode.Password
                )
                if not ok:
                    self.current_room = None
                    return
                message['password'] = password
            
            if self.send_to_server(message):
                # Enable message input when room is selected
                self.message_input.setEnabled(True)
                print(f"Joined room {room_id}")
            else:
                self.current_room = None
                self.message_input.setEnabled(False)
                print("Failed to join room")

    def show_my_profile(self):
        if not self.username:
            QMessageBox.warning(self, 'Error', 'Please login first')
            return

        try:
            dialog = UserProfileDialog(self.username, True, self)
            # Request current profile data
            self.send_to_server({
                'type': 'get_profile',
                'username': self.username
            })
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Send updated profile to server
                profile_data = {
                    'type': 'update_profile',
                    'bio': dialog.bio_edit.toPlainText(),
                    'pronouns': dialog.pronouns_edit.text(),
                    'text_color': dialog.text_color,
                }
                
                if not self.send_to_server(profile_data):
                    raise Exception("Failed to send profile update")
                    
        except Exception as e:
            print(f"Error showing profile: {e}")
            QMessageBox.critical(self, 'Error', f'Failed to show profile: {str(e)}')

    def show_user_profile(self, username):
        try:
            dialog = UserProfileDialog(username, False, self)
            # Request user profile data from server
            self.send_to_server({
                'type': 'get_profile',
                'username': username
            })
            dialog.exec()
        except Exception as e:
            print(f"Error showing user profile: {e}")
            QMessageBox.critical(self, 'Error', f'Failed to show user profile: {str(e)}')

    def user_clicked(self, item):
        username = item.text()
        if username != self.username:
            self.show_user_profile(username)

    def show_room_management(self):
        if not self.current_room:
            QMessageBox.warning(self, 'Error', 'Please select a room first')
            return

        # Find room info from rooms list
        for i in range(self.rooms_list.count()):
            item = self.rooms_list.item(i)
            room_data = item.data(Qt.ItemDataRole.UserRole)
            if room_data['id'] == self.current_room:
                dialog = RoomManagementDialog(self.current_room, room_data, self.username, self)
                dialog.exec()
                break

if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = ChatClient()
    client.show()
    sys.exit(app.exec()) 