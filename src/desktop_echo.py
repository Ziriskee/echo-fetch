import customtkinter as ctk
import threading
import queue
import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from echo_core import FastDownloader
from datetime import datetime
from download_history import DownloadHistory
import json

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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

class DownloadManagerUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            # Load settings
            settings = self._load_settings()

            # Apply saved theme
            saved_theme = self.load_theme_preference()
            ctk.set_appearance_mode(saved_theme)
            
            # Apply saved download folder
            self.download_folder = settings.get('download_folder', os.path.expanduser("~/Downloads"))
    
            # 🔥 INITIALIZE DUPLICATE CHECK SETTINGS 🔥
            self.skip_duplicates_var = tk.BooleanVar(value=settings.get('skip_duplicates', False))
            self.auto_rename_var = tk.BooleanVar(value=settings.get('auto_rename', False))

            saved_scale = settings.get('ui_scale',1.0)
            if saved_scale != 1.0:
                try:
                    ctk.set_widget_scaling(saved_scale)
                    print(f"UI scale set to: {saved_scale}")
                except Exception as scale_error:
                    print(f"Failed to set UI scale: {scale_error}")
                    # Fallback to default scale

            self.title("Echo-fetch")
            self.geometry("1250x740")
                        

            # Initialize data structures
            self.progress_queue = queue.Queue()
            self.download_queue = []
            self.current_download = None
            self.history_manager = DownloadHistory()

            # Tracking variables
            self.thread_speed = []
            self.thread_percents = []
            self.downloader_paused = False
            
            self._create_widgets()
            self.after(100, self.update_thread_display)

            print(f"Download folder set to: {self.download_folder}")

        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize application: {str(e)}")
            raise

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
            right_frame = ctk.CTkFrame(main_frame, width=350)
            right_frame.pack(side="right", fill="both", padx=(5, 0))
            right_frame.pack_propagate(False)
                
            self._create_download_section(left_frame)
            self._create_queue_section(right_frame)
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create widgets: {str(e)}")

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
            pref_window.title("Preferences")
            pref_window.geometry("500x600")
            pref_window.transient(self)
            pref_window.grab_set()
            
            # Create tab view for different settings categories
            tab_view = ctk.CTkTabview(pref_window)
            tab_view.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Appearance Tab
            appearance_tab = tab_view.add("Appearance")
            self._create_appearance_tab(appearance_tab)
            
            # Download Tab
            download_tab = tab_view.add("Download")
            self._create_download_tab(download_tab)
            
            # General Tab
            general_tab = tab_view.add("General")
            self._create_general_tab(general_tab)
            
        except Exception as e:
            messagebox.showerror("Preferences Error", f"Failed to open preferences: {str(e)}")

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
            self._save_setting('ui_scale', scale_map[choice])

            #save the setting
            self.save_setting('ui_scale',selected_scale)

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
            
            ctk.CTkLabel(folder_frame, text="Download Folder:", font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            folder_select_frame = ctk.CTkFrame(folder_frame)
            folder_select_frame.pack(fill="x", pady=5)
            
            self.folder_path_label = ctk.CTkLabel(folder_select_frame, text=self.download_folder, 
                                                anchor="w", width=300, wraplength=400)
            self.folder_path_label.pack(side="left", fill="x", expand=True)
            
            ctk.CTkButton(folder_select_frame, text="Browse", width=80,
                         command=self.select_download_folder).pack(side="right", padx=(5, 0))
            
            # URL Section
            ctk.CTkLabel(parent, text="Download URL:", font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(10, 0))
            
            self.url_entry = ctk.CTkEntry(parent, width=400, font=ctk.CTkFont(size=12))
            self.url_entry.pack(fill="x", pady=5)
            self.url_entry.bind("<Return>", lambda e: self.add_to_queue())
            
            # Right-click menu for URL entry
            self.url_entry.bind("<Button-3>", self.show_menu)
            
            # Batch download section
            batch_frame = ctk.CTkFrame(parent)
            batch_frame.pack(fill="x", pady=10)
            
            ctk.CTkLabel(batch_frame, text="Batch Download (one URL per line):", font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            self.batch_text = ctk.CTkTextbox(batch_frame, height=100, font=ctk.CTkFont(size=12))
            self.batch_text.pack(fill="x", pady=5)

            # Right-click menu for batch text
            self.batch_text.bind("<Button-3>", self.show_menu)
            
            ctk.CTkButton(batch_frame, text="Add All to Queue", 
                         command=self.add_batch_to_queue).pack(pady=5)
            
            # Control Buttons
            control_frame = ctk.CTkFrame(parent)
            control_frame.pack(fill="x", pady=10)
            
            self.add_queue_btn = ctk.CTkButton(control_frame, text="Add to Queue", 
                                             command=self.add_to_queue)
            self.add_queue_btn.pack(side="left", padx=(0, 5))
            
            self.start_btn = ctk.CTkButton(control_frame, text="Start Download", 
                                         command=self.start_download)
            self.start_btn.pack(side="left", padx=5)
            
            self.pause_btn = ctk.CTkButton(control_frame, text="Pause", 
                                         command=self.pause_download, state="disabled")
            self.pause_btn.pack(side="left", padx=5)
            
            self.resume_btn = ctk.CTkButton(control_frame, text="Resume", 
                                          command=self.resume_download, state="disabled")
            self.resume_btn.pack(side="left", padx=5)

            self.cancel_btn = ctk.CTkButton(control_frame, text="Cancel", 
                                                  command=self.cancel_current_download, 
                                                  fg_color="red", hover_color="darkred",
                                                  state="disabled")
            self.cancel_btn.pack(side="left", padx=5)

            # History & Statistics Button
            self.history_btn = ctk.CTkButton(control_frame, text="History & Stats",command=self.show_history_statistics)
            self.history_btn.pack(side="left", padx=5)

            self.preference_btn = ctk.CTkButton(control_frame, text="⚙ Preferences", 
                                               command=self.show_preferences, width=100)
            self.preference_btn.pack(side="left",padx=5)

            # Status Section
            self.status_label = ctk.CTkLabel(parent, text="Idle", text_color="gray", font=ctk.CTkFont(size=12))
            self.status_label.pack(anchor="w", pady=5)
            
            # Overall Progress
            progress_frame = ctk.CTkFrame(parent)
            progress_frame.pack(fill="x", pady=10)
            
            self.overall_label = ctk.CTkLabel(progress_frame, text="Overall: 0%", font=ctk.CTkFont(size=12))
            self.overall_label.pack(anchor="w")
            
            self.overall_speed_label = ctk.CTkLabel(progress_frame, text="Speed: 0.00 MB/s", font=ctk.CTkFont(size=12))
            self.overall_speed_label.pack(anchor="w")
            
            self.overall_progress = ctk.CTkProgressBar(progress_frame, mode="determinate")
            self.overall_progress.set(0)
            self.overall_progress.pack(fill="x", pady=5)
            
            # Current file info
            self.current_file_label = ctk.CTkLabel(progress_frame, text="Current: None", text_color="gray", font=ctk.CTkFont(size=12))
            self.current_file_label.pack(anchor="w")
            
            # Thread Status Section
            thread_frame = ctk.CTkFrame(parent)
            thread_frame.pack(fill="both", expand=True, pady=10)
            
            ctk.CTkLabel(thread_frame, text="Thread Status:", font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            self.thread_scrollable_frame = ctk.CTkScrollableFrame(thread_frame, height=150)
            self.thread_scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            self.thread_labels = []
            for i in range(16):
                lbl = ctk.CTkLabel(self.thread_scrollable_frame, text="", text_color="gray", font=ctk.CTkFont(size=11))
                lbl.pack(anchor="w", pady=1)
                self.thread_labels.append(lbl)
                lbl.pack_forget()
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create download section: {str(e)}")

    def _create_queue_section(self, parent):
        """Create download queue management section"""
        try:
            ctk.CTkLabel(parent, text="Download Queue", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            
            # Queue controls
            queue_controls = ctk.CTkFrame(parent)
            queue_controls.pack(fill="x", padx=10, pady=(0, 10))
            
            ctk.CTkButton(queue_controls, text="Clear Completed", 
                         command=self.clear_completed, width=120).pack(side="left", padx=(0, 5))
            
            ctk.CTkButton(queue_controls, text="Clear All", 
                         command=self.clear_all_queue, width=80).pack(side="right")
            
            # Queue list with proper height
            ctk.CTkLabel(parent, text="Downloads:", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=10, pady=(5, 0))
            
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

    def _create_queue_item(self, index, item):
        """Create a single queue item with proper layout"""
        try:
            # Main frame for the queue item
            item_frame = ctk.CTkFrame(self.queue_frame,height=80)
            item_frame.pack(fill="x", pady=1, padx=1)
            item_frame.pack_propagate(False)  # Prevent frame from resizing to fit contents
            
            # Left side - File info and status
            left_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            left_frame.pack(side="left", fill="both", expand=True, padx=3, pady=1)
            
            # Extract filename
            filename = item.filename or os.path.basename(item.url) or "Unknown File"
            if not filename:
                filename = f"download_{index+1}"
            
            # Truncate filename appropriately but keep important info
            display_filename = filename[:45] + "..." if len(filename) > 45 else filename
            
            # Filename label
            filename_label = ctk.CTkLabel(
                left_frame, 
                text=display_filename,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            filename_label.pack(fill="x", pady=0)
            
            # Status and progress information
            status_text = f"Status: {item.status}"
            if item.status == "Downloading":
                status_text += f" | Progress: {item.progress:.1f}% | Speed: {item.speed:.2f} MB/s"
                if hasattr(item, 'file_size') and item.file_size > 0:
                    status_text += f" | Size: {item.file_size:,} bytes"
            elif item.status == "Completed":
                status_text += f" | Progress: {item.progress:.0f}%"
            elif item.status == "Error" and hasattr(item, 'error_message'):
                error_display = item.error_message[:50] + "..." if len(item.error_message) > 50 else item.error_message
                status_text += f" | {error_display}"
            
            # Status color coding
            status_colors = {
                "Queued": "gray",
                "Downloading": "#3B8ED0",  # Blue
                "Paused": "orange",
                "Completed": "green",
                "Error": "red",
                "Cancelled": "darkgray"
            }
            
            status_label = ctk.CTkLabel(
                left_frame, 
                text=status_text,
                text_color=status_colors.get(item.status, "gray"),
                font=ctk.CTkFont(size=11),
                anchor="w",
                wraplength=250  # Wrap long status text
            )
            status_label.pack(fill="x", pady=0)
            
            # Timestamp information
            timestamp_info = ""
            if item.added_time:
                timestamp_info += f"Added: {item.added_time.strftime('%H:%M:%S')}"
            if item.start_time:
                timestamp_info += f" | Started: {item.start_time.strftime('%H:%M:%S')}"
            if item.end_time and item.status == "Completed":
                timestamp_info += f" | Finished: {item.end_time.strftime('%H:%M:%S')}"
            
            if timestamp_info:
                time_label = ctk.CTkLabel(
                    left_frame,
                    text=timestamp_info,
                    font=ctk.CTkFont(size=9),
                    text_color="lightgray",
                    anchor="w"
                )
                time_label.pack(fill="x", pady=0)
            
            # Right side - Action buttons
            btn_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            btn_frame.pack(side="right", fill="y", padx=5, pady=3)
            
            # Add buttons based on status
            if item.status == "Queued":
                button_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
                button_frame.pack()
                
                ctk.CTkButton(button_frame, text="▲", width=30, height=25,
                            command=lambda idx=index: self._move_up(idx),
                            font=ctk.CTkFont(size=10)).pack(side="left", padx=1)
                ctk.CTkButton(button_frame, text="▼", width=30, height=25,
                            command=lambda idx=index: self._move_down(idx),
                            font=ctk.CTkFont(size=10)).pack(side="left", padx=1)
                ctk.CTkButton(button_frame, text="✕", width=30, height=25,
                            command=lambda idx=index: self._remove_from_queue(idx),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=10)).pack(side="left", padx=1)
            
            elif item.status == "Downloading":
                ctk.CTkButton(btn_frame, text="⏸", width=35, height=30,
                            command=self.pause_download,
                            font=ctk.CTkFont(size=12)).pack(pady=1)
                ctk.CTkButton(btn_frame, text="✕", width=35, height=30,
                            command=lambda: self.cancel_current_download(),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=12)).pack(pady=1)
            
            elif item.status == "Paused":
                ctk.CTkButton(btn_frame, text="▶", width=35, height=30,
                            command=self.resume_download,
                            font=ctk.CTkFont(size=12)).pack(pady=1)
                ctk.CTkButton(btn_frame, text="✕", width=35, height=30,
                            command=lambda: self.cancel_current_download(),
                            fg_color="red", hover_color="darkred",
                            font=ctk.CTkFont(size=12)).pack(pady=1)
            
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

    def start_download(self):
        """Start downloading from queue"""
        try:
            if not self.download_queue:
                messagebox.showwarning("Warning", "Queue is empty")
                return
            
            # Find first queued item
            for item in self.download_queue:
                if item.status == "Queued":
                    self._start_download_item(item)
                    return
            
            messagebox.showinfo("Info", "No queued items to download")
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download: {str(e)}")

    def _start_download_item(self, item):
        """Start downloading a specific item"""
        try:
            self.current_download = item
            item.status = "Downloading"
            item.start_time = datetime.now()
            item.error_message = ""  # Clear previous errors
            
            self.status_label.configure(text=f"Downloading: {os.path.basename(item.url) or 'Unknown'}", 
                                      text_color="white")
            self.current_file_label.configure(text=f"Current: {os.path.basename(item.url) or 'Unknown'}")
            
            # Enable/disable buttons
            self.pause_btn.configure(state="normal")
            self.resume_btn.configure(state="disabled")
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
            
            self._update_queue_display()
            
            # Start download in background thread
            threading.Thread(target=self._run_download_item, args=(item,), daemon=True).start()
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
        """Handle completion of a download item"""
        try:
            self.current_download = None
            self.downloader = None
            
            # Update UI
            self._update_queue_display()
            self.status_label.configure(text="Download completed", text_color="green")
            self.pause_btn.configure(state="disabled")
            self.resume_btn.configure(state="disabled")
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")

            # Start next download if available
            self.after(1000, self._start_next_download)
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

    def pause_download(self):
        """Pause current download"""
        try:
            if self.current_download and self.current_download.status == "Downloading":
                if self.downloader:
                    self.downloader.pause()
                    self.downloader_paused = True
                    self.current_download.status = "Paused"
                    self.status_label.configure(text="Download Paused", text_color="orange")
                    self.pause_btn.configure(state="disabled")
                    self.resume_btn.configure(state="normal")
                    self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Pause Error", f"Failed to pause download: {str(e)}")

    def resume_download(self):
        """Resume current download"""
        try:
            if self.current_download and self.current_download.status == "Paused":
                if self.downloader:
                    self.downloader.resume()
                    self.downloader_paused = False
                    self.current_download.status = "Downloading"
                    self.status_label.configure(text="Downloading...", text_color="white")
                    self.pause_btn.configure(state="normal")
                    self.resume_btn.configure(state="disabled")
                    self._update_queue_display()
        except Exception as e:
            messagebox.showerror("Resume Error", f"Failed to resume download: {str(e)}")

    def cancel_current_download(self, confirm=True):
        """Cancel current download"""
        try:
            if self.current_download:
                if confirm and not messagebox.askyesno("Confirm", "Cancel current download?"):
                    return
                
                self.history_manager.add_record(
                    url=self.current_download.url,
                    filename=self.current_download.filename or os.path.basename(self.current_download.url),
                    file_size=0,
                    status="Cancelled",
                    speed=0,
                    error_msg="Download cancelled by user"
                )

                self.current_download.status = "Cancelled"
                if self.downloader:
                    # We can't easily stop the downloader thread, so we'll mark it as cancelled
                    pass
                self._download_item_finished()
        except Exception as e:
            messagebox.showerror("Cancel Error", f"Failed to cancel download: {str(e)}")

    def update_thread_display(self):
        """Update the UI with current progress and speeds"""
        try:
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
                        
                        # Update thread label
                        if idx < len(self.thread_labels):
                            bar_length = 15
                            filled = int(percent / 100 * bar_length)
                            bar = "█" * filled + "░" * (bar_length - filled)
                            status = f"Thread {idx+1}: {speed:5.2f} MB/s ({percent:5.1f}%) {bar}"
                            self.thread_labels[idx].configure(text=status)
                            
                except queue.Empty:
                    break

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


if __name__ == "__main__":
    try:
        app = DownloadManagerUI()
        app.mainloop()
    except Exception as e:
        print(f"Application error: {e}")
