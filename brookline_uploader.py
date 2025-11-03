import os
import time
import threading
import schedule
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json

class BrooklineCablecastUploader:
    def __init__(self):
        # Website credentials and URLs
        self.login_url = "http://brookline-interactive-group.cablecast.tv:8080/"
        self.username = "charles-intern@brooklineinteractive.org"
        self.password = "FVvta;*tx]];Q?"
        self.main_menu_url = "http://brookline-interactive-group.cablecast.tv:8080/FrontDoor/MainMenu.aspx"
        self.cablecast_url = "http://brookline-interactive-group.cablecast.tv:8080/CablecastUI/#/?location_id=1"
        
        # File paths - sync with downloader script
        self.watch_path = Path("C:/govideosav")  # Same as downloader
        self.upload_log_file = self.watch_path / "uploaded_files.json"
        
        # Tracking
        self.uploaded_files = set()
        self.driver = None
        self.running = True
        self.logged_in = False
        self.uploading_tabs = []  # Track tabs with uploads
        
        # Chrome options for anti-detection
        self.chrome_options = Options()
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-logging")
        self.chrome_options.add_argument("--log-level=3")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Load upload history
        self.load_upload_history()
        
        # Ensure watch path exists
        self.watch_path.mkdir(exist_ok=True)

    def load_upload_history(self):
        """Load previously uploaded files to avoid duplicates"""
        try:
            if self.upload_log_file.exists():
                with open(self.upload_log_file, 'r') as f:
                    data = json.load(f)
                    self.uploaded_files = set(data.get('uploaded_files', []))
                print(f"📋 Loaded {len(self.uploaded_files)} previously uploaded files")
            else:
                print("📋 No previous upload history found")
        except Exception as e:
            print(f"❌ Error loading upload history: {e}")
            self.uploaded_files = set()

    def save_upload_history(self):
        """Save uploaded files list"""
        try:
            data = {
                'uploaded_files': list(self.uploaded_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.upload_log_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving upload history: {e}")

    def init_driver(self):
        """Initialize Chrome driver with anti-detection measures"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            
            # Execute script to hide automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            self.driver.set_window_size(1920, 1080)
            print("✅ Chrome driver initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Chrome driver error: {e}")
            return False

    def check_login_status(self):
        """Check if we're already logged in to avoid unnecessary login"""
        try:
            current_url = self.driver.current_url
            
            # Check if we're already on the main menu or cablecast page
            if "MainMenu.aspx" in current_url or "CablecastUI" in current_url:
                print("✅ Already logged in - skipping login step")
                self.logged_in = True
                return True
            
            # Check if we're on the login page but session might be valid
            if self.login_url in current_url or current_url == self.login_url:
                # Try to navigate directly to main menu to test session
                self.driver.get(self.main_menu_url)
                time.sleep(3)
                
                if "MainMenu.aspx" in self.driver.current_url:
                    print("✅ Session still valid - already logged in")
                    self.logged_in = True
                    return True
                else:
                    print("🔐 Session expired - need to login")
                    self.logged_in = False
                    return False
            
            return False
            
        except Exception as e:
            print(f"⚠️ Login status check failed: {e}")
            return False

    def login_to_cablecast(self):
        """Login to Cablecast website"""
        try:
            print("🔐 Logging into Cablecast...")
            self.driver.get(self.login_url)
            time.sleep(5)  # Wait for page to fully load
            
            # Find and fill login form using correct selectors
            print("🔍 Looking for username field...")
            username_field = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#Login1_UserName"))
            )
            
            print("🔍 Looking for password field...")
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#Login1_Password"))
            )
            
            print("🔍 Looking for login button...")
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#Login1_LoginButton"))
            )
            
            # Clear and fill username
            print("✏️ Entering username...")
            username_field.clear()
            username_field.send_keys(self.username)
            time.sleep(1)
            
            # Clear and fill password
            print("✏️ Entering password...")
            password_field.clear()
            password_field.send_keys(self.password)
            time.sleep(1)
            
            # Click login button
            print("🔐 Clicking login button...")
            login_button.click()
            
            # Wait for redirect to main menu
            print("⏳ Waiting for login redirect...")
            WebDriverWait(self.driver, 15).until(
                EC.url_contains("MainMenu.aspx")
            )
            
            print("✅ Successfully logged in")
            self.logged_in = True
            return True
            
        except TimeoutException as e:
            print(f"❌ Login timeout - element not found: {e}")
            print(f"Current URL: {self.driver.current_url}")
            
            # Debug: Print page source snippet
            try:
                page_source = self.driver.page_source[:1000]
                print(f"Page source snippet: {page_source}...")
            except:
                pass
                
            self.logged_in = False
            return False
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print(f"Current URL: {self.driver.current_url}")
            self.logged_in = False
            return False

    def navigate_to_assets(self, keep_old_tab=False):
        """Navigate to the Assets section with option to keep old tab"""
        try:
            print("📂 Navigating to Assets...")
            
            # Open new tab and switch to it
            print("📂 Opening new tab for CablecastUI...")
            self.driver.execute_script("window.open('');")
            
            # Switch to the new tab
            new_tab_index = len(self.driver.window_handles) - 1
            self.driver.switch_to.window(self.driver.window_handles[new_tab_index])
            
            # Go DIRECTLY to Assets URL - bypass clicking navigation
            print("📂 Going DIRECTLY to Assets URL...")
            self.driver.get("http://brookline-interactive-group.cablecast.tv:8080/CablecastUI/#/assets?location_id=1")
            
            # Wait for Assets page to load
            time.sleep(10)
            
            # Only close old tab if not keeping it (and if there's more than one tab)
            if not keep_old_tab and len(self.driver.window_handles) > 1:
                # Find and close the old MainMenu tab (first tab)
                for i, handle in enumerate(self.driver.window_handles[:-1]):  # All except current new tab
                    try:
                        old_tab = self.driver.current_window_handle
                        self.driver.switch_to.window(handle)
                        current_title = self.driver.execute_script("return document.title;")
                        if "MainMenu" in current_title or i == 0:
                            print("📂 Closing old MainMenu tab...")
                            self.driver.close()
                            self.driver.switch_to.window(old_tab)
                            break
                        else:
                            self.driver.switch_to.window(old_tab)
                    except:
                        try:
                            self.driver.switch_to.window(old_tab)
                        except:
                            pass
            
            print("✅ Successfully navigated to Assets page")
            print(f"📍 Current URL: {self.driver.current_url}")
            
            time.sleep(3)
            return self.driver.current_window_handle
            
        except Exception as e:
            print(f"❌ Failed to navigate to assets: {e}")
            return None

    def cleanup_old_upload_tabs(self):
        """Close tabs that have been uploading for more than 5 minutes"""
        current_time = time.time()
        tabs_to_remove = []
        
        for upload_info in self.uploading_tabs:
            time_elapsed = current_time - upload_info['start_time']
            
            if time_elapsed > 720:  # 12 minutes
                try:
                    # Switch to upload tab and close it
                    if upload_info['tab'] in self.driver.window_handles:
                        current_tab = self.driver.current_window_handle
                        self.driver.switch_to.window(upload_info['tab'])
                        self.driver.close()
                        print(f"✓ Closed upload tab for {upload_info['filename']} (5 min timeout)")
                        # Switch back to a valid tab
                        try:
                            if current_tab in self.driver.window_handles:
                                self.driver.switch_to.window(current_tab)
                            else:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                        except:
                            if self.driver.window_handles:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                    tabs_to_remove.append(upload_info)
                except:
                    tabs_to_remove.append(upload_info)
        
        # Remove closed tabs from tracking
        for tab_info in tabs_to_remove:
            self.uploading_tabs.remove(tab_info)

    def limit_open_upload_tabs(self):
        """Keep max 10 upload tabs open"""
        total_tabs = len(self.driver.window_handles)
        
        if total_tabs > 10:
            # Close oldest upload tabs
            tabs_to_close = total_tabs - 10
            oldest_uploads = sorted(self.uploading_tabs, key=lambda x: x['start_time'])[:tabs_to_close]
            
            for upload_info in oldest_uploads:
                try:
                    if upload_info['tab'] in self.driver.window_handles:
                        current_tab = self.driver.current_window_handle
                        self.driver.switch_to.window(upload_info['tab'])
                        self.driver.close()
                        print(f"✓ Closed tab for {upload_info['filename']} (tab limit)")
                        # Switch back to a valid tab
                        try:
                            if current_tab in self.driver.window_handles:
                                self.driver.switch_to.window(current_tab)
                            else:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                        except:
                            if self.driver.window_handles:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                    self.uploading_tabs.remove(upload_info)
                except:
                    try:
                        self.uploading_tabs.remove(upload_info)
                    except:
                        pass

    def wait_for_upload_slots(self, max_concurrent=10):
        """Wait until we have available upload slots"""
        while len(self.uploading_tabs) >= max_concurrent:
            print(f"⏳ Waiting for upload slots ({len(self.uploading_tabs)}/{max_concurrent} busy)...")
            time.sleep(30)  # Wait 30 seconds
            self.cleanup_old_upload_tabs()  # Clean up finished uploads

    def upload_file(self, file_path):
        """Upload a single file"""
        try:
            print(f"📤 Starting upload for: {file_path.name}")
            
            # Click Upload button
            upload_selectors = [
                "#ember319 > div.canvas > div.container-fluid > div > div.row.assets-view-currentlyshowing > p > button.btn.btn-default.assets-view-uploadbutton",
                "button.assets-view-uploadbutton",
                "button[class*='upload']",
                ".btn.btn-default.assets-view-uploadbutton"
            ]
            
            upload_clicked = False
            for selector in upload_selectors:
                try:
                    upload_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    upload_button.click()
                    upload_clicked = True
                    print(f"✅ Upload button clicked using: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not upload_clicked:
                # Try finding by text
                upload_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Upload') or contains(text(), 'upload')]"))
                )
                upload_button.click()
                print("✅ Upload button clicked using text search")
            
            time.sleep(2)
            
            # Select file input
            file_input_selectors = [
                "#ember2781 > div > div > input",
                "input[type='file']",
                "input[accept*='mp4']"
            ]
            
            file_input_found = False
            for selector in file_input_selectors:
                try:
                    file_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    file_input.send_keys(str(file_path.absolute()))
                    file_input_found = True
                    print(f"✅ File selected using: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not file_input_found:
                print("❌ Could not find file input")
                return False
            
            time.sleep(3)
            
            # Select file store - search for "Flex 4 Content" option
            print("🗃️ Selecting file store...")
            try:
                # Try multiple approaches to find and select filestore
                filestore_selected = False
                
                # Method 1: Find any select dropdown and look for "Flex 4 Content"
                try:
                    select_elements = self.driver.find_elements(By.TAG_NAME, "select")
                    for select_elem in select_elements:
                        options = select_elem.find_elements(By.TAG_NAME, "option")
                        for option in options:
                            if "Flex 4 Content" in option.text or "Flex" in option.text:
                                print(f"✅ Found Flex 4 Content option: {option.text}")
                                option.click()
                                filestore_selected = True
                                print("✅ File store selected using text search")
                                break
                        if filestore_selected:
                            break
                except Exception as e:
                    print(f"Method 1 failed: {e}")
                
                # Method 2: Try dynamic ember IDs if Method 1 failed
                if not filestore_selected:
                    dynamic_selectors = [
                        "#ember4375",
                        "#ember4369", 
                        "#ember4199",
                        "#ember3839"
                    ]
                    
                    for selector in dynamic_selectors:
                        try:
                            filestore_dropdown = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            filestore_dropdown.click()
                            time.sleep(1)
                            
                            # Select the option containing "Flex"
                            first_option = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, f"{selector} option:nth-child(2)"))
                            )
                            first_option.click()
                            filestore_selected = True
                            print(f"✅ File store selected using: {selector}")
                            break
                        except:
                            continue
                
                # Method 3: JavaScript execution as last resort
                if not filestore_selected:
                    try:
                        js_script = '''
                        var selects = document.querySelectorAll('select');
                        for(var i = 0; i < selects.length; i++) {
                            var options = selects[i].querySelectorAll('option');
                            for(var j = 0; j < options.length; j++) {
                                if(options[j].textContent.includes('Flex')) {
                                    selects[i].value = options[j].value;
                                    selects[i].dispatchEvent(new Event('change'));
                                    return 'SUCCESS';
                                }
                            }
                        }
                        return 'FAILED';
                        '''
                        result = self.driver.execute_script(js_script)
                        if result == 'SUCCESS':
                            filestore_selected = True
                            print("✅ File store selected using JavaScript")
                    except Exception as e:
                        print(f"JavaScript method failed: {e}")
                
                if not filestore_selected:
                    print("⚠️ Could not select file store - proceeding anyway")
                    
            except Exception as e:
                print(f"⚠️ File store selection error: {e} - proceeding anyway")
            
            time.sleep(2)
            
            # Click final Upload button
            final_upload_selectors = [
                "#ember2782 > div > button.btn.btn-primary",
                "button.btn.btn-primary",
                "button[class*='btn-primary']"
            ]
            
            final_upload_clicked = False
            for selector in final_upload_selectors:
                try:
                    final_upload_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    final_upload_button.click()
                    final_upload_clicked = True
                    print(f"✅ Final upload button clicked using: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not final_upload_clicked:
                # Try finding by text
                final_upload_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Upload') and contains(@class, 'btn-primary')]"))
                )
                final_upload_button.click()
                print("✅ Final upload button clicked using text search")
            
            # Track this tab for later cleanup instead of closing immediately
            upload_info = {
                'tab': self.driver.current_window_handle,
                'filename': file_path.name,
                'start_time': time.time()
            }
            self.uploading_tabs.append(upload_info)
            
            print(f"✅ Upload initiated for: {file_path.name}")
            print(f"📊 Upload tab will close automatically in 5 minutes...")
            
            # Wait for upload to start
            time.sleep(5)
            
            # Mark as uploaded
            self.uploaded_files.add(str(file_path.relative_to(self.watch_path)))
            self.save_upload_history()
            
            print(f"✅ Successfully started upload: {file_path.name}")
            return True
            
        except Exception as e:
            print(f"❌ Upload failed for {file_path.name}: {e}")
            return False

    def find_files_to_upload(self):
        """Find new video files in corrected_format folders"""
        files_to_upload = []
        
        try:
            # Look for ALL folders that contain corrected_format subfolders
            # Not just Week_ folders, but any folder structure
            all_folders = [f for f in self.watch_path.iterdir() if f.is_dir()]
            
            print(f"📁 Scanning {len(all_folders)} folders for corrected_format subfolders...")
            
            for folder in all_folders:
                corrected_folder = folder / "corrected_format"
                
                if corrected_folder.exists():
                    print(f"📁 Found corrected_format in: {folder.name}")
                    
                    # Find MP4 files in corrected_format folder
                    mp4_files = list(corrected_folder.glob("*.mp4"))
                    print(f"📄 Found {len(mp4_files)} MP4 files in {folder.name}/corrected_format")
                    
                    for mp4_file in mp4_files:
                        relative_path = str(mp4_file.relative_to(self.watch_path))
                        
                        # Check if already uploaded
                        if relative_path not in self.uploaded_files:
                            # Additional check: file should be at least 1MB and stable (not being written)
                            if mp4_file.stat().st_size > 1024 * 1024:  # 1MB minimum
                                # Check if file is stable (not modified in last 5 minutes)
                                current_time = time.time()
                                file_modified_time = mp4_file.stat().st_mtime
                                
                                if current_time - file_modified_time > 300:  # 5 minutes
                                    files_to_upload.append(mp4_file)
                                    print(f"📤 Found new file: {mp4_file.name}")
                                else:
                                    print(f"⏳ File still being modified: {mp4_file.name}")
                            else:
                                print(f"⚠️  File too small: {mp4_file.name}")
                        else:
                            print(f"⏭️  Already uploaded: {mp4_file.name}")
                else:
                    # Check if folder has MP4 files but no corrected_format subfolder
                    direct_mp4s = list(folder.glob("*.mp4"))
                    if direct_mp4s:
                        print(f"⚠️  Found {len(direct_mp4s)} MP4 files in {folder.name} but no corrected_format subfolder")
        
        except Exception as e:
            print(f"❌ Error scanning for files: {e}")
        
        return files_to_upload

    def upload_session(self):
        """Main upload session - login and upload all pending files"""
        print(f"\n{'='*60}")
        print("BROOKLINE CABLECAST UPLOADER")
        print(f"Upload session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        if not self.init_driver():
            print("❌ Failed to initialize driver")
            return
        
        upload_count = 0
        
        try:
            # Step 1: Check if already logged in
            if not self.check_login_status():
                # Step 2: Login if needed
                if not self.login_to_cablecast():
                    print("❌ Login failed, aborting upload session")
                    return
            
            # Step 3: Navigate to assets
            if not self.navigate_to_assets():
                print("❌ Failed to navigate to assets, aborting")
                return
            
            # Step 4: Find files to upload
            files_to_upload = self.find_files_to_upload()
            
            if not files_to_upload:
                print("📭 No new files to upload")
                return
            
            print(f"📤 Found {len(files_to_upload)} files to upload")
            
            # Step 5: Upload each file with tab management
            for i, file_path in enumerate(files_to_upload, 1):
                print(f"\n--- Uploading {i}/{len(files_to_upload)} ---")
                
                # Wait for available upload slots
                self.wait_for_upload_slots(max_concurrent=10)
                
                # Navigate to assets for this upload (keep old tabs)
                upload_tab = self.navigate_to_assets(keep_old_tab=True)
                if not upload_tab:
                    print(f"❌ Failed to navigate to assets for {file_path.name}")
                    continue
                
                success = self.upload_file(file_path)
                if success:
                    upload_count += 1
                
                # Clean up old uploads periodically
                if i % 3 == 0:  # Every 3 uploads
                    print(f"🔄 Periodic cleanup ({i}/{len(files_to_upload)})...")
                    self.cleanup_old_upload_tabs()
                    self.limit_open_upload_tabs()
                
                # Brief pause between uploads
                time.sleep(5)
            
            # FIXED: Final cleanup - wait for uploads to complete (respect 5-minute timeout)
            print("🔄 Waiting for uploads to complete (respecting 5-minute timeout)...")
            print(f"📊 {len(self.uploading_tabs)} upload tabs will remain open for up to 5 minutes each")
            
            # Wait and periodically clean up only tabs that have exceeded 5 minutes
            cleanup_rounds = 0
            max_cleanup_rounds = 20  # Check every 30 seconds for up to 10 minutes total
            
            while self.uploading_tabs and cleanup_rounds < max_cleanup_rounds:
                cleanup_rounds += 1
                time.sleep(30)  # Wait 30 seconds between cleanup checks
                
                print(f"🔄 Cleanup check {cleanup_rounds}/{max_cleanup_rounds} - {len(self.uploading_tabs)} tabs still open")
                self.cleanup_old_upload_tabs()  # Only closes tabs older than 5 minutes
                
                # If no tabs left, break early
                if not self.uploading_tabs:
                    print("✅ All upload tabs completed and closed naturally")
                    break
            
            # Final force cleanup only if tabs are still open after 10 minutes total
            if self.uploading_tabs:
                print(f"⚠️ Force closing {len(self.uploading_tabs)} tabs that exceeded 10-minute maximum")
                remaining_tabs = self.uploading_tabs[:]
                for upload_info in remaining_tabs:
                    try:
                        if upload_info['tab'] in self.driver.window_handles:
                            self.driver.switch_to.window(upload_info['tab'])
                            self.driver.close()
                            print(f"✓ Force closed tab: {upload_info['filename']} (10-min timeout)")
                            self.uploading_tabs.remove(upload_info)
                    except:
                        try:
                            self.uploading_tabs.remove(upload_info)
                        except:
                            pass
            
            # Switch back to first remaining tab if any
            try:
                if self.driver.window_handles:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
            
            # Step 6: Summary
            print(f"\n{'='*60}")
            print("✅ UPLOAD SESSION COMPLETED!")
            print(f"📊 Files processed: {len(files_to_upload)}")
            print(f"✅ Successfully uploaded: {upload_count}")
            print(f"❌ Failed uploads: {len(files_to_upload) - upload_count}")
            print(f"📁 Watch folder: {self.watch_path}")
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"❌ Upload session error: {e}")
        finally:
            try:
                self.driver.quit()
                self.logged_in = False
            except:
                pass

    def auto_upload_scheduler(self):
        """Schedule automatic uploads every 6 hours"""
        schedule.every(6).hours.do(self.upload_session)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def start_auto_upload(self):
        """Start automatic uploads in background"""
        print("🔄 Starting auto upload - will run every 6 hours")
        upload_thread = threading.Thread(target=self.auto_upload_scheduler, daemon=True)
        upload_thread.start()
        return upload_thread

    def stop_auto_upload(self):
        """Stop automatic uploads"""
        self.running = False
        schedule.clear()
        print("⏹️ Auto upload stopped")

    def test_filestore_selection(self):
        """Test function to find and select filestore"""
        print("🧪 Testing filestore selection...")
        
        if not self.init_driver():
            print("❌ Failed to initialize driver")
            return
        
        try:
            # Login first
            if not self.login_to_cablecast():
                print("❌ Login failed")
                return
            
            # Navigate to upload page
            if not self.navigate_to_assets():
                print("❌ Failed to navigate to assets")
                return
            
            # Click upload button
            upload_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Upload') or contains(text(), 'upload')]"))
            )
            upload_button.click()
            time.sleep(3)
            
            # Select a test file first
            print("📁 Selecting a test file first...")
            try:
                # Find files to upload
                files_to_upload = self.find_files_to_upload()
                if files_to_upload:
                    test_file = files_to_upload[0]
                    print(f"📁 Using test file: {test_file.name}")
                    
                    # Select file input
                    file_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                    )
                    file_input.send_keys(str(test_file.absolute()))
                    print("✅ Test file selected")
                    time.sleep(3)  # Wait for filestore dropdown to appear
                else:
                    print("❌ No files found for testing")
                    return
            except Exception as e:
                print(f"❌ Failed to select test file: {e}")
                return
            
            print("🔍 Analyzing filestore options...")
            
            # Find all select elements
            select_elements = self.driver.find_elements(By.TAG_NAME, "select")
            print(f"Found {len(select_elements)} select elements")
            
            for i, select_elem in enumerate(select_elements):
                try:
                    select_id = select_elem.get_attribute("id")
                    select_class = select_elem.get_attribute("class")
                    print(f"Select {i+1}: ID = {select_id}, Class = {select_class}")
                    
                    options = select_elem.find_elements(By.TAG_NAME, "option")
                    print(f"  Options ({len(options)}):")
                    for j, option in enumerate(options):
                        print(f"    {j+1}. '{option.text}' (value: {option.get_attribute('value')})")
                        if "Flex" in option.text:
                            print(f"    ⭐ FOUND FLEX OPTION: {option.text}")
                            # Test selecting this option
                            try:
                                option.click()
                                print(f"    ✅ Successfully clicked Flex option!")
                            except Exception as e:
                                print(f"    ❌ Failed to click: {e}")
                except Exception as e:
                    print(f"  Error reading select {i+1}: {e}")
            
            # Test JavaScript approach
            print("\n🔍 Testing JavaScript approach...")
            js_script = '''
            var selects = document.querySelectorAll('select');
            var results = [];
            for(var i = 0; i < selects.length; i++) {
                var selectInfo = {
                    id: selects[i].id,
                    className: selects[i].className,
                    options: []
                };
                var options = selects[i].querySelectorAll('option');
                for(var j = 0; j < options.length; j++) {
                    selectInfo.options.push({
                        text: options[j].textContent,
                        value: options[j].value
                    });
                }
                results.push(selectInfo);
            }
            return results;
            '''
            js_results = self.driver.execute_script(js_script)
            print("JavaScript results:")
            for i, result in enumerate(js_results):
                print(f"  Select {i+1}: ID = {result['id']}, Class = {result['className']}")
                for option in result['options']:
                    print(f"    - '{option['text']}' (value: {option['value']})")
                    if "Flex" in option['text']:
                        print(f"    ⭐ FLEX OPTION FOUND!")
            
            print("\n🧪 Test completed! Check the results above.")
            input("Press Enter to close browser...")
            
        except Exception as e:
            print(f"❌ Test error: {e}")
        finally:
            try:
                self.driver.quit()
            except:
                pass

    def clear_upload_history(self):
        """Clear upload history"""
        confirm = input("Clear all upload history? This will allow re-uploading all files. (y/N): ").strip().lower()
        if confirm == 'y':
            self.uploaded_files.clear()
            self.save_upload_history()
            print("✅ Upload history cleared")
        else:
            print("❌ Cancelled")

    def run_interface(self):
        """Interactive menu interface"""
        print("BROOKLINE CABLECAST AUTO UPLOADER")
        print("Monitors corrected_format folders and uploads new videos")
        
        auto_thread = None
        
        while True:
            print(f"\n{'='*60}")
            print("UPLOAD OPTIONS:")
            print("1. Single upload session")
            print("2. Start auto upload (every 6 hours)")
            print("3. Stop auto upload")
            print("4. Clear upload history")
            print("5. Test filestore selection")
            print("0. Exit")
            print(f"{'='*60}")
            
            choice = input("Select option (0-5): ").strip()
            
            if choice == '1':
                print("🚀 Starting single upload session...")
                self.upload_session()
                
            elif choice == '2':
                if auto_thread and auto_thread.is_alive():
                    print("Auto upload is already running!")
                else:
                    auto_thread = self.start_auto_upload()
                    print("✅ Auto upload started! Will run every 6 hours.")
                    
            elif choice == '3':
                self.stop_auto_upload()
                
            elif choice == '4':
                self.clear_upload_history()
                
            elif choice == '5':
                self.test_filestore_selection()
                    
            elif choice == '0':
                print("Exiting...")
                self.stop_auto_upload()
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                break
                
            else:
                print("Invalid choice! Please select 0-5.")

if __name__ == "__main__":
    uploader = BrooklineCablecastUploader()
    uploader.run_interface()