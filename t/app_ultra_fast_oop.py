# Multi-Page ManyChat Automation with Pagination Support
# Fully Class-Based Programming Approach
# Object-Oriented Design with Multiple Specialized Classes

from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager as WDMChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json
import os
import random
import string
import shutil
import sys
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

# Import timezone configuration
try:
    from properties import MANYCHAT_TIMEZONE
except ImportError:
    from datetime import timezone

    MANYCHAT_TIMEZONE = timezone(timedelta(hours=-4))

# Import the ChromeProfileManager from profiles file
try:
    from profiels import ChromeProfileManager

    PROFILE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ChromeProfileManager not available: {e}")
    print("Some functions may not work. Make sure profiels.py is in the same directory")
    PROFILE_MANAGER_AVAILABLE = False
    ChromeProfileManager = None


def generate_unique_filename(base_name: str, file_type: str, extension: str) -> str:
    """Generate unique filename with datetime stamp and 8-character unique identifier"""
    # Current datetime stamp
    datetime_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate 8-character unique identifier
    unique_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Combine all parts
    filename = f"{base_name}_{file_type}_{datetime_stamp}_{unique_id}.{extension}"

    return filename


class ChromeDriverManagerOOP:
    """Handles Chrome driver setup and management"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.driver_path = None

    def setup_chromedriver(self) -> Service:
        """Setup ChromeDriver automatically"""
        if self.verbose:
            print("Setting up ChromeDriver automatically...")

        try:
            # Clear any cached corrupted drivers
            cache_dir = os.path.join(os.path.expanduser("~"), ".wdm")
            if os.path.exists(cache_dir):
                if self.verbose:
                    print("Clearing webdriver cache...")
                shutil.rmtree(cache_dir, ignore_errors=True)

            # Download fresh ChromeDriver
            driver_path = WDMChromeDriverManager().install()
            if self.verbose:
                print(f"ChromeDriver manager returned: {driver_path}")

            # webdriver-manager sometimes returns wrong path, let's find the actual executable
            if not driver_path.endswith(".exe"):
                # Look for chromedriver.exe in the directory
                driver_dir = os.path.dirname(driver_path)
                for root, dirs, files in os.walk(driver_dir):
                    for file in files:
                        if file.lower() == "chromedriver.exe":
                            driver_path = os.path.join(root, file)
                            if self.verbose:
                                print(f"Found actual ChromeDriver at: {driver_path}")
                            break

            # Verify the downloaded file is valid
            if not os.path.exists(driver_path):
                raise Exception("ChromeDriver not found at expected location")

            if not driver_path.endswith(".exe"):
                raise Exception("ChromeDriver path doesn't point to executable")

            file_size = os.path.getsize(driver_path)
            if file_size < 1000:  # ChromeDriver should be much larger than 1KB
                raise Exception("Downloaded ChromeDriver appears to be corrupted")

            self.driver_path = driver_path
            if self.verbose:
                print(f"Using ChromeDriver: {driver_path}")

            return Service(driver_path)

        except Exception as e:
            if self.verbose:
                print(f"Webdriver-manager failed: {e}")
            raise Exception(
                "No valid ChromeDriver found. Please install ChromeDriver manually."
            )

    def create_fast_driver(
        self, profile_path: str, headless: bool = True
    ) -> webdriver.Chrome:
        """Create an optimized Chrome driver with the specified profile"""
        if self.verbose:
            print(f"Creating driver with profile: {profile_path}")
            print(f"Headless mode: {headless}")

        # Setup ChromeDriver service
        service = self.setup_chromedriver()
        options = Options()

        # Use the saved profile
        options.add_argument(f"--user-data-dir={profile_path}")

        # Speed optimizations
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-features=TranslateUI")

        # Disable unnecessary features for speed
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Don't load images - much faster
        options.add_argument("--disable-web-security")

        # Memory optimizations
        options.add_argument("--memory-pressure-off")

        # Headless mode for speed (optional)
        if headless:
            options.add_argument("--headless")
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")

        # Reduce logging
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        # Certificate and SSL related options
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--ignore-certificate-errors-spki-list")
        options.add_argument("--allow-running-insecure-content")

        # Add user agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(service=service, options=options)

        # Mask webdriver
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        return driver


class ConfigurationManager:
    """Handles loading and managing page configurations"""

    def __init__(self, config_file: str = "page_ids.json", verbose: bool = True):
        self.config_file = config_file
        self.verbose = verbose
        self.config = None
        self.active_pages = []

    def load_page_config(self) -> Optional[Dict]:
        """Load page IDs configuration from JSON file"""
        try:
            if not os.path.exists(self.config_file):
                if self.verbose:
                    print(f"[ERROR] Config file {self.config_file} not found!")
                return None

            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            # Validate config structure
            if "pages" not in self.config:
                if self.verbose:
                    print("[ERROR] Invalid config file: missing 'pages' key")
                return None

            pages = self.config["pages"]
            self.active_pages = [p for p in pages if p.get("active", True)]

            if self.verbose:
                print(
                    f"[INFO] Loaded {len(pages)} pages from config ({len(self.active_pages)} active)"
                )
                for page in self.active_pages:
                    print(f"   [SUCCESS] {page['name']} ({page['id']})")

            return self.config

        except Exception as e:
            if self.verbose:
                print(f"[ERROR] Error loading config file: {e}")
            return None

    def get_active_pages(self) -> List[Dict]:
        """Get list of active pages"""
        if self.config is None:
            self.load_page_config()
        return self.active_pages

    def get_page_by_id(self, page_id: str) -> Optional[Dict]:
        """Get page configuration by ID"""
        if self.config is None:
            self.load_page_config()

        for page in self.config.get("pages", []):
            if page["id"] == page_id:
                return page
        return None

    def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate configuration and return status with errors"""
        errors = []

        if self.config is None:
            if not self.load_page_config():
                errors.append("Could not load configuration file")
                return False, errors

        pages = self.config.get("pages", [])
        if not pages:
            errors.append("No pages defined in configuration")

        active_count = len([p for p in pages if p.get("active", True)])
        if active_count == 0:
            errors.append("No active pages found")

        # Validate page structure
        required_fields = ["id", "name"]
        for i, page in enumerate(pages):
            for field in required_fields:
                if field not in page:
                    errors.append(f"Page {i+1} missing required field: {field}")

        return len(errors) == 0, errors


class DataExtractor:
    """Handles data extraction from ManyChat pages"""

    def __init__(self, chrome_manager: ChromeDriverManagerOOP, verbose: bool = True):
        self.chrome_manager = chrome_manager
        self.verbose = verbose
        self.current_driver = None

    def load_more_broadcasts_paginated(
        self,
        driver: webdriver.Chrome,
        page_id: str,
        headers: Dict,
        date_filter: Optional[Dict] = None,
        max_pages: int = 25,
    ) -> List[Dict]:
        """Load more broadcasts using pagination with optimized JavaScript requests"""
        all_posts = []
        page_count = 0
        limiter = None

        # Convert date filter to timestamps for comparison
        start_ts = None
        end_ts = None
        if (
            date_filter
            and date_filter.get("start_date")
            and date_filter.get("end_date")
        ):
            # Use ManyChat timezone (UTC-4) for proper timestamp conversion
            start_dt = datetime.strptime(date_filter["start_date"], "%Y-%m-%d")
            start_dt = start_dt.replace(tzinfo=MANYCHAT_TIMEZONE)
            start_ts = int(start_dt.timestamp())

            end_dt = datetime.strptime(
                date_filter["end_date"] + " 23:59:59", "%Y-%m-%d %H:%M:%S"
            )
            end_dt = end_dt.replace(tzinfo=MANYCHAT_TIMEZONE)
            end_ts = int(end_dt.timestamp())

            if self.verbose:
                print(
                    f"[SEARCH] Looking for broadcasts between {date_filter['start_date']} and {date_filter['end_date']} (ManyChat timezone UTC-4)"
                )
                print(f"   Timestamp range: {start_ts} to {end_ts}")

        # Base API URL
        target_url = f"https://app.manychat.com/{page_id}/broadcasting/loadHistory"

        while page_count < max_pages:
            page_count += 1
            if self.verbose:
                print(f"\n[PAGE] Loading page {page_count}...")

            # Build URL with limiter parameter if we have one
            url = target_url
            if limiter:
                url = f"{target_url}?limiter={limiter}"
                if self.verbose:
                    print(f"   Using limiter: {limiter}")

            page_data = None

            if page_count == 1:
                # For first page, check captured requests
                if self.verbose:
                    print("   Checking initial captured requests...")
                time.sleep(2)

                for req in reversed(driver.requests):
                    if req.response and "loadHistory" in req.url:
                        try:
                            body = req.response.body
                            if body.startswith(b"\x1f\x8b"):
                                body = gzip.decompress(body)
                            page_data = json.loads(body.decode("utf-8"))
                            if self.verbose:
                                print(
                                    f"   [SUCCESS] Found initial page data from captured request"
                                )
                            break
                        except Exception:
                            continue
            else:
                # For subsequent pages, use JavaScript to make the request
                if self.verbose:
                    print(f"   Making JavaScript request to: {url}")
                try:
                    # Clear any previous data
                    driver.execute_script("window.manychat_page_data = null;")

                    # Use JavaScript to make the request
                    js_code = f"""
                    fetch('{url}', {{
                        method: 'GET',
                        headers: {json.dumps(dict(headers))},
                        credentials: 'include'
                    }})
                    .then(response => response.json())
                    .then(data => window.manychat_page_data = data)
                    .catch(error => window.manychat_page_error = error.toString());
                    """
                    driver.execute_script(js_code)

                    # Wait and check for response
                    for attempt in range(10):  # Try up to 10 times, 0.5s each
                        time.sleep(0.5)
                        page_data = driver.execute_script(
                            "return window.manychat_page_data;"
                        )
                        if page_data:
                            break

                    if page_data and self.verbose:
                        print(
                            f"   [SUCCESS] Got {len(page_data.get('posts', []))} posts via JavaScript"
                        )
                    elif not page_data:
                        error = driver.execute_script(
                            "return window.manychat_page_error;"
                        )
                        if self.verbose:
                            print(f"   [ERROR] No data received. Error: {error}")
                        break

                except Exception as e:
                    if self.verbose:
                        print(f"   [ERROR] JavaScript request failed: {e}")
                    break

            if not page_data:
                if self.verbose:
                    print(f"   [WARNING] No data found for page {page_count}")
                break

            # Process the page data
            posts = page_data.get("posts", [])
            total_available = page_data.get("total", 0)
            new_limiter = page_data.get("limiter")

            if self.verbose:
                print(f"   Posts in this page: {len(posts)}")
                print(f"   Total available in system: {total_available}")
                print(f"   New limiter: {new_limiter}")

            if not posts:
                if self.verbose:
                    print("   [WARNING] No posts in this page, stopping pagination")
                break

            # Filter posts by date if specified
            page_posts_in_range = []
            oldest_in_page = None
            newest_in_page = None

            for post in posts:
                post_ts = post.get("timestamp")
                if post_ts:
                    if oldest_in_page is None or post_ts < oldest_in_page:
                        oldest_in_page = post_ts
                    if newest_in_page is None or post_ts > newest_in_page:
                        newest_in_page = post_ts

                    # Check if post is in date range
                    if start_ts and end_ts:
                        if start_ts <= post_ts <= end_ts:
                            page_posts_in_range.append(post)
                    else:
                        page_posts_in_range.append(post)

            if oldest_in_page and newest_in_page and self.verbose:
                oldest_date = datetime.fromtimestamp(oldest_in_page).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                newest_date = datetime.fromtimestamp(newest_in_page).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                print(f"   Date range in page: {oldest_date} to {newest_date}")
                print(f"   Posts matching date filter: {len(page_posts_in_range)}")

            # Add posts from this page
            all_posts.extend(page_posts_in_range)

            # Check if we should continue
            if not new_limiter or new_limiter == limiter:
                if self.verbose:
                    print("   [WARNING] No new limiter, stopping pagination")
                break

            # If we're looking for a specific date range and all posts in this page are older than our range, stop
            if start_ts and oldest_in_page and oldest_in_page < start_ts:
                if self.verbose:
                    print(
                        f"   [WARNING] All posts in this page are older than {date_filter['start_date']}, stopping"
                    )
                break

            # Update limiter for next request
            limiter = new_limiter

            # Small delay between requests to be respectful
            time.sleep(1)

        if self.verbose:
            print(f"\n[COMPLETE] Pagination complete!")
            print(f"   Pages loaded: {page_count}")
            print(f"   Total posts collected: {len(all_posts)}")

        return all_posts

    def extract_data_from_page(
        self,
        profile_manager: ChromeProfileManager,
        profile_name: str,
        page_id: str,
        page_name: str = "Unknown Page",
        target_date_start: Optional[str] = None,
        target_date_end: Optional[str] = None,
        headless: bool = True,
    ) -> List[Dict]:
        """Extract data using profile with speed optimizations AND pagination for a specific page"""

        # Create date filter object
        date_filter = None
        if target_date_start and target_date_end:
            date_filter = {"start_date": target_date_start, "end_date": target_date_end}

        # Get profile path
        profile_data = profile_manager.profiles[profile_name]
        profile_path = profile_data["path"]

        # Create driver with selected profile
        driver = self.chrome_manager.create_fast_driver(profile_path, headless)
        self.current_driver = driver

        try:
            if self.verbose:
                print(
                    f"[START] Navigating to ManyChat page: {page_name} ({page_id})..."
                )
            driver.get(f"https://app.manychat.com/{page_id}/posting/history")

            if self.verbose:
                print("[WAIT] Waiting for initial page load...")
            time.sleep(6)  # Wait for page to load and make initial API calls

            # Extract headers from the first request for pagination
            headers = {}
            if self.verbose:
                print(f"[SEARCH] Checking {len(driver.requests)} captured requests...")

            for request in driver.requests:
                if request.response and "loadHistory" in request.url:
                    headers = dict(request.headers)
                    if self.verbose:
                        print(
                            f"   [SUCCESS] Found initial API request, extracted headers"
                        )
                    break

            if not headers:
                if self.verbose:
                    print(
                        "   [WARNING] No initial request found, using default headers"
                    )
                headers = {
                    "accept": "application/json, text/plain, */*",
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "en-GB,en;q=0.6",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                    "x-requested-with": "XMLHttpRequest",
                    "referer": f"https://app.manychat.com/{page_id}/posting/history",
                }

            # Load all broadcasts with pagination
            if self.verbose:
                print("\n[PROCESS] Starting paginated data extraction...")
            all_posts = self.load_more_broadcasts_paginated(
                driver, page_id, headers, date_filter
            )

            if self.verbose:
                print(f"\n[RESULTS] Final Results:")
                print(f"   Total posts extracted: {len(all_posts)}")

            # Update last_used timestamp
            profile_manager.profiles[profile_name]["last_used"] = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            profile_manager._save_profiles()

            return all_posts

        except Exception as e:
            if self.verbose:
                print(f"[ERROR] Error during extraction for {page_name}: {e}")
                import traceback

                traceback.print_exc()
            return []

        finally:
            if self.verbose:
                print(f"[CLOSE] Closing browser for {page_name}...")
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    if self.verbose:
                        print(f"[WARNING] Error closing driver: {e}")
                    # Force kill any remaining processes
                    try:
                        import psutil
                        import os

                        current_pid = os.getpid()
                        for proc in psutil.process_iter(["pid", "name"]):
                            if (
                                "chrome" in proc.info["name"].lower()
                                and proc.info["pid"] != current_pid
                            ):
                                try:
                                    proc.terminate()
                                except:
                                    pass
                    except ImportError:
                        pass  # psutil not available, skip process cleanup
                    except Exception:
                        pass  # Ignore cleanup errors
            self.current_driver = None

    def extract_data_from_multiple_pages(
        self,
        profile_manager: ChromeProfileManager,
        profile_name: str,
        page_config: Dict,
        target_date_start: Optional[str] = None,
        target_date_end: Optional[str] = None,
        headless: bool = True,
    ) -> Dict:
        """Extract data from multiple pages as specified in the config"""

        if not page_config or "pages" not in page_config:
            if self.verbose:
                print("[ERROR] Invalid page configuration")
            return {}

        pages = page_config["pages"]
        active_pages = [p for p in pages if p.get("active", True)]

        if self.verbose:
            print(f"\n[PROCESS] Starting extraction from {len(active_pages)} pages...")

        all_results = {}
        total_posts = 0
        start_time = time.time()

        for i, page in enumerate(active_pages, 1):
            page_id = page["id"]
            page_name = page["name"]

            if self.verbose:
                print(f"\n{'='*60}")
                print(f"[PAGE] Processing page {i}/{len(active_pages)}: {page_name}")
                print(f"   Page ID: {page_id}")
                print(f"   Description: {page.get('description', 'No description')}")
                print(f"{'='*60}")

            # Extract data for this page
            page_posts = self.extract_data_from_page(
                profile_manager,
                profile_name,
                page_id,
                page_name,
                target_date_start,
                target_date_end,
                headless,
            )

            # Store results
            page_result = {
                "page_info": page,
                "posts": page_posts,
                "total_posts": len(page_posts),
                "extraction_time": time.time() - start_time,
            }

            all_results[page_id] = page_result
            total_posts += len(page_posts)

            if self.verbose:
                print(
                    f"\n[SUCCESS] Page {page_name} complete: {len(page_posts)} posts extracted"
                )

            # Small delay between pages to be respectful
            if i < len(active_pages):
                if self.verbose:
                    print("[WAIT] Brief pause before next page...")
                time.sleep(3)

        total_time = time.time() - start_time

        if self.verbose:
            print(f"\n[COMPLETE] Multi-page extraction complete!")
            print(f"   Total pages processed: {len(active_pages)}")
            print(f"   Total posts extracted: {total_posts}")
            print(f"   Total time: {total_time:.1f} seconds")
            if total_time > 0:
                print(f"   Average posts per second: {total_posts/total_time:.1f}")

        return all_results


class ProfileManager:
    """Handles profile management and operations"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.profile_manager = None
        self.available = PROFILE_MANAGER_AVAILABLE

    def initialize(self) -> bool:
        """Initialize the profile manager"""
        if not self.available:
            if self.verbose:
                print(
                    "Error: ChromeProfileManager not available. Cannot manage profiles."
                )
            return False

        self.profile_manager = ChromeProfileManager()
        return True

    def list_profiles(self) -> bool:
        """List all available profiles and their status"""
        if not self.initialize():
            return False

        if not self.profile_manager.profiles:
            if self.verbose:
                print(
                    "No profiles found. Please create a profile first using profiels.py"
                )
            return False

        if self.verbose:
            print("\n=== Available Profiles ===")
            for i, (profile_name, profile_data) in enumerate(
                self.profile_manager.profiles.items(), 1
            ):
                status = (
                    "[VERIFIED] Verified"
                    if profile_data.get("verified", False)
                    else "[NOT VERIFIED] Not verified"
                )
                email = profile_data.get("email", "N/A")
                last_used = profile_data.get("last_used", "Never")

                print(f"{i}. {profile_name}")
                print(f"   Email: {email}")
                print(f"   Status: {status}")
                print(f"   Last used: {last_used}")
                print()

        return True

    def select_profile_interactive(self) -> Optional[str]:
        """Allow user to select a profile interactively"""
        if not self.initialize():
            return None

        profile_names = list(self.profile_manager.profiles.keys())

        while True:
            try:
                choice = input(
                    f"Select profile (1-{len(profile_names)}) or 'q' to quit: "
                )

                if choice.lower() == "q":
                    return None

                profile_index = int(choice) - 1
                if 0 <= profile_index < len(profile_names):
                    selected_profile = profile_names[profile_index]
                    if self.verbose:
                        print(f"Selected profile: {selected_profile}")
                    return selected_profile
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number or 'q' to quit.")

    def get_best_profile(self, preferred_name: Optional[str] = None) -> Optional[str]:
        """Get the best available profile (verified first, or specified profile)"""
        if not self.initialize():
            return None

        profiles = self.profile_manager.profiles

        # If specific profile requested and exists
        if preferred_name and preferred_name in profiles:
            return preferred_name

        # Get verified profiles
        verified_profiles = [
            name for name, data in profiles.items() if data.get("verified", False)
        ]

        if verified_profiles:
            return verified_profiles[0]

        # Fallback to first available profile
        profile_names = list(profiles.keys())
        return profile_names[0] if profile_names else None

    def get_profiles_info(self) -> Dict:
        """Get information about all profiles"""
        if not self.initialize():
            return {"available": False, "profiles": {}}

        return {
            "available": True,
            "profiles": self.profile_manager.profiles,
            "total_count": len(self.profile_manager.profiles),
            "verified_count": sum(
                1
                for data in self.profile_manager.profiles.values()
                if data.get("verified", False)
            ),
        }


class DateFilterManager:
    """Handles date filtering and validation"""

    @staticmethod
    def get_date_filter_interactive() -> (
        Tuple[Optional[str], Optional[str], Optional[str]]
    ):
        """Get date filtering options from user with expanded range options"""
        print("\n=== Date Range Options ===")
        print("1. Today only (current date)")
        print("2. Last 1 day (yesterday + today)")
        print("3. Last 2 days")
        print("4. Last 3 days")
        print("5. Last 7 days (recommended)")
        print("6. Last 30 days")
        print("7. Custom date range")
        print("8. All broadcasts")

        choice = input("\nSelect option (1-8, default=5): ").strip()

        if choice == "1":
            today = datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            print(f"[DATE] Extracting data for TODAY only: {today_str}")
            return (today_str, today_str, "today_only")

        elif choice == "2":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_1_day",
            )

        elif choice == "3":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_2_days",
            )

        elif choice == "4":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_3_days",
            )

        elif choice == "6":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_30_days",
            )

        elif choice == "7":
            return DateFilterManager._get_custom_date_range()

        elif choice == "8":
            return None, None, "all"

        else:  # Default to last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_7_days",
            )

    @staticmethod
    def _get_custom_date_range() -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get custom date range from user"""
        print("\n[DATE] Custom Date Range")
        print("=" * 40)
        print("[INFO] Examples of valid date formats:")
        print("   - 2024-09-01 (September 1, 2024)")
        print("   - 2024-12-25 (Christmas Day 2024)")
        print("   - 2025-01-01 (New Year 2025)")
        print("")
        print("[TIP] Common date range examples:")
        print("   - Last week: Start=2024-09-20, End=2024-09-27")
        print("   - This month: Start=2024-09-01, End=2024-09-30")
        print("   - Specific campaign: Start=2024-09-15, End=2024-09-22")
        print("   - Holiday period: Start=2024-12-20, End=2024-12-31")
        print("")
        print("[WARNING]  Format must be: YYYY-MM-DD")
        print("[WARNING]  Start date should be earlier than end date")
        print("")

        # Show current date for reference
        today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
        print(f"[DATE] Today's date (ManyChat timezone UTC-4): {today}")
        print("")

        start_date = input("Enter START date (YYYY-MM-DD): ").strip()
        end_date = input("Enter END date (YYYY-MM-DD): ").strip()

        if not start_date or not end_date:
            print("[ERROR] Both start and end dates are required for custom range")
            return None, None, None

        try:
            # Validate dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Check if start is before end
            if start_dt > end_dt:
                print("[ERROR] Start date must be earlier than or equal to end date")
                return None, None, None

            # Calculate days difference
            days_diff = (end_dt - start_dt).days + 1
            print(
                f"[SUCCESS] Date range validated: {days_diff} day(s) from {start_date} to {end_date}"
            )

            return start_date, end_date, "custom_range"
        except ValueError:
            print("[ERROR] Invalid date format. Please use YYYY-MM-DD format")
            print("   Examples: 2024-09-27, 2024-12-25, 2025-01-01")
            return None, None, None

    @staticmethod
    def get_date_range_by_type(
        date_type: str, custom_start: str = None, custom_end: str = None
    ) -> Tuple[Optional[str], Optional[str], str]:
        """Get date range by type programmatically"""
        if date_type == "today_only":
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

        elif date_type == "last_7_days":
            end_date = datetime.now(MANYCHAT_TIMEZONE)
            start_date = end_date - timedelta(days=7)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_7_days",
            )

        elif date_type == "last_30_days":
            end_date = datetime.now(MANYCHAT_TIMEZONE)
            start_date = end_date - timedelta(days=30)
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                "last_30_days",
            )

        elif date_type == "custom_range" and custom_start and custom_end:
            return custom_start, custom_end, "custom_range"

        elif date_type == "all":
            return None, None, "all"

        else:
            # Default to today
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

    @staticmethod
    def get_filename_suffix(
        filter_type: str, start_date: str = None, end_date: str = None
    ) -> str:
        """Generate filename suffix based on filter type"""
        if filter_type == "today_only":
            return "_today_paginated"
        elif filter_type == "last_1_day":
            return "_last1day_paginated"
        elif filter_type == "last_2_days":
            return "_last2days_paginated"
        elif filter_type == "last_3_days":
            return "_last3days_paginated"
        elif filter_type == "last_7_days":
            return "_last7days_paginated"
        elif filter_type == "last_30_days":
            return "_last30days_paginated"
        elif filter_type == "custom_range" and start_date and end_date:
            return f"_{start_date}_to_{end_date}_paginated"
        else:
            return "_all_paginated"


class OutputManager:
    """Handles file output and data formatting"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def create_combined_data(
        self,
        all_results: Dict,
        filter_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
        extraction_time: float,
        headless: bool,
        profile_used: str,
    ) -> Dict:
        """Create combined data structure for output"""
        combined_data = {}
        page_summaries = []

        for page_id, result in all_results.items():
            page_info = result["page_info"]
            page_name = page_info["name"]
            page_posts = result["posts"]

            # Create page entry with posts and metadata
            combined_data[page_name] = {
                "posts": page_posts,
                "page_info": {
                    "page_id": page_info["id"],
                    "page_name": page_info["name"],
                    "description": page_info.get("description", ""),
                    "active": page_info.get("active", True),
                },
                "total_posts": result["total_posts"],
            }

            # Create page summary for the summary section
            page_summaries.append(
                {
                    "page_id": page_info["id"],
                    "page_name": page_info["name"],
                    "description": page_info.get("description", ""),
                    "total_posts": result["total_posts"],
                    "active": page_info.get("active", True),
                }
            )

        # Add overall summary at the end
        combined_data["_extraction_summary"] = {
            "total_pages_processed": len(all_results),
            "total_posts_extracted": sum(
                result["total_posts"] for result in all_results.values()
            ),
            "profile_used": profile_used,
            "headless_mode": headless,
            "date_filter": {
                "type": filter_type,
                "start_date": start_date,
                "end_date": end_date,
            },
            "extracted_at": datetime.now().isoformat(),
            "method": "class_based_multi_page_selenium_with_pagination",
            "extraction_time_seconds": extraction_time,
            "pages_included": [
                {
                    "id": p["page_id"],
                    "name": p["page_name"],
                    "posts": p["total_posts"],
                }
                for p in page_summaries
            ],
        }

        return combined_data

    def save_results(
        self,
        all_results: Dict,
        filter_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
        extraction_time: float,
        headless: bool,
        profile_used: str,
    ) -> List[str]:
        """Save extraction results to files"""
        saved_files = []

        if not all_results:
            if self.verbose:
                print("[WARNING] No results to save")
            return saved_files

        total_posts = sum(result["total_posts"] for result in all_results.values())
        all_timestamps = []

        for result in all_results.values():
            for post in result["posts"]:
                if post.get("timestamp"):
                    all_timestamps.append(post["timestamp"])

        # Show results summary
        if self.verbose:
            print(f"\n[COMPLETE] Multi-Page Extraction Complete!")
            print(f"   Total pages processed: {len(all_results)}")
            print(f"   Total broadcasts extracted: {total_posts}")

            # Show date range of extracted data
            if all_timestamps:
                oldest_ts = min(all_timestamps)
                newest_ts = max(all_timestamps)
                oldest_date = datetime.fromtimestamp(oldest_ts).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                newest_date = datetime.fromtimestamp(newest_ts).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                print(f"   Overall date range: {oldest_date} to {newest_date}")
                print(f"   Time span: {(newest_ts - oldest_ts) / 86400:.1f} days")

        # Create filename suffix with date filter info
        filename_suffix = DateFilterManager.get_filename_suffix(
            filter_type, start_date, end_date
        )

        # Save combined file with unique naming convention
        base_filename = f"manychat_all_pages{filename_suffix}"
        combined_filename = generate_unique_filename(base_filename, "combined", "json")

        # Get json_output directory from Properties
        try:
            from properties import Properties

            json_output_dir = Properties.JSON_OUTPUT_DIRECTORY
        except (ImportError, AttributeError):
            json_output_dir = "./json_output/"

        # Create directory if it doesn't exist
        if not os.path.exists(json_output_dir):
            os.makedirs(json_output_dir)

        # Create full path for the combined file
        combined_file = os.path.join(json_output_dir, combined_filename)

        combined_data = self.create_combined_data(
            all_results,
            filter_type,
            start_date,
            end_date,
            extraction_time,
            headless,
            profile_used,
        )

        try:
            with open(combined_file, "w", encoding="utf-8") as f:
                json.dump(combined_data, f, ensure_ascii=False, indent=2)

            saved_files.append(combined_file)

            if self.verbose:
                print(f"\n[SUCCESS] Combined file saved: {combined_file}")
                print(f"   Contains {total_posts} posts from {len(all_results)} pages")

        except Exception as e:
            if self.verbose:
                print(f"[ERROR] Failed to save file {combined_file}: {e}")

        return saved_files

    def show_performance_summary(
        self,
        extraction_time: float,
        total_posts: int,
        pages_processed: int,
        headless: bool,
        files_saved: int,
    ):
        """Show performance summary"""
        if not self.verbose:
            return

        print(f"\n[TARGET] Performance Summary:")
        print(f"   [FAST] Total extraction time: {extraction_time:.1f} seconds")
        print(f"   [PAGE] Total posts extracted: {total_posts}")
        print(f"   [RESULTS] Pages processed: {pages_processed}")
        if extraction_time > 0:
            print(f"   [START] Posts per second: {total_posts/extraction_time:.1f}")
        print(f"   [MODE] Mode used: {'Headless' if headless else 'Windowed'}")
        print(f"   [INFO] Files saved: {files_saved}")


class ManyChatExtractorOOP:
    """
    Main class-based ManyChat extractor with full object-oriented design
    All functionality is encapsulated in specialized classes
    """

    def __init__(self, config_file: str = "page_ids.json", verbose: bool = True):
        """Initialize the extractor with all its components"""
        self.verbose = verbose

        # Initialize all manager components
        self.chrome_manager = ChromeDriverManagerOOP(verbose=verbose)
        self.config_manager = ConfigurationManager(config_file, verbose=verbose)
        self.data_extractor = DataExtractor(self.chrome_manager, verbose=verbose)
        self.profile_manager = ProfileManager(verbose=verbose)
        self.output_manager = OutputManager(verbose=verbose)

        # State variables
        self.selected_profile = None
        self.current_config = None

    def initialize(self) -> bool:
        """Initialize all components and validate system"""
        try:
            # Load configuration
            self.current_config = self.config_manager.load_page_config()
            if not self.current_config:
                if self.verbose:
                    print("[ERROR] Failed to load configuration")
                return False

            # Validate configuration
            valid, errors = self.config_manager.validate_config()
            if not valid:
                if self.verbose:
                    print("[ERROR] Configuration validation failed:")
                    for error in errors:
                        print(f"   - {error}")
                return False

            # Initialize profile manager
            if not self.profile_manager.initialize():
                if self.verbose:
                    print("[WARNING] Profile manager not available")
                # Don't fail completely, some functions might still work

            return True

        except Exception as e:
            if self.verbose:
                print(f"[ERROR] Initialization failed: {e}")
            return False

    def quick_extract_today(
        self, profile_name: Optional[str] = None, headless: bool = True
    ) -> Dict:
        """Quick extraction for today's data"""
        if not self.initialize():
            return {"success": False, "error": "Initialization failed", "files": []}

        # Auto-select profile
        if not profile_name:
            profile_name = self.profile_manager.get_best_profile()

        if not profile_name:
            return {"success": False, "error": "No profile available", "files": []}

        self.selected_profile = profile_name

        # Get today's date range
        start_date, end_date, filter_type = DateFilterManager.get_date_range_by_type(
            "today_only"
        )

        return self._execute_extraction(start_date, end_date, filter_type, headless)

    def quick_extract_last_7_days(
        self, profile_name: Optional[str] = None, headless: bool = True
    ) -> Dict:
        """Quick extraction for last 7 days"""
        if not self.initialize():
            return {"success": False, "error": "Initialization failed", "files": []}

        # Auto-select profile
        if not profile_name:
            profile_name = self.profile_manager.get_best_profile()

        if not profile_name:
            return {"success": False, "error": "No profile available", "files": []}

        self.selected_profile = profile_name

        # Get last 7 days date range
        start_date, end_date, filter_type = DateFilterManager.get_date_range_by_type(
            "last_7_days"
        )

        return self._execute_extraction(start_date, end_date, filter_type, headless)

    def extract_with_custom_range(
        self,
        start_date: str,
        end_date: str,
        profile_name: Optional[str] = None,
        headless: bool = True,
    ) -> Dict:
        """Extract data with custom date range"""
        if not self.initialize():
            return {"success": False, "error": "Initialization failed", "files": []}

        # Auto-select profile
        if not profile_name:
            profile_name = self.profile_manager.get_best_profile()

        if not profile_name:
            return {"success": False, "error": "No profile available", "files": []}

        self.selected_profile = profile_name

        return self._execute_extraction(start_date, end_date, "custom_range", headless)

    def run_interactive_extraction(self) -> Dict:
        """Run interactive extraction with user input"""
        if not self.initialize():
            return {"success": False, "error": "Initialization failed", "files": []}

        print("\n=== Interactive Extraction Mode ===")
        print("[INFO] This mode gives you full control over the extraction process")

        # List and select profile
        if not self.profile_manager.list_profiles():
            return {"success": False, "error": "No profiles available", "files": []}

        selected_profile = self.profile_manager.select_profile_interactive()
        if not selected_profile:
            return {
                "success": False,
                "error": "Profile selection cancelled",
                "files": [],
            }

        self.selected_profile = selected_profile

        # Ask about headless mode
        headless_choice = (
            input("\nRun in headless mode? (faster, no browser window) [y/N]: ")
            .strip()
            .lower()
        )
        headless = headless_choice in ["y", "yes"]

        # Get date filtering options
        start_date, end_date, filter_type = (
            DateFilterManager.get_date_filter_interactive()
        )
        if filter_type is None:
            return {"success": False, "error": "Invalid date filter", "files": []}

        if self.verbose:
            print(f"\n[TARGET] Selected filter: {filter_type}")
            if start_date:
                print(f"   Date range: {start_date} to {end_date}")
            print(
                f"[MODE] Mode: {'Headless (fast)' if headless else 'With browser window'}"
            )

        return self._execute_extraction(start_date, end_date, filter_type, headless)

    def _execute_extraction(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        filter_type: str,
        headless: bool,
    ) -> Dict:
        """Execute the actual extraction process"""
        try:
            if self.verbose:
                print(f"\n[START] Starting extraction...")
                print(f"   Profile: {self.selected_profile}")
                print(
                    f"   Date range: {start_date} to {end_date}"
                    if start_date
                    else "   All data"
                )
                print(f"   Mode: {'Headless' if headless else 'Windowed'}")

            start_time = time.time()

            # Extract data from all pages
            all_results = self.data_extractor.extract_data_from_multiple_pages(
                self.profile_manager.profile_manager,
                self.selected_profile,
                self.current_config,
                start_date,
                end_date,
                headless,
            )

            extraction_time = time.time() - start_time

            if not all_results:
                return {
                    "success": False,
                    "error": "No data extracted from any pages",
                    "files": [],
                }

            # Save results
            saved_files = self.output_manager.save_results(
                all_results,
                filter_type,
                start_date,
                end_date,
                extraction_time,
                headless,
                self.selected_profile,
            )

            # Show performance summary
            total_posts = sum(result["total_posts"] for result in all_results.values())
            self.output_manager.show_performance_summary(
                extraction_time,
                total_posts,
                len(all_results),
                headless,
                len(saved_files),
            )

            return {
                "success": True,
                "files": saved_files,
                "total_posts": total_posts,
                "pages_processed": len(all_results),
                "extraction_time": extraction_time,
                "profile_used": self.selected_profile,
            }

        except Exception as e:
            error_msg = f"Extraction failed: {e}"
            if self.verbose:
                print(f"[ERROR] {error_msg}")
                import traceback

                traceback.print_exc()
            return {"success": False, "error": error_msg, "files": []}

    def show_configuration(self):
        """Display current configuration"""
        if not self.current_config:
            self.initialize()

        print("\n=== Current Configuration ===")

        if self.current_config:
            pages = self.current_config.get("pages", [])
            active_pages = [p for p in pages if p.get("active", True)]

            print(f"📋 Total pages configured: {len(pages)}")
            print(f"✅ Active pages: {len(active_pages)}")

            print("\n📄 Page Details:")
            for i, page in enumerate(pages, 1):
                status = "✅ ACTIVE" if page.get("active", True) else "❌ INACTIVE"
                print(f"{i}. {page['name']} ({page['id']}) - {status}")
                if page.get("description"):
                    print(f"   Description: {page['description']}")

        # Show profile info
        profile_info = self.profile_manager.get_profiles_info()
        if profile_info["available"]:
            print(f"\n👤 Available profiles: {profile_info['total_count']}")
            print(f"✅ Verified profiles: {profile_info['verified_count']}")

    def show_help(self):
        """Show help information"""
        print("\n" + "=" * 60)
        print("    📖 HELP & INFORMATION")
        print("=" * 60)
        print("\n🚀 QUICK START:")
        print("1. Use quick_extract_today() for daily extraction")
        print("2. Use quick_extract_last_7_days() for weekly extraction")
        print("3. Use run_interactive_extraction() for full control")

        print("\n📋 REQUIREMENTS:")
        print("• page_ids.json file with your ManyChat page configurations")
        print("• Chrome browser installed")
        print("• Valid ManyChat account profiles")

        print("\n⚙️ MODES:")
        print("• Headless: Faster, runs in background (no browser window)")
        print("• Windowed: Slower, shows browser (useful for debugging)")

        print("\n📊 OUTPUT:")
        print("• JSON files with extracted broadcast data")
        print("• Combined file: All pages in one file")
        print("• Performance metrics and summaries")

        print("\n🔧 TROUBLESHOOTING:")
        print("• No profiles? Run: python profiels.py")
        print("• Login issues? Use windowed mode to login manually")
        print("• No data? Check date range and page configuration")

    def check_system_status(self) -> Dict:
        """Check system status and dependencies"""
        status = {
            "profile_manager": self.profile_manager.available,
            "configuration": False,
            "chrome_driver": True,  # Assume OK, will be checked during driver creation
            "errors": [],
        }

        # Check configuration
        try:
            if self.current_config or self.config_manager.load_page_config():
                valid, errors = self.config_manager.validate_config()
                status["configuration"] = valid
                if errors:
                    status["errors"].extend([f"Config: {error}" for error in errors])
            else:
                status["errors"].append("Configuration file not found or invalid")
        except Exception as e:
            status["errors"].append(f"Configuration error: {e}")

        # Check profile manager
        if not status["profile_manager"]:
            status["errors"].append(
                "Profile manager not available (profiels.py missing)"
            )

        return status


# Backward compatibility functions
def quick_extract_today(
    profile_name: Optional[str] = None, headless: bool = True, silent: bool = False
) -> Dict:
    """Quick function to extract today's data (backward compatibility)"""
    extractor = ManyChatExtractorOOP(verbose=not silent)
    return extractor.quick_extract_today(profile_name, headless)


def quick_extract_last_7_days(
    profile_name: Optional[str] = None, headless: bool = True, silent: bool = False
) -> Dict:
    """Quick function to extract last 7 days data (backward compatibility)"""
    extractor = ManyChatExtractorOOP(verbose=not silent)
    return extractor.quick_extract_last_7_days(profile_name, headless)


def run_extraction_programmatically(
    profile_name: str = "auto",
    headless: bool = True,
    date_range_type: str = "today_only",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """Run extraction programmatically (backward compatibility)"""
    extractor = ManyChatExtractorOOP()

    if date_range_type == "custom_range" and start_date and end_date:
        return extractor.extract_with_custom_range(
            start_date,
            end_date,
            profile_name if profile_name != "auto" else None,
            headless,
        )
    elif date_range_type == "last_7_days":
        return extractor.quick_extract_last_7_days(
            profile_name if profile_name != "auto" else None, headless
        )
    else:  # Default to today_only
        return extractor.quick_extract_today(
            profile_name if profile_name != "auto" else None, headless
        )


def get_extractor_instance() -> ManyChatExtractorOOP:
    """Get a ManyChatExtractorOOP instance for advanced usage"""
    return ManyChatExtractorOOP()


def check_dependencies() -> Dict:
    """Check if all required dependencies are available"""
    extractor = ManyChatExtractorOOP(verbose=False)
    return extractor.check_system_status()


# Legacy class for backward compatibility
class ManyChatExtractor(ManyChatExtractorOOP):
    """Legacy class name for backward compatibility"""

    def run(self):
        """Main interactive menu (legacy interface)"""
        print("🚀 Welcome to ManyChat Data Extractor!")
        print("Object-Oriented Multi-Page automation with pagination support")

        while True:
            self.show_main_menu()
            choice = input("\nSelect an option (0-6): ").strip()

            if choice == "1":
                result = self.run_interactive_extraction()
                if not result["success"]:
                    print(f"[ERROR] {result['error']}")
            elif choice == "2":
                result = self.quick_extract_today()
                if result["success"]:
                    print(
                        f"✅ Quick extraction successful! {result['total_posts']} posts extracted"
                    )
                else:
                    print(f"❌ Quick extraction failed: {result['error']}")
            elif choice == "3":
                result = self.quick_extract_last_7_days()
                if result["success"]:
                    print(
                        f"✅ Last 7 days extraction successful! {result['total_posts']} posts extracted"
                    )
                else:
                    print(f"❌ Last 7 days extraction failed: {result['error']}")
            elif choice == "4":
                self.profile_management()
            elif choice == "5":
                self.show_configuration()
            elif choice == "6":
                self.show_help()
            elif choice == "0":
                print("\n👋 Thank you for using ManyChat Data Extractor!")
                print("Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select a number from 0-6.")

            # Add a pause between operations
            if choice != "0":
                input("\nPress Enter to continue...")

    def show_main_menu(self):
        """Display main menu options"""
        print("\n" + "=" * 60)
        print("    🚀 MANYCHAT DATA EXTRACTOR (OOP)")
        print("=" * 60)
        print("1. 📊 Interactive Extraction (Full Control)")
        print("2. ⚡ Quick Extraction (Today's Data)")
        print("3. 📅 Last 7 Days Extraction")
        print("4. 🔧 Profile Management")
        print("5. 📋 View Configuration")
        print("6. ❓ Help & Information")
        print("0. 🚪 Exit")
        print("=" * 60)

    def profile_management(self):
        """Handle profile management"""
        print("\n=== Profile Management ===")
        print("1. View all profiles")
        print("2. Create new profile (run profiels.py)")
        print("3. Back to main menu")

        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            self.profile_manager.list_profiles()
        elif choice == "2":
            print("\n[INFO] To create a new profile, run this command:")
            print("python profiels.py")
            print("\nThen return to this application to use the new profile.")
        elif choice == "3":
            return
        else:
            print("Invalid choice. Returning to main menu.")


def main():
    """Main function using the new class-based approach"""
    if not PROFILE_MANAGER_AVAILABLE:
        print("Error: Cannot run main application without ChromeProfileManager")
        print("Please ensure profiels.py is available in the same directory")
        return

    extractor = ManyChatExtractor()
    extractor.run()


if __name__ == "__main__":
    main()
