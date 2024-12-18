# Python Chat Application

A feature-rich chat application built with Python, PyQt6, and SQLite. Supports multiple chat rooms, private messaging, user profiles, and more.

## Features

- User authentication (login/register)
- Public and private chat rooms
- Room management (create, join, moderate)
- User profiles with customizable text colors
- Friend system
- Real-time online user tracking
- Room moderation tools (ban users, add moderators)

## Requirements

- Python 3.8+
- PyQt6
- SQLite3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/chatroom.git
cd chatroom
```

2. Install dependencies:
```bash
pip install PyQt6
```

3. Run the server:
```bash
python server/server.py
```

4. Run the client:
```bash
python client/client.py
```

Or use the executable version (Windows only):
- Run `ChatClient.exe` from the `dist` folder

## Project Structure

```
chatroom/
├── client/
│   └── client.py
├── server/
│   ├── server.py
│   └── database.py
├── dist/
│   └── ChatClient.exe
└── README.md
```

## Usage

1. Start the server first
2. Launch the client application
3. Register a new account or login
4. Create or join chat rooms
5. Start chatting!

## Features in Detail

### Chat Rooms
- Create public or private rooms
- Password protection for private rooms
- Room moderation tools
- Auto-deletion of empty rooms

### User Profiles
- Customizable bio
- Pronouns
- Custom text colors
- Online status tracking

### Friend System
- Send friend requests
- Accept/reject requests
- See online status of friends

## Building the Executable

To build the executable version:

```bash
pip install pyinstaller
pyinstaller client.spec
```

The executable will be created in the `dist` folder.

## License
