import sqlite3
import threading
from datetime import datetime
import base64

class Database:
    _instance = None
    _lock = threading.Lock()
    _local = threading.local()

    def __init__(self):
        # Initialize thread-local storage
        self._local.conn = None
        # Create tables when database is initialized
        self.create_tables()

    @property
    def conn(self):
        # Get or create connection for current thread
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect('chatroom.db')
            # Enable foreign key support
            self._local.conn.execute('PRAGMA foreign_keys = ON')
        return self._local.conn

    def create_tables(self):
        with self._lock:
            cursor = self.conn.cursor()
            
            # Users table with new columns
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                text_color TEXT DEFAULT '#000000',
                last_login DATETIME,
                is_online BOOLEAN DEFAULT 0,
                user_role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'online',
                bio TEXT,
                pronouns TEXT
            )
            ''')

            # Rooms table with new features
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name TEXT NOT NULL,
                creator TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                room_type TEXT DEFAULT 'public',
                password TEXT,
                description TEXT,
                is_archived BOOLEAN DEFAULT 0,
                FOREIGN KEY (creator) REFERENCES users (username)
            )
            ''')

            # Room moderators table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_moderators (
                room_id INTEGER,
                username TEXT,
                PRIMARY KEY (room_id, username),
                FOREIGN KEY (room_id) REFERENCES rooms (room_id),
                FOREIGN KEY (username) REFERENCES users (username)
            )
            ''')

            # Banned users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                room_id INTEGER,
                username TEXT,
                banned_by TEXT,
                banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                PRIMARY KEY (room_id, username),
                FOREIGN KEY (room_id) REFERENCES rooms (room_id),
                FOREIGN KEY (username) REFERENCES users (username),
                FOREIGN KEY (banned_by) REFERENCES users (username)
            )
            ''')

            # Friends table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                user1 TEXT,
                user2 TEXT,
                status TEXT DEFAULT 'pending',
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user1, user2),
                FOREIGN KEY (user1) REFERENCES users (username),
                FOREIGN KEY (user2) REFERENCES users (username)
            )
            ''')

            self.conn.commit()

    def add_user(self, username, password):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                             (username, password))
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def verify_user(self, username, password):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            return result and result[0] == password

    def update_user_status(self, username, is_online):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE users 
            SET is_online = ?, last_login = ? 
            WHERE username = ?
            ''', (is_online, datetime.now(), username))
            self.conn.commit()

    def update_profile(self, username, profile_pic=None, text_color=None):
        with self._lock:
            cursor = self.conn.cursor()
            if profile_pic:
                cursor.execute('UPDATE users SET profile_pic = ? WHERE username = ?',
                             (profile_pic, username))
            if text_color:
                cursor.execute('UPDATE users SET text_color = ? WHERE username = ?',
                             (text_color, username))
            self.conn.commit()

    def create_room(self, room_name, creator, room_type='public', password=None, description=None):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO rooms (room_name, creator, room_type, password, description)
            VALUES (?, ?, ?, ?, ?)
            ''', (room_name, creator, room_type, password, description))
            room_id = cursor.lastrowid
            # Make creator a moderator
            cursor.execute('INSERT INTO room_moderators (room_id, username) VALUES (?, ?)',
                         (room_id, creator))
            self.conn.commit()
            return room_id

    def get_rooms(self, include_private=False):
        with self._lock:
            cursor = self.conn.cursor()
            # Always get all rooms, both public and private
            cursor.execute('''
            SELECT room_id, room_name, creator, room_type, description 
            FROM rooms WHERE is_archived = 0
            ''')
            return cursor.fetchall()

    def verify_room_access(self, room_id, username, password=None):
        with self._lock:
            cursor = self.conn.cursor()
            # Check if user is banned
            cursor.execute('SELECT 1 FROM banned_users WHERE room_id = ? AND username = ?',
                         (room_id, username))
            if cursor.fetchone():
                return False, "You are banned from this room"

            # Get room info
            cursor.execute('SELECT room_type, password FROM rooms WHERE room_id = ?', (room_id,))
            room = cursor.fetchone()
            if not room:
                return False, "Room does not exist"

            room_type, room_password = room
            if room_type == 'public':
                return True, None
            elif room_type == 'private' and room_password:
                if password == room_password:
                    return True, None
                return False, "Incorrect password"
            return False, "Access denied"

    def add_room_moderator(self, room_id, username, added_by):
        with self._lock:
            cursor = self.conn.cursor()
            # Check if added_by is creator or moderator
            cursor.execute('''
            SELECT 1 FROM rooms WHERE room_id = ? AND creator = ?
            UNION
            SELECT 1 FROM room_moderators WHERE room_id = ? AND username = ?
            ''', (room_id, added_by, room_id, added_by))
            if not cursor.fetchone():
                return False, "No permission to add moderators"
            
            try:
                cursor.execute('INSERT INTO room_moderators (room_id, username) VALUES (?, ?)',
                             (room_id, username))
                self.conn.commit()
                return True, None
            except sqlite3.IntegrityError:
                return False, "User is already a moderator"

    def ban_user(self, room_id, username, banned_by, reason=None):
        with self._lock:
            cursor = self.conn.cursor()
            # Check if banned_by is creator or moderator
            cursor.execute('''
            SELECT 1 FROM rooms WHERE room_id = ? AND creator = ?
            UNION
            SELECT 1 FROM room_moderators WHERE room_id = ? AND username = ?
            ''', (room_id, banned_by, room_id, banned_by))
            if not cursor.fetchone():
                return False, "No permission to ban users"
            
            try:
                cursor.execute('''
                INSERT INTO banned_users (room_id, username, banned_by, reason)
                VALUES (?, ?, ?, ?)
                ''', (room_id, username, banned_by, reason))
                self.conn.commit()
                return True, None
            except sqlite3.IntegrityError:
                return False, "User is already banned"

    def send_friend_request(self, from_user, to_user):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                INSERT INTO friends (user1, user2, status)
                VALUES (?, ?, 'pending')
                ''', (from_user, to_user))
                self.conn.commit()
                return True, None
            except sqlite3.IntegrityError:
                return False, "Friend request already exists"

    def accept_friend_request(self, from_user, to_user):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE friends SET status = 'accepted'
            WHERE user1 = ? AND user2 = ? AND status = 'pending'
            ''', (from_user, to_user))
            self.conn.commit()
            return cursor.rowcount > 0

    def get_friends(self, username):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT user2, status FROM friends WHERE user1 = ?
            UNION
            SELECT user1, status FROM friends WHERE user2 = ?
            ''', (username, username))
            return cursor.fetchall()

    def get_room_moderators(self, room_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT username FROM room_moderators WHERE room_id = ?', (room_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_online_users(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT username FROM users WHERE is_online = 1')
            return [user[0] for user in cursor.fetchall()]

    def delete_room(self, room_id):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                # Delete related records first
                cursor.execute('DELETE FROM room_moderators WHERE room_id = ?', (room_id,))
                cursor.execute('DELETE FROM banned_users WHERE room_id = ?', (room_id,))
                # Finally delete the room
                cursor.execute('DELETE FROM rooms WHERE room_id = ?', (room_id,))
                self.conn.commit()
            except Exception as e:
                print(f"Error deleting room {room_id}: {e}")
                self.conn.rollback()

    def update_user_profile(self, username, bio=None, pronouns=None, text_color=None):
        with self._lock:
            cursor = self.conn.cursor()
            updates = []
            params = []
            
            if bio is not None:
                updates.append('bio = ?')
                params.append(bio)
            if pronouns is not None:
                updates.append('pronouns = ?')
                params.append(pronouns)
            if text_color is not None:
                updates.append('text_color = ?')
                params.append(text_color)
                
            if updates:
                params.append(username)
                query = f'''
                UPDATE users 
                SET {', '.join(updates)}
                WHERE username = ?
                '''
                cursor.execute(query, params)
                self.conn.commit()

    def get_user_profile(self, username):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT bio, pronouns, text_color
            FROM users
            WHERE username = ?
            ''', (username,))
            result = cursor.fetchone()
            if result:
                bio, pronouns, text_color = result
                return bio, pronouns, text_color
            return None

    def __del__(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close() 