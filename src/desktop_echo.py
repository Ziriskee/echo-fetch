import customtkinter as ctk
import threading
import queue
import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox
import os
from echo_core import FastDownloader
from datetime import datetime
from download_history import DownloadHistory

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
            self.title("Echo-fetch")
            self.geometry("1100x700")
            
            # Initialize data structures
            self.progress_queue = queue.Queue()
            self.download_queue = []
            self.current_download = None
            self.download_folder = os.path.expanduser("~/Downloads")
            self.history_manager = DownloadHistory()

            # Tracking variables
            self.thread_speed = []
            self.thread_percents = []
            self.downloader_paused = False
            
            self._create_widgets()
            self.after(100, self.update_thread_display)
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize application: {str(e)}")
            raise

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
            self.menu = tk.Menu(self, tearoff=0)
            self.menu.add_command(label="Cut", command=lambda: self.url_entry.event_generate("<<Cut>>"))
            self.menu.add_command(label="Copy", command=lambda: self.url_entry.event_generate("<<Copy>>"))
            self.menu.add_command(label="Paste", command=lambda: self.url_entry.event_generate("<<Paste>>"))
            self.url_entry.bind("<Button-3>", self.show_menu)
            
            # Batch download section
            batch_frame = ctk.CTkFrame(parent)
            batch_frame.pack(fill="x", pady=10)
            
            ctk.CTkLabel(batch_frame, text="Batch Download (one URL per line):", font=ctk.CTkFont(size=14)).pack(anchor="w")
            
            self.batch_text = ctk.CTkTextbox(batch_frame, height=100, font=ctk.CTkFont(size=12))
            self.batch_text.pack(fill="x", pady=5)
            
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
            
            # Status Section
            self.status_label = ctk.CTkLabel(parent, text="Idle", text_color="gray", font=ctk.CTkFont(size=12))
            self.status_label.pack(anchor="w", pady=5)

            # History & Statistics Button
            self.history_btn = ctk.CTkButton(control_frame, text="History & Stats",                             command=self.show_history_statistics)
            self.history_btn.pack(side="left", padx=5)
            
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
            
            self.queue_frame = ctk.CTkScrollableFrame(parent, height=400)  # Increased height
            self.queue_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.queue_item_frames = []
            self.queue_item_widgets = {}
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create queue section: {str(e)}")

    def show_menu(self, event):
        """Show right-click context menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Menu error: {e}")
        finally:
            self.menu.grab_release()

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
            
            download_item = DownloadItem(url, self.download_folder)
            self.download_queue.append(download_item)
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
            
            for url in urls:
                if url and url.startswith(('http://', 'https://')):
                    download_item = DownloadItem(url, self.download_folder)
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
            # Always refresh rather than recreate to prevent flickering
            self._refresh_queue_display()
        except Exception as e:
            print(f"Queue display update error: {e}")

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
            item_frame = ctk.CTkFrame(self.queue_frame)
            item_frame.pack(fill="x", pady=3, padx=2)
            
            # Left side - File info and status
            left_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=3)
            
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
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            )
            filename_label.pack(fill="x", pady=1)
            
            # Status and progress information
            status_text = f"Status: {item.status}"
            if item.status == "Downloading":
                status_text += f" | Progress: {item.progress:.1f}% | Speed: {item.speed:.2f} MB/s"
                if hasattr(item, 'file_size') and item.file_size > 0:
                    status_text += f" | Size: {item.file_size:,} bytes"
            elif item.status == "Completed":
                status_text += f" | Progress: {item.progress:.0f}%"
            elif item.status == "Error" and hasattr(item, 'error_message'):
                status_text += f" | Error: {item.error_message[:50]}{'...' if len(item.error_message) > 50 else ''}"
            
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
            status_label.pack(fill="x", pady=1)
            
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
                    font=ctk.CTkFont(size=10),
                    text_color="lightgray",
                    anchor="w"
                )
                time_label.pack(fill="x", pady=1)
            
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
            
            self._update_queue_display()
            
            # Start download in background thread
            threading.Thread(target=self._run_download_item, args=(item,), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download item: {str(e)}")

    def _run_download_item(self, item):
        """Run the download for a queue item"""
        try:
            # Record start in history
            self.history_manager.add_record(
                url=item.url,
                filename=item.filename or os.path.basename(item.url),
                file_size=0,  # Will be updated on completion
                status="Started",
                speed=0
            )
            
            # Create downloader with progress callback
            downloader = FastDownloader(
                item.url,
                num_threads=8,
                progress_callback=lambda idx, speed, percent: self.progress_queue.put((idx, speed, percent))
            )
            
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
            
        except Exception as e:
            item.status = "Error"
            item.error_message = str(e)
            
            # Record error
            self.history_manager.add_record(
                url=item.url,
                filename=item.filename or os.path.basename(item.url),
                file_size=0,
                status="Error",
                speed=0,
                error_msg=str(e)
            )
            print(f"Download error: {e}")
        
        finally:
            # Move to next item or finish
            self.after(0, self._download_item_finished)

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
        """Clear all download history"""
        if messagebox.askyesno("Confirm Clear", "Clear all download history? This cannot be undone."):
            self.history_manager.clear_history()
            messagebox.showinfo("History Cleared", "Download history has been cleared")

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