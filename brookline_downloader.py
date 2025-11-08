import os
import time
import re
import platform
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import subprocess
import threading
import json
import shutil

# Optional schedule import - auto refresh won't work without it
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    print("⚠️  'schedule' module not installed - auto refresh feature disabled")

class SimpleBrooklineDownloader:
    def __init__(self):
        self.base_url = "https://www.brooklinema.gov/"
        # Use the same directory as the script file
        self.save_path = Path(__file__).parent / "govideosav"
        self.driver = None
        self.downloading_tabs = []  # Track tabs with downloads
        self.downloaded_events = set()  # Track downloaded event IDs
        self.running = True  # For auto refresh
        self.ffmpeg_path = None  # Will be set after checking
        
        self.save_path.mkdir(exist_ok=True)
        
        # Chrome options - no download directory set initially
        self.chrome_options = Options()
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-logging")
        self.chrome_options.add_argument("--log-level=3")
        
        # Basic prefs - download directory will be changed per download
        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
        }
        self.chrome_options.add_experimental_option("prefs", prefs)
        
        # Load previously downloaded events on startup
        self.load_downloaded_events()
        
        # Check FFmpeg availability
        self.check_and_find_ffmpeg()

    def check_and_find_ffmpeg(self):
        """Find FFmpeg executable and test it (cross-platform)"""
        print("🔍 Checking FFmpeg availability...")
        
        system = platform.system()
        is_windows = system == "Windows"
        is_macos = system == "Darwin"
        is_linux = system == "Linux"
        
        # Try different ways to find ffmpeg
        possible_paths = [
            "ffmpeg",  # In PATH (works on all platforms)
            shutil.which("ffmpeg"),  # Use shutil.which (cross-platform)
        ]
        
        # Add .exe for Windows if on Windows
        if is_windows:
            possible_paths.extend([
                "ffmpeg.exe",  # In PATH with .exe
                "C:\\ffmpeg\\bin\\ffmpeg.exe",  # Common Windows installation path
            ])
            
            # Add winget installation paths (Windows only)
            import getpass
            username = getpass.getuser()
            winget_paths = [
                f"C:\\Users\\{username}\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-7.1.1-full_build\\bin\\ffmpeg.exe",
                f"C:\\Users\\{username}\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe"
            ]
            possible_paths.extend(winget_paths)
        
        # Add macOS Homebrew paths
        if is_macos:
            homebrew_paths = [
                "/opt/homebrew/bin/ffmpeg",  # Apple Silicon Homebrew
                "/usr/local/bin/ffmpeg",     # Intel Homebrew
                "/opt/homebrew/opt/ffmpeg/bin/ffmpeg",  # Homebrew formula path
            ]
            possible_paths.extend(homebrew_paths)
        
        # Add Linux common paths
        if is_linux:
            linux_paths = [
                "/usr/bin/ffmpeg",           # Standard system path
                "/usr/local/bin/ffmpeg",     # User-installed
                "/snap/bin/ffmpeg",          # Snap package
            ]
            possible_paths.extend(linux_paths)
        
        # Use shell=True on Windows, shell=False on Unix
        use_shell = is_windows
        
        for path in possible_paths:
            if path is None:
                continue
                
            try:
                # Test the ffmpeg path
                result = subprocess.run([path, '-version'], 
                                      capture_output=True, text=True, timeout=10, shell=use_shell)
                if result.returncode == 0:
                    self.ffmpeg_path = path
                    version_line = result.stdout.split('\n')[0]
                    print(f"✅ FFmpeg found at: {path}")
                    print(f"✅ Version: {version_line}")
                    return True
            except Exception as e:
                continue
        
        # OS-specific installation instructions
        print("❌ FFmpeg not found! Install it with:")
        if is_windows:
            print("   Windows: winget install ffmpeg")
            print("   Or download from: https://ffmpeg.org/download.html")
        elif is_macos:
            print("   macOS: brew install ffmpeg")
        elif is_linux:
            print("   Linux: sudo apt install ffmpeg")
            print("   Or: sudo yum install ffmpeg")
            print("   Or: sudo snap install ffmpeg")
        else:
            print("   Visit: https://ffmpeg.org/download.html")
        print("   Then restart the script")
        
        self.ffmpeg_path = None
        return False

    def load_downloaded_events(self):
        """Load list of previously downloaded events"""
        try:
            downloaded_file = self.save_path / "downloaded_events.txt"
            if downloaded_file.exists():
                with open(downloaded_file, 'r') as f:
                    self.downloaded_events = set(line.strip() for line in f.readlines())
                print(f"📋 Loaded {len(self.downloaded_events)} previously downloaded events")
            else:
                print("📋 No previous download history found")
        except Exception as e:
            print(f"Error loading download history: {e}")

    def save_downloaded_events(self):
        """Save list of downloaded events"""
        try:
            downloaded_file = self.save_path / "downloaded_events.txt"
            with open(downloaded_file, 'w') as f:
                for event_id in sorted(self.downloaded_events):
                    f.write(f"{event_id}\n")
        except Exception as e:
            print(f"Error saving download history: {e}")

    def init_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            print(f"Chrome driver error: {e}")
            return False

    def load_all_events(self):
        """Load main page and scroll to get all events"""
        print("Loading main page and scrolling...")
        
        self.driver.get(self.base_url)
        time.sleep(5)
        
        # Scroll to load events
        try:
            scroll_container = self.driver.find_element(By.CSS_SELECTOR, "#scroll-wrap")
            for i in range(15):
                print(f"Scroll {i+1}/15...")
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollTop - 500", scroll_container)
                time.sleep(2)
            print("Waiting for all content...")
            time.sleep(20)
        except Exception as e:
            print(f"Scroll error: {e}")
        
        # Find all meeting elements
        all_elements = self.driver.find_elements(By.CSS_SELECTOR, "[id^='listItemText-']")
        meeting_elements = []
        
        for elem in all_elements:
            elem_id = elem.get_attribute("id")
            if re.match(r'listItemText-\d+$', elem_id):
                meeting_elements.append(elem)
        
        print(f"Found {len(meeting_elements)} meeting elements loaded")
        
        # Filter for recent events (last 1 week, past events only)
        recent_events = []
        current_date = datetime.now()
        one_week_ago = current_date - timedelta(days=14)
        print(f"📅 Current system time: {current_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Looking for events after: {one_week_ago.strftime('%Y-%m-%d')}")
        
        for element in reversed(meeting_elements):  # Process newest first
            try:
                element_text = element.text.strip()
                element_id = element.get_attribute("id")
                event_number = re.search(r'(\d+)', element_id).group(1)
                
                # CHECK IF ALREADY DOWNLOADED - SKIP IF YES
                if event_number in self.downloaded_events:
                    print(f"⏭️ Skipping Event #{event_number} - already downloaded")
                    continue
                
                # Parse date
                date_match = re.search(r'(\w+)\s+(\w+)\s+(\d+),\s+(\d+)', element_text)
                if date_match:
                    try:
                        month_name = date_match.group(2)
                        day = int(date_match.group(3))
                        year = int(date_match.group(4))
                    except ValueError as e:
                        print(f"Date parse error for event #{event_number}: {e} - skipping")
                        continue
                    
                    month_map = {
                        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                    }
                    month = month_map.get(month_name, 6)
                    event_date = datetime(year, month, day)
                    
                    # ONLY INCLUDE PAST EVENTS FROM LAST 1 WEEK (not future events)
                    if one_week_ago <= event_date <= current_date:
                        recent_events.append({
                            'element': element,
                            'event_number': event_number,
                            'title': element_text,
                            'date': event_date
                        })
                        print(f"✓ Found NEW past event #{event_number}: {element_text[:40]}...")
                    else:
                        if event_date > current_date:
                            print(f"⏭️ Skipping future event #{event_number} from {event_date.strftime('%Y-%m-%d')} (no video yet)")
                        else:
                            print(f"⏳ Skipping old event #{event_number} from {event_date.strftime('%Y-%m-%d')} (older than 1 week)")
                        
            except Exception as e:
                print(f"Date parse error: {e}")
        
        print(f"Found {len(recent_events)} NEW past events (last 1 week, no future events)")
        return recent_events

    def process_single_meeting(self, event_info):
        """Process one meeting - click, check for video, download"""
        print(f"\n--- Processing Event #{event_info['event_number']} ---")
        print(f"Title: {event_info['title'][:60]}...")
        
        try:
            # Remember main tab
            main_tab = self.driver.current_window_handle
            original_tabs = self.driver.window_handles
            
            # Click the meeting element
            print("Clicking meeting element...")
            self.driver.execute_script("arguments[0].click();", event_info['element'])
            time.sleep(8)
            
            # Check for new tab
            new_tabs = self.driver.window_handles
            if len(new_tabs) > len(original_tabs):
                # New tab opened - switch to it
                new_tab = [tab for tab in new_tabs if tab not in original_tabs][0]
                self.driver.switch_to.window(new_tab)
                print("✓ Switched to new meeting page tab")
                
                current_url = self.driver.current_url
                print(f"URL: {current_url}")
                
                if 'civicclerk.com/event' in current_url:
                    # Look for Meeting Media button
                    print("Looking for Meeting Media button...")
                    media_selectors = [
                        "#MeetingMedia",
                        "#MeetingMedia > span.cpp-MuiIconButton-label > span",
                        "#MeetingMedia > span.cpp-MuiIconButton-label"
                    ]
                    
                    media_button = None
                    for selector in media_selectors:
                        try:
                            media_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            print(f"✓ Found Meeting Media button")
                            break
                        except:
                            continue
                    
                    if media_button:
                        # Click Meeting Media
                        print("Clicking Meeting Media button...")
                        self.driver.execute_script("arguments[0].click();", media_button)
                        time.sleep(5)
                        
                        # Look for video link
                        print("Looking for video link...")
                        video_selectors = [
                            "#EventDetailsVideo a",
                            "a[href*='zoom']",
                            "a[href*='zoomgov']",
                            "a[href*='rec/play']"
                        ]
                        
                        video_url = None
                        for selector in video_selectors:
                            try:
                                video_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                video_url = video_element.get_attribute("href")
                                if video_url and ('zoom' in video_url or 'rec' in video_url):
                                    print(f"✓ Found video URL!")
                                    break
                            except:
                                continue
                        
                        if video_url:
                            # Start download with direct folder creation
                            success = self.start_download(video_url, event_info['title'], event_info['event_number'], new_tab)
                            if success:
                                print(f"✅ Download started for Event #{event_info['event_number']}")
                                return True
                            else:
                                print(f"❌ Download failed for Event #{event_info['event_number']}")
                                # Close tab if download failed
                                self.driver.close()
                                self.driver.switch_to.window(main_tab)
                        else:
                            # Check for "no video" message
                            if 'no video' in self.driver.page_source.lower():
                                print("ℹ️ No video available for this event")
                            else:
                                print("✗ No video link found")
                            
                            # Close tab - no video found
                            print("Closing meeting tab...")
                            self.driver.close()
                            self.driver.switch_to.window(main_tab)
                            print("✓ Back to main tab with all events loaded")
                    else:
                        print("✗ Meeting Media button not found")
                        # Close tab - no media button
                        self.driver.close()
                        self.driver.switch_to.window(main_tab)
                else:
                    print("✗ Not a meeting page")
                    # Close tab - not a meeting page
                    self.driver.close()
                    self.driver.switch_to.window(main_tab)
                
            else:
                print("✗ No new tab opened")
            
            return False
            
        except Exception as e:
            print(f"Error processing meeting: {e}")
            # Make sure we're back on main tab
            try:
                self.driver.switch_to.window(main_tab)
            except:
                pass
            return False

    def start_download(self, video_url, event_title, event_number, tab_handle):
        """Download directly to unique folder with meeting info"""
        print(f"Starting download for Event #{event_number}")
        
        try:
            # Go to video URL in current tab
            self.driver.get(video_url)
            time.sleep(10)
            
            # Extract meeting name and date from Zoom page
            meeting_name = "Unknown_Meeting"
            meeting_date = "Unknown_Date"
            
            try:
                print("📋 Extracting meeting info from Zoom page...")
                
                # Extract meeting name
                name_element = self.driver.find_element(By.CSS_SELECTOR, "#app > header > div.header-left > div.header-info > h1 > span.topic")
                meeting_name = name_element.text.strip()
                print(f"📋 Meeting Name: {meeting_name}")
                
                # Extract date
                try:
                    date_element = self.driver.find_element(By.CSS_SELECTOR, "#app > header > div.header-left > div.header-info > div > span")
                    meeting_date = date_element.text.strip()
                    print(f"📅 Meeting Date: {meeting_date}")
                except Exception as e:
                    print(f"⚠️ Could not extract date from Zoom: {e}")
                
            except Exception as e:
                print(f"⚠️ Could not extract meeting info from Zoom page: {e}")
                meeting_name = "Unknown_Meeting"
                meeting_date = "Unknown_Date"
            
            # Create unique download folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_meeting_name = self.sanitize_filename(meeting_name)
            folder_name = f"{timestamp}_{clean_meeting_name}_{event_number}"
            download_folder = self.save_path / folder_name
            download_folder.mkdir(exist_ok=True)
            
            print(f"📁 Created download folder: {folder_name}")
            
            # Create info.txt with all meeting details
            info_data = {
                'event_number': event_number,
                'meeting_name': meeting_name,
                'meeting_date': meeting_date,
                'event_title': event_title,
                'video_url': video_url,
                'download_timestamp': timestamp,
                'folder_name': folder_name
            }
            
            info_file = download_folder / "info.txt"
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write("BROOKLINE MEETING DOWNLOAD INFO\n")
                f.write("="*40 + "\n")
                f.write(f"Event Number: {event_number}\n")
                f.write(f"Meeting Name: {meeting_name}\n")
                f.write(f"Meeting Date: {meeting_date}\n")
                f.write(f"Event Title: {event_title}\n")
                f.write(f"Video URL: {video_url}\n")
                f.write(f"Download Timestamp: {timestamp}\n")
                f.write(f"Folder Name: {folder_name}\n")
                f.write("="*40 + "\n")
            
            print(f"📄 Created info.txt with meeting details")
            
            # Change Chrome download directory to this specific folder
            self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(download_folder.absolute())
            })
            
            print(f"📁 Changed download directory to: {download_folder}")
            
            # Look for download button
            download_selectors = [
                "#app header .header-right a",
                ".download-btn",
                "a[download]"
            ]
            
            download_button = None
            for selector in download_selectors:
                try:
                    download_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if download_button:
                # Click download
                download_button.click()
                print("✓ Download initiated!")
                
                # Track this tab for later cleanup
                download_info = {
                    'tab': tab_handle,
                    'event_number': event_number,
                    'event_title': event_title,
                    'meeting_name': meeting_name,
                    'folder_name': folder_name,
                    'download_folder': download_folder,
                    'start_time': time.time()
                }
                self.downloading_tabs.append(download_info)
                
                # MARK EVENT AS DOWNLOADED
                self.downloaded_events.add(event_number)
                self.save_downloaded_events()
                
                # Go back to main tab immediately
                main_tab = [tab for tab in self.driver.window_handles if tab != tab_handle][0]
                self.driver.switch_to.window(main_tab)
                print("✓ Back to main tab - download continues in background")
                
                return True
            else:
                print("✗ Download button not found")
                return False
                
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def cleanup_old_download_tabs(self):
        """Close tabs that have been downloading for more than 5 minutes"""
        current_time = time.time()
        tabs_to_remove = []
        
        for download_info in self.downloading_tabs:
            time_elapsed = current_time - download_info['start_time']
            
            if time_elapsed > 300:  # 5 minutes
                try:
                    # Switch to download tab and close it
                    if download_info['tab'] in self.driver.window_handles:
                        self.driver.switch_to.window(download_info['tab'])
                        self.driver.close()
                        print(f"✓ Closed download tab for Event #{download_info['event_number']} (5 min timeout)")
                    tabs_to_remove.append(download_info)
                except:
                    tabs_to_remove.append(download_info)
        
        # Remove closed tabs from tracking
        for tab_info in tabs_to_remove:
            self.downloading_tabs.remove(tab_info)
        
        # Switch back to main tab
        try:
            main_tab = self.driver.window_handles[0]
            self.driver.switch_to.window(main_tab)
        except:
            pass

    def limit_open_tabs(self):
        """Keep max 10 tabs open - close oldest download tabs if needed"""
        total_tabs = len(self.driver.window_handles)
        
        if total_tabs > 10:
            # Close oldest download tabs
            tabs_to_close = total_tabs - 10
            oldest_downloads = sorted(self.downloading_tabs, key=lambda x: x['start_time'])[:tabs_to_close]
            
            for download_info in oldest_downloads:
                try:
                    if download_info['tab'] in self.driver.window_handles:
                        self.driver.switch_to.window(download_info['tab'])
                        self.driver.close()
                        print(f"✓ Closed tab for Event #{download_info['event_number']} (tab limit)")
                    self.downloading_tabs.remove(download_info)
                except:
                    pass
            
            # Switch back to main tab
            try:
                main_tab = self.driver.window_handles[0]
                self.driver.switch_to.window(main_tab)
            except:
                pass

    def process_downloaded_files(self):
        """Process all downloaded files - organize and convert (IMPROVED VERSION)"""
        print("\n📁 Processing downloaded files...")
        
        # Check FFmpeg first
        if not self.ffmpeg_path:
            print("❌ FFmpeg not available - cannot convert videos")
            print("   Install FFmpeg and restart the script")
            return
        
        # Find ALL download folders - both original format AND other formats
        download_folders = []
        
        for folder in self.save_path.iterdir():
            if folder.is_dir():
                # Original format: timestamp_meetingname_eventid
                if re.match(r'\d{8}_\d{6}_.*_\d+$', folder.name):
                    download_folders.append(folder)
                    print(f"📁 Found original format folder: {folder.name}")
                # NEW: Any folder that contains video files (check recursively in subfolders too)
                elif any(folder.glob("*.mp4")) or any(folder.glob("*.m4a")) or any(folder.rglob("*.mp4")) or any(folder.rglob("*.m4a")):
                    download_folders.append(folder)
                    print(f"📁 Found video folder: {folder.name}")
        
        print(f"📁 Found {len(download_folders)} download folders to process")
        
        processed_count = 0
        for folder in download_folders:
            print(f"\n📁 Processing folder: {folder.name}")
            
            # Check for video files - both direct and in subfolders
            video_files = list(folder.glob("*.mp4")) + list(folder.glob("*.m4a"))
            video_files_recursive = list(folder.rglob("*.mp4")) + list(folder.rglob("*.m4a"))
            
            # Remove duplicates and corrected_format files
            all_video_files = []
            for video in video_files_recursive:
                # Skip files already in corrected_format folder
                if "corrected_format" not in str(video):
                    all_video_files.append(video)
            
            if not all_video_files:
                print(f"⚠️ No video files found in {folder.name}")
                continue
            
            print(f"📹 Found {len(all_video_files)} video files in {folder.name} (including subfolders)")
            
            # Show where videos were found
            for video in all_video_files:
                relative_path = video.relative_to(folder)
                # Verify file actually exists
                if video.exists():
                    file_size_mb = video.stat().st_size / (1024 * 1024)
                    print(f"  📄 {relative_path} ({file_size_mb:.1f} MB) ✓")
                else:
                    print(f"  📄 {relative_path} ❌ FILE NOT FOUND")
            
            # Create corrected_format subfolder
            corrected_folder = folder / "corrected_format"
            corrected_folder.mkdir(exist_ok=True)
            print(f"📁 Created corrected_format folder")
            
            # Convert each video file
            converted_count = 0
            for video_file in all_video_files:
                success = self.convert_video(video_file, corrected_folder, folder.name)
                if success:
                    converted_count += 1
            
            print(f"✅ Converted {converted_count}/{len(all_video_files)} videos in {folder.name}")
            processed_count += 1
        
        print(f"\n✅ Processed {processed_count} download folders")

    def convert_video(self, video_path, output_dir, folder_name):
        """Convert single video to 29.97fps and limit resolution to 1920x1080 (IMPROVED VERSION)"""
        try:
            # Check if FFmpeg is available
            if not self.ffmpeg_path:
                print(f"❌ FFmpeg not available - skipping {video_path.name}")
                return False
            
            # Verify input file exists
            if not video_path.exists():
                print(f"❌ Input file not found: {video_path}")
                return False
            
            # IMPROVED: Extract meeting name from folder name with flexible parsing
            meeting_name = "Unknown_Meeting"
            
            # Check if it's the original format: timestamp_meetingname_eventid
            if re.match(r'\d{8}_\d{6}_.*_\d+$', folder_name):
                # Original format - extract meeting name between timestamp and event_id
                folder_parts = folder_name.split('_')
                if len(folder_parts) >= 3:
                    meeting_name = '_'.join(folder_parts[2:-1])  # Everything between timestamp and event_id
            else:
                # NEW: For other formats like "Week_20250728", use the folder name itself
                meeting_name = folder_name
            
            # If video is in a subfolder, include subfolder name in the meeting name
            video_parent = video_path.parent.name
            if video_parent != folder_name and video_parent != "corrected_format":
                meeting_name = f"{meeting_name}_{video_parent}"
            
            # Clean up meeting name for filename
            meeting_name = self.sanitize_filename(meeting_name)
            
            # Create output filename with meeting name
            input_filename = video_path.stem
            output_filename = f"{meeting_name}_{input_filename}_29.97fps_1080p{video_path.suffix}"
            output_path = output_dir / output_filename
            
            # Skip if already converted
            if output_path.exists():
                print(f"⏭️ Already converted: {output_filename}")
                return True
            
            print(f"🔄 Converting: {video_path.name}")
            print(f"📁 Output: {output_filename}")
            print(f"🔍 Input file check: {video_path.exists()} - Size: {video_path.stat().st_size / (1024*1024):.1f} MB")
            
            # FFmpeg command with proper path handling for Windows
            # Use raw strings and proper quoting
            input_path_str = str(video_path.absolute())
            output_path_str = str(output_path.absolute())
            
            cmd = [
                self.ffmpeg_path,
                '-i', input_path_str,
                '-r', '29.97',  # Set frame rate to 29.97fps
                '-vf', "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease",  # Limit to 1920x1080 max
                '-c:v', 'libx264',  # Video codec
                '-c:a', 'aac',      # Audio codec
                '-preset', 'medium', # Encoding speed/quality balance
                '-crf', '23',       # Quality setting (lower = better quality)
                '-y',               # Overwrite output file
                output_path_str
            ]
            
            print(f"🔧 Using FFmpeg: {self.ffmpeg_path}")
            print(f"🔧 Command: {' '.join(cmd[:3])} ... {cmd[-1]}")
            
            # Run with shell=True on Windows, shell=False on Unix
            use_shell = platform.system() == "Windows"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=use_shell, timeout=600)
            
            if result.returncode == 0:
                print(f"✅ Successfully converted: {output_filename}")
                
                # Verify output file exists and has reasonable size
                if output_path.exists() and output_path.stat().st_size > 1000:  # At least 1KB
                    file_size_mb = output_path.stat().st_size / (1024 * 1024)
                    print(f"✅ Output file size: {file_size_mb:.1f} MB")
                    return True
                else:
                    print(f"⚠️ Warning: Output file seems too small or missing")
                    return False
            else:
                print(f"❌ FFmpeg error for {video_path.name}:")
                print(f"❌ Return code: {result.returncode}")
                print(f"❌ Error output: {result.stderr[:300]}...")  # Show first 300 chars of error
                if result.stdout:
                    print(f"📝 FFmpeg stdout: {result.stdout[:200]}...")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ FFmpeg timeout for {video_path.name} (took longer than 10 minutes)")
            return False
        except Exception as e:
            print(f"❌ Convert error for {video_path}: {e}")
            return False

    def sanitize_filename(self, filename):
        """Clean filename by removing invalid characters (cross-platform)"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()[:100]  # Limit length

    def auto_refresh_scheduler(self):
        """Auto refresh every 6 hours - only works if schedule module is available"""
        if not SCHEDULE_AVAILABLE:
            print("❌ Auto refresh not available - 'schedule' module not installed")
            return
        
        schedule.every(6).hours.do(self.run_download_scan)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def start_auto_refresh(self):
        """Start auto refresh in background - only works if schedule module is available"""
        if not SCHEDULE_AVAILABLE:
            print("❌ Auto refresh not available - install with: pip install schedule")
            return None
        
        print("🔄 Starting auto refresh - will scan every 6 hours")
        refresh_thread = threading.Thread(target=self.auto_refresh_scheduler, daemon=True)
        refresh_thread.start()
        return refresh_thread

    def stop_auto_refresh(self):
        """Stop auto refresh"""
        self.running = False
        if SCHEDULE_AVAILABLE:
            schedule.clear()
        print("⏹️ Auto refresh stopped")

    def run_download_scan(self):
        """Main scan function - processes ALL available recent events"""
        print(f"\n{'='*60}")
        print("BROOKLINE VIDEO DOWNLOADER - DIRECT FOLDER MODE")
        print("Each download goes to dedicated folder with info.txt")
        print(f"Scan started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        if not self.init_driver():
            print("Failed to initialize Chrome driver")
            return
        
        try:
            # Step 1: Load main page and get all recent events
            recent_events = self.load_all_events()
            
            if not recent_events:
                print("No new recent events found")
                return
            
            print(f"\nWill process {len(recent_events)} NEW recent events...")
            downloaded_count = 0
            
            # Step 2: Process each event (download directly to folders)
            for i, event in enumerate(recent_events, 1):
                print(f"\n{'='*40}")
                print(f"Processing {i}/{len(recent_events)}")
                
                # Clean up old download tabs every 10 events
                if i % 10 == 0:
                    self.cleanup_old_download_tabs()
                
                # Limit tabs to 10 max
                self.limit_open_tabs()
                
                success = self.process_single_meeting(event)
                if success:
                    downloaded_count += 1
                
                time.sleep(2)  # Brief pause between events
            
            # Step 3: Wait for downloads to complete
            print(f"\n{'='*60}")
            print("🔄 Waiting for downloads to complete...")
            
            # Wait for downloads to finish
            time.sleep(60)  # 1 minute
            
            # Close all remaining download tabs
            print("🔄 Closing remaining download tabs...")
            for download_info in self.downloading_tabs[:]:
                try:
                    if download_info['tab'] in self.driver.window_handles:
                        self.driver.switch_to.window(download_info['tab'])
                        self.driver.close()
                        print(f"✓ Closed download tab for Event #{download_info['event_number']}")
                except:
                    pass
            
            # Switch back to main tab
            try:
                main_tab = self.driver.window_handles[0]
                self.driver.switch_to.window(main_tab)
            except:
                pass
            
            # Step 4: Process downloaded files (convert videos)
            print("🔄 Processing downloaded files and converting videos...")
            self.process_downloaded_files()
            
            # Step 5: Summary
            print(f"\n{'='*60}")
            print("✅ SCAN COMPLETED!")
            print(f"📊 Total events processed: {len(recent_events)}")
            print(f"📥 Downloads initiated: {downloaded_count}")
            print(f"📁 Save location: {self.save_path}")
            
            # List the download folders
            print(f"\n📂 DOWNLOAD FOLDERS:")
            download_folders = [f for f in self.save_path.iterdir() if f.is_dir() and re.match(r'\d{8}_\d{6}_.*_\d+$', f.name)]
            if download_folders:
                for folder in sorted(download_folders):
                    info_file = folder / "info.txt"
                    corrected_folder = folder / "corrected_format"
                    video_files = list(folder.glob("*.mp4")) + list(folder.glob("*.m4a"))
                    converted_files = list(corrected_folder.glob("*.mp4")) if corrected_folder.exists() else []
                    
                    print(f"📁 {folder.name}/")
                    if info_file.exists():
                        print(f"  📄 info.txt ✓")
                    print(f"  📹 {len(video_files)} video files")
                    if corrected_folder.exists():
                        print(f"  📁 corrected_format/ ({len(converted_files)} converted files)")
            else:
                print("  No download folders found yet")
            
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"Scan error: {e}")
        finally:
            try:
                self.driver.quit()
            except:
                pass

    def run_interface(self):
        """Interactive menu with direct folder download options"""
        print("BROOKLINE VIDEO DOWNLOADER - DIRECT FOLDER MODE")
        print("Features: Direct folder downloads, meeting names from Zoom, info.txt per folder, 29.97fps conversion")
        
        auto_thread = None
        
        while True:
            print(f"\n{'='*50}")
            print("OPTIONS:")
            print("1. Single scan and download (all recent events)")
            print("2. Start auto refresh (every 6 hours)")
            print("3. Stop auto refresh")
            print("4. View downloaded events list")
            print("5. Clear download history")
            print("6. Check download folders")
            print("7. Process downloaded files only (convert videos)")
            print("8. Exit")
            print(f"{'='*50}")
            
            choice = input("Select option (1-8): ").strip()
            
            if choice == '1':
                print("🔄 Starting scan - direct folder downloads with info.txt")
                self.run_download_scan()
                
            elif choice == '2':
                if not SCHEDULE_AVAILABLE:
                    print("❌ Auto refresh not available - install with: pip install schedule")
                elif auto_thread and auto_thread.is_alive():
                    print("Auto refresh is already running!")
                else:
                    auto_thread = self.start_auto_refresh()
                    if auto_thread:
                        print("✅ Auto refresh started! Will scan every 6 hours.")
                    
            elif choice == '3':
                self.stop_auto_refresh()
                
            elif choice == '4':
                print(f"\n📋 Downloaded Events ({len(self.downloaded_events)} total):")
                if self.downloaded_events:
                    # Find download folders to show names
                    download_folders = {f.name.split('_')[-1]: f for f in self.save_path.iterdir() 
                                      if f.is_dir() and re.match(r'\d{8}_\d{6}_.*_\d+$', f.name)}
                    
                    for event_id in sorted(self.downloaded_events):
                        folder_name = "Unknown folder"
                        for folder_key, folder in download_folders.items():
                            if folder_key == event_id:
                                folder_name = folder.name
                                break
                        print(f"  - Event #{event_id}: {folder_name}")
                else:
                    print("  No events downloaded yet")
                    
            elif choice == '5':
                confirm = input("Clear all download history? (y/N): ").strip().lower()
                if confirm == 'y':
                    self.downloaded_events.clear()
                    self.save_downloaded_events()
                    print("✅ Download history cleared")
                else:
                    print("❌ Cancelled")
            
            elif choice == '6':
                print(f"\n📂 CHECKING DOWNLOAD FOLDERS IN: {self.save_path}")
                download_folders = [f for f in self.save_path.iterdir() if f.is_dir() and re.match(r'\d{8}_\d{6}_.*_\d+$', f.name)]
                
                if download_folders:
                    for folder in sorted(download_folders):
                        print(f"\n📁 {folder.name}/")
                        
                        # Check info.txt
                        info_file = folder / "info.txt"
                        if info_file.exists():
                            print(f"  📄 info.txt ✓")
                            try:
                                with open(info_file, 'r', encoding='utf-8') as f:
                                    for line in f.readlines()[:10]:  # First 10 lines
                                        if line.strip() and not line.startswith('='):
                                            print(f"    {line.strip()}")
                            except:
                                print(f"    (Could not read info.txt)")
                        else:
                            print(f"  📄 info.txt ❌")
                        
                        # Check video files
                        video_files = list(folder.glob("*.mp4")) + list(folder.glob("*.m4a"))
                        print(f"  📹 Video files: {len(video_files)}")
                        for video in video_files:
                            size_mb = video.stat().st_size / (1024 * 1024)
                            print(f"    📄 {video.name} ({size_mb:.1f} MB)")
                        
                        # Check corrected_format
                        corrected_folder = folder / "corrected_format"
                        if corrected_folder.exists():
                            converted_files = list(corrected_folder.glob("*.mp4"))
                            print(f"  📁 corrected_format/ ({len(converted_files)} converted)")
                            for converted in converted_files:
                                size_mb = converted.stat().st_size / (1024 * 1024)
                                print(f"    🎥 {converted.name} ({size_mb:.1f} MB)")
                        else:
                            print(f"  📁 corrected_format/ ❌")
                else:
                    print("  No download folders found")
            
            elif choice == '7':
                print("🔄 Processing downloaded files and converting videos...")
                self.process_downloaded_files()
                
            elif choice == '8':
                print("Exiting...")
                self.stop_auto_refresh()
                if self.driver:
                    self.driver.quit()
                break
                
            else:
                print("Invalid choice! Please select 1-8.")

if __name__ == "__main__":
    downloader = SimpleBrooklineDownloader()
    downloader.run_interface()