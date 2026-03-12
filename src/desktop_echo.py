from tracemalloc import start

import customtkinter as ctk
import threading
import queue
import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox
import sys
import os
import importlib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from echo_core import FastDownloader
from datetime import datetime
from download_history import DownloadHistory
import json
# System tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    SYSTEM_TRAY_AVAILABLE = True
except ImportError:
    SYSTEM_TRAY_AVAILABLE = False
    print("System tray not available. Install pystray and Pillow for tray support.")



# Default categories for auto‑categorization
DEFAULT_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
    "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Programs": [".exe", ".msi", ".deb", ".rpm", ".app", ".dmg"],
    "Others": []  # catch‑all
}


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def log(msg):
    with open("startup_log.txt", "a") as f:
        f.write(f"{time.time():.3f} - {msg}\n")

class DownloadItem:
    def __init__(self, url, download_path, filename=None):
        self.url = url
        self.download_path = download_path
        self.filename = filename
        self.status = "Queued"  # Queued, Downloading, Paused, Completed, Error, Cancelled
        self.progress = 0
        self.speed = 0
        self.downloader = None
        self.added_time = datetime.now()
        self.start_time = None
        self.end_time = None
        self.file_size = 0
        self.error_message = ""  # Added for better error tracking
        self.item_id = str(uuid.uuid4())[:8]  # Unique ID for the item
        self.selected = False  # For selection in the queue

    def toggle_selection(self):
        """Toggle the selection state of the download item"""
        self.selected = not self.selected
        return self.selected

class DownloadManagerUI(ctk.CTk):
    def __init__(self):
        log("Starting application initialization")
        total_start = time.time()
        super().__init__()
        log("Super init completed")
        
        print(f"Step 1: super init took {step - total_start:.3f}s")
        # Bind window close event for proper tray cleanup
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.tray_running = False
        step = time.time()  
        print(f"Step 1: super init took {step - total_start:.3f}s")

        try:
            # Load settings
            t = time.time()
            settings = self._load_settings()
            print(f"Step 2: Load settings took {time.time() - t:.3f}s")

            # Apply saved theme
            t = time.time()
            saved_theme = self.load_theme_preference()
            ctk.set_appearance_mode(saved_theme)
            print(f"Step 3: Apply theme took {time.time() - t:.3f}s")

            # Apply saved download folder
            t = time.time()
            self.download_folder = settings.get('download_folder', os.path.expanduser("~/Downloads"))
            self.download_folder = os.path.normpath(self.download_folder)
    
            # 🔥 INITIALIZE DUPLICATE CHECK SETTINGS 🔥
            self.skip_duplicates_var = tk.BooleanVar(value=settings.get('skip_duplicates', False))
            self.auto_rename_var = tk.BooleanVar(value=settings.get('auto_rename', False))
            print(f"Step 4: Load download folder and duplicate settings took {time.time() - t:.3f}s")

            saved_scale = settings.get('ui_scale',1.0)
            if saved_scale != 1.0:
                try:
                    ctk.set_widget_scaling(saved_scale)
                    print(f"UI scale set to: {saved_scale}")
                except Exception as scale_error:
                    print(f"Failed to set UI scale: {scale_error}")
                    # Fallback to default scale
            print(f"Step 5: Apply UI scale took {time.time() - t:.3f}s")

            # Initialize language strings FIRST before any UI that uses them
            t = time.time()
            self.current_lang = self._load_setting('language', 'en')
            self.strings = self._load_language(self.current_lang)
            print(f"Step 6a: Load language strings took {time.time() - t:.3f}s")

            t = time.time()
            self.title(self._s('app_title'))
            self.geometry("1250x740")
            print(f"Step 6b: Set window properties took {time.time() - t:.3f}s")

            # Initialize data structures
            t = time.time()
            self.progress_queue = queue.Queue()
            self.download_queue = []
            self.current_download = None
            
            # Initialize history manager directly
            from download_history import DownloadHistory
            self.history_manager = DownloadHistory()
           

            # Tracking variables
            self.thread_speed = []
            self.thread_percents = []
            self.downloader_paused = False
            print(f"Step 7: Initialize data structures took {time.time() - t:.3f}s") 
            
            t = time.time()
            self._create_widgets()
            print(f"Step 8: Create widgets took {time.time() - t:.3f}s")

            self.after(100, self.update_thread_display)
            
             # Create system tray icon if enabled
            if self._load_setting('minimize_to_tray', False) and SYSTEM_TRAY_AVAILABLE:
                self._create_tray_icon()

            # Bind minimize event
            self.bind('<Unmap>', self._on_minimize)

            print(f"Total initialization time: {time.time() - total_start:.3f}s")
            print(f"Download folder set to: {self.download_folder}")

        except Exception as e:
            messagebox.showerror(self._s('init_error'), self._s('init_error_msg', str(e)))
            raise

    def _on_minimize(self, event):
        """Handle window minimize event"""
        if self._load_setting('minimize_to_tray', False) and SYSTEM_TRAY_AVAILABLE:
            if self.tray_icon:
                self.withdraw()


    def _save_theme_preference(self, theme):
        """Save theme preference to file for persistence"""
        try:
            config_dir = os.path.expanduser("~/.download_manager")
            os.makedirs(config_dir, exist_ok=True)
            
            config_file = os.path.join(config_dir, "settings.json")
            config = {}
            
            # Load existing config if available
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Update theme setting
            config['theme'] = theme
            
            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            print(f"Could not save theme preference: {e}")

    def _load_theme_preference(self):
        """Load saved theme preference"""
        try:
            config_file = os.path.expanduser("~/.download_manager/settings.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('theme', 'Dark')
        except Exception as e:
            print(f"Could not load theme preference: {e}")
        return "Dark"  # Default theme

    def _load_language(self, lang_code):
        """Load language strings with fallback support"""
        try:
            module = importlib.import_module(f'locales.{lang_code}')
            return module.LANG
        except (ImportError, AttributeError):
            # fallback to English
            from locales import en
            return en.LANG

    def _s(self, key, *args):
        """
        Get a localized string with fallback support.
        Usage: self._s('key') or self._s('key', arg1, arg2) for format strings
        """
        # Try to get from current language
        string_value = self.strings.get(key)
        
        # If not found, try English fallback
        if string_value is None:
            try:
                from locales import en
                string_value = en.LANG.get(key)
            except:
                string_value = key  # Ultimate fallback: show the key itself
        
        # If there are format arguments, apply them
        if args:
            try:
                return string_value.format(*args)
            except (AttributeError, ValueError):
                return string_value
        
        return string_value

    def _create_tray_icon(self):
        """Create system tray icon"""
        if not SYSTEM_TRAY_AVAILABLE:
            return
        
        # Create a simple icon image
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color='white')
        dc = ImageDraw.Draw(image)
        dc.rectangle([8, 8, 56, 56], fill='blue', outline='darkblue', width=2)
        dc.rectangle([16, 20, 48, 44], fill='white')
        dc.rectangle([20, 24, 44, 40], fill='blue')
        
        # Dynamic tooltip with status
        def get_tray_status():
            downloading = len([item for item in self.download_queue if item.status == "Downloading"])
            paused = len([item for item in self.download_queue if item.status == "Paused"])
            queued = len([item for item in self.download_queue if item.status == "Queued"])
            if downloading > 0:
                return f"Echo-Fetch: {downloading} downloading, {paused} paused"
            elif queued > 0:
                return f"Echo-Fetch: {queued} queued"
            else:
                return "Echo-Fetch: Ready"
        
        # Create tray menu with Resume All
        menu = pystray.Menu(
            pystray.MenuItem('📊 Show', self._show_from_tray),
            pystray.MenuItem('🚀 Start All', self._start_all_from_tray),
            pystray.MenuItem('⏸ Pause All', self._pause_all_from_tray),
            pystray.MenuItem('▶️ Resume All', self._resume_all_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('❌ Quit', self._quit_from_tray),
        )
        
        self.tray_icon = pystray.Icon("echo_fetch", image, get_tray_status(), menu)
        # Update tooltip every 2 seconds
        self.update_tray_tooltip()
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon, item):
        """Show window from tray"""
        self.after(0, self._restore_window)

    def _start_all_from_tray(self, icon, item):
        """Start all downloads from tray"""
        self.after(0, self._start_all_downloads)

    def _pause_all_from_tray(self, icon, item):
        """Pause all downloads from tray"""
        self.after(0, self._pause_all_downloads)

    def _quit_from_tray(self, icon, item):
        """Quit application from tray"""
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.destroy()
    
    def _resume_all_from_tray(self, icon, item):
        """Resume all paused downloads from tray"""
        self.after(0, self._pause_all_downloads)  # Reuse pause_all logic for resume_all
        # Note: Need proper resume logic here
    
    def update_tray_tooltip(self):
        """Update system tray tooltip with current status"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            downloading = len([item for item in self.download_queue if item.status == "Downloading"])
            paused = len([item for item in self.download_queue if item.status == "Paused"])
            queued = len([item for item in self.download_queue if item.status == "Queued"])
            
            if downloading > 0:
                tooltip = f"Echo-Fetch: {downloading} ↓, {paused} ⏸"
            elif queued > 0:
                tooltip = f"Echo-Fetch: {queued} queued"
            else:
                tooltip = "Echo-Fetch: Ready"
            
            self.tray_icon.visible = False
            self.tray_icon.visible = True  # Force refresh
        self.after(2000, self.update_tray_tooltip)

    def _restore_window(self):
        """Restore window from minimized state"""
        self.deiconify()
        self.state('normal')
        self.lift()
        self.focus_force()

    def _start_all_downloads(self):
        """Start all queued downloads"""
        queued = [i for i in self.download_queue if i.status == "Queued"]
        for item in queued:
            self._start_download_item(item)

    def _pause_all_downloads(self):
        """Pause all active downloads"""
        active = [i for i in self.download_queue if i.status == "Downloading"]
        for item in active:
            if item.downloader:
                item.downloader.pause()
                item.status = "Paused"
        self._update_queue_display()

    def minimize_to_tray(self):
        """Minimize window to system tray"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.withdraw()
        else:
            self.iconify()


    def change_language(self, choice):
        self._save_setting('language', choice)
        messagebox.showinfo(self._s('restart_required'), self._s('language_change_msg'))

        # Optionally, restart the app programmatically (tricky) or just tell user.

    def _create_widgets(self):
        """Create and arrange all UI widgets"""
        try:
            # Main container with two sections
            main_frame = ctk.CTkFrame(self)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Left side - Download controls
            left_frame = ctk.CTkFrame(main_frame)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
            
            # Right side - Queue management
            right_frame = ctk.CTkFrame(main_frame, width=400)
            right_frame.pack(side="right", fill="both", padx=(5, 0))
            right_frame.pack_propagate(False)
                
            self._create_download_section(left_frame)
            self._create_queue_section(right_frame)
        except Exception as e:
            messagebox.showerror(self._s('ui_error'), self._s('ui_error_msg', str(e)))

    def cleanup_downloaded_files(self):
        """Cleanup downloaded files with selective options"""
        try:
            # Get completed downloads from history
            completed_downloads = [
                record for record in self.history_manager.history 
                if record['status'] == 'Completed'
            ]
            
            if not completed_downloads:
                messagebox.showinfo("No Files", "No completed downloads found in history")
                return
            
            # Create a selection window for file cleanup
            cleanup_window = ctk.CTkToplevel(self)
            cleanup_window.title("Cleanup Downloaded Files")
            cleanup_window.geometry("600x400")
            cleanup_window.transient(self)
            cleanup_window.grab_set()
            
            ctk.CTkLabel(cleanup_window, text="Select files to delete:",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            # Scrollable frame for file list
            files_frame = ctk.CTkScrollableFrame(cleanup_window)
            files_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            file_vars = {}
            
            for record in completed_downloads:
                filename = record.get('filename', 'Unknown')
                filepath = os.path.join(self.download_folder, filename)
                file_exists = os.path.exists(filepath)
                
                file_frame = ctk.CTkFrame(files_frame)
                file_frame.pack(fill="x", pady=2)
                
                var = ctk.BooleanVar(value=True)
                file_vars[filename] = var
                
                cb = ctk.CTkCheckBox(file_frame, text="", variable=var, width=20)
                cb.pack(side="left", padx=5)
                
                file_text = f"{filename}"
                if not file_exists:
                    file_text += " (File not found)"
                
                file_label = ctk.CTkLabel(file_frame, text=file_text, anchor="w")
                file_label.pack(side="left", fill="x", expand=True)
                
                if not file_exists:
                    file_label.configure(text_color="gray")
            
            # Action buttons
            btn_frame = ctk.CTkFrame(cleanup_window)
            btn_frame.pack(fill="x", padx=20, pady=10)
            
            ctk.CTkButton(btn_frame, text="Select All", 
                         command=lambda: self._select_all_files(file_vars, True)).pack(side="left", padx=5)
            
            ctk.CTkButton(btn_frame, text="Deselect All", 
                         command=lambda: self._select_all_files(file_vars, False)).pack(side="left", padx=5)
            
            ctk.CTkButton(btn_frame, text="Delete Selected", 
                         command=lambda: self._delete_selected_files(file_vars, cleanup_window),
                         fg_color="red", hover_color="darkred").pack(side="right", padx=5)
            
        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to open cleanup window: {str(e)}")
    
    def _select_all_files(self, file_vars, select):
        """Select or deselect all files in cleanup window"""
        for var in file_vars.values():
            var.set(select)
    
    def _delete_selected_files(self, file_vars, window):
        """Delete selected files from cleanup window"""
        try:
            selected_files = [filename for filename, var in file_vars.items() if var.get()]
            
            if not selected_files:
                messagebox.showwarning("No Selection", "No files selected for deletion")
                return
            
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                f"Are you sure you want to delete {len(selected_files)} file(s)?\n\n"
                "This action cannot be undone!"
            )
            
            if not confirm:
                return
            
            deleted_count = 0
            for filename in selected_files:
                filepath = os.path.join(self.download_folder, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_count += 1
            
            messagebox.showinfo("Deletion Complete", f"Successfully deleted {deleted_count} file(s)")
            window.destroy()
            
        except Exception as e:
            messagebox.showerror("Deletion Error", f"Failed to delete files: {str(e)}")

    def show_preferences(self):
        """Show preferences/settings window"""
        try:
            # Create preferences window
            pref_window = ctk.CTkToplevel(self)
            pref_window.title(self._s('preferences'))
            pref_window.geometry("500x600")
            pref_window.transient(self)
            pref_window.grab_set()
            
            # Create tab view for different settings categories
            tab_view = ctk.CTkTabview(pref_window)
            tab_view.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Appearance Tab
            appearance_tab = tab_view.add(self._s('appearance'))
            self._create_appearance_tab(appearance_tab)
            
            # Download Tab
            download_tab = tab_view.add(self._s('download_settings'))
            self._create_download_tab(download_tab)
            
            # General Tab
            general_tab = tab_view.add(self._s('general'))
            self._create_general_tab(general_tab)
            
        except Exception as e:
            messagebox.showerror(self._s('preferences_error'), self._s('preferences_error_msg').format(str(e)))

    def _create_appearance_tab(self, parent):
        """Create appearance settings tab"""
        try:
            # Theme Section
            theme_frame = ctk.CTkFrame(parent)
            theme_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(theme_frame, text="Theme Settings", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Current theme display
            current_theme = ctk.get_appearance_mode()
            self.current_theme_label = ctk.CTkLabel(theme_frame, 
                                                text=f"Current Theme: {current_theme}",
                                                font=ctk.CTkFont(size=14))
            self.current_theme_label.pack(anchor="w", pady=5)
            
            # Theme toggle button
            theme_btn_frame = ctk.CTkFrame(theme_frame, fg_color="transparent")
            theme_btn_frame.pack(fill="x", pady=10)
            
            ctk.CTkButton(theme_btn_frame, text="Toggle Dark/Light Theme", 
                        command=self.toggle_theme, width=200).pack(side="left", padx=(0, 10))
            
            # Theme selection (alternative method)
            ctk.CTkLabel(theme_btn_frame, text="Or select:", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(20, 10))
            
            theme_var = ctk.StringVar(value=current_theme)
            theme_combo = ctk.CTkComboBox(theme_btn_frame, 
                                        values=["Dark", "Light"],
                                        variable=theme_var,
                                        command=self.change_theme,
                                        width=100)
            theme_combo.pack(side="left")
            
            # UI Scale Section
            scale_frame = ctk.CTkFrame(parent)
            scale_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(scale_frame, text="UI Scaling", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            ctk.CTkLabel(scale_frame, text="Adjust UI scaling (requires restart):",
                        font=ctk.CTkFont(size=12)).pack(anchor="w", pady=5)
            
            current_scale = self._load_setting('ui_scale',1.0)
            scale_percent = f"{int(current_scale * 100)}%"

            scale_var = ctk.StringVar(value=scale_percent)
            scale_combo = ctk.CTkComboBox(scale_frame,
                                        values=["80%", "90%", "100%", "110%", "120%"],
                                        variable=scale_var,
                                        command=self.change_ui_scale,
                                        width=100)
            scale_combo.pack(anchor="w", pady=5)
            
        except Exception as e:
            print(f"Appearance tab error: {e}")

    def _create_download_tab(self, parent):
        """Create download settings tab"""
        try:
            # Download Folder Section
            folder_frame = ctk.CTkFrame(parent)
            folder_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(folder_frame, text="Download Location", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Current folder display
            folder_display_frame = ctk.CTkFrame(folder_frame, fg_color="transparent")
            folder_display_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(folder_display_frame, text="Current folder:", 
                        font=ctk.CTkFont(size=12)).pack(anchor="w")
            
            self.pref_folder_label = ctk.CTkLabel(folder_display_frame, 
                                                text=self.download_folder,
                                                font=ctk.CTkFont(size=11),
                                                text_color="gray",
                                                wraplength=400)
            self.pref_folder_label.pack(anchor="w", pady=2)
            
            ctk.CTkButton(folder_display_frame, text="Change Download Folder", 
                        command=self.change_download_folder, width=180).pack(anchor="w", pady=5)
           
            # Download Behavior Section
            behavior_frame = ctk.CTkFrame(parent)
            behavior_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(behavior_frame, text="Download Behavior", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Auto-start downloads
            self.auto_start_var = ctk.BooleanVar(value=self._load_setting('auto_start', False))
            auto_start_cb = ctk.CTkCheckBox(behavior_frame, 
                                        text="Auto-start downloads when added to queue",
                                        variable=self.auto_start_var,
                                        command=self.toggle_auto_start)
            auto_start_cb.pack(anchor="w", pady=5)
            
            # Auto-remove completed
            self.auto_remove_var = ctk.BooleanVar(value=self._load_setting('auto_remove', False))
            auto_remove_cb = ctk.CTkCheckBox(behavior_frame, 
                                        text="Auto-remove completed downloads from queue",
                                        variable=self.auto_remove_var,
                                        command=self.toggle_auto_remove)
            auto_remove_cb.pack(anchor="w", pady=5)
            
            # Auto‑categorization Section
            categorize_frame = ctk.CTkFrame(parent)
            categorize_frame.pack(fill="x", padx=10, pady=10)

            ctk.CTkLabel(categorize_frame, text="Auto‑Categorization", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)

            self.auto_categorize_var = ctk.BooleanVar(value=self._load_setting('auto_categorize', False))
            auto_categorize_cb = ctk.CTkCheckBox(categorize_frame, 
                                                text="Automatically sort downloads into folders by type",
                                                variable=self.auto_categorize_var,
                                                command=self.toggle_auto_categorize)
            auto_categorize_cb.pack(anchor="w", pady=5)

            # Default thread count
            thread_frame = ctk.CTkFrame(behavior_frame, fg_color="transparent")
            thread_frame.pack(fill="x", pady=10)
            
            ctk.CTkLabel(thread_frame, text="Default Threads:", 
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))
            
            self.thread_var = ctk.StringVar(value=str(self._load_setting('default_threads', 8)))
            thread_combo = ctk.CTkComboBox(thread_frame,
                                        values=["1", "2", "4", "8", "12", "16"],
                                        variable=self.thread_var,
                                        command=self.change_default_threads,
                                        width=80)
            thread_combo.pack(side="left")

            # Duplicate Check Section
            duplicate_frame = ctk.CTkFrame(parent)
            duplicate_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(duplicate_frame, text="Duplicate File Handling", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Auto-rename duplicates
            self.auto_rename_var = ctk.BooleanVar(value=self._load_setting('auto_rename', False))
            auto_rename_cb = ctk.CTkCheckBox(duplicate_frame, 
                                            text="Auto-rename duplicate files (no prompt)",
                                            variable=self.auto_rename_var,
                                            command=self.toggle_auto_rename)
            auto_rename_cb.pack(anchor="w", pady=5)
            
            # Skip duplicates
            self.skip_duplicates_var = ctk.BooleanVar(value=self._load_setting('skip_duplicates', False))
            skip_duplicates_cb = ctk.CTkCheckBox(duplicate_frame, 
                                                text="Auto-skip duplicate files",
                                                variable=self.skip_duplicates_var,
                                                command=self.toggle_skip_duplicates)
            skip_duplicates_cb.pack(anchor="w", pady=5)
            
        except Exception as e:
            print(f"Download tab error: {e}")

    def toggle_auto_categorize(self):
        self._save_setting('auto_categorize', self.auto_categorize_var.get())

    def _categorize_file(self, item):
        """Move downloaded file to a category subfolder based on its extension."""
        item_download_path = os.path.normpath(item.download_path)
        filepath = os.path.join(item_download_path, item.filename)

        if not self._load_setting('auto_categorize', False):
            return False

        filepath = os.path.join(item.download_path, item.filename)
        if not os.path.exists(filepath):
            print(f"File not found for categorization: {filepath}")
            return False

        # Get file extension (lowercase)
        ext = os.path.splitext(item.filename)[1].lower()
        
        # Find category
        category = "Others"
        for cat, exts in DEFAULT_CATEGORIES.items():
            if ext in exts:
                category = cat
                break

        # Create category folder if needed
        category_folder = os.path.join(item.download_path, category)
        os.makedirs(category_folder, exist_ok=True)

        # New file path
        new_path = os.path.join(category_folder, item.filename)

        # Handle name conflict: if file already exists, add a number suffix
        if os.path.exists(new_path):
            base, ext = os.path.splitext(item.filename)
            counter = 1
            while os.path.exists(os.path.join(category_folder, f"{base}_{counter}{ext}")):
                counter += 1
            new_path = os.path.join(category_folder, f"{base}_{counter}{ext}")

        try:
            import shutil
            shutil.move(filepath, new_path)
            print(f"Moved {item.filename} to {category} folder")

            # Update item's download path and filename
            item.download_path = category_folder
            item.filename = os.path.basename(new_path)
            # Optionally update history record? The history already stores the original path, but we could update it.
            # For now, we'll just update the item so the queue displays the correct location.
            self._update_queue_display()
            return True
        except Exception as e:
            print(f"Failed to move file: {e}")
            return False

    def toggle_auto_rename(self):
        self._save_setting('auto_rename', self.auto_rename_var.get())
    
    def toggle_skip_duplicates(self):
        self._save_setting('skip_duplicates', self.skip_duplicates_var.get())

    def _create_general_tab(self, parent):
        """Create general settings tab"""
        try:
            # Startup Section
            startup_frame = ctk.CTkFrame(parent)
            startup_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(startup_frame, text="Startup", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Start with system
            self.startup_var = ctk.BooleanVar(value=self._load_setting('start_with_system', False))
            startup_cb = ctk.CTkCheckBox(startup_frame, 
                                    text="Start with system (Windows)",
                                    variable=self.startup_var,
                                    command=self.toggle_startup)
            startup_cb.pack(anchor="w", pady=5)
            
            # Language Section
            lang_frame = ctk.CTkFrame(parent)
            lang_frame.pack(fill="x", padx=10, pady=10)

            ctk.CTkLabel(lang_frame, text="Language", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)

            self.lang_var = ctk.StringVar(value=self.current_lang)
            lang_combo = ctk.CTkComboBox(lang_frame, values=["en", "es", "fr", "de", "zh"],  # add as needed
                                        variable=self.lang_var, command=self.change_language, width=100)
            lang_combo.pack(anchor="w", pady=5)

            # Minimize to tray
            self.minimize_var = ctk.BooleanVar(value=self._load_setting('minimize_to_tray', False))
            minimize_cb = ctk.CTkCheckBox(startup_frame, 
                                        text="Minimize to system tray",
                                        variable=self.minimize_var,
                                        command=self.toggle_minimize_tray)
            minimize_cb.pack(anchor="w", pady=5)
            
            # Notifications Section
            notif_frame = ctk.CTkFrame(parent)
            notif_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(notif_frame, text="Notifications", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            # Download complete notifications
            self.notify_var = ctk.BooleanVar(value=self._load_setting('notify_complete', True))
            notify_cb = ctk.CTkCheckBox(notif_frame, 
                                    text="Show notifications when downloads complete",
                                    variable=self.notify_var,
                                    command=self.toggle_notifications)
            notify_cb.pack(anchor="w", pady=5)
            
            # Sound notifications
            self.sound_var = ctk.BooleanVar(value=self._load_setting('sound_notifications', False))
            sound_cb = ctk.CTkCheckBox(notif_frame, 
                                    text="Play sound for notifications",
                                    variable=self.sound_var,
                                    command=self.toggle_sound)
            sound_cb.pack(anchor="w", pady=5)
            
            # Reset Section
            reset_frame = ctk.CTkFrame(parent)
            reset_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(reset_frame, text="Reset & Maintenance", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=5)
            
            reset_btn_frame = ctk.CTkFrame(reset_frame, fg_color="transparent")
            reset_btn_frame.pack(fill="x", pady=10)
            
            ctk.CTkButton(reset_btn_frame, text="Reset All Settings", 
                        command=self.reset_settings,
                        fg_color="orange", hover_color="darkorange",
                        width=150).pack(side="left", padx=(0, 10))
            
            ctk.CTkButton(reset_btn_frame, text="Clear All Data", 
                        command=self.clear_all_data,
                        fg_color="red", hover_color="darkred",
                        width=150).pack(side="left")
            
        except Exception as e:
            print(f"General tab error: {e}")

    def toggle_theme(self):
        """Toggle between dark and light theme - USING THREADING"""
        try:
            current_theme = ctk.get_appearance_mode()
            new_theme = "Light" if current_theme == "Dark" else "Dark"
            
            # Run theme change in a separate thread
            threading.Thread(target=self._apply_theme_threaded, args=(new_theme,), daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to switch theme: {str(e)}")

    def _apply_theme_threaded(self, new_theme):
        """Apply theme change in a separate thread"""
        try:
            # This might still block, but in a separate thread
            ctk.set_appearance_mode(new_theme)
            
            # Save settings and update UI in main thread
            self.after(0, lambda: self._finish_theme_change(new_theme))
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Theme Error", f"Failed to apply theme: {str(e)}"))

    def _finish_theme_change(self, new_theme):
        """Finish theme change in main thread"""
        try:
            self._save_setting('theme', new_theme)
            
            # Update UI if preferences window is open
            if hasattr(self, 'current_theme_label'):
                self.current_theme_label.configure(text=f"Current Theme: {new_theme}")
            
            # Show feedback
            self.status_label.configure(text=f"Theme: {new_theme}", text_color="green")
            self.after(2000, lambda: self.status_label.configure(text="Idle", text_color="gray"))
            
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to save theme: {str(e)}")

    def change_theme(self, choice):
        """Change theme via dropdown"""
        threading.Thread(target=self._apply_theme_threaded, args=(choice,), daemon=True).start()

    def change_ui_scale(self, choice):
        """Change UI scaling (requires restart)"""
        try:
            scale_map = {"80%": 0.8, "90%": 0.9, "100%": 1.0, "110%": 1.1, "120%": 1.2}
            selected_scale = scale_map[choice]
            self._save_setting('ui_scale', selected_scale)

            if hasattr(self, 'current_scale_label'):
                self.current_scale_label.configure(text=f"Current Scale: {choice}")

            messagebox.showinfo("Restart Required", "UI scaling change will take effect after restart.")

        except Exception as e:
            messagebox.showerror("Scale Error", f"Failed to change UI scale: {str(e)}")

    def change_download_folder(self):
        """Change download folder from preferences"""
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.folder_path_label.configure(text=folder)
            self.pref_folder_label.configure(text=folder)
            self._save_setting('download_folder', folder)

    def toggle_auto_start(self):
        self._save_setting('auto_start', self.auto_start_var.get())

    def toggle_auto_remove(self):
        self._save_setting('auto_remove', self.auto_remove_var.get())

    def change_default_threads(self, choice):
        self._save_setting('default_threads', int(choice))

    def toggle_startup(self):
        self._save_setting('start_with_system', self.startup_var.get())

    def toggle_minimize_tray(self):
        self._save_setting('minimize_to_tray', self.minimize_var.get())

    def toggle_notifications(self):
        self._save_setting('notify_complete', self.notify_var.get())

    def toggle_sound(self):
        self._save_setting('sound_notifications', self.sound_var.get())

    def reset_settings(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno("Confirm Reset", "Reset all settings to default values?"):
            # Clear settings file
            config_file = self._get_config_file()
            if os.path.exists(config_file):
                os.remove(config_file)
            messagebox.showinfo("Settings Reset", "All settings have been reset to defaults.")

    def clear_all_data(self):
        """Clear all application data including downloaded files"""
        try:
            # Count downloaded files
            completed_downloads = [
                record for record in self.history_manager.history 
                if record['status'] == 'Completed'
            ]
            file_count = len(completed_downloads)
            
            response = messagebox.askyesno(
                "Confirm Clear ALL Data",
                f"This will delete:\n\n"
                f"• All download history ({len(self.history_manager.history)} records)\n"
                f"• All application settings\n"
                f"• All downloaded files ({file_count} files)\n\n"
                f"This action cannot be undone!\n\n"
                f"Are you absolutely sure?"
            )
            
            if response:
                # Delete downloaded files first
                deleted_files = 0
                for record in completed_downloads:
                    filename = record.get('filename')
                    if filename:
                        filepath = os.path.join(self.download_folder, filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            deleted_files += 1
                
                # Clear all data
                config_dir = os.path.dirname(self._get_config_file())
                if os.path.exists(config_dir):
                    import shutil
                    shutil.rmtree(config_dir)
                
                messagebox.showinfo(
                    "Data Cleared", 
                    f"All application data has been cleared.\n"
                    f"Deleted {deleted_files} downloaded files."
                )
                
        except Exception as e:
            messagebox.showerror("Clear Error", f"Failed to clear data: {str(e)}")

    def _get_config_file(self):
        """Get config file path"""
        config_dir = os.path.expanduser("~/.download_manager")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "settings.json")

    def _load_settings(self):
        """Load all settings from file"""
        try:
            config_file = self._get_config_file()
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Settings load error: {e}")
        return {}

    def _load_setting(self, key, default):
        """Load a specific setting"""
        settings = self._load_settings()
        return settings.get(key, default)

    def _save_setting(self, key, value):
        """Save a setting to file"""
        try:
            config_file = self._get_config_file()
            settings = self._load_settings()
            settings[key] = value
            
            with open(config_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Settings save error: {e}")

    def load_theme_preference(self):
        """Load saved theme preference - keep your exisiting method"""
        try:
            config_file = self._get_config_file()
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('theme', 'Dark')
        except Exception as e:
            print(f"Could not load theme preference: {e}")
        return "Dark"

    def _create_download_section(self, parent):
        """Create download controls section"""
        try:
            # Download folder selection
            folder_frame = ctk.CTkFrame(parent)
            folder_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(folder_frame, text=self._s('download_folder'), font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            folder_select_frame = ctk.CTkFrame(folder_frame)
            folder_select_frame.pack(fill="x", pady=5)
            
            self.folder_path_label = ctk.CTkLabel(folder_select_frame, text=self._s('download_folder'), 
                                                anchor="w", width=300, wraplength=400)
            self.folder_path_label.pack(side="left", fill="x", expand=True)
            
            ctk.CTkButton(folder_select_frame, text="Browse", width=80,
                         command=self.select_download_folder).pack(side="right", padx=(5, 0))
            
            # URL Section
            ctk.CTkLabel(parent, text=self._s('download_url'), font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(10, 0))
            
            self.url_entry = ctk.CTkEntry(parent, width=400, font=ctk.CTkFont(size=12))
            self.url_entry.pack(fill="x", pady=5)
            self.url_entry.bind("<Return>", lambda e: self.add_to_queue())
            
            # Right-click menu for URL entry
            self.url_entry.bind("<Button-3>", self.show_menu)
            
            # Batch download section
            batch_frame = ctk.CTkFrame(parent)
            batch_frame.pack(fill="x", pady=10)
            
            ctk.CTkLabel(batch_frame, text=self._s('batch_download'), font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            self.batch_text = ctk.CTkTextbox(batch_frame, height=100, font=ctk.CTkFont(size=12))
            self.batch_text.pack(fill="x", pady=5)

            # Right-click menu for batch text
            self.batch_text.bind("<Button-3>", self.show_menu)
            
            ctk.CTkButton(batch_frame, text=self._s('add_all_to_queue'), 
                         command=self.add_batch_to_queue).pack(pady=5)
            
            # Control Buttons
            control_frame = ctk.CTkFrame(parent)
            control_frame.pack(fill="x", pady=10)

            
            self.add_queue_btn = ctk.CTkButton(control_frame, text=self._s('add_to_queue'), 
                                             command=self.add_to_queue)
            self.add_queue_btn.pack(side="left", padx=(0, 5))
            
            self.start_btn = ctk.CTkButton(control_frame, text=self._s('start_download'), 
                                         command=self.start_download)
            self.start_btn.pack(side="left", padx=5)
            
            self.pause_btn = ctk.CTkButton(control_frame, text=self._s('pause'), 
                                         command=self.pause_download, state="disabled")
            self.pause_btn.pack(side="left", padx=5)
            
            self.resume_btn = ctk.CTkButton(control_frame, text=self._s('resume'), 
                                          command=self.resume_download, state="disabled")
            self.resume_btn.pack(side="left", padx=5)

            self.cancel_btn = ctk.CTkButton(control_frame, text=self._s('cancel'), 
                                                  command=self.cancel_current_download, 
                                                  fg_color="red", hover_color="darkred",
                                                  state="disabled")
            self.cancel_btn.pack(side="left", padx=5)

            # Selection info label
            self.selection_info_label = ctk.CTkLabel(parent, text=self._s('no_items_selected'), 
                                                   text_color="gray", font=ctk.CTkFont(size=11))
            self.selection_info_label.pack(anchor="w", pady=(5, 0))
            
            # Update the _update_main_button_states to also update this label:
            def _update_main_button_states(self):
                """Update main control button states based on selection"""
                # Get selected items
                selected_items = [item for item in self.download_queue if item.selected]
                
                # Update selection info label
                if selected_items:
                    downloading = sum(1 for item in selected_items if item.status == "Downloading")
                    paused = sum(1 for item in selected_items if item.status == "Paused")
                    queued = sum(1 for item in selected_items if item.status == "Queued")
                    
                    info_text = f"Selected: {len(selected_items)} item(s)"
                    if downloading: info_text += f" | Downloading: {downloading}"
                    if paused: info_text += f" | Paused: {paused}"
                    if queued: info_text += f" | Queued: {queued}"
                    
                    self.selection_info_label.configure(text=info_text, text_color="#FFD700")
                else:
                    self.selection_info_label.configure(text="No items selected", text_color="gray")

            # History & Statistics Button
            self.history_btn = ctk.CTkButton(control_frame, text=self._s('history_stats'),command=self.show_history_statistics)
            self.history_btn.pack(side="left", padx=5)

            self.preference_btn = ctk.CTkButton(control_frame, text=self._s('preferences'), 
                                               command=self.show_preferences, width=100)
            self.preference_btn.pack(side="left",padx=5)

            # Status Section
            self.status_label = ctk.CTkLabel(parent, text=self._s('idle'), text_color="gray", font=ctk.CTkFont(size=12))
            self.status_label.pack(anchor="w", pady=5)
            
            # Overall Progress
            progress_frame = ctk.CTkFrame(parent)
            progress_frame.pack(fill="x", pady=10)
            
            self.overall_label = ctk.CTkLabel(progress_frame, text=self._s('overall').format(0), font=ctk.CTkFont(size=12))
            self.overall_label.pack(anchor="w")
            
            self.overall_speed_label = ctk.CTkLabel(progress_frame, text=self._s('speed').format(0.00), font=ctk.CTkFont(size=12))
            self.overall_speed_label.pack(anchor="w")
            
            self.overall_progress = ctk.CTkProgressBar(progress_frame, mode="determinate")
            self.overall_progress.set(0)
            self.overall_progress.pack(fill="x", pady=5)
            
            # Current file info
            self.current_file_label = ctk.CTkLabel(progress_frame, text=self._s('current_none'), text_color="gray", font=ctk.CTkFont(size=12))
            self.current_file_label.pack(anchor="w")
            
            # Thread Status Section
            thread_frame = ctk.CTkFrame(parent)
            thread_frame.pack(fill="both", expand=True, pady=10)
            
            ctk.CTkLabel(thread_frame, text=self._s('thread_status'), font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            self.thread_scrollable_frame = ctk.CTkScrollableFrame(thread_frame, height=150)
            self.thread_scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            self.thread_labels = []
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create download section: {str(e)}")

    def _create_queue_section(self, parent):
        """Create download queue management section"""
        try:
            ctk.CTkLabel(parent, text=self._s('download_queue'), font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            # ✅ ADD SELECTION CONTROLS FRAME
            selection_frame = ctk.CTkFrame(parent)
            selection_frame.pack(fill="x", padx=10, pady=(0, 5))
            
            # Left side: Selection controls
            select_controls = ctk.CTkFrame(selection_frame, fg_color="transparent")
            select_controls.pack(side="left", fill="x", expand=True)
            
            ctk.CTkButton(select_controls, text=self._s('select_all'), 
                        command=self._select_all_items, width=100).pack(side="left", padx=(0, 5))
            
            ctk.CTkButton(select_controls, text=self._s('deselect_all'), 
                        command=self._deselect_all_items, width=100).pack(side="left", padx=(0, 5))
            
            # Right side: Bulk actions
            bulk_controls = ctk.CTkFrame(selection_frame, fg_color="transparent")
            bulk_controls.pack(side="right")
            
            # Store references to bulk buttons for later enabling/disabling
            self.pause_selected_btn = ctk.CTkButton(bulk_controls, text=self._s('pause_selected'), 
                                                command=self._pause_selected, width=120,
                                                state="disabled")
            self.pause_selected_btn.pack(side="top", padx=2)
            
            self.resume_selected_btn = ctk.CTkButton(bulk_controls, text=self._s('resume_selected'), 
                                                command=self._resume_selected, width=120,
                                                state="disabled")
            self.resume_selected_btn.pack(side="top", padx=2)
            
            self.cancel_selected_btn = ctk.CTkButton(bulk_controls, text=self._s('cancel_selected'), 
                                                command=self._cancel_selected, width=120,
                                                fg_color="red", hover_color="darkred",
                                                state="disabled")
            self.cancel_selected_btn.pack(side="top", padx=2)
            
            # Existing Queue controls (moved down)
            queue_controls = ctk.CTkFrame(parent)
            queue_controls.pack(fill="x", padx=10, pady=(0, 10))
            
            ctk.CTkButton(queue_controls, text=self._s('clear_completed'), 
                        command=self.clear_completed, width=120).pack(side="left", padx=(0, 5))
            
            ctk.CTkButton(queue_controls, text=self._s('clear_all'), 
                        command=self.clear_all_queue, width=80).pack(side="right")
            
            # Queue list with proper height
            ctk.CTkLabel(parent, text=self._s('downloads'), font=ctk.CTkFont(size=14)).pack(anchor="w", padx=10, pady=(5, 0))
            
            self.queue_frame = ctk.CTkScrollableFrame(parent, height=300)  # Increased height
            self.queue_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.queue_item_frames = []
            self.queue_item_widgets = {}
            
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create queue section: {str(e)}")

    def show_menu(self, event):
        """Show right-click context menu for text widgets"""
        try:
            # Get the widget that was clicked
            widget = event.widget
            
            # Create menu
            menu = tk.Menu(self, tearoff=0)
            
            # Cut, Copy, Paste work the same way
            menu.add_command(label="Cut", 
                            command=lambda: widget.event_generate("<<Cut>>"))
            menu.add_command(label="Copy", 
                            command=lambda: widget.event_generate("<<Copy>>"))
            menu.add_command(label="Paste", 
                            command=lambda: widget.event_generate("<<Paste>>"))
            menu.add_separator()
            
            # Select All works differently
            menu.add_command(label="Select All", 
                            command=lambda: self._select_all_in_widget(widget))
            
            menu.tk_popup(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"Menu error: {e}")
        finally:
            try:
                menu.grab_release()
            except:
                pass

    def _select_all_in_widget(self, widget):
        """Handle Select All for different widget types"""
        if widget == self.url_entry:
            widget.select_range(0, 'end')  # For CTkEntry
        elif widget == self.batch_text:
            # For CTkTextbox, use the underlying tkinter text widget
            widget._textbox.event_generate("<<SelectAll>>")

    def select_download_folder(self):
        """Let user select download folder"""
        try:
            folder = filedialog.askdirectory(initialdir=self.download_folder)
            if folder:
                self.download_folder = folder
                self.folder_path_label.configure(text=folder)
        except Exception as e:
            messagebox.showerror("Folder Selection Error", f"Failed to select folder: {str(e)}")

    def add_to_queue(self):
        """Add single URL to download queue"""
        try:
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("Warning", "Please enter a URL")
                return
            
            if not url.startswith(('http://', 'https://')):
                messagebox.showwarning("Invalid URL", "Please enter a valid HTTP/HTTPS URL")
                return
            

            # 🔥 CHECK FOR DUPLICATE WHEN ADDING TO QUEUE 🔥
            filename = os.path.basename(url) or "downloaded_file"
            duplicate_action = self.check_duplicate_file(filename, url)
            
            if duplicate_action == "skip":
                messagebox.showinfo("Skipped", f"Skipped duplicate file: {filename}")
                return
            elif duplicate_action == "rename":
                filename = self.generate_unique_filename(filename)
            
          # 🔥 ADD DEBUG INFO TO TRACK THE ISSUE 🔥
            print("=== BEFORE ADDING TO QUEUE ===")
            self.debug_queue_state()
            
            download_item = DownloadItem(url, self.download_folder, filename)
            self.download_queue.append(download_item)
            
            print("=== AFTER ADDING TO QUEUE ===")
            self.debug_queue_state()

            # Single update call
            self._update_queue_display()
            
            self.url_entry.delete(0, 'end')
            messagebox.showinfo("Success", f"Added to queue: {url}")
            
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to add URL to queue: {str(e)}")   
            
    def add_batch_to_queue(self):
        """Add multiple URLs from text box to queue"""
        try:
            urls_text = self.batch_text.get("1.0", "end").strip()
            if not urls_text:
                messagebox.showwarning("Warning", "Please enter URLs in the batch box")
                return
            
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            added_count = 0
            invalid_urls = []
            skipped_duplicates = []
            

            for url in urls:
                if url and url.startswith(('http://', 'https://')):

                    # 🔥 CHECK FOR DUPLICATE FOR EACH URL 🔥
                    filename = os.path.basename(url) or "downloaded_file"
                    duplicate_action = self.check_duplicate_file(filename, url)
                    
                    if duplicate_action == "skip":
                        skipped_duplicates.append(url)
                        continue
                    elif duplicate_action == "rename":
                        filename = self.generate_unique_filename(filename)

                    download_item = DownloadItem(url, self.download_folder, filename)
                    self.download_queue.append(download_item)
                    added_count += 1
                elif url.strip():  # Non-empty but invalid URL
                    invalid_urls.append(url)
            
            self._update_queue_display()
            self.batch_text.delete("1.0", "end")
            
            message = f"Added {added_count} URLs to queue"
            if invalid_urls:
                message += f"\n\nInvalid URLs ignored:\n" + "\n".join(invalid_urls[:5])  # Show max 5 invalid URLs
                if len(invalid_urls) > 5:
                    message += f"\n... and {len(invalid_urls) - 5} more"
            
            messagebox.showinfo("Batch Add Result", message)
        except Exception as e:
            messagebox.showerror("Batch Error", f"Failed to add batch URLs: {str(e)}")

    def _update_queue_display(self):
        """Update the queue display without blinking"""
        try:

            if hasattr(self, '_updating_queue') and self._updating_queue:
                return
            self._updating_queue = True

            # Always refresh rather than recreate to prevent flickering
            self._refresh_queue_display()

            # Update main buttons state
            self._update_main_button_states()

            if hasattr(self, '_update_bulk_buttons_state'):
                self._update_bulk_buttons_state()

        except Exception as e:
            print(f"Queue display update error: {e}")
        finally:
            self._updating_queue = False

    def debug_queue_state(self):
        """Debug method to check queue state"""
        print(f"=== QUEUE DEBUG ===")
        print(f"Queue length: {len(self.download_queue)}")
        for i, item in enumerate(self.download_queue):
            print(f"  {i}: {item.url} | {item.status}")
        print(f"===================")

    def _refresh_queue_display(self):
        """Update existing queue items without recreating"""
        try:
            # Clear existing queue display
            for widget in self.queue_frame.winfo_children():
                widget.destroy()
            
            # Create new queue items with proper sizing
            for i, item in enumerate(self.download_queue):
                self._create_queue_item(i, item)

        except Exception as e:
            print(f"Queue refresh error: {e}")

    def _pause_single_download(self, index):
        """Pause a specific download by index"""
        try:
            if 0 <= index < len(self.download_queue):
                item = self.download_queue[index]
                if item.status == "Downloading" and item.downloader:
                    item.downloader.pause()
                    item.status = "Paused"
                    self._update_queue_display()
                    print(f"⏸ Paused individual download: {item.filename or item.url}")
                else:
                    print(f"⚠ Cannot pause: Item not downloading or no downloader")
        except Exception as e:
            print(f"❌ Error pausing individual download: {e}")

    def _resume_single_download(self, index):
        """Resume a specific download by index"""
        try:
            if 0 <= index < len(self.download_queue):
                item = self.download_queue[index]
                if item.status == "Paused" and item.downloader:
                    item.downloader.resume()
                    item.status = "Downloading"
                    self._update_queue_display()
                    print(f"▶ Resumed individual download: {item.filename or item.url}")
                else:
                    print(f"⚠ Cannot resume: Item not paused or no downloader")
        except Exception as e:
            print(f"❌ Error resuming individual download: {e}")

    def _cancel_single_download(self, index):
        """Cancel a specific download by index"""
        try:
            if 0 <= index < len(self.download_queue):
                item = self.download_queue[index]
                
                # Ask for confirmation (only if not already in error/cancelled state)
                if item.status in ["Queued", "Downloading", "Paused"]:
                    if not messagebox.askyesno("Confirm Cancel", 
                                            f"Cancel download: {item.filename or os.path.basename(item.url)}?"):
                        return
                
                # Handle based on status
                if item.status == "Downloading" and item.downloader:
                    # Mark as cancelled and stop the downloader
                    item.downloader.paused = True  # This will stop download threads
                    item.status = "Cancelled"
                    item.progress = 0
                    
                    # Record cancellation in history
                    self.history_manager.add_record(
                        url=item.url,
                        filename=item.filename or os.path.basename(item.url),
                        file_size=0,
                        status="Cancelled",
                        speed=0,
                        error_msg="Cancelled by user (individual)"
                    )
                    
                    # If this was the current active download, move to next
                    if self.current_download == item:
                        self._download_item_finished()
                    
                elif item.status == "Paused" and item.downloader:
                    item.status = "Cancelled"
                    item.progress = 0
                    
                    # Record cancellation in history
                    self.history_manager.add_record(
                        url=item.url,
                        filename=item.filename or os.path.basename(item.url),
                        file_size=0,
                        status="Cancelled",
                        speed=0,
                        error_msg="Cancelled by user (individual)"
                    )
                    
                    # If this was the current active download, move to next
                    if self.current_download == item:
                        self._download_item_finished()
                        
                elif item.status == "Queued":
                    # Just remove from queue (this will be handled by _remove_from_queue)
                    self._remove_from_queue(index)
                    return
                
                # Update the queue display to reflect the new status
                self._update_queue_display()
                print(f"✕ Cancelled individual download: {item.filename or item.url}")
                
        except Exception as e:
            print(f"❌ Error cancelling individual download: {e}")

    def _remove_from_queue(self, index):
        """Remove item from queue (updated to handle individual removal)"""
        try:
            if 0 <= index < len(self.download_queue):
                item = self.download_queue[index]
                
                # Record cancellation for queued items that are removed
                if item.status == "Queued":
                    self.history_manager.add_record(
                        url=item.url,
                        filename=item.filename or os.path.basename(item.url),
                        file_size=0,
                        status="Cancelled", 
                        speed=0,
                        error_msg="Removed from queue before download"
                    )
                
                # If removing current download, cancel it first
                if self.current_download == self.download_queue[index]:
                    self.cancel_current_download(confirm=False)
                
                del self.download_queue[index]
                self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to remove item: {str(e)}")

    def _create_queue_item(self, index, item):
        """Create a single queue item with selection and individual controls"""
        try:
            # Main frame for the queue item
            item_frame = ctk.CTkFrame(self.queue_frame, height=80)
            item_frame.pack(fill="x", pady=1, padx=1)
            item_frame.pack_propagate(False)
            
            # ✅ ADD CLICK-TO-SELECT FUNCTIONALITY
            def handle_frame_click(event):
                clicked_widget = event.widget

                # Don't allow selection of completed/cancelled/error items
                if item.status in ["Completed", "Cancelled", "Error"]:
                    return

                # Check if the clicked widget is the checkbox (if it exists)
                if item.selection_checkbox is not None:
                    if clicked_widget == item.selection_checkbox._canvas or clicked_widget == item.selection_checkbox:
                        return

                # Check if clicked widget is one of the buttons
                is_button_or_checkbox = False
                for btn in btn_frame.winfo_children():
                    if clicked_widget == btn or clicked_widget == btn._canvas:
                        is_button_or_checkbox = True
                        break

                if not is_button_or_checkbox:
                    item.selected = not item.selected
                    # Update checkbox if it exists
                    if item.selection_checkbox is not None:
                        item.selection_checkbox.select() if item.selected else item.selection_checkbox.deselect()

                    # Visual feedback
                    if item.selected:
                        item_frame.configure(border_width=2, border_color="#FFD700")
                        filename_label.configure(font=ctk.CTkFont(size=11, weight="bold"))
                    else:
                        item_frame.configure(border_width=0)
                        filename_label.configure(font=ctk.CTkFont(size=11, weight="normal"))

                    if item == self.current_download:
                        item_frame.configure(border_width=1, border_color="#3B8ED0")

                    self._update_queue_display()
            item_frame.bind("<Button-1>", handle_frame_click)
            
            # Content frame
            content_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            content_frame.pack(fill="both", expand=True, padx=3, pady=2)
            
            # Top row: Checkbox, filename, and action buttons
            top_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            top_frame.pack(fill="x", pady=(0, 1))
            
            # ✅ SELECTION CHECKBOX
            if item.status in ["Queued", "Downloading", "Paused"]:
                selection_var = ctk.BooleanVar(value=item.selected)
                
                # In _create_queue_item method, update the selection highlighting:
                def toggle_selection():
                    item.selected = selection_var.get()
                    # Visual feedback for selection
                    if item.selected:
                        # Highlight selected items with yellow border
                        item_frame.configure(border_width=2, border_color="#FFD700")  # Gold color for selected
                        filename_label.configure(font=ctk.CTkFont(size=11))
                    else:
                        item_frame.configure(border_width=0)
                        filename_label.configure(font=ctk.CTkFont(size=11, weight="normal"))
                    
                    # Also highlight if this is the current active download
                    if item == self.current_download:
                        item_frame.configure(border_width=1, border_color="#3B8ED0")  # Blue for current

                    self._update_queue_display()
            
                selection_cb = ctk.CTkCheckBox(
                    top_frame, 
                    text="", 
                    variable=selection_var,
                    command=toggle_selection,
                    width=20
                )
                selection_cb.pack(side="left", padx=(0, 5))
                selection_cb.bind("<Button-1>", lambda e: "break")  # Prevent frame click
                item.selection_checkbox = selection_cb
            else:
                # For completed items, add a placeholder to align
                placeholder = ctk.CTkLabel(top_frame, text="", width=20)
                placeholder.pack(side="left", padx=(0, 5))
                item.selection_checkbox = None  # No checkbox for completed items
                selection_cb = None  # Set to None for else branch
            
            # Filename (expanded area)
            filename = item.filename or os.path.basename(item.url) or "Unknown File"
            display_filename = filename[:40] + "..." if len(filename) > 40 else filename
            
            filename_label = ctk.CTkLabel(
                top_frame, 
                text=display_filename,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w"
            )
            filename_label.pack(side="left", fill="x", expand=True, padx=(0, 5))
            filename_label.bind("<Button-1>", lambda e: "break")  # Prevent frame click
            
            # ✅ INDIVIDUAL ACTION BUTTONS
            btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=(5, 0))
            
            # Status-specific individual buttons
            if item.status == "Queued":
                # Move up/down buttons
                ctk.CTkButton(btn_frame, text="▲", width=25, height=20,
                            command=lambda idx=index: self._move_up(idx),
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
                ctk.CTkButton(btn_frame, text="▼", width=25, height=20,
                            command=lambda idx=index: self._move_down(idx),
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
                # Remove button
                ctk.CTkButton(btn_frame, text="✕", width=25, height=20,
                            command=lambda idx=index: self._remove_from_queue(idx),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
            
            elif item.status == "Downloading":
                # Individual pause button for this item
                ctk.CTkButton(btn_frame, text="⏸", width=25, height=20,
                            command=lambda idx=index: self._pause_single_download(idx),
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
                # Individual cancel button for this item
                ctk.CTkButton(btn_frame, text="✕", width=25, height=20,
                            command=lambda idx=index: self._cancel_single_download(idx),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
            
            elif item.status == "Paused":
                # Individual resume button for this item
                ctk.CTkButton(btn_frame, text="▶", width=25, height=20,
                            command=lambda idx=index: self._resume_single_download(idx),
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
                # Individual cancel button for this item
                ctk.CTkButton(btn_frame, text="✕", width=25, height=20,
                            command=lambda idx=index: self._cancel_single_download(idx),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=9)).pack(side="left", padx=1)
            
            # Prevent button clicks from triggering frame selection
            for btn in btn_frame.winfo_children():
                btn.bind("<Button-1>", lambda e: "break")
            
            # Middle row: Status information
            middle_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            middle_frame.pack(fill="x", pady=(0, 1))
            
            status_colors = {
                "Queued": "gray",
                "Downloading": "#3B8ED0",
                "Paused": "orange", 
                "Completed": "green",
                "Error": "red",
                "Cancelled": "darkgray"
            }
            
            status_text = f"{item.status}"
            if item.status == "Downloading":
                status_text += f" | {item.progress:.1f}% | {item.speed:.2f} MB/s"
                if hasattr(item, 'file_size') and item.file_size > 0:
                    size_mb = item.file_size / (1024 * 1024)
                    status_text += f" | {size_mb:.1f} MB"
            elif item.status == "Error" and hasattr(item, 'error_message'):
                error_display = item.error_message[:40] + "..." if len(item.error_message) > 40 else item.error_message
                status_text += f" | {error_display}"
            
            status_label = ctk.CTkLabel(
                middle_frame, 
                text=status_text,
                text_color=status_colors.get(item.status, "gray"),
                font=ctk.CTkFont(size=10),
                anchor="w"
            )
            status_label.pack(fill="x")
            status_label.bind("<Button-1>", lambda e: "break")  # Prevent frame click
            
            # Bottom row: Timestamps
            bottom_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            bottom_frame.pack(fill="x")
            
            timestamp_info = f"Added: {item.added_time.strftime('%H:%M:%S')}"
            if item.start_time:
                timestamp_info += f" | Started: {item.start_time.strftime('%H:%M:%S')}"
            if item.end_time and item.status == "Completed":
                timestamp_info += f" | Finished: {item.end_time.strftime('%H:%M:%S')}"
            
            time_label = ctk.CTkLabel(
                bottom_frame,
                text=timestamp_info,
                font=ctk.CTkFont(size=9),
                text_color="lightgray",
                anchor="w"
            )
            time_label.pack(fill="x")
            time_label.bind("<Button-1>", lambda e: "break")  # Prevent frame click
            
            # Store references for later
            item.ui_frame = item_frame
            # selection_checkbox is already set in the if/else blocks above
            
            # Apply visual selection state
            if item.selected:
                item_frame.configure(border_width=1, border_color="#3B8ED0")
                
        except Exception as e:
            print(f"Error creating queue item {index}: {e}")

    def _move_up(self, index):
        """Move item up in queue"""
        try:
            if index > 0 and index < len(self.download_queue):
                self.download_queue[index], self.download_queue[index-1] = \
                    self.download_queue[index-1], self.download_queue[index]
                self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to move item up: {str(e)}")

    def _move_down(self, index):
        """Move item down in queue"""
        try:
            if index < len(self.download_queue) - 1:
                self.download_queue[index], self.download_queue[index+1] = \
                    self.download_queue[index+1], self.download_queue[index]
                self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to move item down: {str(e)}")

    def _remove_from_queue(self, index):
        """Remove item from queue"""
        try:
            if 0 <= index < len(self.download_queue):
                item = self.download_queue[index]
                
                # ✅ Record cancellation for queued items that are removed
                if item.status == "Queued":
                    self.history_manager.add_record(
                        url=item.url,
                        filename=item.filename or os.path.basename(item.url),
                        file_size=0,
                        status="Cancelled", 
                        speed=0,
                        error_msg="Removed from queue before download"
                    )
                
                # If removing current download, cancel it first
                if self.current_download == self.download_queue[index]:
                    self.cancel_current_download(confirm=False)
                
                del self.download_queue[index]
                self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to remove item: {str(e)}")

    def clear_completed(self):
        """Remove completed downloads from queue"""
        try:
            initial_count = len(self.download_queue)
            self.download_queue = [item for item in self.download_queue 
                                if item.status not in ["Completed", "Cancelled", "Error"]]
            removed_count = initial_count - len(self.download_queue)
            
            if removed_count > 0:
                self._update_queue_display()
                messagebox.showinfo("Queue Cleared", f"Removed {removed_count} completed items from queue")
            else:
                messagebox.showinfo("Queue Status", "No completed items to remove")
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to clear completed items: {str(e)}")

    def clear_all_queue(self):
        """Clear all items from queue"""
        try:
            if self.current_download and self.current_download.status == "Downloading":
                messagebox.showwarning("Warning", "Cannot clear queue while download is in progress")
                return
            
            if not self.download_queue:
                messagebox.showinfo("Queue Status", "Queue is already empty")
                return
            
            if messagebox.askyesno("Confirm", f"Clear all {len(self.download_queue)} downloads from queue?"):
                self.download_queue.clear()
                self._update_queue_display()
                messagebox.showinfo("Queue Cleared", "All items removed from queue")
        except Exception as e:
            messagebox.showerror("Queue Error", f"Failed to clear queue: {str(e)}")

    def _start_download_item(self, item):
        """Start downloading a specific item"""
        try:
            # Don't start if already downloading
            if item.status in ["Downloading"]:
                print(f"⚠ Item {item.filename} is already downloading")
                return

            # Don't start if already completed
            if item.status == "Completed":
                print(f"⚠ Item {item.filename} is already completed")
                return
                
            # Set this as active download ONLY for tracking purposes
            # But allow multiple items to be "current" by having a list
            if not hasattr(self, 'active_downloads'):
                self.active_downloads = []
            
            # Add to active downloads if not already there
            if item not in self.active_downloads:
                self.active_downloads.append(item)
            
            item.status = "Downloading"
            item.start_time = datetime.now()
            item.error_message = ""  # Clear previous errors
            
            # Update status to show which items are downloading
            active_count = len([d for d in self.active_downloads if d.status == "Downloading"])
            paused_count = len([d for d in self.active_downloads if d.status == "Paused"])
            
            status_text = f"Active: {active_count} downloading"
            if paused_count > 0:
                status_text += f", {paused_count} paused"
                
            self.status_label.configure(text=status_text, text_color="white")
            
            # Update current file label for this specific item
            short_name = item.filename or os.path.basename(item.url) or "Unknown"
            if len(short_name) > 30:
                short_name = short_name[:27] + "..."
            self.current_file_label.configure(text=f"Started: {short_name}")
            
            # Update button states based on selection
            self._update_main_button_states()
            
            # Update the queue display
            self._update_queue_display()
            
            # Start download in background thread
            threading.Thread(target=self._run_download_item, args=(item,), daemon=True).start()
            
            print(f"🚀 Started download: {item.filename} (Active downloads: {len(self.active_downloads)})")
            
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download item: {str(e)}")
            
    def _run_download_item(self, item):
        """Run the download for a queue item with proper error handling"""
        download_successful = False
        error_message = ""
        
        try:
            num_threads = 8  # Default thread count

            # Create downloader
            downloader = FastDownloader(
                item.url,
                num_threads=num_threads,
                progress_callback=lambda idx, speed, percent: self.progress_queue.put((idx, speed, percent)),
                download_path=item.download_path,
            )
        
        # ... rest of your existing code ...
            
            item.downloader = downloader
            self.downloader = downloader
            
            # Initialize progress arrays
            num_threads = downloader.num_threads
            self.thread_percents = [0] * num_threads
            self.thread_speed = [0] * num_threads
            
            # Update UI with thread count
            self.after(0, lambda: self._update_thread_labels_visibility(num_threads))
            self.after(0, lambda: self._ensure_thread_labels(downloader.num_threads))
            # Start download
            downloader.start()

            # Determine actual download path
            actual_download_path = item.download_path
            if hasattr(downloader, 'download_path') and downloader.download_path:
                actual_download_path = downloader.download_path

            if actual_download_path:
                expected_path = os.path.join(actual_download_path, downloader.filename)
                expected_path = os.path.abspath(expected_path)
            else:
                expected_path = downloader.filename
            
            # ✅ ADD DEBUG INFO
            print(f"🔍 DEBUG: Downloader filename: {downloader.filename}")
            print(f"🔍 DEBUG: Download path: {item.download_path}")
            print(f"🔍 DEBUG: Current directory: {os.getcwd()}")
            print(f"🔍 DEBUG: Looking for file at: {expected_path}")
            print(f"🔍 DEBUG: Downloader's download_path: {getattr(downloader, 'download_path', 'Not set')}")
            print(f"🔍 DEBUG: Item's download_path: {item.download_path}")

            # check multiple possible locations
            possible_paths = []
            # the expected path
            possible_paths.append(expected_path)
            # current working directory
            possible_paths.append(os.path.join(os.getcwd(), downloader.filename))
            # just the filename in current directory
            possible_paths.append(downloader.filename)
            # the downloader's download path
            if hasattr(downloader, 'download_path') and downloader.download_path:
                possible_paths.append(os.path.join(downloader.download_path, downloader.filename))
            # the temp file location
            if actual_download_path:
                possible_paths.append(os.path.join(actual_download_path, downloader.filename + ".temp"))

            found_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    found_path = os.path.abspath(path)
                    print(f"🔍 DEBUG: Found downloaded file at: {found_path}")
                    break

            if found_path:
                #verify file is not empty and has expected size
                file_size = os.path.getsize(found_path)
                if file_size > 0:
                    download_successful = True
                    item.filename = os.path.basename(found_path)
                    item.file_size = file_size
                    print(f"✅ File size: {file_size} bytes")
                else:
                    error_message = f"Downloaded file is empty (0 bytes) at {found_path}."
            else:
                #list files in download directory for debugging
                if item.download_path and os.path.exists(item.download_path):
                    print(f"📁 Files in download directory ({item.download_path}):")
                    for f in os.listdir(item.download_path):
                        print(f" - {f}")
                    
                    error_message = f"Download completed but file not found. Expected at: {expected_path}"
        
        except Exception as e:
            error_message = str(e)
            #✅ Better error message for connection issues
            if "403" in error_message:
                error_message = "Server blocked the download (403 Forbidden) - The website may block download managers"
            elif "Connection aborted" in error_message or "RemoteDisconnected" in error_message:
                error_message = "Connection lost with server"
            elif "Timed out" in error_message.lower():
                error_message = "Connection timed out"
            elif "size mismatch" in error_message.lower():
                error_message = "Downloaded file doesn't match expected size"
            print(f"Download error: {error_message}")

        finally:
            if download_successful:
                # Download completed successfully
                item.status = "Completed"
                item.progress = 100
                item.end_time = datetime.now()
                self.after(0, lambda: self._categorize_file(item))
                
                # Record successful completion
                self.history_manager.add_record(
                    url=item.url,
                    filename=item.filename or os.path.basename(item.url),
                    file_size=item.file_size,
                    status="Completed",
                    speed=sum(self.thread_speed) if self.thread_speed else 0
                )
                print(f"✅ Download completed successfully: {item.filename}")
            else:
                item.status = "Error"
                item.error_message = error_message
                item.progress = 0
                item.end_time = datetime.now()

                # Start next download if any
                self._check_and_start_next_download()
                
                # Record error
                self.history_manager.add_record(
                    url=item.url,
                    filename=item.filename or os.path.basename(item.url),
                    file_size=0,
                    status="Error",
                    speed=0,
                    error_msg= error_message
                )
                print(f"Download error: {error_message}")
            
                # Move to next item or finish
            self.after(0, self._download_item_finished)

    def generate_unique_filename(self, filename):
        """Generate a unique filename by appending numbers if duplicate exists"""
        try:
            base, ext = os.path.splitext(filename)
            counter = 1
            new_filename = filename
            
            while os.path.exists(os.path.join(self.download_folder, new_filename)):
                new_filename = f"{base}_{counter}{ext}"
                counter += 1
            
            return new_filename
        except Exception as e:
            print(f"Error generating unique filename: {e}")
            return filename

    def check_duplicate_file(self, filename, url=None):
        """Check if file already exists in download folder with settings"""
        try:
            filepath = os.path.join(self.download_folder, filename)
            
            if not os.path.exists(filepath):
                return "proceed"
            
            # Use settings directly (avoids UI variable issues)
            skip_duplicates = self._load_setting('skip_duplicates', False)
            auto_rename = self._load_setting('auto_rename', False)
            
            # Check settings for automatic behavior
            if skip_duplicates:
                return "skip"
            elif auto_rename:
                return "rename"
            
            # Manual prompt
            response = messagebox.askyesnocancel(
                "Duplicate File Found", 
                f"File '{filename}' already exists.\n\n"
                f"What would you like to do?\n\n"
                f"• Yes: Rename new file\n"
                f"• No: Overwrite existing file\n"
                f"• Cancel: Skip this download"
            )
            
            if response is None:  # Cancel
                return "skip"
            elif response:  # Yes - Rename
                return "rename"
            else:  # No - Overwrite
                return "overwrite"
            
        except Exception as e:
            print(f"Duplicate check error: {e}")
            return "proceed"

    def show_history_statistics(self):
        """Show download history and statistics window"""
        try:
            # Create history window
            history_window = ctk.CTkToplevel(self)
            history_window.title("Download History & Statistics")
            history_window.geometry("800x600")
            history_window.transient(self)
            history_window.grab_set()
            
            # Create tab view
            tab_view = ctk.CTkTabview(history_window)
            tab_view.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Statistics Tab
            stats_tab = tab_view.add("Statistics")
            self._create_stats_tab(stats_tab)
            
            # Recent Downloads Tab
            history_tab = tab_view.add("Recent Downloads")
            self._create_history_tab(history_tab)
            
            # Export Tab
            export_tab = tab_view.add("Export")
            self._create_export_tab(export_tab)
            
        except Exception as e:
            messagebox.showerror("History Error", f"Failed to open history: {str(e)}")

    def _create_stats_tab(self, parent):
        """Create statistics tab content"""
        # Get statistics
        stats = self.history_manager.get_statistics(days=30)
        
        # Statistics frame
        stats_frame = ctk.CTkScrollableFrame(parent)
        stats_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Overall statistics
        ctk.CTkLabel(stats_frame, text="Last 30 Days Statistics", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=10)
        
        # Stats grid
        stats_grid = ctk.CTkFrame(stats_frame)
        stats_grid.pack(fill="x", pady=10)
        
        stats_data = [
            ("Total Downloads", f"{stats['total_downloads']}"),
            ("Successful", f"{stats['successful_downloads']}"),
            ("Failed", f"{stats['failed_downloads']}"),
            ("Success Rate", f"{stats['success_rate']:.1f}%"),
            ("Total Size", f"{stats['total_size'] / (1024*1024*1024):.2f} GB"),
            ("Average Speed", f"{stats['average_speed']:.2f} MB/s")
        ]
        
        for i, (label, value) in enumerate(stats_data):
            row = i % 3
            col = i // 3
            
            stat_frame = ctk.CTkFrame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            ctk.CTkLabel(stat_frame, text=label, font=ctk.CTkFont(size=12), 
                        text_color="gray").pack(anchor="w")
            ctk.CTkLabel(stat_frame, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")

    def _create_history_tab(self, parent):
        """Create recent downloads history tab"""
        # Get recent downloads
        recent_downloads = self.history_manager.get_recent_downloads(limit=100)
        
        # History frame
        history_frame = ctk.CTkScrollableFrame(parent)
        history_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        if not recent_downloads:
            ctk.CTkLabel(history_frame, text="No download history yet", 
                        text_color="gray").pack(pady=20)
            return
        
        for record in recent_downloads:
            self._create_history_item(history_frame, record)

    def _create_history_item(self, parent, record):
        """Create a single history item"""
        item_frame = ctk.CTkFrame(parent)
        item_frame.pack(fill="x", pady=2, padx=5)
        
        # Status color
        status_colors = {
            "Completed": "green",
            "Error": "red",
            "Started": "blue",
            "Cancelled": "gray"
        }
        
        # Left side - Basic info
        left_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=3)
        
        # Filename and status
        filename = record.get('filename', 'Unknown')
        display_name = filename[:50] + "..." if len(filename) > 50 else filename
        
        ctk.CTkLabel(left_frame, text=display_name, 
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w").pack(fill="x")
        
        status_text = f"Status: {record['status']}"
        if record.get('file_size'):
            size_mb = record['file_size'] / (1024 * 1024)
            status_text += f" | Size: {size_mb:.1f} MB"
        if record.get('download_speed'):
            status_text += f" | Speed: {record['download_speed']:.2f} MB/s"
        
        ctk.CTkLabel(left_frame, text=status_text,
                    text_color=status_colors.get(record['status'], "gray"),
                    font=ctk.CTkFont(size=10),
                    anchor="w").pack(fill="x")
        
        # Timestamp
        timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        ctk.CTkLabel(left_frame, text=timestamp,
                    font=ctk.CTkFont(size=9),
                    text_color="lightgray",
                    anchor="w").pack(fill="x")

    def _create_export_tab(self, parent):
        """Create export tab content"""
        export_frame = ctk.CTkFrame(parent)
        export_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(export_frame, text="Export Options",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Export buttons
        ctk.CTkButton(export_frame, text="Export to CSV", 
                    command=self.export_history_csv,
                    width=200).pack(pady=10)
        
        ctk.CTkButton(export_frame, text="🗑️ Cleanup Downloaded Files", 
                        command=self.cleanup_downloaded_files,
                        fg_color="orange", hover_color="darkorange",
                        width=200).pack(pady=5)

        ctk.CTkButton(export_frame, text="Clear History", 
                    command=self.clear_history,
                    fg_color="red", hover_color="darkred",
                    width=200).pack(pady=10)
        
        # History info
        total_records = len(self.history_manager.history)
        ctk.CTkLabel(export_frame, text=f"Total records: {total_records}",
                    font=ctk.CTkFont(size=12),
                    text_color="gray").pack(pady=10)

    def export_history_csv(self):
        """Export history to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                if self.history_manager.export_to_csv(filename):
                    messagebox.showinfo("Export Successful", f"History exported to {filename}")
                else:
                    messagebox.showerror("Export Failed", "Failed to export history")
        except Exception as e:
            messagebox.showerror("Export Error", f"Export failed: {str(e)}")

    def clear_history(self):
        """Clear download history with file cleanup options"""
        try:
            response = messagebox.askyesnocancel(
                "Clear History Options",
                "What would you like to clear?\n\n"
                "• Yes: Clear history records only (keep files)\n"
                "• No: Clear history AND delete downloaded files\n"
                "• Cancel: Do nothing"
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - Clear history only
                self.history_manager.clear_history()
                messagebox.showinfo("History Cleared", "Download history has been cleared")
            else:  # No - Clear history AND delete files
                deleted_count = self.delete_downloaded_files()
                self.history_manager.clear_history()
                messagebox.showinfo("History Cleared", 
                                    f"Download history cleared and {deleted_count} files deleted")
                
        except Exception as e:
            messagebox.showerror("Clear Error", f"Failed to clear history: {str(e)}")

    def delete_downloaded_files(self):
        """Delete all downloaded files from history"""
        try:
            deleted_count = 0
            history_records = self.history_manager.get_recent_downloads(limit=1000)  # Get all records
            
            for record in history_records:
                if record['status'] == 'Completed':
                    filename = record.get('filename')
                    if filename:
                        filepath = os.path.join(self.download_folder, filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            deleted_count += 1
                            print(f"Deleted: {filename}")
            
            return deleted_count
            
        except Exception as e:
            print(f"File deletion error: {e}")
            return 0   

    def _download_item_finished(self):
        """Handle completion of a download item (success or error)"""
        try:
            # Clear thread display
            self.thread_percents = []
            self.thread_speed = []
            
            # Hide all thread labels
            for label in self.thread_labels:
                label.pack_forget()
            
            # Clear current download references
            self.current_download = None
            self.downloader = None
            
            # Update status based on remaining active downloads
            active_downloads = [item for item in self.download_queue 
                              if item.status in ["Downloading", "Paused"]]
            
            if active_downloads:
                active_count = len([d for d in active_downloads if d.status == "Downloading"])
                paused_count = len([d for d in active_downloads if d.status == "Paused"])
                
                status_text = f"Active: {active_count} downloading"
                if paused_count > 0:
                    status_text += f", {paused_count} paused"
                self.status_label.configure(text=status_text, text_color="white")
                
                # Update current file info if there are active downloads
                if active_count > 0:
                    current_files = ", ".join([item.filename[:20] + "..." if len(item.filename) > 20 else item.filename 
                                              for item in active_downloads[:2] if item.status == "Downloading"])
                    if active_count > 2:
                        current_files += f" (+{active_count - 2} more)"
                    self.current_file_label.configure(text=f"Current: {current_files}")
                else:
                    self.current_file_label.configure(text="Current: None (paused)")
            else:
                # No active downloads
                self.status_label.configure(text="Idle", text_color="green")
                self.current_file_label.configure(text="Current: None")
                
                # Check if we should auto-start next download
                self._check_and_start_next_download()
            
            # Update button states
            self._update_main_button_states()
            
            # Update queue display (this will refresh checkboxes, etc.)
            self._update_queue_display()
            
            self._ensure_thread_labels(0)   # hides all thread labels

        except Exception as e:
            print(f"Download finished error: {e}")

    def _start_next_download(self):
        """Start the next download in queue"""
        try:
            for item in self.download_queue:
                if item.status == "Queued":
                    self._start_download_item(item)
                    return
        except Exception as e:
            print(f"Next download error: {e}")

    def _update_thread_labels_visibility(self, num_threads):
        """Show/hide thread labels based on actual thread count"""
        try:
            for i, label in enumerate(self.thread_labels):
                if i < num_threads:
                    label.pack(anchor="w", pady=1)
                else:
                    label.pack_forget()
        except Exception as e:
            print(f"Thread label update error: {e}")

    def _ensure_thread_labels(self, needed):
        """Make sure we have at least 'needed' thread labels, creating them on demand."""
        # Create new labels if we don't have enough
        while len(self.thread_labels) < needed:
            lbl = ctk.CTkLabel(
                self.thread_scrollable_frame,
                text="",
                text_color="gray",
                font=ctk.CTkFont(size=11)
            )
            lbl.pack(anchor="w", pady=1)
            self.thread_labels.append(lbl)
        
        # Show the first 'needed' labels, hide any extras
        for i, lbl in enumerate(self.thread_labels):
            if i < needed:
                # Make sure it's visible (pack it again if hidden)
                lbl.pack(anchor="w", pady=1)
            else:
                lbl.pack_forget()

    def start_download(self):

        """Start SELECTED queued downloads"""
        try:
            # Get selected queued items
            selected_queued = [item for item in self.download_queue 
                              if item.selected and item.status == "Queued"]
            
            if selected_queued:
                print(f"🚀 Starting {len(selected_queued)} selected queued item(s)")
                # Start each selected queued item
                for item in selected_queued:
                    self._start_download_item(item)
                
                # Clear selection after starting
                for item in selected_queued:
                    item.selected = False
                    
                self._update_queue_display()
                self.status_label.configure(
                    text=f"Started {len(selected_queued)} selected item(s)", 
                    text_color="white"
                )
            else:
                # If nothing selected, find first queued item
                queued_items = [item for item in self.download_queue if item.status == "Queued"]
                if queued_items:
                    print(f"🚀 Starting first queued item: {queued_items[0].filename}") 
                    self._start_download_item(queued_items[0])
                    self.status_label.configure(
                        text=f"Started: {queued_items[0].filename}", 
                        text_color="white"
                    )
                else:
                    messagebox.showwarning("Warning", "No queued items to download")
                    
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download: {str(e)}")

    def pause_download(self):
        """Pause SELECTED downloads that are downloading"""
        try:
            selected_items = [item for item in self.download_queue if item.selected]
            
            if selected_items:
                # Pause all selected downloading items
                paused_count = 0
                for item in selected_items:
                    if item.status == "Downloading" and item.downloader:
                        item.downloader.pause()
                        item.status = "Paused"
                        paused_count += 1
                
                if paused_count > 0:
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Paused {paused_count} selected item(s)", 
                        text_color="orange"
                    )
                    print(f"⏸ Paused {paused_count} selected item(s)")
                else:
                    messagebox.showinfo("Info", "No downloading items selected to pause")
            else:
                # If nothing selected, pause current active download
                active_downloads = [item for item in self.download_queue 
                                  if item.status == "Downloading"]
                if active_downloads:
                    for item in active_downloads:
                        if item.downloader:
                            item.downloader.pause()
                            item.status = "Paused"
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Paused {len(active_downloads)} active download(s)", 
                        text_color="orange"
                    )
                else:
                    messagebox.showinfo("Info", "No active downloads to pause")
                    
        except Exception as e:
            messagebox.showerror("Pause Error", f"Failed to pause download: {str(e)}")

    def pause_download(self):
        """Pause SELECTED downloads that are downloading"""
        try:
            selected_items = [item for item in self.download_queue if item.selected]
            
            if selected_items:
                # Pause all selected downloading items
                paused_count = 0
                for item in selected_items:
                    if item.status == "Downloading" and item.downloader:
                        # Ensure the downloader has a paused attribute
                        if not hasattr(item.downloader, 'paused'):
                            print(f"⚠ Downloader missing paused attribute: {item.filename}")
                            # Add the attribute if missing
                            item.downloader.paused = False
                        
                        item.downloader.pause()
                        item.downloader.paused = True  # Explicitly set to True
                        item.status = "Paused"
                        paused_count += 1
                        print(f"⏸ Paused: {item.filename}")
                
                if paused_count > 0:
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Paused {paused_count} selected item(s)", 
                        text_color="orange"
                    )
                    print(f"⏸ Paused {paused_count} selected item(s)")
                else:
                    messagebox.showinfo("Info", "No downloading items selected to pause")
            else:
                # If nothing selected, pause all active downloads
                active_downloads = [item for item in self.download_queue 
                                if item.status == "Downloading"]
                if active_downloads:
                    for item in active_downloads:
                        if item.downloader:
                            if not hasattr(item.downloader, 'paused'):
                                item.downloader.paused = False
                            item.downloader.pause()
                            item.downloader.paused = True
                            item.status = "Paused"
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Paused {len(active_downloads)} active download(s)", 
                        text_color="orange"
                    )
                    print(f"⏸ Paused {len(active_downloads)} active download(s)")
                else:
                    messagebox.showinfo("Info", "No active downloads to pause")
            
            # Update button states
            self._update_main_button_states()
                    
        except Exception as e:
            messagebox.showerror("Pause Error", f"Failed to pause download: {str(e)}")

    def cancel_current_download(self):
        """Cancel SELECTED downloads (or current if none selected)"""
        try:
            selected_items = [item for item in self.download_queue if item.selected]
            
            if selected_items:
                # Cancel selected items
                if not messagebox.askyesno("Confirm Cancel", 
                                          f"Cancel {len(selected_items)} selected download(s)?"):
                    return
                
                cancelled_count = 0
                for item in selected_items:
                    if item.status in ["Queued", "Downloading", "Paused"]:
                        # Stop the downloader if it exists
                        if item.downloader:
                            item.downloader.paused = True
                        
                        # Record in history
                        self.history_manager.add_record(
                            url=item.url,
                            filename=item.filename or os.path.basename(item.url),
                            file_size=0,
                            status="Cancelled",
                            speed=0,
                            error_msg="Cancelled by user (selected)"
                        )
                        
                        item.status = "Cancelled"
                        item.progress = 0

                        # Remove from active downloads if present
                        if hasattr(self, 'active_downloads') and item in self.active_downloads:
                            self.active_downloads.remove(item)
                            print(f"Removed {item.filename} from active downloads")

                        cancelled_count += 1
                        print(f"✕ Cancelled: {item.filename}")
                
                if cancelled_count > 0:
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Cancelled {cancelled_count} selected item(s)", 
                        text_color="red"
                    )
                    self._check_and_start_next_download()

                    if not any(item.status == "Downloading" for item in self.download_queue):
                        auto_start = self._load_setting('auto_start', False)
                        if auto_start:
                            queued_items = [item for item in self.download_queue if item.status == "Queued"]
                            if queued_items:
                                self.after(1000, lambda: self._start_download_item(queued_items[0]))
                else:
                    messagebox.showinfo("Info", "No cancellable items selected")
                    
            else:
                # If nothing selected, cancel all active downloads
                active_items = [item for item in self.download_queue 
                               if item.status in ["Downloading", "Paused"]]
                
                if active_items:
                    if not messagebox.askyesno("Confirm Cancel", 
                                              f"Cancel {len(active_items)} active download(s)?"):
                        return
                    
                    cancelled_count = 0
                    for item in active_items:
                        if item.downloader:
                            item.downloader.paused = True
                        
                        self.history_manager.add_record(
                            url=item.url,
                            filename=item.filename or os.path.basename(item.url),
                            file_size=0,
                            status="Cancelled",
                            speed=0,
                            error_msg="Download cancelled by user"
                        )
                        
                        item.status = "Cancelled"
                        item.progress = 0

                        # Remove from active downloads if present
                        if hasattr(self, 'active_downloads') and item in self.active_downloads:
                            self.active_downloads.remove(item)
                            print(f"Removed {item.filename} from active downloads")

                        cancelled_count += 1
                        print(f"✕ Cancelled: {item.filename}")
                    
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Cancelled {len(active_items)} active download(s)", 
                        text_color="red"
                    )

                    self._check_and_start_next_download()

                    if not any(item.status == "Downloading" for item in self.download_queue):
                        auto_start = self._load_setting('auto_start', False)
                        if auto_start:
                            queued_items = [item for item in self.download_queue if item.status == "Queued"]
                            if queued_items:
                                self.after(1000, lambda: self._start_download_item(queued_items[0]))

                else:
                    messagebox.showinfo("Info", "No active downloads to cancel")

            self._update_main_button_states()
                    
        except Exception as e:
            messagebox.showerror("Cancel Error", f"Failed to cancel download: {str(e)}")

    def update_thread_display(self):
        """Update the UI with current progress and speeds"""
        try:
            # Determine how many threads are active
            active_threads = len(self.thread_percents)

            # Ensure we have enough thread labels (creates them if needed)
            self._ensure_thread_labels(active_threads)

            # Process queued progress updates
            while not self.progress_queue.empty():
                try:
                    item = self.progress_queue.get_nowait()
                    if isinstance(item, tuple) and len(item) == 3:
                        idx, speed, percent = item
                        
                        # Ensure arrays are large enough
                        while len(self.thread_percents) <= idx:
                            self.thread_percents.append(0)
                        while len(self.thread_speed) <= idx:
                            self.thread_speed.append(0)
                        
                        # Update progress and speed
                        self.thread_percents[idx] = percent
                        self.thread_speed[idx] = speed
                        
                        # Update current download progress
                        if self.current_download:
                            self.current_download.progress = percent
                            self.current_download.speed = speed
                        
                except queue.Empty:
                    break

            # Update all thread labels based on current arrays
            for i in range(active_threads):
                if i < len(self.thread_labels):
                    speed = self.thread_speed[i] if i < len(self.thread_speed) else 0
                    percent = self.thread_percents[i] if i < len(self.thread_percents) else 0
                    bar_length = 15
                    filled = int(percent / 100 * bar_length) if percent else 0
                    bar = "█" * filled + "░" * (bar_length - filled)
                    status = f"Thread {i+1}: {speed:5.2f} MB/s ({percent:5.1f}%) {bar}"
                    self.thread_labels[i].configure(text=status)

            # Update overall progress
            if self.thread_percents:
                valid_percents = [p for p in self.thread_percents if p is not None]
                if valid_percents:
                    overall_percent = sum(valid_percents) / len(valid_percents)
                    self.overall_label.configure(text=f"Overall: {overall_percent:.1f}%")
                    self.overall_progress.set(overall_percent / 100)

            # Update overall speed
            if self.thread_speed:
                valid_speeds = [s for s in self.thread_speed if s is not None]
                if valid_speeds:
                    total_speed = sum(valid_speeds)
                    self.overall_speed_label.configure(text=f"Speed: {total_speed:.2f} MB/s")

            # Update queue display (only refreshes, no recreation unless needed)
            if self.download_queue:
                # Only update if there are significant changes
                pass  # We're already doing efficient updates

        except Exception as e:
            print(f"UI update error: {e}")

        # Schedule next update
        self.after(100, self.update_thread_display)

    def resume_download(self):
        """Resume SELECTED paused downloads, or all paused if none selected"""
        try:
            # Get selected items
            selected_items = [item for item in self.download_queue if item.selected]
            
            if selected_items:
                # Resume all selected paused items
                resumed_count = 0
                failed_count = 0

                for item in selected_items:
                    if item.status == "Paused" and item.downloader:
                        try:    
                            # Check if downloader is actually paused
                            if hasattr(item.downloader, 'paused') and item.downloader.paused:
                                item.downloader.resume()
                                item.status = "Downloading"
                                item.downloader.paused = False
                                resumed_count += 1
                                print(f"▶ Resumed: {item.filename}")
                            else:
                                print(f"⚠️ Downloader not paused or no paused attribute for: {item.filename}")
                                failed_count += 1
                        except Exception as e:
                            print(f"Error resuming {item.filename}: {e}")
                            item.error_message = f"Resume error: {e}"
                            failed_count += 1

                    elif item.status == "Paused" and not item.downloader:
                        print(f"⚠️ No downloader instance for paused item: {item.filename}")
                        # Try to restart the download from scratch
                        try:
                            print(f"🔄 Restarting download: {item.filename}")
                            # Change status back to Queued so it can be started again
                            item.status = "Queued"
                            item.progress = 0
                            # Remove from active downloads if present
                            if hasattr(self, 'active_downloads') and item in self.active_downloads:
                                self.active_downloads.remove(item)
                            resumed_count += 1
                        except Exception as e:
                            print(f"❌ Failed to restart: {e}")
                            failed_count += 1

                if resumed_count > 0:
                    self._update_queue_display()
                    self.status_label.configure(
                        text=f"Resumed {resumed_count} selected item(s)", 
                        text_color="white"
                    )
                    print(f"▶ Resumed {resumed_count} selected item(s)")

                    # If any failed to resume, show a warning
                    if failed_count > 0:
                        messagebox.showinfo("Partial Success",
                                            f"Resumed {resumed_count} items, but {failed_count} failed to resume.")

                else:
                    messagebox.showinfo("Info", "No paused items selected to resume")
            else:
                # If nothing selected, resume all paused downloads
                paused_items = [item for item in self.download_queue 
                            if item.status == "Paused"]
                
                if paused_items:
                    resumed_count = 0
                    failed_count = 0


                    for item in paused_items:
                        if item.downloader:
                            try:
                                if hasattr(item.downloader, 'paused') and item.downloader.paused:    
                                    item.downloader.resume()
                                    item.status = "Downloading"
                                    resumed_count += 1
                                    print(f"▶ Resumed: {item.filename}")
                                else:
                                    print(f"⚠️ Downloader not paused or no paused attribute for: {item.filename}")
                                    failed_count += 1
                            except Exception as e:
                                print(f"Error resuming {item.filename}: {e}")
                                item.error_message = f"Resume error: {e}"
                                failed_count += 1
                        else:
                            print(f"⚠️ No downloader instance for paused item: {item.filename}")
                            # Try to restart the download from scratch
                            try:
                                print(f"🔄 Restarting download: {item.filename}")
                                # Change status back to Queued so it can be started again
                                item.status = "Queued"
                                item.progress = 0
                                # Remove from active downloads if present
                                if hasattr(self, 'active_downloads') and item in self.active_downloads:
                                    self.active_downloads.remove(item)
                                resumed_count += 1
                            except Exception as e:
                                print(f"❌ Failed to restart: {e}")
                                failed_count += 1
                        
                    if resumed_count > 0:
                        self._update_queue_display()
                        self.status_label.configure(
                            text=f"Resumed {resumed_count} paused item(s)", 
                            text_color="white"
                        )
                        print(f"▶ Resumed {resumed_count} paused item(s)")

                        if failed_count > 0:
                            messagebox.showinfo("Partial Success",
                                                f"Resumed {resumed_count} items, but {failed_count} failed to resume.")

                    else:
                        messagebox.showinfo("Info", "No paused downloads to resume")
                else:
                    messagebox.showinfo("Info", "No paused downloads to resume")
            
            # Update button states using centralized method
            self._update_main_button_states()
                    
        except Exception as e:
            messagebox.showerror("Resume Error", f"Failed to resume download: {str(e)}")

    def _check_and_start_next_download(self):
        """Check if auto-start is enabled and start next queued download"""
        try:
            # Check if there are any downloads running
            if not any(item.status == "Downloading" for item in self.download_queue):
                # Check if auto-start is enabled
                auto_start = self._load_setting('auto_start', False)
                if auto_start:
                    queued_items = [item for item in self.download_queue if item.status == "Queued"]
                    if queued_items:
                        print(f"🔄 Auto-starting next download: {queued_items[0].filename}")
                        self.after(1000, lambda: self._start_download_item(queued_items[0]))
                        return True
            return False
        except Exception as e:
            print(f"Error in auto-start check: {e}")
            return False

    def _update_main_button_states(self):
        """Update main control button states based on selection and overall state"""
        try:
            # Get selected items
            selected_items = [item for item in self.download_queue if item.selected]

            # debug info
            print(f"\n=== DEBUG: _update_main_button_states ===")
            print(f"Total queue items: {len(self.download_queue)}")
            print(f"Selected items: {len(selected_items)}")

            for i,item in enumerate(self.download_queue):
                print(f"[{i}] {item.filename[:20]}: status={item.status}, selected={item.selected}")
            
            if selected_items:
                # Check what actions are possible on selected items
                can_start = any(item.status == "Queued" for item in selected_items)
                can_pause = any(item.status == "Downloading" for item in selected_items)
                can_resume = any(item.status == "Paused" for item in selected_items)
                can_cancel = any(item.status in ["Queued", "Downloading", "Paused"] 
                               for item in selected_items)
                
                print(f"can_start={can_start}, can_pause={can_pause}, can_resume={can_resume}, can_cancel={can_cancel}")

                # Update button states
                self.start_btn.configure(state="normal" if can_start else "disabled")
                self.pause_btn.configure(state="normal" if can_pause else "disabled")
                self.resume_btn.configure(state="normal" if can_resume else "disabled")
                self.cancel_btn.configure(state="normal" if can_cancel else "disabled")
                
                # Update selection info label
                downloading = sum(1 for item in selected_items if item.status == "Downloading")
                paused = sum(1 for item in selected_items if item.status == "Paused")
                queued = sum(1 for item in selected_items if item.status == "Queued")
                
                info_text = f"Selected: {len(selected_items)} item(s)"
                if downloading: info_text += f" | Downloading: {downloading}"
                if paused: info_text += f" | Paused: {paused}"
                if queued: info_text += f" | Queued: {queued}"
                
                if hasattr(self, 'selection_info_label'):
                    self.selection_info_label.configure(text=info_text, text_color="#FFD700")
            else:
                # No selection - check overall state
                queued_items = [item for item in self.download_queue if item.status == "Queued"]
                downloading_items = [item for item in self.download_queue if item.status == "Downloading"]
                paused_items = [item for item in self.download_queue if item.status == "Paused"]

                print(f"No selection: queued={len(queued_items)}, downloading={len(downloading_items)}, paused={len(paused_items)}")
                
                # Enable buttons if there's something to do
                self.start_btn.configure(state="normal" if queued_items else "disabled")
                self.pause_btn.configure(state="normal" if downloading_items else "disabled")
                self.resume_btn.configure(state="normal" if paused_items else "disabled")
                self.cancel_btn.configure(state="normal" if downloading_items or paused_items else "disabled")

            # Print final button states for debugging
            start_state = self.start_btn.cget("state")
            pause_state = self.pause_btn.cget("state")
            resume_state = self.resume_btn.cget("state")
            cancel_state = self.cancel_btn.cget("state")
                
            print(f"Button states: Start={start_state}, Pause={pause_state}, Resume={resume_state}, Cancel={cancel_state}")
            print("=========================================\n")

        except Exception as e:
            print(f"Error updating button states: {e}")

    def _select_all_items(self):
        """Select all items in the queue"""
        for item in self.download_queue:
            item.selected = True
        self._update_queue_display()
        self._update_bulk_buttons_state()

    def _deselect_all_items(self):
        """Deselect all items in the queue"""
        for item in self.download_queue:
            item.selected = False
        self._update_queue_display()
        self._update_bulk_buttons_state()

    def _pause_selected(self):
        """Pause all selected downloads"""
        selected_items = [item for item in self.download_queue if item.selected]
        for item in selected_items:
            if item.status == "Downloading" and item.downloader:
                item.downloader.pause()
                item.status = "Paused"
        self._update_queue_display()
        print(f"⏸ Paused {len(selected_items)} selected items")

    def _resume_selected(self):
        """Resume all selected downloads"""
        selected_items = [item for item in self.download_queue if item.selected]
        for item in selected_items:
            if item.status == "Paused" and item.downloader:
                item.downloader.resume()
                item.status = "Downloading"
        self._update_queue_display()
        print(f"▶ Resumed {len(selected_items)} selected items")

    def _cancel_selected(self):
        """Cancel all selected downloads"""
        selected_items = [item for item in self.download_queue if item.selected]
        
        if not selected_items:
            return
        
        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Confirm Cancel", 
            f"Cancel {len(selected_items)} selected download(s)?"
        )
        
        if not confirm:
            return
        
        # Process each selected item
        indices_to_remove = []
        for i, item in enumerate(self.download_queue):
            if item.selected:
                if item.status in ["Downloading", "Paused"] and item.downloader:
                    # Mark as cancelled
                    item.downloader.paused = True  # Stop downloader
                    item.status = "Cancelled"
                    item.progress = 0
                    
                    # Record in history
                    self.history_manager.add_record(
                        url=item.url,
                        filename=item.filename or os.path.basename(item.url),
                        file_size=0,
                        status="Cancelled",
                        speed=0,
                        error_msg="Cancelled by user (bulk)"
                    )
                    
                    # If current download was cancelled, handle it
                    if self.current_download == item:
                        indices_to_remove.append(i)
                        
                elif item.status == "Queued":
                    indices_to_remove.append(i)
        
        # Remove queued items (process in reverse to maintain indices)
        for i in sorted(indices_to_remove, reverse=True):
            if i < len(self.download_queue):
                del self.download_queue[i]
        
        # If current download was cancelled, move to next
        if any(self.current_download == item for item in selected_items):
            self._download_item_finished()
        
        self._update_queue_display()
        self._update_bulk_buttons_state()
        print(f"✕ Cancelled {len(selected_items)} selected items")

    def _update_bulk_buttons_state(self):
        """Enable/disable bulk action buttons based on selection and status"""
        selected_items = [item for item in self.download_queue if item.selected]
        has_selected = len(selected_items) > 0
        
        # Check if any selected items can be paused/resumed/cancelled
        can_pause = any(item.status == "Downloading" for item in selected_items)
        can_resume = any(item.status == "Paused" for item in selected_items)
        can_cancel = any(item.status in ["Queued", "Downloading", "Paused"] for item in selected_items)
        
        # Update button states
        if hasattr(self, 'pause_selected_btn'):
            self.pause_selected_btn.configure(state="normal" if has_selected and can_pause else "disabled")
        
        if hasattr(self, 'resume_selected_btn'):
            self.resume_selected_btn.configure(state="normal" if has_selected and can_resume else "disabled")
        
        if hasattr(self, 'cancel_selected_btn'):
            self.cancel_selected_btn.configure(state="normal" if has_selected and can_cancel else "disabled")

    def debug_check_methods(self):
        """Check if all required methods exist"""
        required_methods = [
            '_pause_single_download',
            '_resume_single_download', 
            '_cancel_single_download',
            '_select_all_items',
            '_deselect_all_items',
            '_pause_selected',
            '_resume_selected',
            '_cancel_selected',
            '_update_bulk_buttons_state'
        ]
        
        for method in required_methods:
            if hasattr(self, method):
                print(f"✅ {method} exists")
            else:
                print(f"❌ {method} is MISSING")

    def debug_resume_issue(self):
        """Debug why resume isn't working"""
        print("\n" + "="*60)
        print("DEBUG RESUME ISSUE")
        print("="*60)
        
        # Check all items
        for i, item in enumerate(self.download_queue):
            print(f"\n[{i}] '{item.filename[:30]}...'")
            print(f"    Status: {item.status}")
            print(f"    Selected: {item.selected}")
            print(f"    Has downloader: {item.downloader is not None}")
            if item.downloader:
                print(f"    Downloader paused attr: {getattr(item.downloader, 'paused', 'NO PAUSED ATTR')}")
                print(f"    Downloader threads: {getattr(item.downloader, 'num_threads', 'N/A')}")
        
        # Check paused items
        paused_items = [item for item in self.download_queue if item.status == "Paused"]
        print(f"\nTotal paused items: {len(paused_items)}")
        
        # Check selected paused items
        selected_paused = [item for item in paused_items if item.selected]
        print(f"Selected paused items: {len(selected_paused)}")
        
        print("="*60 + "\n")

if __name__ == "__main__":
    try:
        app = DownloadManagerUI()
        app.mainloop()
    except Exception as e:
        print(f"Application error: {e}")
