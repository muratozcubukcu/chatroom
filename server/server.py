import socket
import threading
import json
from database import Database
import pickle

class ChatServer:
    def __init__(self, host='10.0.0.38', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        
        self.db = Database()
        self.clients = {}  # {client_socket: username}
        self.rooms = {}    # {room_id: set(usernames)}
        
        # Initialize rooms from database
        db_rooms = self.db.get_rooms(include_private=True)
        for room in db_rooms:
            room_id = room[0]  # First element is room_id
            self.rooms[room_id] = set()  # Initialize with empty set of users
        
        print(f"Server running on {host}:{port}")
        print(f"Loaded {len(self.rooms)} rooms from database")

    def broadcast_room_state(self):
        try:
            # Get room names from database
            db_rooms = self.db.get_rooms(include_private=True)
            print(f"Broadcasting rooms: Found {len(db_rooms)} rooms in database")
            room_info = []  # Change to list instead of dict
            for room in db_rooms:
                room_id, room_name, creator, room_type, description = room
                # Make sure room exists in self.rooms
                if room_id not in self.rooms:
                    self.rooms[room_id] = set()
                moderators = self.db.get_room_moderators(room_id)
                room_data = {
                    'id': room_id,
                    'name': room_name,
                    'creator': creator,
                    'type': room_type,
                    'description': description,
                    'moderators': moderators,
                    'user_count': len(self.rooms.get(room_id, set()))
                }
                room_info.append(room_data)
            
            room_state = {
                'type': 'room_state',
                'rooms': room_info
            }
            print(f"Broadcasting room state: {json.dumps(room_state)}")
            self.broadcast_message(room_state)  # Send as dict, not JSON string
        except Exception as e:
            print(f"Error broadcasting room state: {e}")

    def broadcast_online_users(self):
        online_users = {
            'type': 'online_users',
            'users': list(self.clients.values())
        }
        # Send as dict, not JSON string
        self.broadcast_message(online_users)

    def send_to_client(self, client_socket, message_dict):
        try:
            # Convert message to JSON string
            json_str = json.dumps(message_dict)
            message_bytes = json_str.encode()
            
            # First send the message length
            message_length = len(message_bytes)
            length_header = str(message_length).zfill(10).encode()  # Fixed 10-byte length header
            client_socket.send(length_header)
            
            # Then send the actual message in chunks
            chunk_size = 8192
            for i in range(0, len(message_bytes), chunk_size):
                chunk = message_bytes[i:i + chunk_size]
                client_socket.send(chunk)
                
            return True
        except Exception as e:
            print(f"Error sending message to client: {e}")
            return False

    def broadcast_message(self, message, room_id=None):
        if room_id:
            # Send to specific room
            room_clients = [client for client, username in self.clients.items()
                          if username in self.rooms.get(room_id, set())]
            for client in room_clients:
                try:
                    self.send_to_client(client, message)
                except:
                    self.remove_client(client)
        else:
            # Send to all clients
            for client in list(self.clients.keys()):
                try:
                    self.send_to_client(client, message)
                except:
                    self.remove_client(client)

    def handle_client(self, client_socket, addr):
        while True:
            try:
                # First receive the message length
                length_header = client_socket.recv(10)
                if not length_header:
                    print(f"Client {addr} disconnected")
                    break
                
                message_length = int(length_header.decode().strip())
                
                # Initialize buffer for receiving data
                data_buffer = bytearray()
                bytes_received = 0
                
                # Receive the full message
                while bytes_received < message_length:
                    chunk_size = min(8192, message_length - bytes_received)
                    chunk = client_socket.recv(chunk_size)
                    if not chunk:
                        raise ConnectionError("Connection closed while receiving message")
                    data_buffer.extend(chunk)
                    bytes_received += len(chunk)
                
                # Decode and parse the complete message
                message = data_buffer.decode()
                data = json.loads(message)
                
                # Log the received data for debugging
                print(f"Received message type: {data.get('type')}")
                if data.get('type') == 'update_profile':
                    print(f"Profile update received for user: {self.clients.get(client_socket)}")
                    if 'profile_pic' in data:
                        pic_length = len(data['profile_pic']) if data['profile_pic'] else 0
                        print(f"Profile picture data length: {pic_length}")
                
                # Handle different message types
                if data['type'] == 'login':
                    if self.db.verify_user(data['username'], data['password']):
                        self.clients[client_socket] = data['username']
                        self.db.update_user_status(data['username'], True)
                        self.send_to_client(client_socket, {
                            'type': 'login_response',
                            'success': True,
                            'username': data['username']
                        })
                        self.broadcast_online_users()
                        self.broadcast_room_state()  # Broadcast rooms after successful login
                        print(f"User {data['username']} logged in, broadcasting room state")
                    else:
                        self.send_to_client(client_socket, {
                            'type': 'login_response',
                            'success': False
                        })

                elif data['type'] == 'update_profile':
                    if client_socket in self.clients:
                        try:
                            username = self.clients[client_socket]
                            print(f"Processing profile update for {username}")
                            
                            # Update the profile
                            self.db.update_user_profile(
                                username,
                                bio=data.get('bio', ''),
                                pronouns=data.get('pronouns', ''),
                                text_color=data.get('text_color', '#000000')
                            )
                            
                            # Notify client of successful update
                            response = {
                                'type': 'profile_updated',
                                'success': True
                            }
                            self.send_to_client(client_socket, response)
                            print(f"Profile updated successfully for {username}")
                            
                        except Exception as e:
                            print(f"Error updating profile: {e}")
                            error_response = {
                                'type': 'profile_updated',
                                'success': False,
                                'message': str(e)
                            }
                            self.send_to_client(client_socket, error_response)
                    else:
                        print("Client not found in connected clients")

                elif data['type'] == 'register':
                    try:
                        success = self.db.add_user(data['username'], data['password'])
                        self.send_to_client(client_socket, {
                            'type': 'register_response',
                            'success': success,
                            'message': 'Registration successful' if success else 'Username already exists'
                        })
                        print(f"Registration {'successful' if success else 'failed'} for {data['username']}")
                    except Exception as e:
                        print(f"Registration error: {e}")
                        self.send_to_client(client_socket, {
                            'type': 'register_response',
                            'success': False,
                            'message': f'Registration failed: {str(e)}'
                        })

                elif data['type'] == 'create_room':
                    try:
                        if client_socket not in self.clients:
                            self.send_to_client(client_socket, {
                                'type': 'error',
                                'message': 'Must be logged in to create rooms'
                            })
                            continue

                        username = self.clients[client_socket]
                        room_id = self.db.create_room(
                            data['room_name'],
                            username,
                            room_type=data.get('room_type', 'public'),
                            password=data.get('password'),
                            description=data.get('description')
                        )
                        self.rooms[room_id] = set([username])
                        
                        # Send confirmation to the client
                        self.send_to_client(client_socket, {
                            'type': 'room_created',
                            'room_id': room_id,
                            'room_name': data['room_name']
                        })
                        
                        # Broadcast updated room state to all clients
                        self.broadcast_room_state()
                        print(f"Room created: {data['room_name']} by {username}")
                    except Exception as e:
                        print(f"Error creating room: {e}")
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': f'Failed to create room: {str(e)}'
                        })

                elif data['type'] == 'join_room':
                    room_id = data['room_id']
                    username = self.clients[client_socket]
                    password = data.get('password')

                    # Verify access
                    can_join, error_message = self.db.verify_room_access(room_id, username, password)
                    if not can_join:
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': error_message
                        })
                        continue

                    # Remove user from other rooms
                    for room_users in self.rooms.values():
                        room_users.discard(username)
                    # Add to new room
                    if room_id not in self.rooms:
                        self.rooms[room_id] = set()
                    self.rooms[room_id].add(username)
                    # Broadcast updated room state
                    self.broadcast_room_state()
                    print(f"User {username} joined room {room_id}")

                elif data['type'] == 'add_moderator':
                    room_id = data['room_id']
                    target_user = data['username']
                    username = self.clients[client_socket]
                    success, message = self.db.add_room_moderator(room_id, target_user, username)
                    if success:
                        self.broadcast_room_state()
                        self.send_to_client(client_socket, {
                            'type': 'success',
                            'message': f'Added {target_user} as moderator'
                        })
                    else:
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': message
                        })

                elif data['type'] == 'ban_user':
                    room_id = data['room_id']
                    target_user = data['username']
                    username = self.clients[client_socket]
                    reason = data.get('reason')
                    success, message = self.db.ban_user(room_id, target_user, username, reason)
                    if success:
                        # Remove user from room if they're in it
                        if room_id in self.rooms:
                            self.rooms[room_id].discard(target_user)
                            self.broadcast_room_state()
                        # Notify the banned user
                        for client, name in self.clients.items():
                            if name == target_user:
                                self.send_to_client(client, {
                                    'type': 'banned',
                                    'room_id': room_id,
                                    'reason': reason
                                })
                                break
                        self.send_to_client(client_socket, {
                            'type': 'success',
                            'message': f'Banned {target_user} from room'
                        })
                    else:
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': message
                        })

                elif data['type'] == 'send_friend_request':
                    from_user = self.clients[client_socket]
                    to_user = data['username']
                    
                    # Check if user exists
                    if not self.db.user_exists(to_user):
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': f'User {to_user} does not exist'
                        })
                        continue
                        
                    success, message = self.db.send_friend_request(from_user, to_user)
                    if success:
                        # Notify the recipient if they're online
                        for client, name in self.clients.items():
                            if name == to_user:
                                self.send_to_client(client, {
                                    'type': 'friend_request',
                                    'from_user': from_user
                                })
                                break
                        self.send_to_client(client_socket, {
                            'type': 'success',
                            'message': f'Friend request sent to {to_user}'
                        })
                    else:
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': message
                        })

                elif data['type'] == 'accept_friend_request':
                    to_user = self.clients[client_socket]
                    from_user = data['username']
                    if self.db.accept_friend_request(from_user, to_user):
                        # Notify both users
                        self.send_to_client(client_socket, {
                            'type': 'friend_added',
                            'username': from_user
                        })
                        for client, name in self.clients.items():
                            if name == from_user:
                                self.send_to_client(client, {
                                    'type': 'friend_added',
                                    'username': to_user
                                })
                                break
                    else:
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': 'Could not accept friend request'
                        })

                elif data['type'] == 'get_friends':
                    username = self.clients[client_socket]
                    try:
                        friends = self.db.get_friends(username)
                        # Convert friends to list of [username, status] pairs
                        friend_list = []
                        for friend in friends:
                            status = 'online' if friend in self.clients.values() else 'offline'
                            friend_list.append([friend, status])
                        self.send_to_client(client_socket, {
                            'type': 'friends_list',
                            'friends': friend_list
                        })
                    except Exception as e:
                        print(f"Error getting friends list: {e}")
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': 'Failed to get friends list'
                        })

                elif data['type'] == 'get_profile':
                    target_username = data['username']
                    try:
                        print(f"Getting profile data for user: {target_username}")
                        profile = self.db.get_user_profile(target_username)
                        if profile:
                            bio, pronouns, text_color = profile
                            response = {
                                'type': 'profile_data',
                                'username': target_username,
                                'bio': bio or '',
                                'pronouns': pronouns or '',
                                'text_color': text_color or '#000000'
                            }
                        else:
                            print(f"No profile found for user: {target_username}")
                            response = {
                                'type': 'profile_data',
                                'username': target_username,
                                'bio': '',
                                'pronouns': '',
                                'text_color': '#000000'
                            }
                        print("Sending profile data response")
                        self.send_to_client(client_socket, response)
                        print(f"Sent profile data for user: {target_username}")
                    except Exception as e:
                        print(f"Error getting profile: {e}")
                        self.send_to_client(client_socket, {
                            'type': 'error',
                            'message': 'Failed to get user profile'
                        })

                elif data['type'] == 'message':
                    if client_socket in self.clients:
                        username = self.clients[client_socket]
                        room_id = data['room_id']
                        content = data['content'].strip()
                        
                        if not content:
                            continue
                            
                        if room_id in self.rooms and username in self.rooms[room_id]:
                            # Get user's text color
                            profile = self.db.get_user_profile(username)
                            text_color = profile[2] if profile else '#000000'
                            
                            message = {
                                'type': 'message',
                                'room_id': room_id,
                                'username': username,
                                'content': content,
                                'text_color': text_color
                            }
                            print(f"Broadcasting message from {username} in room {room_id}: {content}")
                            self.broadcast_message(message, room_id)  # Send as dict, not JSON string
                        else:
                            print(f"User {username} not in room {room_id}")
                            self.send_to_client(client_socket, {
                                'type': 'error',
                                'message': 'You are not in this room'
                            })

            except json.JSONDecodeError as e:
                print(f"JSON decode error from {addr}: {e}")
                continue
            except Exception as e:
                print(f"Error handling client {addr}: {e}")
                break

        self.remove_client(client_socket)

    def remove_empty_rooms(self):
        try:
            # Get all rooms from database
            db_rooms = self.db.get_rooms(include_private=True)
            for room in db_rooms:
                room_id = room[0]
                # Check if room exists in memory and has zero users
                if room_id in self.rooms and len(self.rooms[room_id]) == 0:
                    print(f"Deleting empty room {room_id}")
                    # Delete room from database
                    self.db.delete_room(room_id)
                    # Remove from memory
                    del self.rooms[room_id]
            
            # Broadcast updated room state to all clients
            if self.rooms:  # Only broadcast if there are rooms
                self.broadcast_room_state()
        except Exception as e:
            print(f"Error removing empty rooms: {e}")

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]
            self.db.update_user_status(username, False)
            del self.clients[client_socket]
            # Remove user from all rooms
            for room_users in self.rooms.values():
                room_users.discard(username)
            self.broadcast_online_users()
            self.remove_empty_rooms()  # Check for empty rooms after user leaves
            self.broadcast_room_state()  # Update room state to reflect user counts
        client_socket.close()

    def run(self):
        print("Server starting...")
        try:
            while True:
                print("Waiting for connections...")
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr}")
                thread = threading.Thread(target=self.handle_client,
                                       args=(client_socket, addr))
                thread.start()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.server_socket.close()
            print("Server shutdown")

if __name__ == "__main__":
    try:
        server = ChatServer()
        print("Server initialized successfully")
        server.run()
    except Exception as e:
        print(f"Failed to start server: {e}") 