# VibePlayer - User Guide

A feature-rich, browser-based video course player with progress tracking, subtitle support, and an elegant dark theme interface.

---

## ✨ Features

### 🎥 Video Playback
- Custom video player with full controls
- Play/Pause, Previous/Next navigation
- Volume control with slider
- Progress bar with seek functionality
- Playback speed control (0.25x - 2x)
- Fullscreen mode with auto-hide controls

### 📝 Subtitle Support
- Automatic subtitle detection (.srt, .vtt files)
- Toggle subtitles on/off
- Load custom subtitle files
- SRT to VTT conversion (server-side and client-side)

### 📊 Progress Tracking
- **Server-side persistence** using `progress.json`
- Mark videos as watched (automatically or manually)
- Toggle watched status via checkmarks
- Section-level progress indicators (X/Y videos)
- Global completion percentage badge
- Green highlighting for completed sections
- Reset progress functionality

### 🔄 Resume Playback
- Auto-save current video position
- Resume from last watched position on reload
- Periodic saves (every 30 seconds while playing)
- Save on pause and tab close

### 📁 Resource Management
- Detect and display course resources (PDFs, documents)
- Organized by video
- Click to open in new tab

### 🎨 User Interface
- Modern dark theme (VS Code inspired)
- Resizable sidebar (200-600px)
- Collapsible sections
- Active video highlighting
- Keyboard shortcuts
- Responsive design

---

## 📋 Requirements

- **Python 3.x** (Python 3.6 or higher recommended)
- **Web Browser** (Chrome, Firefox, Edge, Safari)
- **Video Files** organized in folders

### No Additional Python Packages Required!
The script uses only Python standard library:
- `http.server` - Web server
- `socketserver` - Server handling
- `json` - Progress data storage
- `os`, `pathlib` - File system operations
- `re` - Regular expressions
- `urllib.parse` - URL handling

---

## 📂 Folder Structure

Organize your course content like this:

```
Your-Course-Folder/
├── course_player.py          # The script
├── progress.json             # Auto-generated (progress data)
├── index.html               # Auto-generated (player interface)
├── 01-Introduction/
│   ├── 01-Welcome.mp4
│   ├── 01-Welcome.srt       # Optional subtitle
│   ├── 02-Setup.mp4
│   └── resources/           # Optional resources folder
│       └── setup-guide.pdf
├── 02-Module-2/
│   ├── 01-Lesson.mp4
│   ├── 01-Lesson.vtt
│   └── 02-Practice.mp4
└── 03-Module-3/
    └── 01-Final.mp4
```

### Naming Conventions
- **Sections/Folders**: Name your folders in order (01-, 02-, 03- or just natural names)
- **Videos**: Any name works, natural sorting is applied
- **Subtitles**: Same name as video with `.srt` or `.vtt` extension
  - Example: `lesson.mp4` → `lesson.srt`
- **Resources**: Place in a `resources/` subfolder within each section

### Supported Formats
- **Video**: `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`
- **Subtitles**: `.srt`, `.vtt`
- **Resources**: `.pdf`, `.docx`, `.txt`, `.zip`, etc.

---

## 🚀 How to Use

### Step 1: Place the Script
Copy `course_player.py` into your course folder (the folder containing all video sections).

```bash
cd "/path/to/your/course/folder"
```

### Step 2: Run the Script
```bash
python3 course_player.py
```

### Step 3: Open in Browser
The script will:
1. Scan for videos and subtitles
2. Generate the HTML interface
3. Start a web server on port 8000
4. Display: `🌐 URL: http://localhost:8000`

Open your browser and navigate to:
```
http://localhost:8000
```

### Step 4: Start Learning!
- Click any video in the sidebar to start
- Videos are organized by section
- Your progress is automatically saved

---

## 🎮 Controls & Shortcuts

### Video Controls
| Action | Method |
|--------|--------|
| Play/Pause | Click video or spacebar |
| Seek | Click progress bar or drag |
| Volume | Click volume icon or use slider |
| Fullscreen | Click fullscreen button or double-click video |
| Next Video | Click ▶ button or End key |
| Previous Video | Click ◀ button or Home key |

### Playback Speed
Click the ⚙️ (Settings) button to change speed:
- 0.25x, 0.5x, 0.75x
- **1x (Normal)**
- 1.25x, 1.5x, 1.75x, 2x

### Subtitles
Click the 🗨️ (CC) button:
- **Toggle On/Off** - Show/hide subtitles
- **📂 Load Subtitle...** - Load custom subtitle file

### Keyboard Shortcuts
- **Space** - Play/Pause
- **Left Arrow** - Rewind 5 seconds
- **Right Arrow** - Forward 5 seconds
- **F** - Toggle fullscreen
- **M** - Mute/Unmute

---

## 📊 Progress Tracking Features

### Automatic Tracking
Videos are automatically marked as watched when:
- ✅ Video plays to the end
- ✅ You click the "Next" button

### Manual Toggle
- Click the **checkmark (✓)** next to any video to toggle its watched status
- Green checkmark = watched
- Gray circle = not watched

### Section Progress
Each section header shows:
- **In Progress**: `3/5` (gray badge)
- **Completed**: `✓ 5/5` (green badge, green header)

### Global Progress
The blue badge at the top shows overall completion:
- **📈 45% Complete** (updates in real-time)

### Reset Progress
Click the **🔄 Reset** button to clear all progress.
- Confirmation dialog will appear
- Clears watched status for all videos
- Resets resume position

---

## 🔄 Resume Playback

The script saves your position automatically:
- ✅ Every 30 seconds while playing
- ✅ When you pause
- ✅ When you close the tab

**Next time you open the player:**
1. It loads your last video
2. Seeks to your last position
3. Shows a "Resumed at MM:SS" notification

---

## 📁 Resources

If you have PDFs, documents, or other materials:

1. Create a `resources/` folder in each section
2. Place files there
3. Click the **📦 Resources** button (appears when available)
4. Click any resource to open in new tab

---

## ⚙️ Customization

### Change Server Port
Edit line 20 in `course_player.py`:
```python
PORT = 8000  # Change to any available port
```

### Progress File Location
The `progress.json` file is created automatically in the same folder as the script.

**Format:**
```json
{
  "watched": [
    "01-Introduction/01-Welcome.mp4",
    "01-Introduction/02-Setup.mp4"
  ],
  "resume": {
    "video": "02-Module/01-Lesson.mp4",
    "time": 120.5
  }
}
```

---

## 🛠️ Troubleshooting

### Problem: "Address already in use" error
**Solution:** Another instance is running. Stop it:
```bash
pkill -f "python3.*course_player"
# Then run again
python3 course_player.py
```

### Problem: No videos appear
**Possible causes:**
1. ✅ Videos not in correct format (.mp4, .mkv, .webm, .avi, .mov)
2. ✅ Script not run from the correct folder
3. ✅ Check terminal output for "Found X videos"

**Solution:**
```bash
# Make sure you're in the course folder
cd "/path/to/course/folder"
# Check if videos exist
ls -R *.mp4
```

### Problem: Subtitles not loading
**Causes:**
1. ✅ Subtitle file must have same name as video
2. ✅ Must be `.srt` or `.vtt` format

**Example:**
```
✅ Correct:
   lesson.mp4
   lesson.srt

❌ Wrong:
   lesson.mp4
   subtitles.srt
```

### Problem: Can't access from another device
The server runs on `localhost` only by default.

**To allow network access**, edit line 2236:
```python
# Change from:
with socketserver.TCPServer(("", PORT), handler) as httpd:

# To bind to specific IP or all interfaces:
with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
```

Then access via: `http://YOUR-IP:8000`

### Problem: Progress not saving
**Check:**
1. ✅ Write permissions in folder
2. ✅ Check if `progress.json` exists
3. ✅ Browser console for errors (F12)

---

## 🔒 Security Notes

- ⚠️ The server is meant for **local use only**
- ⚠️ Don't expose to the internet without authentication
- ✅ Runs on localhost (127.0.0.1) by default
- ✅ Only serves files from the course directory

---

## 💡 Tips & Best Practices

1. **Organize your folders**: Use numbered prefixes (01-, 02-) for proper ordering
2. **Name videos clearly**: Descriptive names help navigation
3. **Include subtitles**: Improves accessibility and searchability
4. **Backup progress.json**: Copy it to save your progress
5. **Use fullscreen**: Better learning experience with auto-hide controls
6. **Adjust speed**: 1.25x or 1.5x can save time without losing comprehension

---

## 🆘 Support

### Common Questions

**Q: Can I use this for multiple courses?**
A: Yes! Just copy the script to each course folder. Each course has its own `progress.json`.

**Q: Can I share my progress with others?**
A: Yes, share the `progress.json` file. Place it in the course folder before running the script.

**Q: Does this work offline?**
A: Yes! No internet connection needed. Everything runs locally.

**Q: Can I customize the appearance?**
A: Yes! Edit the CSS in the `generate_html()` function (around line 200-800).

**Q: Will it work on mobile?**
A: The interface is responsive, but best experienced on desktop/laptop with keyboard.

---

## 📊 Feature Summary

| Feature | Status |
|---------|--------|
| Video Playback | ✅ Full support |
| Subtitle Support | ✅ Auto-detect + Manual load |
| Progress Tracking | ✅ Server-side persistence |
| Resume Playback | ✅ Auto-save position |
| Section Progress | ✅ Visual indicators |
| Resources Panel | ✅ Auto-detect resources |
| Keyboard Shortcuts | ✅ Full support |
| Fullscreen Mode | ✅ With auto-hide |
| Resizable Sidebar | ✅ 200-600px |
| Dark Theme | ✅ VS Code style |

---

## 🎓 Example Usage Session

```bash
# 1. Navigate to your course folder
cd "~/Courses/Python-Course"

# 2. Start the server
python3 course_player.py

# Output:
# 🔍 Scanning for video files and subtitles...
# 📚 Course: Python-Course
# ✅ Found 45 videos in 8 sections
# 🚀 Starting web server...
# 🌐 URL: http://localhost:8000

# 3. Open browser to http://localhost:8000

# 4. Start learning! Progress auto-saves.

# 5. To stop server: Press Ctrl+C
```

---

## 🎉 Enjoy Your Learning Journey!

This course player is designed to give you a distraction-free, professional learning experience. Focus on the content, and let the player handle the rest!

**Happy Learning! 📚🚀**

