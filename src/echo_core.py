import requests
import threading
import os
import re
import psutil
import time

MAX_RETRIES = 10
RETRY_DELAY = 2  # seconds

def sanitize_filename(url):
        filename = url.split("/")[-1]
        filename = filename.split("?")[0]
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        return filename if filename else "downloaded_file"

class FastDownloader:
    def __init__(self, url, num_threads=8, progress_callback=None, download_path=None):
        self.url = url
        self.callback = progress_callback
        self.download_path = download_path or os.getcwd()
        self.exceptions = [] # To track exceptions from thread
        self.messages = []

        # Convert to absolute path for consistency
        if self.download_path:
            self.download_path = os.path.abspath(self.download_path)
            print(f"📂 Download path set to: {self.download_path}")
        
        
        # ✅ BETTER HEADERS TO MIMIC A REAL BROWSER
        self.headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
        # Create a session to maintain cookies
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        try:
            # Get file size with error handling
            response = requests.head(url, allow_redirects=True, timeout=10)
            
            # ✅ HANDLE 403 ERRORS DURING HEAD REQUEST
            if response.status_code == 403:
                print("⚠ Server blocked HEAD request with 403 Forbidden, trying GET request for file size...")
                response = self.session.get(url, stream=True, timeout=10, headers={'Range': 'bytes=0-0'})


                #try with GET instead for servers that block HEAD requests
                response = self.session.get(url, stream=True, timeout=10, headers={'Range': 'bytes=0-0'})

                if response.status_code in (200, 206):
                    self.file_size = int(response.headers.get("Content-Length", 0))
                else:
                    raise Exception(f"Server returned {response.status_code}: {response.reason}")
            else:
                response.raise_for_status()
                self.file_size = int(response.headers.get("Content-Length", 0))
            
            
            self.filename = sanitize_filename(url)
            
            if self.download_path:
                os.makedirs(self.download_path, exist_ok=True)

            # FIXED: Use the provided num_threads, only override if file is small
            if self.file_size > 0:
                self.num_threads = self.choose_optimal_threads(self.file_size, num_threads)
            else:
                self.num_threads = 1
                
            # Initialize progress tracking
            self.thread_progress = [0] * self.num_threads
            self.thread_speed = [0] * self.num_threads
            self.paused = False
            
            # Check range support
            self.range_supported = response.headers.get("Accept-Ranges", "") == "bytes"
            
            if not self.range_supported and self.file_size > 0:
                self.log("Testing if server supports range requests...","info")
                test = self.session.get(url, headers ={ "Range": "bytes=0-0"}, timeout = 10)

                self.range_supported = test.status_code == 206
                if not self.range_supported:
                    self.num_threads =1 
            
            # Calculate part size only if range is supported and file has size
            if self.range_supported and self.file_size > 0:
                self.part_size = self.file_size // self.num_threads
            else:
                self.num_threads = 1
                
        except requests.RequestException as e:
            self.log(f"Error connecting to server: {e}","error")

            # Try one more time with GET
            try:
                self.log("Trying alternative connection method...","info")
                response = self.session.get(url, stream=True, timeout=10)
                if response.status_code == 200:
                    self.file_size = self.extract_file_size(response)
                    self.filename = sanitize_filename(url)
                    self.num_threads = 1
                    self.range_supported = False
                    self.thread_progress = [0]
                    self.thread_speed = [0]
                    self.paused = False
                    return
            except:
                pass
            # Set safe defaults
            self.file_size = 0
            self.num_threads = 1
            self.range_supported = False
            self.filename = sanitize_filename(url)
            self.thread_progress = [0]
            self.thread_speed = [0]
            self.paused = False

    def _extract_file_size(self, response):
            """Extract file size from response headers"""
            size = response.headers.get("Content-Length")
            if size:
                return int(size)
            
            range_header = response.headers.get("Content-Range")
            if range_header and "/" in range_header:
                total = range_header.split("/")[-1]
                if total != "*":
                    return int(total)
            
            return 0
        
    def get_final_filepath(self):
            """Get the actual path where the file was saved"""
            if self.download_path:
                return os.path.join(self.download_path, self.filename)
            else:
                return self.filename

    def log(self, message, level="info"):
        """Log messages (can be displayed in UI)"""
        self.messages.append(f"[{level.upper()}] {message}")
        if level in ["error", "warning"]:
            print(f"{'❌' if level == 'error' else '⚠'} {message}")

    def choose_optimal_threads(self, file_size_bytes, default_threads):
        """Choose optimal thread count based on file size and system capabilities"""
        if file_size_bytes == 0:
            return 1
            
        # CPU cores
        cores = psutil.cpu_count(logical=True) or 4
        
        # Base thread selection from file size
        if file_size_bytes < 10 * 1024 * 1024:  # < 10MB
            suggested_threads = 2
        elif file_size_bytes < 50 * 1024 * 1024:  # < 50MB
            suggested_threads = 4
        elif file_size_bytes < 500 * 1024 * 1024:  # < 500MB
            suggested_threads = 8
        else:
            suggested_threads = min(16, default_threads)
        
        # Adjust based on CPU (don't overload weak devices)
        if cores <= 2:
            suggested_threads = min(suggested_threads, 4)
        elif cores <= 4:
            suggested_threads = min(suggested_threads, 8)
            
        return min(suggested_threads, default_threads)

    def download_part(self, start, end, part_index):
        # ✅ FIX: Use self.download_path consistently
        if self.download_path:
            part_file = os.path.join(self.download_path, f"{self.filename}.part{part_index}")
        
        else:
            part_file = f"{self.filename}.part{part_index}"

        downloaded = 0
        retries = 0
        
        # Resume support
        if os.path.exists(part_file):
            downloaded = os.path.getsize(part_file)
            # Check if part is already complete
            if start + downloaded >= end:
                self.thread_progress[part_index] = 100
                self.thread_speed[part_index] = 0
                if self.callback:
                    self.callback(part_index, 0, 100)
                return

        while downloaded < (end - start + 1) and retries < MAX_RETRIES:
            try:
                range_start = start + downloaded
                headers = {"Range": f"bytes={range_start}-{end}"}
                
                with self.session.get(self.url, headers=headers, stream=True, timeout=30) as r:
                    if r.status_code == 403:
                        raise Exception("Server blocked download (403 Forbidden)")

                    r.raise_for_status()
                    
                    with open(part_file, "ab") as f:
                        last_time = time.time()
                        last_downloaded = downloaded
                        
                        for chunk in r.iter_content(chunk_size=1024 * 16):
                            # Handle pause
                            while self.paused:
                                time.sleep(0.1)
                                
                            if not chunk:
                                continue
                                
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Progress calculation
                            total_size = end - start + 1
                            percent = min(100, (downloaded / total_size) * 100) if total_size > 0 else 0
                            
                            # Speed calculation
                            now = time.time()
                            delta_bytes = downloaded - last_downloaded
                            delta_time = now - last_time
                            
                            if delta_time > 0.5:  # Update speed every 0.5s
                                speed_in_MB = (delta_bytes / delta_time) / (1024 * 1024)
                                self.thread_speed[part_index] = speed_in_MB
                                last_time = now
                                last_downloaded = downloaded
                            
                            self.thread_progress[part_index] = percent
                            
                            if self.callback:
                                self.callback(part_index, self.thread_speed[part_index], percent)
                
                break  # Successfully completed
                
            except Exception as e:
                retries += 1
                if retries >= MAX_RETRIES:
                    error_type = type(e).__name__
                    print(f"❌ Thread {part_index+1} failed after {MAX_RETRIES} retries:")
                    print(f"   Error Type: {error_type}")
                    print(f"   Error Message: {e}")
                    print(f"   Download URL: {self.url}")
                    print(f"   Range: {range_start}-{end}")
                    # Record the exception to raise later
                    self.exceptions.append(e)
                    return
                print(f"⚠ Thread {part_index+1} error, retry {retries}/{MAX_RETRIES}: {e}")
                time.sleep(RETRY_DELAY)

    def pause(self):
        self.paused = True
        print("⏸ Download Paused.")

    def resume(self):
        self.paused = False
        print("▶ Download Resumed.")

    def merge_parts(self):
        print("\n🔗 Merging downloaded parts...")

        if self.download_path:
            temp_output = os.path.join(self.download_path, self.filename + ".temp")
            final_output = os.path.join(self.download_path, self.filename)

            # Ensure download path exists
            os.makedirs(self.download_path, exist_ok=True)
        else:
            temp_output = self.filename + ".temp"
            final_output = self.filename
        
        print(f"→ Merging into: {final_output}")
        
        try:
            with open(temp_output, "wb") as final_file:
                for i in range(self.num_threads):
                    if self.download_path:
                        part_file = os.path.join(self.download_path, f"{self.filename}.part{i}")
                    else:
                        part_file = f"{self.filename}.part{i}"

                    if not os.path.exists(part_file):
                        print(f"❌ Missing part: {part_file}. Merge aborted.")
                        
                        if self.download_path:
                            alt_part_file = f"{self.filename}.part{i}"
                            if os.path.exists(alt_part_file):
                                print(f"→ Found part in current directory: {alt_part_file}")
                                part_file = alt_part_file
                            else:
                                return False
                        else:
                            return False
                        
                    print(f"📄 Adding part {i}: {part_file}")    
                    with open(part_file, "rb") as pf:
                        final_file.write(pf.read())
                    os.remove(part_file)
            
            # ✅ FIX: Check if final file exists at correct path
            if os.path.exists(final_output):
                print(f"❌ Replacing existing file: {final_output}")
                os.remove(final_output)

            # use correct path for rename
            os.rename(temp_output, final_output)

            #
            if os.path.exists(final_output):
                final_size = os.path.getsize(final_output)
                print(f"✅ Merge complete! Final size: {final_size} bytes")

                # Also clean up temp file if it still exists
                if os.path.exists(temp_output):
                    os.remove(temp_output)

                return True
            else:
                print(f"❌ Merge failed: {final_output} not created")
                return False
            
        except Exception as e:
            print(f"❌ Error during merge: {e}")

            # Clean up on error
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except:
                    pass
            return False

    def download_single_thread(self):
        print("\n⚡ Downloading in single-thread mode...")
        
        # use the correct download path for single-thread downloads
        if self.download_path:
            output_file = os.path.join(self.download_path, self.filename)
        else:
            output_file = self.filename

        try:
            with self.session.get(self.url, stream=True, timeout=30) as r:
                # Handle 403 errors
                if r.status_code == 403:
                    raise Exception("Server blocked download (403 Forbidden)")

                r.raise_for_status()
                
                # Get total size from headers if not already known
                total_size = self.file_size or int(r.headers.get('Content-Length', 0))
                downloaded = 0
                start_time = time.time()
                last_update = start_time
                
                with open(self.filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        while self.paused:
                            time.sleep(0.1)
                            
                        if not chunk:
                            continue
                            
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress periodically
                        now = time.time()
                        if now - last_update > 0.1:  # Update every 100ms
                            elapsed = now - start_time
                            speed_in_MB = (downloaded / elapsed) / (1024 * 1024) if elapsed > 0 else 0
                            percent = (downloaded / total_size * 100) if total_size > 0 else 0
                            
                            if self.callback:
                                self.callback(0, speed_in_MB, percent)
                            last_update = now
                
                # Final update
                if self.callback and total_size > 0:
                    self.callback(0, 0, 100)
                    
        except Exception as e:
            print(f"❌ Single-thread download failed: {e}")
            raise

    def start(self):
        print(f"🚀 Starting download: {self.filename}")
        print(f"📁 File size: {self.file_size} bytes")
        print(f"📁 Download path: {self.download_path}")
        print(f"🧵 Using {self.num_threads} thread(s)")
        try:
            if not self.range_supported or self.file_size == 0:
                self.download_single_thread()
            else:
                threads = []
                for i in range(self.num_threads):
                    start = i * self.part_size
                    if i == self.num_threads - 1:
                        end = self.file_size - 1
                    else:
                        end = start + self.part_size - 1
                        
                    t = threading.Thread(target=self.download_part, args=(start, end, i))

                    threads.append(t)
                    t.daemon = True
                    t.start()

                # Wait for all threads to complete
                for t in threads:
                    t.join()

                if hasattr(self, 'exceptions') and self.exceptions:
                    print(f"❌ Download failed with {len(self.exceptions)} error(s)")
                    raise self.exceptions[0] # Raise the first exception

                # Merge parts if multi-threaded download
                if self.num_threads > 1:
                    if self.merge_parts():
                        final_path = os.path.join(self.download_path, self.filename) if self.download_path else self.filename
                        
                        # Verify download size
                        if os.path.exists(self.filename):
                            final_size = os.path.getsize(self.filename)
                            if self.file_size > 0 and final_size != self.file_size:
                                print(f"❌ Size mismatch! Expected: {self.file_size}, Got: {final_size}")
                                print("→ Re-downloading in single-thread mode...")
                                self.download_single_thread()
                        else:
                            print(f"❌ Final file not found after merge: {final_path}")
                            raise Exception(f"Final file not created at {final_path}")
                    else:
                        raise Exception("Merging parts failed")
            print(f"✅ Download complete: {self.filename}")
            if self.download_path:
                print(f"✅ File saved to: {os.path.join(self.download_path, self.filename)}")

            else:
                print(f"✅ File saved to: {self.filename}")

        except Exception as e:
            print(f"❌ Download failed: {e}")
            raise #re-raise the exception to be caught by the ui


if __name__ == "__main__":
    import multiprocessing 
    multiprocessing.freeze_support()
    from desktop_echo import DownloadManagerUI
    app = DownloadManagerUI()
    app.mainloop()