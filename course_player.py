#!/usr/bin/env python3
"""
Course Player - A Local Video Course Platform with Advanced Controls
Recursively scans for video files and creates an interactive LMS-style player.
"""

import os
import json
import re
import http.server
import socketserver
import webbrowser
import threading
from pathlib import Path
from urllib.parse import quote, unquote, parse_qs, urlparse

# Configuration
PORT = 8000
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.webm')
SUBTITLE_EXTENSIONS = ('.srt', '.vtt')
PROGRESS_FILE = 'progress.json'

def natural_sort_key(s):
    """
    Sort strings naturally (e.g., '2' before '10').
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]

def load_progress():
    """
    Load the list of watched video paths from progress.json.
    Returns a list of paths (strings).
    """
    if not os.path.exists(PROGRESS_FILE):
        return []
    
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('watched', [])
    except Exception as e:
        print(f"Error loading progress: {e}")
        return []

def save_progress(video_path):
    """
    Add a video path to the watched list and save to progress.json.
    """
    watched = load_progress()
    
    # Normalize path for comparison
    normalized_path = video_path.replace('\\', '/')
    
    if normalized_path not in watched:
        watched.append(normalized_path)
        
        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'watched': watched}, f, indent=2)
            print(f"✓ Marked as watched: {video_path}")
        except Exception as e:
            print(f"Error saving progress: {e}")

def remove_progress(video_path):
    """
    Remove a video path from the watched list and save to progress.json.
    """
    watched = load_progress()
    
    # Normalize path for comparison
    normalized_path = video_path.replace('\\', '/')
    
    if normalized_path in watched:
        watched.remove(normalized_path)
        
        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'watched': watched}, f, indent=2)
            print(f"✗ Unmarked: {video_path}")
        except Exception as e:
            print(f"Error removing progress: {e}")

def reset_progress():
    """
    Clear all progress by deleting or emptying progress.json.
    """
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'watched': []}, f, indent=2)
        print("🔄 Progress reset")
    except Exception as e:
        print(f"Error resetting progress: {e}")

def find_subtitle_for_video(video_path, dirpath):
    """
    Find matching subtitle file for a video.
    Returns relative path to subtitle or None.
    """
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    for ext in SUBTITLE_EXTENSIONS:
        subtitle_name = video_name + ext
        subtitle_path = os.path.join(dirpath, subtitle_name)
        if os.path.exists(subtitle_path):
            return subtitle_name

    return None

def srt_to_vtt(srt_content):
    """
    Convert SRT subtitle format to WebVTT format.
    """
    # Add WebVTT header
    vtt_content = "WEBVTT\n\n"

    # Replace comma with period in timestamps (SRT uses comma, VTT uses period)
    vtt_content += re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_content)

    return vtt_content

def scan_videos(root_dir):
    """
    Recursively scan for video files and organize by TOP-LEVEL folders only.
    
    GROUPING LOGIC:
    - Each immediate subdirectory of root becomes a Section
    - Files in root are grouped under "General" section
    
    RECURSIVE COLLECTION:
    - Inside each top-level section, recursively find all videos regardless of depth
    
    SMART NAMING (Context Preservation):
    - Video display names include parent folder context (excluding section name)
    - Example: SECTION 10.../Module 2.../1. Security.../Video.mp4
      Display: "Module 2 - 1. Security - Video"
    - Uses " - " as separator
    
    SORTING:
    - Sections sorted naturally
    - Videos within a section sorted by FULL FILE PATH (not just filename)
      This ensures Module 1 videos appear before Module 2 videos
    
    Returns a dictionary with sections and their videos.
    """
    course_structure = {}
    root_path = Path(root_dir)
    
    # First, collect videos from root directory (not in any folder)
    root_videos = []
    root_resources = []
    
    for item in root_path.iterdir():
        if item.is_file():
            filename = item.name
            if filename.lower().endswith(VIDEO_EXTENSIONS):
                # Find matching subtitle
                subtitle = find_subtitle_for_video(filename, root_dir)
                
                root_videos.append({
                    'name': item.stem,  # Remove extension
                    'path': filename,
                    'full_path': filename,  # For sorting
                    'subtitle': subtitle if subtitle else None,
                    'resources': []  # Root videos have no resources
                })
            elif (not filename.lower().endswith(SUBTITLE_EXTENSIONS) and
                  not filename.startswith('.') and
                  filename not in ['index.html', 'progress.json', 'course_player.py']):
                root_resources.append({
                    'name': filename,
                    'path': filename
                })
    
    # Add root videos to "General" section if any exist
    if root_videos:
        root_videos.sort(key=lambda x: natural_sort_key(x['full_path']))
        root_resources.sort(key=lambda x: natural_sort_key(x['name']))
        # Remove full_path before storing
        for vid in root_videos:
            vid.pop('full_path', None)
        course_structure['00-General'] = {
            'path': '.',
            'videos': root_videos
        }
    
    # Get only TOP-LEVEL directories (immediate subdirectories of root)
    top_level_dirs = [d for d in root_path.iterdir() if d.is_dir()]
    top_level_dirs.sort(key=lambda x: natural_sort_key(x.name))
    
    # Process each top-level section
    for top_dir in top_level_dirs:
        section_name = top_dir.name
        section_videos = []
        
        # Recursively walk through this top-level directory and ALL its subfolders
        for dirpath, dirnames, filenames in os.walk(str(top_dir)):
            current_dir = Path(dirpath)
            
            # Get relative path from top-level section folder (excludes section name)
            rel_from_section = current_dir.relative_to(top_dir)
            
            # Get relative path from root (includes section name) - for full path sorting
            rel_from_root = current_dir.relative_to(root_path)
            
            # Find video files in current directory
            video_files = [f for f in filenames if f.lower().endswith(VIDEO_EXTENSIONS)]
            
            if video_files:
                # Find resource files in this directory
                resource_files = []
                for f in filenames:
                    f_lower = f.lower()
                    if (not f_lower.endswith(VIDEO_EXTENSIONS) and
                        not f_lower.endswith(SUBTITLE_EXTENSIONS) and
                        not f.startswith('.') and
                        f != 'index.html'):
                        # Path relative to root
                        resource_rel_path = current_dir.relative_to(root_path) / f
                        resource_files.append({
                            'name': f,
                            'path': str(resource_rel_path).replace('\\', '/')
                        })
                
                resource_files.sort(key=lambda x: natural_sort_key(x['name']))
                
                # Process each video
                for video in video_files:
                    video_stem = Path(video).stem
                    
                    # Build display name with SMART context (parent folders, excluding section name)
                    if str(rel_from_section) != '.':
                        # Get path parts
                        subfolder_parts = str(rel_from_section).replace('\\', '/').split('/')
                        
                        # Smart context extraction: Look for "Module" folders
                        # If we find a folder starting with "Module", only show context from there
                        module_start_idx = None
                        for idx, part in enumerate(subfolder_parts):
                            if part.lower().startswith('module'):
                                module_start_idx = idx
                                break
                        
                        # Use context from Module onwards, or all if no Module found
                        if module_start_idx is not None:
                            context_parts = subfolder_parts[module_start_idx:]
                        else:
                            context_parts = subfolder_parts
                        
                        # Join with " - " separator
                        context_prefix = ' - '.join(context_parts)
                        video_display_name = f"{context_prefix} - {video_stem}"
                    else:
                        # Video is directly in the top-level section folder
                        video_display_name = video_stem
                    
                    # Full path relative to root (for storage and sorting)
                    video_rel_path = rel_from_root / video
                    video_full_path_str = str(video_rel_path).replace('\\', '/')
                    
                    # Find matching subtitle
                    subtitle = find_subtitle_for_video(video, str(current_dir))
                    subtitle_path = None
                    if subtitle:
                        subtitle_rel_path = current_dir.relative_to(root_path) / subtitle
                        subtitle_path = str(subtitle_rel_path).replace('\\', '/')
                    
                    section_videos.append({
                        'name': video_display_name,
                        'path': video_full_path_str,
                        'full_path': video_full_path_str,  # For sorting by full path
                        'subtitle': subtitle_path,
                        'resources': resource_files
                    })
        
        # CRUCIAL: Sort videos by FULL FILE PATH (not just display name)
        # This ensures proper ordering: Module 1 before Module 2, etc.
        section_videos.sort(key=lambda x: natural_sort_key(x['full_path']))
        
        # Remove the temporary full_path field before storing
        for vid in section_videos:
            vid.pop('full_path', None)
        
        # Add section to course structure if it has videos
        if section_videos:
            course_structure[section_name] = {
                'path': str(top_dir.relative_to(root_path)).replace('\\', '/'),
                'videos': section_videos
            }
    
    # Sort sections naturally by section name
    sorted_sections = sorted(course_structure.items(), key=lambda x: natural_sort_key(x[0]))
    return dict(sorted_sections)

def generate_html(course_data, course_name):
    """
    Generate a complete HTML page with embedded CSS and JavaScript.
    """
    # Convert course data to JSON for embedding
    course_json = json.dumps(course_data, indent=2)
    
    # Load watched videos for injection
    watched_videos = load_progress()
    watched_json = json.dumps(watched_videos)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{course_name} - Course Player</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e1e;
            color: #e0e0e0;
            overflow: hidden;
        }}

        .container {{
            display: flex;
            height: 100vh;
        }}

        /* Sidebar Styles */
        .sidebar {{
            min-width: 200px;
            max-width: 600px;
            width: 280px;
            background: #252526;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }}

        .sidebar-header {{
            padding: 20px;
            background: #2d2d30;
            border-bottom: 1px solid #3c3c3c;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .sidebar-header h1 {{
            font-size: 18px;
            color: #fff;
            margin-bottom: 12px;
        }}

        .header-controls {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }}

        .progress-badge {{
            flex: 1;
            background: #007acc;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }}

        .reset-progress-btn {{
            background: #d32f2f;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            white-space: nowrap;
        }}

        .reset-progress-btn:hover {{
            background: #b71c1c;
        }}

        .sections {{
            flex: 1;
            padding: 10px;
        }}

        .section {{
            margin-bottom: 10px;
        }}

        .section-header {{
            padding: 12px 15px;
            background: #2d2d30;
            border-radius: 5px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
            user-select: none;
        }}

        .section-header:hover {{
            background: #37373d;
        }}

        .section-header.active {{
            background: #094771;
        }}

        .section-header.completed {{
            background: #2e7d32;
            color: white;
        }}

        .section-header.completed:hover {{
            background: #388e3c;
        }}

        .section-header.completed .section-title {{
            color: white;
        }}

        .section-title {{
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .section-progress {{
            font-size: 12px;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.1);
        }}

        .section-progress.in-progress {{
            color: #888;
        }}

        .section-progress.completed {{
            color: #4caf50;
            background: rgba(76, 175, 80, 0.2);
        }}

        .section-progress .checkmark {{
            font-size: 14px;
            margin-right: 2px;
        }}

        .section-arrow {{
            transition: transform 0.3s;
            color: #888;
        }}

        .section.expanded .section-arrow {{
            transform: rotate(90deg);
        }}

        .video-list {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}

        .section.expanded .video-list {{
            max-height: 2000px;
        }}

        .video-item {{
            padding: 10px 15px 10px 30px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s, padding-left 0.2s;
            border-left: 3px solid transparent;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}

        .video-item:hover {{
            background: #2d2d30;
            padding-left: 35px;
        }}

        .video-item.active {{
            background: #1e3a52;
            border-left: 3px solid #007acc;
            color: #4fc3f7;
            font-weight: 500;
        }}

        .video-item.watched {{
            opacity: 0.8;
        }}

        .video-item.watched .video-name {{
            text-decoration: line-through;
        }}

        .video-checkmark {{
            width: 18px;
            height: 18px;
            border-radius: 50%;
            border: 2px solid #555;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            flex-shrink: 0;
            transition: all 0.2s;
            cursor: pointer;
        }}

        .video-item.watched .video-checkmark {{
            background: #4caf50;
            border-color: #4caf50;
            color: white;
        }}

        .video-checkmark:hover {{
            border-color: #4caf50;
            transform: scale(1.1);
        }}

        .video-name {{
            flex: 1;
        }}

        /* Resizer Styles */
        .resizer {{
            width: 5px;
            background: #3c3c3c;
            cursor: col-resize;
            flex-shrink: 0;
            transition: background 0.2s;
            position: relative;
        }}

        .resizer:hover {{
            background: #007acc;
        }}

        .resizer::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -2px;
            right: -2px;
            bottom: 0;
        }}

        body.resizing {{
            cursor: col-resize;
            user-select: none;
        }}

        body.resizing * {{
            cursor: col-resize !important;
            user-select: none !important;
        }}

        /* Main Content Styles */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #1e1e1e;
            overflow-y: auto;
            overflow-x: hidden;
        }}

        .video-wrapper {{
            width: 100%;
            background: #000;
            flex-shrink: 0;
        }}

        .video-container {{
            width: 100%;
            aspect-ratio: 16 / 9;
            max-height: 86vh;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #000;
            cursor: pointer;
        }}

        .video-container.fullscreen {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 9999;
        }}

        .video-container.fullscreen.hide-cursor {{
            cursor: none;
        }}

        video {{
            width: 100%;
            height: auto;
            max-height: 100%;
            outline: none;
            display: block;
        }}

        .video-container.fullscreen video {{
            width: 100%;
            height: 100%;
        }}

        /* Welcome Screen */
        .welcome-screen {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: #888;
            pointer-events: none;
        }}

        .welcome-screen svg {{
            width: 100px;
            height: 100px;
            margin-bottom: 20px;
            opacity: 0.5;
        }}

        .welcome-screen h2 {{
            font-size: 24px;
            margin-bottom: 10px;
        }}

        .welcome-screen p {{
            font-size: 16px;
        }}

        /* Custom Video Controls Overlay */
        .video-controls {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.7) 70%, transparent 100%);
            padding: 40px 20px 15px;
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
        }}

        .video-container:hover .video-controls,
        .video-controls:hover,
        .video-controls.always-show {{
            opacity: 1;
            pointer-events: all;
        }}

        /* In fullscreen, only show controls when explicitly set */
        .video-container.fullscreen .video-controls {{
            opacity: 0;
            pointer-events: none;
        }}

        .video-container.fullscreen .video-controls.always-show {{
            opacity: 1;
            pointer-events: all;
        }}

        /* Progress Bar */
        .progress-bar-container {{
            width: 100%;
            height: 5px;
            background: rgba(255, 255, 255, 0.3);
            cursor: pointer;
            position: relative;
            margin-bottom: 10px;
            border-radius: 2px;
        }}

        .progress-bar-container:hover {{
            height: 7px;
        }}

        .progress-bar {{
            height: 100%;
            background: #ff0000;
            width: 0%;
            position: relative;
            border-radius: 2px;
        }}

        .progress-bar::after {{
            content: '';
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 12px;
            height: 12px;
            background: #ff0000;
            border-radius: 50%;
            opacity: 0;
            transition: opacity 0.2s;
        }}

        .progress-bar-container:hover .progress-bar::after {{
            opacity: 1;
        }}

        .progress-tooltip {{
            position: absolute;
            bottom: 10px;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }}

        .progress-bar-container:hover .progress-tooltip {{
            opacity: 1;
        }}

        /* Control Buttons Row */
        .controls-row {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .control-button {{
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s, opacity 0.2s;
            opacity: 0.9;
        }}

        .control-button:hover {{
            transform: scale(1.1);
            opacity: 1;
        }}

        .control-button:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}

        .control-button svg {{
            width: 24px;
            height: 24px;
            fill: currentColor;
        }}

        .control-button.play-pause svg {{
            width: 32px;
            height: 32px;
        }}

        /* Volume Control */
        .volume-control {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .volume-slider {{
            width: 0;
            opacity: 0;
            transition: width 0.3s, opacity 0.3s;
            -webkit-appearance: none;
            height: 4px;
            background: rgba(255, 255, 255, 0.3);
            outline: none;
            border-radius: 2px;
        }}

        .volume-control:hover .volume-slider {{
            width: 60px;
            opacity: 1;
        }}

        .volume-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 12px;
            height: 12px;
            background: #fff;
            cursor: pointer;
            border-radius: 50%;
        }}

        .volume-slider::-moz-range-thumb {{
            width: 12px;
            height: 12px;
            background: #fff;
            cursor: pointer;
            border-radius: 50%;
            border: none;
        }}

        /* Time Display */
        .time-display {{
            color: white;
            font-size: 14px;
            font-weight: 500;
            min-width: 100px;
        }}

        /* Spacer */
        .spacer {{
            flex: 1;
        }}

        /* Settings Menu (Speed) */
        .settings-menu {{
            position: relative;
        }}

        .settings-dropdown {{
            position: absolute;
            bottom: 100%;
            right: 0;
            background: rgba(28, 28, 28, 0.95);
            border-radius: 4px;
            padding: 8px 0;
            margin-bottom: 10px;
            min-width: 120px;
            display: none;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        }}

        .settings-dropdown.show {{
            display: block;
        }}

        /* CC Menu */
        .cc-menu {{
            position: relative;
        }}

        .cc-dropdown {{
            position: absolute;
            bottom: 100%;
            right: 0;
            background: rgba(28, 28, 28, 0.95);
            border-radius: 4px;
            padding: 8px 0;
            margin-bottom: 10px;
            min-width: 160px;
            display: none;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        }}

        .cc-dropdown.show {{
            display: block;
        }}

        .settings-item {{
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .settings-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        .settings-item.active {{
            color: #4fc3f7;
        }}

        .settings-item.active::after {{
            content: '✓';
            margin-left: 10px;
        }}

        .cc-item {{
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .cc-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        .cc-item.active {{
            color: #4fc3f7;
        }}

        /* Speed Toast */
        .speed-toast {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 16px 32px;
            border-radius: 6px;
            font-size: 20px;
            font-weight: 600;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
            z-index: 1000;
        }}

        .speed-toast.show {{
            opacity: 1;
        }}

        /* Video Info Bar */
        .video-info {{
            padding: 20px 30px;
            background: #252526;
            border-top: 1px solid #3c3c3c;
        }}

        .video-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #fff;
        }}

        .video-section {{
            font-size: 14px;
            color: #888;
        }}

        /* Course Resources */
        .resources-button {{
            margin-top: 15px;
            background: #007acc;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}

        .resources-button:hover {{
            background: #005a9e;
        }}

        .resources-button:disabled {{
            background: #555;
            cursor: not-allowed;
            opacity: 0.5;
        }}

        .resources-panel {{
            margin-top: 15px;
            padding: 15px;
            background: #2d2d30;
            border-radius: 6px;
            border: 1px solid #3c3c3c;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }}

        .resources-panel.show {{
            display: block;
        }}

        .resources-panel h3 {{
            font-size: 16px;
            color: #fff;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .resource-item {{
            padding: 10px 12px;
            margin-bottom: 8px;
            background: #1e1e1e;
            border-radius: 4px;
            border-left: 3px solid #007acc;
            transition: background 0.2s, transform 0.2s;
        }}

        .resource-item:hover {{
            background: #252526;
            transform: translateX(5px);
        }}

        .resource-item a {{
            color: #4fc3f7;
            text-decoration: none;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .resource-item a:hover {{
            color: #81d4fa;
            text-decoration: underline;
        }}

        .resource-icon {{
            font-size: 16px;
        }}

        .resources-empty {{
            color: #888;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

        .resources-panel::-webkit-scrollbar {{
            width: 8px;
        }}

        .resources-panel::-webkit-scrollbar-track {{
            background: #1e1e1e;
            border-radius: 4px;
        }}

        .resources-panel::-webkit-scrollbar-thumb {{
            background: #555;
            border-radius: 4px;
        }}

        .resources-panel::-webkit-scrollbar-thumb:hover {{
            background: #666;
        }}

        /* Keyboard Shortcuts Help */
        .shortcuts-info {{
            padding: 15px 30px;
            background: #2d2d30;
            border-top: 1px solid #3c3c3c;
            font-size: 12px;
            color: #888;
        }}

        .shortcuts-info strong {{
            color: #007acc;
        }}

        /* Scrollbar Styles */
        .sidebar::-webkit-scrollbar {{
            width: 8px;
        }}

        .sidebar::-webkit-scrollbar-track {{
            background: #1e1e1e;
        }}

        .sidebar::-webkit-scrollbar-thumb {{
            background: #555;
            border-radius: 4px;
        }}

        .sidebar::-webkit-scrollbar-thumb:hover {{
            background: #666;
        }}

        .main-content::-webkit-scrollbar {{
            width: 8px;
        }}

        .main-content::-webkit-scrollbar-track {{
            background: #1e1e1e;
        }}

        .main-content::-webkit-scrollbar-thumb {{
            background: #555;
            border-radius: 4px;
        }}

        .main-content::-webkit-scrollbar-thumb:hover {{
            background: #666;
        }}

        /* Loading Spinner */
        .loading-spinner {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 4px solid rgba(255, 255, 255, 0.2);
            border-top-color: #007acc;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            display: none;
        }}

        @keyframes spin {{
            to {{ transform: translate(-50%, -50%) rotate(360deg); }}
        }}

        .loading-spinner.show {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h1>📚 {course_name}</h1>
                <div class="header-controls">
                    <div class="progress-badge" id="progress-badge">
                        <span>📈</span>
                        <span id="global-progress">0% Complete</span>
                    </div>
                    <button class="reset-progress-btn" id="reset-progress-btn" title="Reset all progress">
                        🔄 Reset
                    </button>
                </div>
            </div>
            <div class="sections" id="sections-container"></div>
        </div>

        <!-- Resizer -->
        <div class="resizer" id="resizer"></div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="video-wrapper">
                <div class="video-container" id="video-container">
                    <div class="welcome-screen" id="welcome-screen">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M8 5v14l11-7z"/>
                        </svg>
                        <h2>Welcome to {course_name}</h2>
                        <p>Select a video from the sidebar to begin</p>
                    </div>

                    <video id="video-player" style="display: none;" preload="metadata">
                        <track id="subtitle-track" kind="captions" srclang="en" label="English">
                    </video>

                    <div class="loading-spinner" id="loading-spinner"></div>
                    <div class="speed-toast" id="speed-toast"></div>

                    <!-- Custom Video Controls -->
                    <div class="video-controls" id="video-controls" style="display: none;">
                        <!-- Progress Bar -->
                        <div class="progress-bar-container" id="progress-container">
                            <div class="progress-bar" id="progress-bar"></div>
                            <div class="progress-tooltip" id="progress-tooltip">0:00</div>
                        </div>

                        <!-- Control Buttons -->
                        <div class="controls-row">
                            <!-- Play/Pause -->
                            <button class="control-button play-pause" id="play-pause-btn" title="Play/Pause (Space)">
                                <svg viewBox="0 0 24 24" id="play-icon">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>
                                <svg viewBox="0 0 24 24" id="pause-icon" style="display: none;">
                                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                                </svg>
                            </button>

                            <!-- Previous -->
                            <button class="control-button" id="prev-btn" title="Previous Video">
                                <svg viewBox="0 0 24 24">
                                    <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
                                </svg>
                            </button>

                            <!-- Next -->
                            <button class="control-button" id="next-btn" title="Next Video">
                                <svg viewBox="0 0 24 24">
                                    <path d="M16 18h2V6h-2v12zM6 18l8.5-6L6 6v12z"/>
                                </svg>
                            </button>

                            <!-- Volume Control -->
                            <div class="volume-control">
                                <button class="control-button" id="volume-btn" title="Mute/Unmute">
                                    <svg viewBox="0 0 24 24" id="volume-icon">
                                        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
                                    </svg>
                                    <svg viewBox="0 0 24 24" id="mute-icon" style="display: none;">
                                        <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                                    </svg>
                                </button>
                                <input type="range" class="volume-slider" id="volume-slider" min="0" max="100" value="100">
                            </div>

                            <!-- Time Display -->
                            <span class="time-display" id="time-display">0:00 / 0:00</span>

                            <div class="spacer"></div>

                            <!-- Subtitles/CC -->
                            <div class="cc-menu">
                                <button class="control-button" id="cc-btn" title="Closed Captions">
                                    <svg viewBox="0 0 24 24">
                                        <path d="M19 4H5c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1c0 .55-.45 1-1 1H7c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1zm7 0h-1.5v-.5h-2v3h2V13H18v1c0 .55-.45 1-1 1h-3c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1z"/>
                                    </svg>
                                </button>
                                <div class="cc-dropdown" id="cc-dropdown">
                                    <div class="cc-item" id="cc-toggle">Toggle On/Off</div>
                                    <div class="cc-item" id="cc-load">📂 Load Subtitle...</div>
                                </div>
                            </div>
                            <input type="file" id="subtitle-file-input" accept=".srt,.vtt" style="display: none;">

                            <!-- Settings (Speed) -->
                            <div class="settings-menu">
                                <button class="control-button" id="settings-btn" title="Settings">
                                    <svg viewBox="0 0 24 24">
                                        <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                                    </svg>
                                </button>
                                <div class="settings-dropdown" id="settings-dropdown">
                                    <div class="settings-item" data-speed="0.25">0.25x</div>
                                    <div class="settings-item" data-speed="0.5">0.5x</div>
                                    <div class="settings-item" data-speed="0.75">0.75x</div>
                                    <div class="settings-item active" data-speed="1">Normal</div>
                                    <div class="settings-item" data-speed="1.25">1.25x</div>
                                    <div class="settings-item" data-speed="1.5">1.5x</div>
                                    <div class="settings-item" data-speed="1.75">1.75x</div>
                                    <div class="settings-item" data-speed="2">2x</div>
                                </div>
                            </div>

                            <!-- Fullscreen -->
                            <button class="control-button" id="fullscreen-btn" title="Fullscreen (F)">
                                <svg viewBox="0 0 24 24" id="fullscreen-icon">
                                    <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                                </svg>
                                <svg viewBox="0 0 24 24" id="fullscreen-exit-icon" style="display: none;">
                                    <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="video-info" id="video-info" style="display: none;">
                <div class="video-title" id="video-title"></div>
                <div class="video-section" id="video-section"></div>

                <!-- Course Resources -->
                <button class="resources-button" id="resources-btn" disabled>
                    📂 View Resources
                </button>
                <div class="resources-panel" id="resources-panel">
                    <h3>📂 Course Resources</h3>
                    <div id="resources-list"></div>
                </div>
            </div>

            <div class="shortcuts-info">
                <strong>Keyboard Shortcuts:</strong> Space = Play/Pause | [ = Slow Down | ] = Speed Up | ← = Seek -5s | → = Seek +5s | F = Fullscreen | M = Mute
            </div>
        </div>
    </div>

    <script>
        // Course data embedded from Python
        const courseData = {course_json};
        
        // Watched videos injected from server
        let watchedVideos = {watched_json};

        // State
        let currentVideo = null;
        let currentSection = null;
        let videoList = [];
        let isDraggingProgress = false;
        let isFullscreen = false;
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        let inactivityTimer = null;
        let isControlsVisible = true;

        // DOM Elements
        const sidebar = document.getElementById('sidebar');
        const resizer = document.getElementById('resizer');
        const sectionsContainer = document.getElementById('sections-container');
        const videoContainer = document.getElementById('video-container');
        const videoPlayer = document.getElementById('video-player');
        const welcomeScreen = document.getElementById('welcome-screen');
        const videoInfo = document.getElementById('video-info');
        const videoTitle = document.getElementById('video-title');
        const videoSection = document.getElementById('video-section');
        const videoControls = document.getElementById('video-controls');
        const playPauseBtn = document.getElementById('play-pause-btn');
        const playIcon = document.getElementById('play-icon');
        const pauseIcon = document.getElementById('pause-icon');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const volumeBtn = document.getElementById('volume-btn');
        const volumeIcon = document.getElementById('volume-icon');
        const muteIcon = document.getElementById('mute-icon');
        const volumeSlider = document.getElementById('volume-slider');
        const ccBtn = document.getElementById('cc-btn');
        const ccDropdown = document.getElementById('cc-dropdown');
        const ccToggle = document.getElementById('cc-toggle');
        const ccLoad = document.getElementById('cc-load');
        const subtitleFileInput = document.getElementById('subtitle-file-input');
        const settingsBtn = document.getElementById('settings-btn');
        const settingsDropdown = document.getElementById('settings-dropdown');
        const fullscreenBtn = document.getElementById('fullscreen-btn');
        const fullscreenIcon = document.getElementById('fullscreen-icon');
        const fullscreenExitIcon = document.getElementById('fullscreen-exit-icon');
        const speedToast = document.getElementById('speed-toast');
        const timeDisplay = document.getElementById('time-display');
        const progressContainer = document.getElementById('progress-container');
        const progressBar = document.getElementById('progress-bar');
        const progressTooltip = document.getElementById('progress-tooltip');
        const courseStats = document.getElementById('course-stats');
        const loadingSpinner = document.getElementById('loading-spinner');
        const subtitleTrack = document.getElementById('subtitle-track');
        const resourcesBtn = document.getElementById('resources-btn');
        const resourcesPanel = document.getElementById('resources-panel');
        const resourcesList = document.getElementById('resources-list');
        const resetProgressBtn = document.getElementById('reset-progress-btn');

        // Build flat list of all videos for navigation
        function buildVideoList() {{
            videoList = [];
            Object.entries(courseData).forEach(([sectionName, sectionData]) => {{
                sectionData.videos.forEach(video => {{
                    videoList.push({{
                        section: sectionName,
                        video: video
                    }});
                }});
            }});
        }}

        // Mark video as watched (server-side)
        async function markAsWatched(videoPath) {{
            try {{
                const response = await fetch('/api/mark_watched', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ path: videoPath }})
                }});
                
                if (response.ok) {{
                    // Add to local list
                    if (!watchedVideos.includes(videoPath)) {{
                        watchedVideos.push(videoPath);
                        updateSidebarCheckmarks();
                        updateStats();
                    }}
                }}
            }} catch (error) {{
                console.error('Error marking video as watched:', error);
            }}
        }}

        // Toggle watched status (server-side)
        async function toggleWatched(videoPath) {{
            try {{
                const response = await fetch('/api/toggle_watched', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ path: videoPath }})
                }});
                
                if (response.ok) {{
                    const data = await response.json();
                    
                    // Update local list
                    if (data.watched) {{
                        if (!watchedVideos.includes(videoPath)) {{
                            watchedVideos.push(videoPath);
                        }}
                    }} else {{
                        watchedVideos = watchedVideos.filter(p => p !== videoPath);
                    }}
                    
                    updateSidebarCheckmarks();
                    updateStats();
                }}
            }} catch (error) {{
                console.error('Error toggling watched status:', error);
            }}
        }}

        // Reset all progress (server-side)
        async function resetProgress() {{
            if (!confirm('Are you sure you want to reset all progress? This cannot be undone.')) {{
                return;
            }}
            
            try {{
                const response = await fetch('/api/reset_progress', {{
                    method: 'POST'
                }});
                
                if (response.ok) {{
                    watchedVideos = [];
                    updateSidebarCheckmarks();
                    updateStats();
                }}
            }} catch (error) {{
                console.error('Error resetting progress:', error);
            }}
        }}

        // Update checkmarks in sidebar
        function updateSidebarCheckmarks() {{
            document.querySelectorAll('.video-item').forEach(item => {{
                const videoPath = item.dataset.path;
                const isWatched = watchedVideos.includes(videoPath);
                
                if (isWatched) {{
                    item.classList.add('watched');
                }} else {{
                    item.classList.remove('watched');
                }}
                
                // Update checkmark
                const checkmark = item.querySelector('.video-checkmark');
                if (checkmark) {{
                    checkmark.textContent = isWatched ? '✓' : '';
                }}
            }});
            
            // Update section progress indicators and completed state
            document.querySelectorAll('.section').forEach(section => {{
                const sectionHeader = section.querySelector('.section-header');
                const sectionTitle = sectionHeader.querySelector('.section-title');
                const videoItems = section.querySelectorAll('.video-item');
                
                const totalVideos = videoItems.length;
                const watchedCount = Array.from(videoItems).filter(item => 
                    watchedVideos.includes(item.dataset.path)
                ).length;
                const isComplete = watchedCount === totalVideos && totalVideos > 0;
                
                // Remove old progress indicator
                const oldProgress = sectionTitle.querySelector('.section-progress');
                if (oldProgress) {{
                    oldProgress.remove();
                }}
                
                // Create new progress indicator
                const progressSpan = document.createElement('span');
                progressSpan.className = `section-progress ${{isComplete ? 'completed' : 'in-progress'}}`;
                
                if (isComplete) {{
                    progressSpan.innerHTML = `<span class="checkmark">✓</span>${{watchedCount}}/${{totalVideos}}`;
                }} else {{
                    progressSpan.textContent = `${{watchedCount}}/${{totalVideos}}`;
                }}
                
                sectionTitle.appendChild(progressSpan);
                
                // Add or remove completed class on section header
                if (isComplete) {{
                    sectionHeader.classList.add('completed');
                }} else {{
                    sectionHeader.classList.remove('completed');
                }}
            }});
        }}

        // Initialize UI
        function init() {{
            buildVideoList();
            renderSidebar();
            updateStats();
            setupEventListeners();
        }}

        // Render sidebar sections
        function renderSidebar() {{
            sectionsContainer.innerHTML = '';

            Object.entries(courseData).forEach(([sectionName, sectionData]) => {{
                const section = document.createElement('div');
                section.className = 'section';

                // Calculate section progress
                const totalVideos = sectionData.videos.length;
                const watchedCount = sectionData.videos.filter(v => watchedVideos.includes(v.path)).length;
                const isComplete = watchedCount === totalVideos && totalVideos > 0;
                
                // Create progress indicator HTML
                let progressHTML = '';
                if (isComplete) {{
                    progressHTML = `<span class="section-progress completed"><span class="checkmark">✓</span>${{watchedCount}}/${{totalVideos}}</span>`;
                }} else if (watchedCount > 0) {{
                    progressHTML = `<span class="section-progress in-progress">${{watchedCount}}/${{totalVideos}}</span>`;
                }} else {{
                    progressHTML = `<span class="section-progress in-progress">0/${{totalVideos}}</span>`;
                }}

                const header = document.createElement('div');
                header.className = 'section-header';
                
                // Add completed class if all videos are watched
                if (isComplete) {{
                    header.classList.add('completed');
                }}
                
                header.innerHTML = `
                    <span class="section-title">
                        ${{sectionName}}
                        ${{progressHTML}}
                    </span>
                    <span class="section-arrow">▶</span>
                `;

                const videoListDiv = document.createElement('div');
                videoListDiv.className = 'video-list';

                sectionData.videos.forEach(video => {{
                    const videoItem = document.createElement('div');
                    videoItem.className = 'video-item';
                    videoItem.dataset.section = sectionName;
                    videoItem.dataset.path = video.path;
                    
                    // Check if watched
                    if (watchedVideos.includes(video.path)) {{
                        videoItem.classList.add('watched');
                    }}
                    
                    // Create video name span
                    const videoName = document.createElement('span');
                    videoName.className = 'video-name';
                    videoName.textContent = video.name;
                    
                    // Create checkmark
                    const checkmark = document.createElement('div');
                    checkmark.className = 'video-checkmark';
                    checkmark.textContent = watchedVideos.includes(video.path) ? '✓' : '';
                    checkmark.title = 'Toggle watched status';
                    
                    // Checkmark click - toggle without loading video
                    checkmark.addEventListener('click', (e) => {{
                        e.stopPropagation();
                        toggleWatched(video.path);
                    }});
                    
                    // Video name click - load video
                    videoName.addEventListener('click', () => {{
                        loadVideo(sectionName, video);
                    }});
                    
                    videoItem.appendChild(videoName);
                    videoItem.appendChild(checkmark);

                    videoListDiv.appendChild(videoItem);
                }});

                header.addEventListener('click', () => {{
                    section.classList.toggle('expanded');
                }});

                section.appendChild(header);
                section.appendChild(videoListDiv);
                sectionsContainer.appendChild(section);
            }});

            // Auto-expand first section
            if (sectionsContainer.firstChild) {{
                sectionsContainer.firstChild.classList.add('expanded');
            }}
        }}

        // Update course statistics
        function updateStats() {{
            const sectionCount = Object.keys(courseData).length;
            const videoCount = videoList.length;
            const watchedCount = watchedVideos.length;
            const percentage = videoCount > 0 ? Math.round((watchedCount / videoCount) * 100) : 0;
            
            // Update the blue progress badge
            const globalProgress = document.getElementById('global-progress');
            if (globalProgress) {{
                globalProgress.textContent = `${{percentage}}% Complete`;
            }}
        }}

        // Load and play video
        function loadVideo(sectionName, video) {{
            currentSection = sectionName;
            currentVideo = video;

            // Show loading
            loadingSpinner.classList.add('show');

            // Update UI
            welcomeScreen.style.display = 'none';
            videoPlayer.style.display = 'block';
            videoInfo.style.display = 'block';
            videoControls.style.display = 'block';

            // Set video source
            videoPlayer.src = encodeURI(video.path);

            // Handle subtitles
            if (video.subtitle) {{
                subtitleTrack.src = encodeURI(video.subtitle);
                ccBtn.style.opacity = '0.9';
            }} else {{
                subtitleTrack.src = '';
                ccBtn.style.opacity = '0.5';
                videoPlayer.textTracks[0].mode = 'hidden';
                ccBtn.style.color = 'white';
                ccToggle.classList.remove('active');
            }}

            videoPlayer.load();

            // Update info
            videoTitle.textContent = video.name;
            videoSection.textContent = `Section: ${{sectionName}}`;

            // Handle resources
            loadResources(video);

            // Update sidebar highlights
            updateSidebarHighlight();

            // Update navigation buttons
            updateNavigationButtons();
        }}

        // Update sidebar to highlight current video
        function updateSidebarHighlight() {{
            document.querySelectorAll('.video-item').forEach(item => {{
                item.classList.remove('active');
            }});

            document.querySelectorAll('.section-header').forEach(header => {{
                header.classList.remove('active');
            }});

            if (currentVideo) {{
                const activeItem = document.querySelector(
                    `.video-item[data-path="${{currentVideo.path}}"]`
                );
                if (activeItem) {{
                    activeItem.classList.add('active');

                    const section = activeItem.closest('.section');
                    if (section) {{
                        section.classList.add('expanded');
                        section.querySelector('.section-header').classList.add('active');
                    }}

                    activeItem.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
                }}
            }}
        }}

        // Update navigation buttons state
        function updateNavigationButtons() {{
            const currentIndex = videoList.findIndex(
                item => item.video.path === currentVideo?.path
            );

            prevBtn.disabled = currentIndex <= 0;
            nextBtn.disabled = currentIndex >= videoList.length - 1;
        }}

        // Load and display resources for current video
        function loadResources(video) {{
            // Hide resources panel initially
            resourcesPanel.classList.remove('show');

            // Check if video has resources
            if (video.resources && video.resources.length > 0) {{
                // Enable button
                resourcesBtn.disabled = false;
                resourcesBtn.style.opacity = '1';

                // Populate resources list
                resourcesList.innerHTML = '';
                video.resources.forEach(resource => {{
                    const resourceItem = document.createElement('div');
                    resourceItem.className = 'resource-item';

                    const link = document.createElement('a');
                    link.href = encodeURI(resource.path);
                    link.target = '_blank';
                    link.innerHTML = `
                        <span class="resource-icon">📄</span>
                        <span>${{resource.name}}</span>
                    `;

                    resourceItem.appendChild(link);
                    resourcesList.appendChild(resourceItem);
                }});
            }} else {{
                // Disable button if no resources
                resourcesBtn.disabled = true;
                resourcesBtn.style.opacity = '0.5';
                resourcesList.innerHTML = '<div class="resources-empty">No resources available for this video</div>';
            }}
        }}

        // Toggle resources panel visibility
        function toggleResources() {{
            resourcesPanel.classList.toggle('show');
        }}

        // Toggle play/pause
        function togglePlayPause() {{
            if (videoPlayer.paused) {{
                videoPlayer.play();
            }} else {{
                videoPlayer.pause();
            }}
        }}

        // Navigate to previous video
        function playPrevious() {{
            const currentIndex = videoList.findIndex(
                item => item.video.path === currentVideo?.path
            );
            if (currentIndex > 0) {{
                const prev = videoList[currentIndex - 1];
                loadVideo(prev.section, prev.video);
            }}
        }}

        // Navigate to next video
        function playNext() {{
            const currentIndex = videoList.findIndex(
                item => item.video.path === currentVideo?.path
            );
            if (currentIndex < videoList.length - 1) {{
                const next = videoList[currentIndex + 1];
                loadVideo(next.section, next.video);
            }}
        }}

        // Toggle mute
        function toggleMute() {{
            videoPlayer.muted = !videoPlayer.muted;
            updateVolumeIcon();
        }}

        // Update volume icon
        function updateVolumeIcon() {{
            if (videoPlayer.muted || videoPlayer.volume === 0) {{
                volumeIcon.style.display = 'none';
                muteIcon.style.display = 'block';
            }} else {{
                volumeIcon.style.display = 'block';
                muteIcon.style.display = 'none';
            }}
        }}

        // Change playback speed
        function changeSpeed(speed) {{
            videoPlayer.playbackRate = speed;
            showSpeedToast(speed);

            // Update active state in dropdown
            document.querySelectorAll('.settings-item').forEach(item => {{
                item.classList.remove('active');
                if (parseFloat(item.dataset.speed) === speed) {{
                    item.classList.add('active');
                }}
            }});
        }}

        // Show speed change notification
        function showSpeedToast(speed) {{
            speedToast.textContent = `Speed: ${{speed}}x`;
            speedToast.classList.add('show');
            setTimeout(() => {{
                speedToast.classList.remove('show');
            }}, 1000);
        }}

        // Toggle fullscreen
        function toggleFullscreen() {{
            if (!isFullscreen) {{
                if (videoContainer.requestFullscreen) {{
                    videoContainer.requestFullscreen();
                }} else if (videoContainer.webkitRequestFullscreen) {{
                    videoContainer.webkitRequestFullscreen();
                }} else if (videoContainer.mozRequestFullScreen) {{
                    videoContainer.mozRequestFullScreen();
                }} else if (videoContainer.msRequestFullscreen) {{
                    videoContainer.msRequestFullscreen();
                }}
            }} else {{
                if (document.exitFullscreen) {{
                    document.exitFullscreen();
                }} else if (document.webkitExitFullscreen) {{
                    document.webkitExitFullscreen();
                }} else if (document.mozCancelFullScreen) {{
                    document.mozCancelFullScreen();
                }} else if (document.msExitFullscreen) {{
                    document.msExitFullscreen();
                }}
            }}
        }}

        // Show controls and reset inactivity timer
        function showControlsAndResetTimer() {{
            if (isFullscreen) {{
                videoControls.classList.add('always-show');
                videoContainer.classList.remove('hide-cursor');
                isControlsVisible = true;

                // Clear existing timer
                if (inactivityTimer) {{
                    clearTimeout(inactivityTimer);
                }}

                // Set new timer to hide after 3 seconds
                inactivityTimer = setTimeout(() => {{
                    if (isFullscreen && !videoPlayer.paused) {{
                        videoControls.classList.remove('always-show');
                        videoContainer.classList.add('hide-cursor');
                        isControlsVisible = false;
                    }}
                }}, 3000);
            }}
        }}

        // Hide controls immediately
        function hideControls() {{
            if (isFullscreen && !videoPlayer.paused) {{
                videoControls.classList.remove('always-show');
                videoContainer.classList.add('hide-cursor');
                isControlsVisible = false;
                if (inactivityTimer) {{
                    clearTimeout(inactivityTimer);
                }}
            }}
        }}

        // Toggle subtitles
        function toggleSubtitles() {{
            const track = videoPlayer.textTracks[0];
            // Check if subtitles are loaded
            if (!subtitleTrack.src) {{
                alert('No subtitles loaded. Please load a subtitle file first.');
                ccDropdown.classList.remove('show');
                return;
            }}

            if (track.mode === 'hidden') {{
                track.mode = 'showing';
                ccBtn.style.color = '#4fc3f7';
                ccToggle.classList.add('active');
            }} else {{
                track.mode = 'hidden';
                ccBtn.style.color = 'white';
                ccToggle.classList.remove('active');
            }}
        }}

        // Convert SRT content to VTT format
        function srtToVtt(srtContent) {{
            // Add WebVTT header
            let vttContent = 'WEBVTT\\n\\n';

            // Replace comma with period in timestamps (SRT uses comma, VTT uses period)
            vttContent += srtContent.replace(/(\d{{2}}:\d{{2}}:\d{{2}}),(\d{{3}})/g, '$1.$2');

            return vttContent;
        }}

        // Load custom subtitle file
        function loadSubtitleFile(file) {{
            const reader = new FileReader();

            reader.onload = function(e) {{
                let content = e.target.result;
                const fileName = file.name.toLowerCase();

                // Convert SRT to VTT if needed
                if (fileName.endsWith('.srt')) {{
                    content = srtToVtt(content);
                }}

                // Create Blob URL
                const blob = new Blob([content], {{ type: 'text/vtt' }});
                const blobUrl = URL.createObjectURL(blob);

                // Update subtitle track
                subtitleTrack.src = blobUrl;

                // Enable CC button with full opacity
                ccBtn.style.opacity = '0.9';

                // Auto-enable subtitles
                videoPlayer.textTracks[0].mode = 'showing';
                ccBtn.style.color = '#4fc3f7';
                ccToggle.classList.add('active');

                // Close the dropdown
                ccDropdown.classList.remove('show');

                console.log('Subtitle loaded successfully:', file.name);
            }};

            reader.onerror = function() {{
                console.error('Error reading subtitle file');
                alert('Failed to load subtitle file. Please try again.');
            }};

            reader.readAsText(file);
        }}

        // Format time (seconds to MM:SS or HH:MM:SS)
        function formatTime(seconds) {{
            if (isNaN(seconds)) return '0:00';

            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = Math.floor(seconds % 60);

            if (h > 0) {{
                return `${{h}}:${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
            }}
            return `${{m}}:${{s.toString().padStart(2, '0')}}`;
        }}

        // Update progress bar
        function updateProgress() {{
            if (!isDraggingProgress) {{
                const percent = (videoPlayer.currentTime / videoPlayer.duration) * 100;
                progressBar.style.width = percent + '%';
            }}
            timeDisplay.textContent = `${{formatTime(videoPlayer.currentTime)}} / ${{formatTime(videoPlayer.duration)}}`;
        }}

        // Seek video
        function seekVideo(e) {{
            const rect = progressContainer.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const time = percent * videoPlayer.duration;
            videoPlayer.currentTime = time;
            progressBar.style.width = (percent * 100) + '%';
        }}

        // Show time tooltip on progress bar hover
        function showProgressTooltip(e) {{
            const rect = progressContainer.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const time = percent * videoPlayer.duration;
            progressTooltip.textContent = formatTime(time);
            progressTooltip.style.left = (e.clientX - rect.left) + 'px';
        }}

        // Setup all event listeners
        function setupEventListeners() {{
            // Video player events
            videoPlayer.addEventListener('play', () => {{
                playIcon.style.display = 'none';
                pauseIcon.style.display = 'block';
                if (isFullscreen) {{
                    showControlsAndResetTimer();
                }}
            }});

            videoPlayer.addEventListener('pause', () => {{
                playIcon.style.display = 'block';
                pauseIcon.style.display = 'none';
                if (isFullscreen) {{
                    videoControls.classList.add('always-show');
                    videoContainer.classList.remove('hide-cursor');
                    if (inactivityTimer) {{
                        clearTimeout(inactivityTimer);
                    }}
                }}
            }});

            videoPlayer.addEventListener('timeupdate', updateProgress);

            videoPlayer.addEventListener('ended', () => {{
                // Mark current video as watched
                if (currentVideo) {{
                    markAsWatched(currentVideo.path);
                }}
                playNext();
            }});

            videoPlayer.addEventListener('loadedmetadata', () => {{
                loadingSpinner.classList.remove('show');
                videoPlayer.play();
            }});

            videoPlayer.addEventListener('volumechange', updateVolumeIcon);

            // Video container click = play/pause
            videoContainer.addEventListener('click', (e) => {{
                if (e.target === videoPlayer || e.target === videoContainer) {{
                    togglePlayPause();
                }}
            }});

            // Double click = fullscreen
            videoContainer.addEventListener('dblclick', (e) => {{
                if (e.target === videoPlayer || e.target === videoContainer) {{
                    toggleFullscreen();
                }}
            }});

            // Control buttons
            playPauseBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                togglePlayPause();
            }});

            prevBtn.addEventListener('click', playPrevious);
            nextBtn.addEventListener('click', () => {{
                // Mark current video as watched when clicking Next
                if (currentVideo) {{
                    markAsWatched(currentVideo.path);
                }}
                playNext();
            }});

            volumeBtn.addEventListener('click', toggleMute);

            volumeSlider.addEventListener('input', (e) => {{
                videoPlayer.volume = e.target.value / 100;
                videoPlayer.muted = false;
            }});

            // CC button and menu
            ccBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                ccDropdown.classList.toggle('show');
                settingsDropdown.classList.remove('show');
            }});

            ccToggle.addEventListener('click', () => {{
                toggleSubtitles();
                ccDropdown.classList.remove('show');
            }});

            ccLoad.addEventListener('click', () => {{
                subtitleFileInput.click();
            }});

            subtitleFileInput.addEventListener('change', (e) => {{
                const file = e.target.files[0];
                if (file) {{
                    loadSubtitleFile(file);
                }}
                // Reset input so same file can be selected again
                e.target.value = '';
            }});

            // Settings dropdown
            settingsBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                settingsDropdown.classList.toggle('show');
            }});

            document.querySelectorAll('.settings-item').forEach(item => {{
                item.addEventListener('click', () => {{
                    const speed = parseFloat(item.dataset.speed);
                    changeSpeed(speed);
                    settingsDropdown.classList.remove('show');
                }});
            }});

            // Close dropdowns on outside click
            document.addEventListener('click', (e) => {{
                if (!settingsBtn.contains(e.target) && !settingsDropdown.contains(e.target)) {{
                    settingsDropdown.classList.remove('show');
                }}
                if (!ccBtn.contains(e.target) && !ccDropdown.contains(e.target)) {{
                    ccDropdown.classList.remove('show');
                }}
            }});

            fullscreenBtn.addEventListener('click', toggleFullscreen);

            // Fullscreen change events
            document.addEventListener('fullscreenchange', () => {{
                isFullscreen = !!document.fullscreenElement;
                updateFullscreenIcon();
                if (isFullscreen) {{
                    showControlsAndResetTimer();
                }} else {{
                    // Clear timer and show controls when exiting fullscreen
                    if (inactivityTimer) {{
                        clearTimeout(inactivityTimer);
                    }}
                    videoControls.classList.remove('always-show');
                    videoContainer.classList.remove('hide-cursor');
                }}
            }});

            document.addEventListener('webkitfullscreenchange', () => {{
                isFullscreen = !!document.webkitFullscreenElement;
                updateFullscreenIcon();
                if (isFullscreen) {{
                    showControlsAndResetTimer();
                }} else {{
                    if (inactivityTimer) {{
                        clearTimeout(inactivityTimer);
                    }}
                    videoControls.classList.remove('always-show');
                    videoContainer.classList.remove('hide-cursor');
                }}
            }});

            // Mouse movement in video container for fullscreen
            videoContainer.addEventListener('mousemove', () => {{
                if (isFullscreen) {{
                    showControlsAndResetTimer();
                }}
            }});

            // Show controls when video is paused
            videoPlayer.addEventListener('pause', () => {{
                if (isFullscreen) {{
                    videoControls.classList.add('always-show');
                    videoContainer.classList.remove('hide-cursor');
                    if (inactivityTimer) {{
                        clearTimeout(inactivityTimer);
                    }}
                }}
            }});

            // Resume auto-hide when video plays
            videoPlayer.addEventListener('play', () => {{
                if (isFullscreen) {{
                    showControlsAndResetTimer();
                }}
            }});

            // Progress bar
            progressContainer.addEventListener('click', seekVideo);

            progressContainer.addEventListener('mousedown', (e) => {{
                isDraggingProgress = true;
                seekVideo(e);
            }});

            document.addEventListener('mousemove', (e) => {{
                if (isDraggingProgress) {{
                    seekVideo(e);
                }}
            }});

            document.addEventListener('mouseup', () => {{
                isDraggingProgress = false;
            }});

            progressContainer.addEventListener('mousemove', showProgressTooltip);

            // Resources button
            resourcesBtn.addEventListener('click', toggleResources);
            
            // Reset progress button
            resetProgressBtn.addEventListener('click', resetProgress);

            // Resizer drag functionality
            resizer.addEventListener('mousedown', (e) => {{
                isResizing = true;
                startX = e.clientX;
                startWidth = sidebar.offsetWidth;
                document.body.classList.add('resizing');
                e.preventDefault();
            }});

            document.addEventListener('mousemove', (e) => {{
                if (!isResizing) return;

                const delta = e.clientX - startX;
                const newWidth = startWidth + delta;

                // Apply constraints
                if (newWidth >= 200 && newWidth <= 600) {{
                    sidebar.style.width = newWidth + 'px';
                }}
            }});

            document.addEventListener('mouseup', () => {{
                if (isResizing) {{
                    isResizing = false;
                    document.body.classList.remove('resizing');
                }}
            }});

            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {{
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {{
                    return;
                }}

                switch(e.key.toLowerCase()) {{
                    case ' ':
                        e.preventDefault();
                        togglePlayPause();
                        break;
                    case '[':
                        e.preventDefault();
                        const newSlowSpeed = Math.max(0.25, videoPlayer.playbackRate - 0.25);
                        changeSpeed(newSlowSpeed);
                        break;
                    case ']':
                        e.preventDefault();
                        const newFastSpeed = Math.min(2, videoPlayer.playbackRate + 0.25);
                        changeSpeed(newFastSpeed);
                        break;
                    case 'arrowleft':
                        e.preventDefault();
                        videoPlayer.currentTime = Math.max(0, videoPlayer.currentTime - 5);
                        break;
                    case 'arrowright':
                        e.preventDefault();
                        videoPlayer.currentTime = Math.min(
                            videoPlayer.duration,
                            videoPlayer.currentTime + 5
                        );
                        break;
                    case 'f':
                        e.preventDefault();
                        toggleFullscreen();
                        break;
                    case 'm':
                        e.preventDefault();
                        toggleMute();
                        break;
                    case 'c':
                        e.preventDefault();
                        ccDropdown.classList.toggle('show');
                        settingsDropdown.classList.remove('show');
                        break;
                }}
            }});
        }}

        // Update fullscreen icon
        function updateFullscreenIcon() {{
            if (isFullscreen) {{
                fullscreenIcon.style.display = 'none';
                fullscreenExitIcon.style.display = 'block';
                videoContainer.classList.add('fullscreen');
            }} else {{
                fullscreenIcon.style.display = 'block';
                fullscreenExitIcon.style.display = 'none';
                videoContainer.classList.remove('fullscreen');
            }}
        }}

        // Initialize on page load
        init();
    </script>
</body>
</html>"""

    return html

class CourseHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler to serve video files, handle subtitle conversion,
    and manage progress tracking API endpoints.
    """
    def do_GET(self):
        # Parse the URL
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path.lstrip('/'))

        # Check if it's a subtitle file
        if path.lower().endswith('.srt'):
            # Convert SRT to VTT on the fly
            file_path = os.path.join(os.getcwd(), path)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        srt_content = f.read()

                    vtt_content = srt_to_vtt(srt_content)

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/vtt; charset=utf-8')
                    self.send_header('Content-Length', len(vtt_content.encode('utf-8')))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.end_headers()
                    self.wfile.write(vtt_content.encode('utf-8'))
                    return
                except Exception as e:
                    print(f"Error converting SRT to VTT: {e}")

        # Default behavior for other files
        super().do_GET()
    
    def do_POST(self):
        """
        Handle POST requests for progress tracking API.
        """
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Get content length and read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # API: Mark video as watched
        if path == '/api/mark_watched':
            video_path = data.get('path', '')
            if video_path:
                save_progress(video_path)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({'success': True, 'path': video_path})
                self.wfile.write(response.encode('utf-8'))
            else:
                self.send_error(400, "Missing 'path' parameter")
        
        # API: Toggle watched status
        elif path == '/api/toggle_watched':
            video_path = data.get('path', '')
            if video_path:
                watched = load_progress()
                normalized_path = video_path.replace('\\', '/')
                
                if normalized_path in watched:
                    remove_progress(video_path)
                    is_watched = False
                else:
                    save_progress(video_path)
                    is_watched = True
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({'success': True, 'watched': is_watched, 'path': video_path})
                self.wfile.write(response.encode('utf-8'))
            else:
                self.send_error(400, "Missing 'path' parameter")
        
        # API: Reset all progress
        elif path == '/api/reset_progress':
            reset_progress()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({'success': True})
            self.wfile.write(response.encode('utf-8'))
        
        else:
            self.send_error(404, "API endpoint not found")

    def end_headers(self):
        # Add headers to support video streaming and CORS
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, format, *args):
        # Custom logging
        if not self.path.endswith('.ico'):  # Skip favicon requests in logs
            print(f"[{self.log_date_time_string()}] {format % args}")

def start_server():
    """
    Start the HTTP server and open browser.
    """
    handler = CourseHTTPRequestHandler

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n{'='*60}")
        print(f"🎓 Course Player Server Started")
        print(f"{'='*60}")
        print(f"📂 Serving from: {os.getcwd()}")
        print(f"🌐 URL: http://localhost:{PORT}")
        print(f"{'='*60}\n")
        print("Press Ctrl+C to stop the server\n")

        # Open browser
        webbrowser.open(f'http://localhost:{PORT}')

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n🛑 Server stopped by user")
            print("Goodbye! 👋\n")

def main():
    """
    Main function to orchestrate the course player.
    """
    print("\n🔍 Scanning for video files and subtitles...")

    # Scan current directory for videos
    current_dir = os.getcwd()

    # Get the course name from the current directory
    course_name = os.path.basename(current_dir)

    course_structure = scan_videos(current_dir)

    if not course_structure:
        print("\n❌ No video files found!")
        print("   Supported formats: .mp4, .mkv, .webm")
        print("   Please run this script in a directory containing video files.\n")
        return

    # Count total sections, videos, and subtitles
    total_sections = len(course_structure)
    total_videos = sum(len(section['videos']) for section in course_structure.values())
    total_subtitles = sum(1 for section in course_structure.values()
                         for video in section['videos'] if video['subtitle'])

    print(f"📚 Course: {course_name}")
    print(f"✅ Found {total_videos} videos in {total_sections} sections")
    if total_subtitles > 0:
        print(f"📝 Found {total_subtitles} subtitle files\n")
    else:
        print()

    # Generate HTML
    print("📝 Generating course player interface...")
    html_content = generate_html(course_structure, course_name)

    # Write HTML file
    index_path = os.path.join(current_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Generated: {index_path}\n")

    # Start server
    print("🚀 Starting web server...")
    start_server()

if __name__ == '__main__':
    main()
