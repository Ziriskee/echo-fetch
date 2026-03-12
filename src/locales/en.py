# English Language Strings for Echo-Fetch Download Manager

LANG = {
    # App basic
    "app_title": "Echo-fetch",
    
    # Download section
    "download_folder": "Download Folder:",
    "download_url": "Download URL:",
    "batch_download": "Batch Download (one URL per line):",
    "add_all_to_queue": "Add All to Queue",
    "add_to_queue": "Add to Queue",
    "start_download": "Start Download",
    "pause": "Pause",
    "resume": "Resume",
    "cancel": "Cancel",
    
    # Queue section
    "download_queue": "Download Queue",
    "select_all": "Select All",
    "deselect_all": "Deselect All",
    "pause_selected": "Pause Selected",
    "resume_selected": "Resume Selected",
    "cancel_selected": "Cancel Selected",
    "clear_completed": "Clear Completed",
    "clear_all": "Clear All",
    "downloads": "Downloads:",
    "no_items_selected": "No items selected",
    
    # Status messages
    "idle": "Idle",
    "overall": "Overall: {:.1f}%",
    "speed": "Speed: {:.2f} MB/s",
    "current_none": "Current: None",
    "thread_status": "Thread Status",
    
    # Preferences
    "preferences": "Preferences",
    "appearance": "Appearance",
    "download_settings": "Download Settings",
    "general": "General",
    "preferences_error": "Preferences Error",
    "preferences_error_msg": "Failed to open preferences: {}",
    
    # Appearance tab
    "theme_settings": "Theme Settings",
    "current_theme": "Current Theme: {}",
    "toggle_theme": "Toggle Dark/Light Theme",
    "or_select": "Or select:",
    "ui_scaling": "UI Scaling",
    "ui_scaling_desc": "Adjust UI scaling (requires restart):",
    "current_scale": "Current Scale: {}",
    
    # Download settings tab
    "download_location": "Download Location",
    "current_folder": "Current folder:",
    "change_folder": "Change Download Folder",
    "download_behavior": "Download Behavior",
    "auto_start": "Auto-start downloads when added to queue",
    "auto_remove": "Auto-remove completed downloads from queue",
    "auto_categorize": "Auto-Categorization",
    "auto_categorize_desc": "Automatically sort downloads into folders by type",
    "default_threads": "Default Threads:",
    "duplicate_handling": "Duplicate File Handling",
    "auto_rename": "Auto-rename duplicate files (no prompt)",
    "skip_duplicates": "Auto-skip duplicate files",
    
    # General tab
    "startup": "Startup",
    "start_with_system": "Start with system (Windows)",
    "language": "Language",
    "minimize_to_tray": "Minimize to system tray",
    "notifications": "Notifications",
    "notify_complete": "Show notifications when downloads complete",
    "sound_notifications": "Play sound for notifications",
    "reset_maintenance": "Reset & Maintenance",
    "reset_settings": "Reset All Settings",
    "clear_data": "Clear All Data",
    
    # History & Statistics
    "history_stats": "History & Stats",
    "statistics": "Statistics",
    "recent_downloads": "Recent Downloads",
    "export": "Export",
    "export_csv": "Export to CSV",
    "cleanup_files": "Cleanup Downloaded Files",
    "clear_history": "Clear History",
    "total_records": "Total records: {}",
    
    # Cleanup window
    "cleanup_title": "Cleanup Downloaded Files",
    "select_files_delete": "Select files to delete:",
    "select_all_btn": "Select All",
    "deselect_all_btn": "Deselect All",
    "delete_selected": "Delete Selected",
    "file_not_found": "(File not found)",
    
    # Message boxes - Initialization
    "init_error": "Initialization Error",
    "init_error_msg": "Failed to initialize application: {}",
    
    # Message boxes - Language
    "restart_required": "Restart Required",
    "language_change_msg": "Language change will take effect after restart.",
    
    # Message boxes - UI
    "ui_error": "UI Error",
    "ui_error_msg": "Failed to create widgets: {}",
    "ui_error_download": "Failed to create download section: {}",
    "ui_error_queue": "Failed to create queue section: {}",
    
    # Message boxes - Cleanup
    "no_files": "No Files",
    "no_completed_found": "No completed downloads found in history",
    "cleanup_error": "Cleanup Error",
    "cleanup_error_msg": "Failed to open cleanup window: {}",
    "no_selection": "No Selection",
    "no_files_selected": "No files selected for deletion",
    "confirm_deletion": "Confirm Deletion",
    "confirm_delete_files": "Are you sure you want to delete {} file(s)?\n\nThis action cannot be undone!",
    "deletion_complete": "Deletion Complete",
    "deleted_files_msg": "Successfully deleted {} file(s)",
    "deletion_error": "Deletion Error",
    "deletion_error_msg": "Failed to delete files: {}",
    
    # Message boxes - Theme
    "theme_error": "Theme Error",
    "theme_error_switch": "Failed to switch theme: {}",
    "theme_error_apply": "Failed to apply theme: {}",
    "theme_error_save": "Failed to save theme: {}",
    
    # Message boxes - Scale
    "scale_error": "Scale Error",
    "scale_error_msg": "Failed to change UI scale: {}",
    "scale_restart": "UI scaling change will take effect after restart.",
    
    # Message boxes - Folder
    "folder_error": "Folder Selection Error",
    "folder_error_msg": "Failed to select folder: {}",
    
    # Message boxes - Settings
    "confirm_reset": "Confirm Reset",
    "reset_settings_msg": "Reset all settings to default values?",
    "settings_reset": "Settings Reset",
    "settings_reset_msg": "All settings have been reset to defaults.",
    "confirm_clear_data": "Confirm Clear ALL Data",
    "clear_data_msg": "This will delete:\n\n• All download history ({} records)\n• All application settings\n• All downloaded files ({} files)\n\nThis action cannot be undone!\n\nAre you absolutely sure?",
    "data_cleared": "Data Cleared",
    "data_cleared_msg": "All application data has been cleared.\nDeleted {} downloaded files.",
    "clear_error": "Clear Error",
    "clear_error_msg": "Failed to clear data: {}",
    
    # Message boxes - Download
    "download_error": "Download Error",
    "download_error_start": "Failed to start download: {}",
    "warning": "Warning",
    "enter_url": "Please enter a URL",
    "invalid_url": "Invalid URL",
    "valid_url_msg": "Please enter a valid HTTP/HTTPS URL",
    "skipped": "Skipped",
    "skipped_duplicate": "Skipped duplicate file: {}",
    "success": "Success",
    "added_to_queue": "Added to queue: {}",
    "queue_error": "Queue Error",
    "queue_error_add": "Failed to add URL to queue: {}",
    "queue_error_remove": "Failed to remove item: {}",
    "queue_error_move": "Failed to move item: {}",
    "queue_error_clear": "Failed to clear queue: {}",
    "queue_cleared": "Queue Cleared",
    "removed_completed": "Removed {} completed items from queue",
    "queue_status": "Queue Status",
    "no_completed": "No completed items to remove",
    "cannot_clear": "Cannot clear queue while download is in progress",
    "queue_empty": "Queue is already empty",
    "confirm_clear_queue": "Confirm",
    "confirm_clear_queue_msg": "Clear all {} downloads from queue?",
    "queue_cleared_all": "All items removed from queue",
    
    # Message boxes - Batch
    "batch_error": "Batch Error",
    "batch_error_msg": "Failed to add batch URLs: {}",
    "enter_urls": "Please enter URLs in the batch box",
    "batch_result": "Batch Add Result",
    "added_urls_msg": "Added {} URLs to queue",
    "invalid_urls_ignored": "Invalid URLs ignored:\n{}",
    "and_more": "... and {} more",
    
    # Message boxes - Cancel
    "confirm_cancel": "Confirm Cancel",
    "confirm_cancel_single": "Cancel download: {}?",
    "confirm_cancel_selected": "Cancel {} selected download(s)?",
    "confirm_cancel_active": "Cancel {} active download(s)?",
    "cancel_error": "Cancel Error",
    "cancel_error_msg": "Failed to cancel download: {}",
    "no_cancellable": "No cancellable items selected",
    "no_active_cancel": "No active downloads to cancel",
    
    # Message boxes - Pause
    "pause_error": "Pause Error",
    "pause_error_msg": "Failed to pause download: {}",
    "no_pause_selection": "No downloading items selected to pause",
    "no_active_pause": "No active downloads to pause",
    "paused_selected": "Paused {} selected item(s)",
    "paused_active": "Paused {} active download(s)",
    
    # Message boxes - Resume
    "resume_error": "Resume Error",
    "resume_error_msg": "Failed to resume download: {}",
    "no_resume_selection": "No paused items selected to resume",
    "no_active_resume": "No paused downloads to resume",
    "resumed_selected": "Resumed {} selected item(s)",
    "resumed_active": "Resumed {} paused item(s)",
    "partial_success": "Partial Success",
    "partial_resume_msg": "Resumed {} items, but {} failed to resume.",
    
    # Message boxes - Duplicate
    "duplicate_found": "Duplicate File Found",
    "duplicate_msg": "File '{}' already exists.\n\nWhat would you like to do?\n\n• Yes: Rename new file\n• No: Overwrite existing file\n• Cancel: Skip this download",
    "duplicate_rename": "Rename",
    "duplicate_overwrite": "Overwrite",
    "duplicate_skip": "Skip",
    
    # Message boxes - History
    "history_error": "History Error",
    "history_error_msg": "Failed to open history: {}",
    "export_success": "Export Successful",
    "export_success_msg": "History exported to {}",
    "export_failed": "Export Failed",
    "export_failed_msg": "Failed to export history",
    "export_error": "Export Error",
    "export_error_msg": "Export failed: {}",
    "history_options": "Clear History Options",
    "history_options_msg": "What would you like to clear?\n\n• Yes: Clear history records only (keep files)\n• No: Clear history AND delete downloaded files\n• Cancel: Do nothing",
    "history_cleared": "History Cleared",
    "history_cleared_records": "Download history has been cleared",
    "history_cleared_all": "Download history cleared and {} files deleted",
    "clear_history_error": "Clear Error",
    "clear_history_error_msg": "Failed to clear history: {}",
    
    # Message boxes - Info
    "info": "Info",
    "no_queued": "No queued items to download",
    "started_selected": "Started {} selected item(s)",
    "started_item": "Started: {}",
    
    # Statistics
    "last_30_days": "Last 30 Days Statistics",
    "total_downloads": "Total Downloads",
    "successful": "Successful",
    "failed": "Failed",
    "success_rate": "Success Rate",
    "total_size": "Total Size",
    "avg_speed": "Average Speed",
    "no_history": "No download history yet",
}

