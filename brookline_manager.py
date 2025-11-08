#!/usr/bin/env python3
"""
Brookline Download & Upload Manager
Manages both downloader and uploader scripts automatically
"""

import os
import sys
import time
import threading
import schedule
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

class BrooklineManager:
    def __init__(self):
        self.script_path = Path(__file__).parent
        self.running = True
        
        # Try to import the classes directly
        try:
            from brookline_downloader import SimpleBrooklineDownloader
            from brookline_uploader import BrooklineCablecastUploader
            self.downloader_class = SimpleBrooklineDownloader
            self.uploader_class = BrooklineCablecastUploader
            print("✅ Successfully imported downloader and uploader classes")
        except ImportError as e:
            print(f"❌ Failed to import classes: {e}")
            print("Make sure brookline_downloader.py and brookline_uploader.py are in the same folder")
            self.downloader_class = None
            self.uploader_class = None

    def run_downloader(self):
        """Run downloader - single scan"""
        print(f"\n{'='*60}")
        print("🔽 STARTING DOWNLOADER")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        try:
            if self.downloader_class is None:
                print("❌ Downloader class not available")
                return False
            
            downloader = self.downloader_class()
            downloader.run_download_scan()  # Direct function call
            print("✅ Downloader completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Downloader error: {e}")
            return False

    def run_uploader(self):
        """Run uploader - single upload session"""
        print(f"\n{'='*60}")
        print("🔼 STARTING UPLOADER")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        try:
            if self.uploader_class is None:
                print("❌ Uploader class not available")
                return False
            
            uploader = self.uploader_class()
            uploader.upload_session()  # Direct function call
            print("✅ Uploader completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Uploader error: {e}")
            return False

    def run_single_video_test(self):
        """Download ONE video and immediately upload it - for testing pipeline"""
        print(f"\n{'='*80}")
        print("🧪 SINGLE VIDEO TEST MODE")
        print("Will download ONE video and immediately upload it")
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        if self.downloader_class is None or self.uploader_class is None:
            print("❌ Downloader or Uploader class not available")
            return False
        
        try:
            # Step 1: Create downloader instance
            print("🔽 Initializing downloader for single video test...")
            downloader = self.downloader_class()
            
            if not downloader.init_driver():
                print("❌ Failed to initialize downloader driver")
                return False
            
            try:
                # Step 2: Load events and find ONE to download
                print("🔍 Loading events to find ONE video to download...")
                recent_events = downloader.load_all_events()
                
                if not recent_events:
                    print("❌ No recent events found")
                    return False
                
                print(f"📋 Found {len(recent_events)} recent events")
                
                # Step 3: Try to download ONE video successfully
                downloaded_video = None
                for i, event in enumerate(recent_events, 1):
                    print(f"\n--- Attempting Event {i}/{len(recent_events)} ---")
                    print(f"Event #{event['event_number']}: {event['title'][:50]}...")
                    
                    success = downloader.process_single_meeting(event)
                    if success:
                        downloaded_video = event
                        print(f"✅ Successfully started download for Event #{event['event_number']}")
                        break
                    else:
                        print(f"⏭️ Event #{event['event_number']} had no video, trying next...")
                
                if not downloaded_video:
                    print("❌ No videos found to download in recent events")
                    return False
                
                # Step 4: Wait for download to complete and organize
                print(f"\n🔄 Waiting for download to complete...")
                print(f"Downloaded Event #{downloaded_video['event_number']}: {downloaded_video['title'][:50]}...")
                
                # Wait for download to finish (longer than normal)
                print("⏳ Waiting 2 minutes for download to complete...")
                time.sleep(120)  # 2 minutes
                
                # Clean up download tabs
                print("🔄 Cleaning up download tabs...")
                downloader.cleanup_old_download_tabs()
                
                # Process and organize the downloaded file
                print("📁 Processing downloaded files...")
                downloader.process_downloaded_files()
                
                print(f"✅ Download phase completed for Event #{downloaded_video['event_number']}")
                
            finally:
                # Always close downloader driver
                try:
                    downloader.driver.quit()
                except:
                    pass
            
            # Step 5: Wait for file stability, then upload
            print(f"\n🔼 Waiting 5 minutes for file stability, then uploading...")
            time.sleep(300)  # 5 minutes
            
            uploader = self.uploader_class()
            uploader.upload_session()
            
            # Step 6: Summary
            print(f"\n{'='*80}")
            print("🧪 SINGLE VIDEO TEST COMPLETED!")
            print(f"✅ Downloaded: Event #{downloaded_video['event_number']}")
            print(f"📋 Title: {downloaded_video['title'][:60]}...")
            print(f"📁 Check {Path(__file__).parent / 'govideosav'} for organized files")
            print(f"📤 Upload attempted - check Cablecast for uploaded video")
            print(f"🕒 Test finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")
            
            return True
            
        except Exception as e:
            print(f"❌ Single video test error: {e}")
            return False

    def run_sync_cycle(self):
        """Run one complete download → upload cycle"""
        print(f"\n{'='*80}")
        print("🔄 STARTING SYNC CYCLE")
        print(f"Cycle started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        # Step 1: Download
        download_success = self.run_downloader()
        
        # Step 2: Upload (only if download was successful)
        if download_success:
            print("⏳ Waiting 5 minutes for file stability before upload...")
            time.sleep(300)  # 5 minutes
            upload_success = self.run_uploader()
        else:
            print("⚠️ Skipping upload due to download failure")
            upload_success = False
        
        print(f"\n{'='*80}")
        if download_success and upload_success:
            print("✅ SYNC CYCLE COMPLETED SUCCESSFULLY")
        else:
            print("⚠️ SYNC CYCLE COMPLETED WITH ISSUES")
        print(f"Cycle finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")

    def schedule_auto_sync(self):
        """Schedule automatic sync every 6 hours"""
        try:
            schedule.every(6).hours.do(self.run_sync_cycle)
            
            print("📅 Scheduled auto sync every 6 hours")
            print("🔄 Running first sync cycle now...")
            
            # Run first cycle immediately
            self.run_sync_cycle()
            
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except Exception as e:
            print(f"❌ Schedule error: {e}")

    def start_auto_sync(self):
        """Start automatic sync in background"""
        print("🔄 Starting auto sync - will run every 6 hours")
        sync_thread = threading.Thread(target=self.schedule_auto_sync, daemon=True)
        sync_thread.start()
        return sync_thread

    def stop_auto_sync(self):
        """Stop automatic sync"""
        self.running = False
        try:
            schedule.clear()
        except:
            pass
        print("⏹️ Auto sync stopped")

    def start_downloader_auto(self):
        """Start downloader in auto mode"""
        print("🔽 Starting downloader auto mode...")
        
        def downloader_auto():
            try:
                if self.downloader_class is None:
                    print("❌ Downloader class not available")
                    return
                
                downloader = self.downloader_class()
                # Set up auto refresh manually
                schedule.every(6).hours.do(downloader.run_download_scan)
                
                # Run first scan immediately
                downloader.run_download_scan()
                
                while self.running:
                    schedule.run_pending()
                    time.sleep(60)
                    
            except Exception as e:
                print(f"❌ Downloader auto error: {e}")
        
        downloader_thread = threading.Thread(target=downloader_auto, daemon=True)
        downloader_thread.start()
        return downloader_thread

    def start_uploader_auto(self):
        """Start uploader in auto mode"""
        print("🔼 Starting uploader auto mode...")
        
        def uploader_auto():
            try:
                if self.uploader_class is None:
                    print("❌ Uploader class not available")
                    return
                
                uploader = self.uploader_class()
                # Set up auto upload manually
                schedule.every(6).hours.do(uploader.upload_session)
                
                # Wait a bit then run first upload
                time.sleep(120)  # 2 minute delay
                uploader.upload_session()
                
                while self.running:
                    schedule.run_pending()
                    time.sleep(60)
                    
            except Exception as e:
                print(f"❌ Uploader auto error: {e}")
        
        uploader_thread = threading.Thread(target=uploader_auto, daemon=True)
        uploader_thread.start()
        return uploader_thread

    def run_parallel_mode(self):
        """Run both scripts in parallel with their own auto modes"""
        print(f"\n{'='*60}")
        print("⚡ STARTING PARALLEL MODE")
        print("Both scripts will run independently with auto modes")
        print(f"{'='*60}")
        
        try:
            # Start both in auto mode
            downloader_thread = self.start_downloader_auto()
            uploader_thread = self.start_uploader_auto()
            
            print("\n✅ Both scripts running in parallel!")
            print("📅 Both will run every 6 hours automatically")
            print("Use option 3 to stop auto modes")
            
        except Exception as e:
            print(f"❌ Parallel mode error: {e}")

    def check_script_status(self):
        """Check if scripts are available and working"""
        print("🔍 Checking script status...")
        
        # Check class imports
        if self.downloader_class:
            print("✅ Downloader class imported successfully")
        else:
            print("❌ Downloader class import failed")
        
        if self.uploader_class:
            print("✅ Uploader class imported successfully")
        else:
            print("❌ Uploader class import failed")
        
        # Check if govideosav folder exists (in same directory as scripts)
        watch_path = Path(__file__).parent / "govideosav"
        if watch_path.exists():
            week_folders = [f for f in watch_path.iterdir() if f.is_dir() and f.name.startswith("Week_")]
            print(f"✅ Watch folder exists with {len(week_folders)} week folders")
            
            # Check for corrected_format folders
            corrected_count = 0
            pending_uploads = 0
            for week in week_folders:
                corrected_folder = week / "corrected_format"
                if corrected_folder.exists():
                    corrected_count += 1
                    mp4_files = list(corrected_folder.glob("*.mp4"))
                    pending_uploads += len(mp4_files)
            
            print(f"📁 {corrected_count} week folders have corrected_format subfolders")
            print(f"📤 {pending_uploads} MP4 files ready for upload")
        else:
            print(f"❌ Watch folder missing: {watch_path}")

    def run_interface(self):
        """Interactive menu for manager"""
        print("BROOKLINE DOWNLOAD & UPLOAD MANAGER")
        print("Coordinates both downloader and uploader scripts")
        
        auto_thread = None
        
        while True:
            print(f"\n{'='*60}")
            print("MANAGER OPTIONS:")
            print("1. Single sync cycle (download → upload)")
            print("2. Start auto sync (every 6 hours)")
            print("3. Stop auto sync")
            print("4. Run parallel mode (both scripts independent)")
            print("5. Check script status")
            print("6. Run downloader only")
            print("7. Run uploader only")
            print("8. 🧪 Test: Download ONE video and upload it")
            print("0. Exit")
            print(f"{'='*60}")
            
            choice = input("Select option (0-8): ").strip()
            
            if choice == '1':
                print("🔄 Starting single sync cycle...")
                self.run_sync_cycle()
                
            elif choice == '2':
                if auto_thread and auto_thread.is_alive():
                    print("Auto sync is already running!")
                else:
                    auto_thread = self.start_auto_sync()
                    print("✅ Auto sync started! Will run every 6 hours.")
                    
            elif choice == '3':
                self.stop_auto_sync()
                
            elif choice == '4':
                self.run_parallel_mode()
                
            elif choice == '5':
                self.check_script_status()
                
            elif choice == '6':
                self.run_downloader()
                
            elif choice == '7':
                self.run_uploader()
                
            elif choice == '8':
                print("🧪 Starting single video test...")
                confirm = input("This will download ONE video and immediately upload it. Continue? (y/N): ").strip().lower()
                if confirm == 'y':
                    self.run_single_video_test()
                else:
                    print("❌ Test cancelled")
                    
            elif choice == '0':
                print("Exiting...")
                self.stop_auto_sync()
                break
                
            else:
                print("Invalid choice! Please select 0-8.")

if __name__ == "__main__":
    manager = BrooklineManager()
    manager.run_interface()