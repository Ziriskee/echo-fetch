# download_history.py
import json
import os
from datetime import datetime, timedelta
import csv

class DownloadHistory:
    def __init__(self, history_file="download_history.json"):
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self):
        """Load history from JSON file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                return []
        return []
    
    def _save_history(self):
        """Save history to JSON file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def add_record(self, url, filename, file_size, status, speed=0, error_msg=""):
        """Add a download record to history"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'filename': filename,
            'file_size': file_size,
            'status': status,  # Completed, Error, Cancelled
            'download_speed': speed,
            'error_message': error_msg,
            'duration': None  # Will be calculated when completed
        }
        
        # Update duration for previous record if this is a completion
        if status == "Completed" and self.history:
            for prev_record in reversed(self.history[-5:]):  # Check last 5 records
                if prev_record['url'] == url and prev_record.get('duration') is None:
                    start_time = datetime.fromisoformat(prev_record['timestamp'])
                    end_time = datetime.now()
                    prev_record['duration'] = (end_time - start_time).total_seconds()
                    break
        
        self.history.append(record)
        
        # Keep only last 1000 records to prevent file bloat
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        self._save_history()
    
    def get_recent_downloads(self, limit=50):
        """Get recent download records"""
        return self.history[-limit:][::-1]  # Return in reverse order (newest first)
    
    def get_statistics(self, days=30):
        """Get download statistics for the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_downloads = [
            record for record in self.history 
            if datetime.fromisoformat(record['timestamp']) >= cutoff_date
        ]
        
        if not recent_downloads:
            return {
                'total_downloads': 0,
                'successful_downloads': 0,
                'failed_downloads': 0,
                'total_size': 0,
                'average_speed': 0,
                'success_rate': 0
            }
        
        total_downloads = len(recent_downloads)
        successful_downloads = len([r for r in recent_downloads if r['status'] == 'Completed'])
        failed_downloads = len([r for r in recent_downloads if r['status'] == 'Error'])
        total_size = sum(r.get('file_size', 0) for r in recent_downloads if r.get('file_size'))
        
        speeds = [r.get('download_speed', 0) for r in recent_downloads if r.get('download_speed', 0) > 0]
        average_speed = sum(speeds) / len(speeds) if speeds else 0
        success_rate = (successful_downloads / total_downloads) * 100 if total_downloads > 0 else 0
        
        return {
            'total_downloads': total_downloads,
            'successful_downloads': successful_downloads,
            'failed_downloads': failed_downloads,
            'total_size': total_size,
            'average_speed': average_speed,
            'success_rate': success_rate
        }
    
    def export_to_csv(self, filename="download_history_export.csv"):
        """Export history to CSV file"""
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'filename', 'url', 'file_size', 'status', 'download_speed', 'error_message']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for record in self.history:
                    # Create a clean record for CSV
                    clean_record = {
                        'timestamp': record['timestamp'],
                        'filename': record['filename'],
                        'url': record['url'][:100],  # Truncate long URLs
                        'file_size': record.get('file_size', 0),
                        'status': record['status'],
                        'download_speed': f"{record.get('download_speed', 0):.2f}",
                        'error_message': record.get('error_message', '')[:50]  # Truncate long errors
                    }
                    writer.writerow(clean_record)
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False
    
    def clear_history(self):
        """Clear all download history"""
        self.history = []
        self._save_history()