import os
import json
import shutil
from datetime import datetime, timezone, timedelta
import logging
import random
import time
import subprocess
import psutil
from seleniumwire import webdriver

# ManyChat timezone (UTC-4:00)
MANYCHAT_TIMEZONE = timezone(timedelta(hours=-4))
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import certifi
import ssl
import tempfile
from OpenSSL import crypto
import requests
import socket

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("spam_handler.log")],
)
# Suppress unnecessary logs
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("WDM").setLevel(logging.WARNING)
logging.getLogger("seleniumwire").setLevel(logging.WARNING)


class ChromeProfileManager:
    def __init__(self):
        # Keep ChromeProfiles directory for profile data
        self.base_profile_dir = os.path.join(os.path.expanduser("~"), "ChromeProfiles")
        # Add current directory profile storage
        self.current_dir_profiles = os.path.join(os.getcwd(), "profiles.json")
        self.profiles_file = os.path.join(self.base_profile_dir, "profiles.json")
        self.backup_dir = os.path.join(self.base_profile_dir, "backups")
        self.profiles = {}
        self.signed_in_profiles = set()
        self.logger = logging.getLogger(__name__)

        # Create necessary directories
        os.makedirs(self.base_profile_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # Set up certificate handling
        self._setup_certificates()  # Load existing profiles
        self._load_profiles()  # Fix any missing paths in existing profiles
        self.fix_missing_paths()

    def _setup_certificates(self):
        """Set up certificate handling for Selenium Wire"""
        try:
            # Create certificates directory if it doesn't exist
            self.cert_dir = os.path.join(self.base_profile_dir, "certificates")
            os.makedirs(self.cert_dir, exist_ok=True)

            # Check for ca.crt in current directory first
            current_dir_cert = os.path.join(os.getcwd(), "ca.crt")
            if os.path.exists(current_dir_cert):
                # Use the existing ca.crt from current directory
                self.ca_cert_path = current_dir_cert
                self.logger.info(
                    f"Using existing certificate from: {self.ca_cert_path}"
                )
                # For existing certificates, we don't have the key file
                self.ca_key_path = None
            else:
                # Path for the custom CA certificate in certificates directory
                self.ca_cert_path = os.path.join(self.cert_dir, "ca.crt")
                self.ca_key_path = os.path.join(self.cert_dir, "ca.key")

                # Generate CA certificate if it doesn't exist
                if not os.path.exists(self.ca_cert_path):
                    self._generate_ca_certificate()

            # Create a custom SSL context that doesn't verify certificates
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

            # Load the custom CA certificate if available
            if os.path.exists(self.ca_cert_path):
                try:
                    self.ssl_context.load_verify_locations(cafile=self.ca_cert_path)
                except Exception as cert_load_error:
                    self.logger.warning(
                        f"Could not load certificate: {cert_load_error}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to set up certificates: {e}")
            # Set fallback values
            self.ca_cert_path = None
            self.ca_key_path = None

    def _generate_ca_certificate(self):
        """Generate a CA certificate for Selenium Wire"""
        try:
            # Generate key
            key = crypto.PKey()
            key.generate_key(crypto.TYPE_RSA, 2048)

            # Generate certificate
            cert = crypto.X509()
            cert.get_subject().CN = "Selenium Wire CA"
            cert.get_subject().O = "Selenium Wire"
            cert.set_serial_number(1000)
            cert.gmtime_adj_notBefore(0)
            cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)  # Valid for 1 year
            cert.set_issuer(cert.get_subject())
            cert.set_pubkey(key)
            cert.sign(key, "sha256")

            # Save certificate and key
            with open(self.ca_cert_path, "wb") as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
            with open(self.ca_key_path, "wb") as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

            self.logger.info("Generated new CA certificate")

        except Exception as e:
            self.logger.error(f"Failed to generate CA certificate: {e}")

    def _load_profiles(self):
        """Load profiles from JSON file with enhanced backup mechanism"""
        try:
            # Try loading from current directory first
            if os.path.exists(self.current_dir_profiles):
                with open(self.current_dir_profiles, "r") as f:
                    stored_profiles = json.load(f)
            # Fall back to ChromeProfiles directory
            elif os.path.exists(self.profiles_file):
                with open(self.profiles_file, "r") as f:
                    stored_profiles = json.load(f)
            else:
                stored_profiles = {}

            # Verify and update profile paths
            for profile_name, profile_data in stored_profiles.items():
                profile_path = os.path.join(self.base_profile_dir, profile_name)
                # Update path in case directory structure changed
                profile_data["path"] = profile_path

                # If profile directory exists, load it
                if os.path.exists(profile_path):
                    self.profiles[profile_name] = profile_data
                    if profile_data.get("verified", False):
                        self.signed_in_profiles.add(profile_name)

            # Save updated paths to both locations
            self._save_profiles()

            # Create daily backup
            self._create_daily_backup()

        except Exception as e:
            self.logger.error(f"Failed to load profiles: {e}")
            self._restore_latest_backup()

    def _save_profiles(self):
        """Save profiles with backup mechanism"""
        try:
            # Add verification status to profile data
            for profile_name in self.profiles:
                self.profiles[profile_name]["verified"] = (
                    profile_name in self.signed_in_profiles
                )

            # Save to both locations
            with open(self.profiles_file, "w") as f:
                json.dump(self.profiles, f, indent=4)

            # Save copy in current directory
            with open(self.current_dir_profiles, "w") as f:
                json.dump(self.profiles, f, indent=4)

            # Create backup after successful save
            self._backup_profiles()

        except Exception as e:
            self.logger.error(f"Failed to save profiles: {e}")
            self._restore_from_backup()

    def _backup_profiles(self):
        """Create a backup of the profiles file"""
        backup_file = f"{self.profiles_file}.backup"
        try:
            if os.path.exists(self.profiles_file):
                shutil.copy2(self.profiles_file, backup_file)
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")

    def _restore_from_backup(self):
        """Restore profiles from backup file"""
        backup_file = f"{self.profiles_file}.backup"
        try:
            if os.path.exists(backup_file):
                with open(backup_file, "r") as f:
                    self.profiles = json.load(f)
                    # Restore verification status
                    self.signed_in_profiles = {
                        name
                        for name, data in self.profiles.items()
                        if data.get("verified", False)
                    }
                self.logger.info("Profiles restored from backup")
        except Exception as e:
            self.logger.error(f"Failed to restore from backup: {e}")

    def _create_daily_backup(self):
        """Create a daily backup of profiles"""
        try:
            if os.path.exists(self.profiles_file):
                timestamp = datetime.now().strftime("%Y%m%d")
                backup_file = os.path.join(
                    self.backup_dir, f"profiles_{timestamp}.json"
                )

                # Only create one backup per day
                if not os.path.exists(backup_file):
                    shutil.copy2(self.profiles_file, backup_file)

                # Keep only last 7 days of backups
                backups = sorted(os.listdir(self.backup_dir))
                if len(backups) > 7:
                    for old_backup in backups[:-7]:
                        os.remove(os.path.join(self.backup_dir, old_backup))

        except Exception as e:
            self.logger.error(f"Failed to create daily backup: {e}")

    def _restore_latest_backup(self):
        """Restore from the most recent backup"""
        try:
            if os.path.exists(self.backup_dir):
                backups = sorted(os.listdir(self.backup_dir))
                if backups:
                    latest_backup = os.path.join(self.backup_dir, backups[-1])
                    with open(latest_backup, "r") as f:
                        self.profiles = json.load(f)
                    self.signed_in_profiles = {
                        name
                        for name, data in self.profiles.items()
                        if data.get("verified", False)
                    }
                    self.logger.info(f"Restored profiles from backup: {backups[-1]}")
                    # Save restored profiles to main file
                    self._save_profiles()
        except Exception as e:
            self.logger.error(f"Failed to restore from backup: {e}")

    def verify_gmail_login(self, profile_name, email, password):
        """Verify Gmail login credentials"""
        try:
            options = webdriver.ChromeOptions()
            profile_path = self.profiles[profile_name]["path"]

            # Enhanced anti-detection options
            options.add_argument(f"user-data-dir={profile_path}")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-notifications")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Certificate and SSL related options
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--ignore-ssl-errors")
            options.add_argument("--ignore-certificate-errors-spki-list")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=VizDisplayCompositor")

            # Add user agent
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
            )

            # Disable automation flags
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            driver = webdriver.Chrome(options=options)

            # Mask webdriver
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # Add stealth js
            stealth_js = """
                const newProto = navigator.__proto__;
                delete newProto.webdriver;
                navigator.__proto__ = newProto;
            """
            driver.execute_script(stealth_js)

            try:
                # Navigate to Gmail with random delays
                driver.get("https://accounts.google.com")
                self._random_sleep(2, 4)

                # Handle email input
                email_field = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.NAME, "identifier"))
                )
                self._type_like_human(email_field, email)
                self._random_sleep(1, 2)

                next_button = driver.find_element(By.ID, "identifierNext")
                next_button.click()
                self._random_sleep(2, 4)

                # Handle password input
                password_field = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                self._type_like_human(password_field, password)
                self._random_sleep(1, 2)

                driver.find_element(By.ID, "passwordNext").click()
                self._random_sleep(3, 5)

                # Handle security challenges
                if "challenge" in driver.current_url:
                    self.logger.warning("Security challenge detected")
                    print("\n=== Security Challenge Detected ===")
                    print("1. Please complete the verification in the browser")
                    print("2. You have 120 seconds to complete it")
                    print("3. The browser will close automatically after completion")

                    # Wait longer for manual verification
                    time.sleep(120)

                # Check for successful login
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div[data-ogsr-up]")
                        )
                    )
                    self.signed_in_profiles.add(profile_name)
                    return True
                except:
                    self.logger.error("Failed to detect successful login")
                    return False

            finally:
                driver.quit()

        except Exception as e:
            self.logger.error(f"Failed to verify Gmail login: {str(e)}")
            return False

    def _random_sleep(self, min_seconds, max_seconds):
        """Add random delay between actions"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def _type_like_human(self, element, text):
        """Simulate human-like typing"""
        for character in text:
            element.send_keys(character)
            time.sleep(random.uniform(0.1, 0.3))

    def add_profile(self, profile_name, email, password, proxy_details=None):
        """Add a new Chrome profile with manual Gmail sign-in"""
        if not all([profile_name, email, password]):
            self.logger.error("Profile name, email, and password are required")
            return False

        try:
            profile_path = os.path.join(self.base_profile_dir, profile_name)
            if profile_name in self.profiles:
                self.logger.warning(f"Profile {profile_name} already exists")
                return False

            os.makedirs(profile_path, exist_ok=True)

            # Use provided proxy details or ask for them
            if proxy_details is None:
                # Ask for proxy details
                use_proxy = (
                    input(
                        "\nDo you want to use a proxy for this profile? (y/n): "
                    ).lower()
                    == "y"
                )

                if use_proxy:
                    print("\n=== Proxy Configuration ===")
                    print("1. HTTP/HTTPS")
                    print("2. SOCKS4")
                    print("3. SOCKS5")
                    proxy_type = input("Select proxy type (1-3): ")

                    proxy_ip = input("Enter proxy IP: ")
                    proxy_port = input("Enter proxy port: ")
                    proxy_username = input(
                        "Enter proxy username (leave empty if none): "
                    )
                    proxy_password = input(
                        "Enter proxy password (leave empty if none): "
                    )

                    # Map proxy type to protocol
                    proxy_protocol = {"1": "http", "2": "socks4", "3": "socks5"}.get(
                        proxy_type, "http"
                    )

                    proxy_details = {
                        "type": proxy_protocol,
                        "ip": proxy_ip,
                        "port": proxy_port,
                        "username": proxy_username if proxy_username else None,
                        "password": proxy_password if proxy_password else None,
                    }

            # Enhanced Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-data-dir={profile_path}")
            options.add_argument("--start-maximized")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-notifications")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Certificate and SSL related options
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--ignore-ssl-errors")
            options.add_argument("--ignore-certificate-errors-spki-list")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=VizDisplayCompositor")

            # GPU and virtualization fixes
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-gpu-sandbox")
            options.add_argument("--disable-gpu-compositing")
            options.add_argument("--disable-gpu-rasterization")
            options.add_argument("--disable-gpu-driver-bug-workarounds")
            options.add_argument("--disable-gpu-program-cache")
            options.add_argument("--disable-gpu-shader-disk-cache")
            options.add_argument("--disable-gpu-vsync")
            options.add_argument("--disable-accelerated-2d-canvas")
            options.add_argument("--disable-accelerated-jpeg-decoding")
            options.add_argument("--disable-accelerated-mjpeg-decode")
            options.add_argument("--disable-accelerated-video-decode")
            options.add_argument("--disable-accelerated-video")
            options.add_argument("--disable-accelerated-video-encode")
            options.add_argument("--disable-accelerated-webgl")
            options.add_argument("--disable-accelerated-webgl2")
            options.add_argument("--disable-accelerated-webgl2-compute")
            options.add_argument("--disable-accelerated-webgl2-compute-context")
            options.add_argument("--disable-accelerated-webgl2-compute-context-2")
            options.add_argument("--disable-accelerated-webgl2-compute-context-3")
            options.add_argument("--disable-accelerated-webgl2-compute-context-4")
            options.add_argument("--disable-accelerated-webgl2-compute-context-5")
            options.add_argument("--disable-accelerated-webgl2-compute-context-6")
            options.add_argument("--disable-accelerated-webgl2-compute-context-7")
            options.add_argument("--disable-accelerated-webgl2-compute-context-8")
            options.add_argument("--disable-accelerated-webgl2-compute-context-9")
            options.add_argument("--disable-accelerated-webgl2-compute-context-10")

            # Additional performance options
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-breakpad")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-features=TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument(
                "--enable-features=NetworkService,NetworkServiceInProcess"
            )
            options.add_argument("--force-color-profile=srgb")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--mute-audio")

            # Experimental options
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging", "enable-automation"]
            )
            options.add_experimental_option("useAutomationExtension", False)

            # Add preferences to disable GPU
            prefs = {
                "hardware_acceleration_mode_enabled": False,
                "gpu": {
                    "enabled": False,
                    "disabled": True,
                    "disabled_extensions": True,
                    "disabled_software_rasterizer": True,
                    "disabled_webgl": True,
                    "disabled_webgl2": True,
                    "disabled_webgl2_compute": True,
                    "disabled_webgl2_compute_context": True,
                    "disabled_webgl2_compute_context_2": True,
                    "disabled_webgl2_compute_context_3": True,
                    "disabled_webgl2_compute_context_4": True,
                    "disabled_webgl2_compute_context_5": True,
                    "disabled_webgl2_compute_context_6": True,
                    "disabled_webgl2_compute_context_7": True,
                    "disabled_webgl2_compute_context_8": True,
                    "disabled_webgl2_compute_context_9": True,
                    "disabled_webgl2_compute_context_10": True,
                },
            }
            options.add_experimental_option("prefs", prefs)

            # Configure Selenium Wire options with our custom certificates
            seleniumwire_options = {
                "verify_ssl": False,
                "connection_timeout": 30,
                "read_timeout": 30,
                "retry_connection": True,
                "max_retries": 3,
                "suppress_connection_errors": True,
                "disable_encoding": True,
            }

            # Only add certificate if it exists
            if self.ca_cert_path and os.path.exists(self.ca_cert_path):
                seleniumwire_options["ca_cert"] = self.ca_cert_path

            # Only add ca_key if it exists (for generated certificates)
            if (
                hasattr(self, "ca_key_path")
                and self.ca_key_path
                and os.path.exists(self.ca_key_path)
            ):
                seleniumwire_options["ca_key"] = self.ca_key_path

            # Add proxy if specified
            if proxy_details:
                try:
                    # Format proxy URL with authentication
                    if proxy_details["username"] and proxy_details["password"]:
                        proxy_url = f"{proxy_details['type']}://{proxy_details['username']}:{proxy_details['password']}@{proxy_details['ip']}:{proxy_details['port']}"
                    else:
                        proxy_url = f"{proxy_details['type']}://{proxy_details['ip']}:{proxy_details['port']}"

                    # Add proxy settings
                    seleniumwire_options["proxy"] = {
                        "http": proxy_url,
                        "https": proxy_url,
                    }

                    # Add proxy settings to Chrome options
                    options.add_argument(f"--proxy-server={proxy_url}")

                    # Add additional options to handle connection issues
                    options.add_argument("--dns-prefetch-disable")
                    options.add_argument("--disable-gpu")
                    options.add_argument("--disable-software-rasterizer")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--no-first-run")
                    options.add_argument("--no-default-browser-check")
                    options.add_argument("--disable-background-networking")
                    options.add_argument("--disable-background-timer-throttling")
                    options.add_argument("--disable-backgrounding-occluded-windows")
                    options.add_argument("--disable-breakpad")
                    options.add_argument(
                        "--disable-component-extensions-with-background-pages"
                    )
                    options.add_argument("--disable-extensions")
                    options.add_argument("--disable-features=TranslateUI")
                    options.add_argument("--disable-ipc-flooding-protection")
                    options.add_argument("--disable-renderer-backgrounding")
                    options.add_argument(
                        "--enable-features=NetworkService,NetworkServiceInProcess"
                    )
                    options.add_argument("--force-color-profile=srgb")
                    options.add_argument("--metrics-recording-only")
                    options.add_argument("--mute-audio")

                except Exception as e:
                    self.logger.error(f"Failed to configure proxy: {e}")
                    return False

            # Kill any existing Chrome sessions before opening new one
            self.kill_existing_chrome_sessions()

            # Initialize the driver with our custom options
            driver = webdriver.Chrome(
                options=options, seleniumwire_options=seleniumwire_options
            )

            try:
                # Open Gmail for manual sign-in
                driver.get("https://gmail.com")
                print(f"\n🌐 Opening Gmail for profile '{profile_name}'...")
                print("📝 Please sign in to Gmail manually in the browser window.")

                # Show login verification prompt immediately
                is_logged_in = self.prompt_login_verification()

                if is_logged_in:
                    # Store profile information only if user confirms login
                    self.profiles[profile_name] = {
                        "email": email,
                        "password": password,
                        "path": profile_path,
                        "proxy": proxy_details,
                        "created_at": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                        "status": "active",
                        "verified": True,
                    }

                    # Add to signed in profiles
                    self.signed_in_profiles.add(profile_name)

                    # Save profiles
                    self._save_profiles()

                    self.logger.info(
                        f"Profile {profile_name} created and verified successfully"
                    )
                    print(f"✅ Profile '{profile_name}' saved successfully!")
                    return True
                else:
                    # User is not logged in, don't save the profile
                    self.logger.info(
                        f"Profile {profile_name} not saved - user not logged in"
                    )
                    print(f"❌ Profile '{profile_name}' not saved (not logged in)")

                    # Schedule cleanup of profile directory after browser closes
                    self._scheduled_cleanup_path = profile_path
                    return False

            finally:
                # Always close the browser
                try:
                    driver.quit()
                    print("🔒 Browser closed")

                    # Clean up profile directory if it was scheduled for cleanup
                    if hasattr(self, "_scheduled_cleanup_path") and os.path.exists(
                        self._scheduled_cleanup_path
                    ):
                        try:
                            # Wait a moment for Chrome to fully release files
                            time.sleep(2)
                            shutil.rmtree(self._scheduled_cleanup_path)
                            self.logger.info(
                                f"Cleaned up profile directory: {self._scheduled_cleanup_path}"
                            )
                            print("🧹 Profile directory cleaned up")
                            delattr(self, "_scheduled_cleanup_path")
                        except Exception as e:
                            self.logger.error(
                                f"Failed to cleanup profile directory: {e}"
                            )
                            print(
                                f"⚠️ Warning: Could not clean up profile directory: {e}"
                            )

                except Exception as e:
                    self.logger.error(f"Error closing browser: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to add profile {profile_name}: {e}")
            return False

    def list_profiles(self):
        """Return a list of profile names"""
        return list(self.profiles.keys())

    def get_profile(self, profile_name):
        """Get profile information by name"""
        return self.profiles.get(profile_name)

    def remove_profile(self, profile_name):
        """Remove a profile"""
        try:
            if profile_name not in self.profiles:
                self.logger.warning(f"Profile {profile_name} does not exist")
                return False

            # Kill all Chrome processes before attempting to remove profile
            print(f"🔄 Preparing to remove profile '{profile_name}'...")
            self.kill_existing_chrome_sessions()

            # Wait a moment for Chrome to fully release files
            time.sleep(3)

            profile_path = self.profiles[profile_name]["path"]
            # Remove profile directory
            if os.path.exists(profile_path):
                try:
                    shutil.rmtree(profile_path)
                    print(f"🗂️ Profile directory removed: {profile_path}")
                except Exception as e:
                    self.logger.error(f"Failed to remove profile directory: {e}")
                    print(
                        f"⚠️ Warning: Could not remove profile directory. Trying force removal..."
                    )

                    # Try force removal with extended wait
                    time.sleep(2)
                    try:
                        shutil.rmtree(profile_path)
                        print(f"✅ Profile directory force-removed: {profile_path}")
                    except Exception as e2:
                        self.logger.error(f"Force removal also failed: {e2}")
                        print(
                            f"❌ Could not remove profile directory. Please close all Chrome windows manually and try again."
                        )
                        return False

            # Remove from profiles dictionary
            del self.profiles[profile_name]
            self.signed_in_profiles.discard(profile_name)
            self._save_profiles()
            self.logger.info(f"Profile {profile_name} removed successfully")
            print(f"✅ Profile '{profile_name}' removed successfully!")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove profile {profile_name}: {e}")
            print(f"❌ Failed to remove profile '{profile_name}': {e}")
            return False

    def remove_profiles(self, profile_names):
        """Remove multiple profiles"""
        if not profile_names:
            print("❌ No profiles selected for removal")
            return False

        print(f"🔄 Preparing to remove {len(profile_names)} profile(s)...")
        print("📋 Profiles to remove:", ", ".join(profile_names))

        # Kill all Chrome processes once before removing any profiles
        print("🛑 Closing all Chrome sessions to ensure clean removal...")
        self.kill_existing_chrome_sessions()

        # Wait for Chrome to fully release all files
        time.sleep(3)

        success = True
        removed_count = 0
        failed_profiles = []

        for profile_name in profile_names:
            print(f"\n🗑️ Removing profile: {profile_name}")
            if self.remove_profile_without_chrome_kill(profile_name):
                removed_count += 1
                print(f"✅ Successfully removed: {profile_name}")
            else:
                success = False
                failed_profiles.append(profile_name)
                print(f"❌ Failed to remove: {profile_name}")

        # Summary
        print(f"\n📊 Removal Summary:")
        print(f"✅ Successfully removed: {removed_count}/{len(profile_names)} profiles")
        if failed_profiles:
            print(f"❌ Failed to remove: {', '.join(failed_profiles)}")

        return success

    def remove_profile_without_chrome_kill(self, profile_name):
        """Remove a profile without killing Chrome (used by remove_profiles)"""
        try:
            if profile_name not in self.profiles:
                self.logger.warning(f"Profile {profile_name} does not exist")
                return False

            profile_path = self.profiles[profile_name]["path"]
            # Remove profile directory
            if os.path.exists(profile_path):
                try:
                    shutil.rmtree(profile_path)
                except Exception as e:
                    self.logger.error(f"Failed to remove profile directory: {e}")
                    # Try one more time with a small delay
                    time.sleep(1)
                    try:
                        shutil.rmtree(profile_path)
                    except Exception as e2:
                        self.logger.error(f"Second attempt also failed: {e2}")
                        return False

            # Remove from profiles dictionary
            del self.profiles[profile_name]
            self.signed_in_profiles.discard(profile_name)
            self._save_profiles()
            self.logger.info(f"Profile {profile_name} removed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove profile {profile_name}: {e}")
            return False

    def export_profiles(self, export_path):
        """Export all profiles to a specified JSON file"""
        try:
            # Add verification status to profile data
            for profile_name in self.profiles:
                self.profiles[profile_name]["verified"] = (
                    profile_name in self.signed_in_profiles
                )

            # Create directory if it doesn't exist
            export_dir = os.path.dirname(export_path)
            if export_dir and not os.path.exists(export_dir):
                os.makedirs(export_dir, exist_ok=True)

            # Export profiles to the specified file
            with open(export_path, "w") as f:
                json.dump(self.profiles, f, indent=4)

            self.logger.info(f"Profiles exported successfully to {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export profiles: {e}")
            return False

    def import_profiles(self, import_path):
        """Import profiles from a specified JSON file"""
        try:
            if not os.path.exists(import_path):
                self.logger.error(f"Import file {import_path} does not exist")
                return False

            # Load profiles from the import file
            with open(import_path, "r") as f:
                imported_profiles = json.load(f)

            # Backup current profiles before import
            self._backup_profiles()

            # Update paths for imported profiles
            for profile_name, profile_data in imported_profiles.items():
                profile_path = os.path.join(self.base_profile_dir, profile_name)
                profile_data["path"] = profile_path

                # Create profile directory if it doesn't exist
                if not os.path.exists(profile_path):
                    os.makedirs(profile_path, exist_ok=True)

                # Add to profiles dictionary
                self.profiles[profile_name] = profile_data

                # Update signed_in_profiles set
                if profile_data.get("verified", False):
                    self.signed_in_profiles.add(profile_name)

            # Save updated profiles
            self._save_profiles()

            self.logger.info(f"Profiles imported successfully from {import_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to import profiles: {e}")
            self._restore_from_backup()
            return False

    def fix_missing_paths(self):
        """Fix missing paths in existing profiles"""
        try:
            updated = False
            for profile_name, profile_data in self.profiles.items():
                if "path" not in profile_data or not profile_data["path"]:
                    profile_path = os.path.join(self.base_profile_dir, profile_name)
                    profile_data["path"] = profile_path
                    updated = True
                    self.logger.info(f"Fixed missing path for profile: {profile_name}")

            if updated:
                self._save_profiles()
                self.logger.info("Fixed missing paths and saved profiles")
                return True
            else:
                self.logger.info("All profiles already have valid paths")
                return True

        except Exception as e:
            self.logger.error(f"Failed to fix missing paths: {e}")
            return False

    def verify_all_profiles(self):
        """Verify all profiles by checking Gmail login status"""
        print("\nVerifying all profiles...")
        self.signed_in_profiles.clear()  # Reset verification status

        for profile_name, profile_info in self.profiles.items():
            print(f"\nChecking {profile_name}...")
            try:
                options = webdriver.ChromeOptions()
                profile_path = profile_info["path"]
                options.add_argument(f"user-data-dir={profile_path}")

                driver = webdriver.Chrome(options=options)
                driver.get("https://accounts.google.com")

                # Wait for either the email input field (not logged in) or the account info (logged in)
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                "div[data-ogsr-up], input[name='identifier']",
                            )
                        )
                    )

                    # Check if logged in by looking for the account info
                    if (
                        len(driver.find_elements(By.CSS_SELECTOR, "div[data-ogsr-up]"))
                        > 0
                    ):
                        self.signed_in_profiles.add(profile_name)
                        print(f"✓ {profile_name} is verified")
                    else:
                        print(f"✗ {profile_name} is not verified")

                except Exception as e:
                    print(f"✗ {profile_name} verification failed: {str(e)}")

            except Exception as e:
                self.logger.error(f"Failed to verify {profile_name}: {e}")
                print(f"✗ Error verifying {profile_name}")

            finally:
                if "driver" in locals():
                    driver.quit()

        print("\nVerification complete!")

    def open_profile(self, profile_name, force_no_proxy=False):
        """Open a Chrome profile with Gmail"""
        if profile_name not in self.profiles:
            self.logger.error(f"Profile {profile_name} not found")
            return False

        try:
            profile_path = os.path.join(self.base_profile_dir, profile_name)
            if not os.path.exists(profile_path):
                self.logger.error(f"Profile directory {profile_path} not found")
                return False

            # Check proxy configuration and test connectivity
            proxy_details = self.profiles[profile_name].get("proxy")
            use_proxy = False

            if proxy_details and not force_no_proxy:
                print(
                    f"\nTesting proxy connection for {proxy_details['ip']}:{proxy_details['port']}..."
                )
                if self.test_proxy_connection(proxy_details):
                    use_proxy = True
                    self.logger.info("Proxy connection successful, using proxy")
                else:
                    print("❌ Proxy connection failed!")
                    choice = input(
                        "Choose an option:\n1. Continue without proxy\n2. Try anyway (may fail)\n3. Cancel\nEnter choice (1-3): "
                    ).strip()

                    if choice == "1":
                        print("✅ Continuing without proxy...")
                        use_proxy = False
                    elif choice == "2":
                        print("⚠️ Attempting to use proxy despite test failure...")
                        use_proxy = True
                    else:
                        print("❌ Operation cancelled")
                        return False
            elif force_no_proxy:
                print("🚫 Proxy disabled by force_no_proxy flag")
                use_proxy = False

            # Enhanced Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-data-dir={profile_path}")
            options.add_argument("--start-maximized")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-notifications")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Certificate and SSL related options
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--ignore-ssl-errors")
            options.add_argument("--ignore-certificate-errors-spki-list")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=VizDisplayCompositor")

            # GPU and virtualization fixes
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-gpu-sandbox")
            options.add_argument("--disable-gpu-compositing")
            options.add_argument("--disable-gpu-rasterization")
            options.add_argument("--disable-gpu-driver-bug-workarounds")
            options.add_argument("--disable-gpu-program-cache")
            options.add_argument("--disable-gpu-shader-disk-cache")
            options.add_argument("--disable-gpu-vsync")
            options.add_argument("--disable-accelerated-2d-canvas")
            options.add_argument("--disable-accelerated-jpeg-decoding")
            options.add_argument("--disable-accelerated-mjpeg-decode")
            options.add_argument("--disable-accelerated-video-decode")
            options.add_argument("--disable-accelerated-video")
            options.add_argument("--disable-accelerated-video-encode")
            options.add_argument("--disable-accelerated-webgl")
            options.add_argument("--disable-accelerated-webgl2")
            options.add_argument("--disable-accelerated-webgl2-compute")
            options.add_argument("--disable-accelerated-webgl2-compute-context")
            options.add_argument("--disable-accelerated-webgl2-compute-context-2")
            options.add_argument("--disable-accelerated-webgl2-compute-context-3")
            options.add_argument("--disable-accelerated-webgl2-compute-context-4")
            options.add_argument("--disable-accelerated-webgl2-compute-context-5")
            options.add_argument("--disable-accelerated-webgl2-compute-context-6")
            options.add_argument("--disable-accelerated-webgl2-compute-context-7")
            options.add_argument("--disable-accelerated-webgl2-compute-context-8")
            options.add_argument("--disable-accelerated-webgl2-compute-context-9")
            options.add_argument("--disable-accelerated-webgl2-compute-context-10")

            # Additional performance options
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-breakpad")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-features=TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument(
                "--enable-features=NetworkService,NetworkServiceInProcess"
            )
            options.add_argument("--force-color-profile=srgb")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--mute-audio")

            # Experimental options
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging", "enable-automation"]
            )
            options.add_experimental_option("useAutomationExtension", False)

            # Add preferences to disable GPU
            prefs = {
                "hardware_acceleration_mode_enabled": False,
                "gpu": {
                    "enabled": False,
                    "disabled": True,
                    "disabled_extensions": True,
                    "disabled_software_rasterizer": True,
                    "disabled_webgl": True,
                    "disabled_webgl2": True,
                    "disabled_webgl2_compute": True,
                    "disabled_webgl2_compute_context": True,
                    "disabled_webgl2_compute_context_2": True,
                    "disabled_webgl2_compute_context_3": True,
                    "disabled_webgl2_compute_context_4": True,
                    "disabled_webgl2_compute_context_5": True,
                    "disabled_webgl2_compute_context_6": True,
                    "disabled_webgl2_compute_context_7": True,
                    "disabled_webgl2_compute_context_8": True,
                    "disabled_webgl2_compute_context_9": True,
                    "disabled_webgl2_compute_context_10": True,
                },
            }
            options.add_experimental_option("prefs", prefs)

            # Configure Selenium Wire options with our custom certificates
            seleniumwire_options = {
                "verify_ssl": False,
                "connection_timeout": 30,
                "read_timeout": 30,
                "retry_connection": True,
                "max_retries": 3,
                "suppress_connection_errors": True,
                "disable_encoding": True,
            }

            # Only add certificate if it exists
            if self.ca_cert_path and os.path.exists(self.ca_cert_path):
                seleniumwire_options["ca_cert"] = self.ca_cert_path

            # Only add ca_key if it exists (for generated certificates)
            if (
                hasattr(self, "ca_key_path")
                and self.ca_key_path
                and os.path.exists(self.ca_key_path)
            ):
                seleniumwire_options["ca_key"] = self.ca_key_path

            # Add proxy if configured and proxy test passed
            if proxy_details and use_proxy:
                try:
                    # Format proxy URL with authentication
                    if proxy_details["username"] and proxy_details["password"]:
                        proxy_url = f"{proxy_details['type']}://{proxy_details['username']}:{proxy_details['password']}@{proxy_details['ip']}:{proxy_details['port']}"
                    else:
                        proxy_url = f"{proxy_details['type']}://{proxy_details['ip']}:{proxy_details['port']}"

                    # Add proxy settings
                    seleniumwire_options["proxy"] = {
                        "http": proxy_url,
                        "https": proxy_url,
                    }

                    # Add proxy settings to Chrome options
                    options.add_argument(f"--proxy-server={proxy_url}")

                    self.logger.info(
                        f"Using proxy: {proxy_details['ip']}:{proxy_details['port']}"
                    )

                except Exception as e:
                    self.logger.error(f"Failed to configure proxy: {e}")
                    return False
            else:
                if proxy_details:
                    self.logger.info(
                        "Proxy configured but not using due to connection issues"
                    )
                else:
                    self.logger.info("No proxy configured for this profile")

            # Kill any existing Chrome sessions before opening
            self.kill_existing_chrome_sessions()

            # Initialize the driver with our custom options
            driver = webdriver.Chrome(
                options=options, seleniumwire_options=seleniumwire_options
            )

            try:
                # Update last used timestamp
                self.profiles[profile_name]["last_used"] = datetime.now().isoformat()
                self._save_profiles()

                # Open Gmail
                driver.get("https://gmail.com")

                print(f"\n🌐 Profile '{profile_name}' is now open.")
                print("📝 Please complete any necessary actions in the browser.")
                print(
                    "⌨️ Type 'quit' or 'exit' to close the browser and return to the main menu."
                )

                while True:
                    user_input = input().lower().strip()
                    if user_input in ["quit", "exit"]:
                        print("🔒 Closing browser...")
                        break

                return True

            finally:
                # Always close the browser
                try:
                    driver.quit()
                    print("✅ Browser closed successfully")
                except Exception as e:
                    self.logger.error(f"Error closing browser: {e}")

        except Exception as e:
            self.logger.error(f"Failed to open profile {profile_name}: {e}")
            return False

    def test_proxy_connection(self, proxy_details):
        """Test if proxy is working before using it"""
        if not proxy_details:
            return True

        try:
            # Format proxy URL
            if proxy_details["username"] and proxy_details["password"]:
                proxy_url = f"{proxy_details['type']}://{proxy_details['username']}:{proxy_details['password']}@{proxy_details['ip']}:{proxy_details['port']}"
            else:
                proxy_url = f"{proxy_details['type']}://{proxy_details['ip']}:{proxy_details['port']}"

            # Test with a simple HTTP request
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

            # Try to connect to a simple endpoint with short timeout
            response = requests.get(
                "http://httpbin.org/ip", proxies=proxies, timeout=10, verify=False
            )

            if response.status_code == 200:
                self.logger.info(
                    f"Proxy {proxy_details['ip']}:{proxy_details['port']} is working"
                )
                return True
            else:
                self.logger.warning(
                    f"Proxy returned status code: {response.status_code}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Proxy connection test failed: {e}")
            return False

    def remove_proxy_from_profile(self, profile_name):
        """Remove proxy configuration from a profile"""
        if profile_name not in self.profiles:
            self.logger.error(f"Profile {profile_name} not found")
            return False

        try:
            if "proxy" in self.profiles[profile_name]:
                del self.profiles[profile_name]["proxy"]
                self._save_profiles()
                self.logger.info(
                    f"Proxy configuration removed from profile {profile_name}"
                )
                return True
            else:
                self.logger.info(
                    f"No proxy configuration found for profile {profile_name}"
                )
                return True
        except Exception as e:
            self.logger.error(
                f"Failed to remove proxy from profile {profile_name}: {e}"
            )
            return False

    def update_proxy_for_profile(self, profile_name, proxy_details):
        """Update proxy configuration for a profile"""
        if profile_name not in self.profiles:
            self.logger.error(f"Profile {profile_name} not found")
            return False

        try:
            self.profiles[profile_name]["proxy"] = proxy_details
            self._save_profiles()
            self.logger.info(f"Proxy configuration updated for profile {profile_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update proxy for profile {profile_name}: {e}")
            return False

    def kill_existing_chrome_sessions(self):
        """Kill all existing Chrome browser sessions"""
        try:
            chrome_processes = []
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    if proc.info["name"] and "chrome" in proc.info["name"].lower():
                        chrome_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if chrome_processes:
                self.logger.info(
                    f"Found {len(chrome_processes)} Chrome processes. Terminating..."
                )
                print(f"🔄 Closing {len(chrome_processes)} existing Chrome sessions...")

                # First try graceful termination
                for proc in chrome_processes:
                    try:
                        proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Wait a bit for graceful termination
                time.sleep(2)

                # Force kill any remaining processes
                for proc in chrome_processes:
                    try:
                        if proc.is_running():
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Wait for processes to fully terminate
                time.sleep(1)
                self.logger.info("Chrome processes terminated successfully")
                print("✅ All Chrome sessions closed")
            else:
                self.logger.info("No existing Chrome processes found")
                print("ℹ️ No existing Chrome sessions to close")

        except Exception as e:
            self.logger.error(f"Failed to kill Chrome processes: {e}")
            print(f"⚠️ Warning: Could not close all Chrome sessions: {e}")

    def prompt_login_verification(self):
        """Prompt user to verify if they are logged into Gmail"""
        while True:
            try:
                print("\n" + "=" * 50)
                print("📧 GMAIL LOGIN VERIFICATION")
                print("=" * 50)
                print("🔍 Check the browser window:")
                print("• If you see Gmail inbox/interface: Choose option 1")
                print("• If you see login page/errors: Choose option 2")
                print("=" * 50)
                print("Are you successfully logged into Gmail?")
                print("1. Yes - I'm logged in (save profile)")
                print("2. No - I'm not logged in (don't save)")
                print("=" * 50)

                choice = input("👆 Enter your choice (1 or 2): ").strip()

                if choice == "1":
                    print("✅ Profile will be saved as logged in")
                    return True
                elif choice == "2":
                    print("❌ Profile will not be saved")
                    return False
                else:
                    print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

            except KeyboardInterrupt:
                print("\n❌ Operation cancelled by user")
                return False
            except Exception as e:
                self.logger.error(f"Error in login verification prompt: {e}")
                return False

    def get_profile_stats(self):
        """Get profile statistics"""
        total = len(self.profiles)
        verified = len(self.signed_in_profiles)
        unverified = total - verified
        return {"total": total, "verified": verified, "unverified": unverified}

    def get_verified_profiles(self):
        """Get list of verified profiles"""
        return [
            name for name in self.profiles.keys() if name in self.signed_in_profiles
        ]

    def get_unverified_profiles(self):
        """Get list of unverified profiles"""
        return [
            name for name in self.profiles.keys() if name not in self.signed_in_profiles
        ]

    def validate_and_get_profile_name(self):
        """Get and validate profile name with edit option"""
        while True:
            profile_name = input("Enter profile name: ").strip()

            if not profile_name:
                print("❌ Profile name cannot be empty.")
                continue

            if profile_name in self.profiles:
                print(f"❌ Profile '{profile_name}' already exists.")
                continue

            # Check for invalid characters
            invalid_chars = '<>:"/\\|?*'
            if any(char in profile_name for char in invalid_chars):
                print(
                    f"❌ Profile name cannot contain these characters: {invalid_chars}"
                )
                continue

            # Show confirmation
            print(f"\n📝 Profile name: '{profile_name}'")
            confirm = input("Is this correct? (y/n/edit): ").lower().strip()

            if confirm == "y":
                return profile_name
            elif confirm == "edit":
                continue
            elif confirm == "n":
                return None
            else:
                print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

    def validate_and_get_email(self):
        """Get and validate email with edit option"""
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        while True:
            email = input("Enter Gmail address: ").strip()

            if not email:
                print("❌ Email cannot be empty.")
                continue

            if not re.match(email_pattern, email):
                print("❌ Please enter a valid email address (e.g., user@gmail.com)")
                continue

            if not email.endswith("@gmail.com"):
                print("⚠️ Warning: This doesn't appear to be a Gmail address.")
                proceed = input("Continue anyway? (y/n): ").lower().strip()
                if proceed != "y":
                    continue

            # Show confirmation
            print(f"\n📧 Email: '{email}'")
            confirm = input("Is this correct? (y/n/edit): ").lower().strip()

            if confirm == "y":
                return email
            elif confirm == "edit":
                continue
            elif confirm == "n":
                return None
            else:
                print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

    def validate_and_get_password(self):
        """Get and validate password with edit option"""

        while True:
            print("\n🔒 Password Requirements:")
            print("  • At least 8 characters long")
            print("  • Should contain letters and numbers")

            # Use regular input (visible password)
            password = input("Enter password: ").strip()

            if not password:
                print("❌ Password cannot be empty.")
                continue

            if len(password) < 8:
                print("❌ Password must be at least 8 characters long.")
                continue

            # Show visible confirmation
            print(f"\n🔒 Password: '{password}' (length: {len(password)})")
            confirm = input("Is this correct? (y/n/edit): ").lower().strip()

            if confirm == "y":
                return password
            elif confirm == "edit":
                continue
            elif confirm == "n":
                return None
            else:
                print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

    def validate_and_get_proxy_details(self):
        """Get and validate proxy details with comprehensive edit options"""
        proxy_details = {}

        # Ask if user wants proxy
        while True:
            use_proxy = (
                input("\nDo you want to use a proxy for this profile? (y/n): ")
                .lower()
                .strip()
            )
            if use_proxy in ["y", "n"]:
                break
            print("⚠️ Please enter 'y' for yes or 'n' for no")

        if use_proxy == "n":
            return None

        print("\n=== Proxy Configuration ===")

        # Get proxy type
        while True:
            print("\n🌐 Select proxy type:")
            print("1. HTTP/HTTPS")
            print("2. SOCKS4")
            print("3. SOCKS5")

            proxy_type = input("Select proxy type (1-3): ").strip()
            if proxy_type in ["1", "2", "3"]:
                proxy_protocol = {"1": "http", "2": "socks4", "3": "socks5"}[proxy_type]
                break
            print("❌ Please select 1, 2, or 3")

        # Get proxy IP
        proxy_ip = self.validate_and_get_proxy_ip()
        if proxy_ip is None:
            return None

        # Get proxy port
        proxy_port = self.validate_and_get_proxy_port()
        if proxy_port is None:
            return None

        # Get proxy credentials
        proxy_username, proxy_password = self.validate_and_get_proxy_credentials()

        proxy_details = {
            "type": proxy_protocol,
            "ip": proxy_ip,
            "port": proxy_port,
            "username": proxy_username,
            "password": proxy_password,
        }

        # Final confirmation
        return self.confirm_proxy_details(proxy_details)

    def validate_and_get_proxy_ip(self):
        """Validate and get proxy IP address"""
        import re

        ip_pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"

        while True:
            proxy_ip = input("Enter proxy IP address: ").strip()

            if not proxy_ip:
                print("❌ Proxy IP cannot be empty.")
                continue

            # Check if it's a valid IP address
            if re.match(ip_pattern, proxy_ip):
                # Show confirmation
                print(f"\n🌐 Proxy IP: '{proxy_ip}'")
                confirm = input("Is this correct? (y/n/edit): ").lower().strip()

                if confirm == "y":
                    return proxy_ip
                elif confirm == "edit":
                    continue
                elif confirm == "n":
                    return None
                else:
                    print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")
            else:
                # Could be a hostname/domain
                if "." in proxy_ip and not " " in proxy_ip:
                    print(f"🌐 Using hostname/domain: '{proxy_ip}'")
                    confirm = input("Is this correct? (y/n/edit): ").lower().strip()

                    if confirm == "y":
                        return proxy_ip
                    elif confirm == "edit":
                        continue
                    elif confirm == "n":
                        return None
                    else:
                        print(
                            "⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change"
                        )
                else:
                    print(
                        "❌ Please enter a valid IP address (e.g., 192.168.1.1) or hostname"
                    )

    def validate_and_get_proxy_port(self):
        """Validate and get proxy port"""
        while True:
            proxy_port = input("Enter proxy port (1-65535): ").strip()

            if not proxy_port:
                print("❌ Proxy port cannot be empty.")
                continue

            try:
                port_num = int(proxy_port)
                if 1 <= port_num <= 65535:
                    # Show confirmation
                    print(f"\n🔌 Proxy port: '{proxy_port}'")
                    confirm = input("Is this correct? (y/n/edit): ").lower().strip()

                    if confirm == "y":
                        return proxy_port
                    elif confirm == "edit":
                        continue
                    elif confirm == "n":
                        return None
                    else:
                        print(
                            "⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change"
                        )
                else:
                    print("❌ Port must be between 1 and 65535")
            except ValueError:
                print("❌ Please enter a valid number")

    def validate_and_get_proxy_credentials(self):
        """Get and validate proxy username and password"""
        print("\n🔐 Proxy Authentication (leave empty if not required)")

        # Get username
        while True:
            proxy_username = input(
                "Enter proxy username (or press Enter to skip): "
            ).strip()

            if not proxy_username:
                print("ℹ️ No username provided (will use proxy without authentication)")
                break

            print(f"\n👤 Proxy username: '{proxy_username}'")
            confirm = input("Is this correct? (y/n/edit): ").lower().strip()

            if confirm == "y":
                break
            elif confirm == "edit":
                continue
            elif confirm == "n":
                proxy_username = None
                break
            else:
                print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

        # Get password only if username is provided
        proxy_password = None
        if proxy_username:
            while True:
                proxy_password = input("Enter proxy password: ").strip()

                if not proxy_password:
                    print("ℹ️ No password provided")
                    break

                print(
                    f"\n🔒 Proxy password: '{proxy_password}' (length: {len(proxy_password)})"
                )
                confirm = input("Is this correct? (y/n/edit): ").lower().strip()

                if confirm == "y":
                    break
                elif confirm == "edit":
                    continue
                elif confirm == "n":
                    proxy_password = None
                    break
                else:
                    print("⚠️ Please enter 'y' for yes, 'n' for no, or 'edit' to change")

        return proxy_username, proxy_password

    def confirm_proxy_details(self, proxy_details):
        """Show final proxy configuration confirmation"""
        while True:
            print("\n" + "=" * 50)
            print("🔍 PROXY CONFIGURATION SUMMARY")
            print("=" * 50)
            print(f"Type: {proxy_details['type'].upper()}")
            print(f"IP/Host: {proxy_details['ip']}")
            print(f"Port: {proxy_details['port']}")
            print(f"Username: {proxy_details['username'] or 'Not provided'}")
            print(f"Password: {proxy_details['password'] or 'Not provided'}")
            print("=" * 50)

            print("\nOptions:")
            print("1. ✅ Confirm and continue")
            print("2. 🔧 Edit proxy type")
            print("3. 🌐 Edit IP/hostname")
            print("4. 🔌 Edit port")
            print("5. 👤 Edit credentials")
            print("6. ❌ Cancel proxy setup")

            choice = input("\nSelect option (1-6): ").strip()

            if choice == "1":
                return proxy_details
            elif choice == "2":
                # Edit proxy type
                print("\n🌐 Select new proxy type:")
                print("1. HTTP/HTTPS")
                print("2. SOCKS4")
                print("3. SOCKS5")

                new_type = input("Select proxy type (1-3): ").strip()
                if new_type in ["1", "2", "3"]:
                    proxy_details["type"] = {"1": "http", "2": "socks4", "3": "socks5"}[
                        new_type
                    ]

            elif choice == "3":
                # Edit IP
                new_ip = self.validate_and_get_proxy_ip()
                if new_ip:
                    proxy_details["ip"] = new_ip

            elif choice == "4":
                # Edit port
                new_port = self.validate_and_get_proxy_port()
                if new_port:
                    proxy_details["port"] = new_port

            elif choice == "5":
                # Edit credentials
                new_username, new_password = self.validate_and_get_proxy_credentials()
                proxy_details["username"] = new_username
                proxy_details["password"] = new_password

            elif choice == "6":
                print("❌ Proxy setup cancelled")
                return None
            else:
                print("❌ Please select a valid option (1-6)")

    def validate_and_get_profile_selection(self, profiles):
        """Validate and get profile selection with edit option"""
        while True:
            try:
                selection = input(f"Select profile (1-{len(profiles)}): ").strip()

                if not selection:
                    print("❌ Please enter a profile number.")
                    continue

                profile_index = int(selection) - 1

                if 0 <= profile_index < len(profiles):
                    selected_profile = profiles[profile_index]
                    profile_info = self.get_profile(selected_profile)

                    print(f"\n📋 Selected Profile:")
                    print(f"  Name: {selected_profile}")
                    print(f"  Email: {profile_info['email']}")
                    print(
                        f"  Status: {'✓ Verified' if selected_profile in self.signed_in_profiles else '✗ Unverified'}"
                    )

                    confirm = (
                        input("\nIs this the correct profile? (y/n): ").lower().strip()
                    )

                    if confirm == "y":
                        return profile_index
                    elif confirm == "n":
                        continue
                    else:
                        print("⚠️ Please enter 'y' for yes or 'n' for no")
                else:
                    print(f"❌ Please enter a number between 1 and {len(profiles)}")

            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n❌ Selection cancelled")
                return None

    def enhanced_add_profile(self):
        """Enhanced profile addition with comprehensive validation"""
        print("\n🆕 CREATE NEW PROFILE")
        print("=" * 50)

        # Get and validate profile name
        profile_name = self.validate_and_get_profile_name()
        if profile_name is None:
            print("❌ Profile creation cancelled")
            return False

        # Get and validate email
        email = self.validate_and_get_email()
        if email is None:
            print("❌ Profile creation cancelled")
            return False

        # Skip password validation - user will enter manually during login
        print(
            "\n📝 Note: You will enter your password manually when signing in to Gmail"
        )
        password = "dummy_password"  # Placeholder password

        # Get and validate proxy details
        proxy_details = self.validate_and_get_proxy_details()

        # Final confirmation before creating profile
        print("\n" + "=" * 60)
        print("📋 PROFILE CREATION SUMMARY")
        print("=" * 60)
        print(f"Profile Name: {profile_name}")
        print(f"Email: {email}")
        print("Password: Will be entered manually during Gmail login")
        if proxy_details:
            print(
                f"Proxy: {proxy_details['type']}://{proxy_details['ip']}:{proxy_details['port']}"
            )
            if proxy_details["username"]:
                print(
                    f"Proxy Auth: {proxy_details['username']}:{proxy_details['password'] if proxy_details['password'] else 'No password'}"
                )
        else:
            print("Proxy: Not configured")
        print("=" * 60)

        final_confirm = input("\n🚀 Create this profile? (y/n): ").lower().strip()
        if final_confirm != "y":
            print("❌ Profile creation cancelled")
            return False

        # Create the profile using existing add_profile method
        return self.add_profile(profile_name, email, password, proxy_details)

    # ...existing code...


def main():
    """Main function with improved error handling"""
    try:
        profile_manager = ChromeProfileManager()

        while True:
            try:
                # Display available profiles with sign-in status
                profiles = profile_manager.list_profiles()
                if profiles:
                    print("\n=== Available Profiles ===")
                    for i, profile in enumerate(profiles, 1):
                        profile_info = profile_manager.get_profile(profile)
                        status = (
                            "✓ Signed in"
                            if profile in profile_manager.signed_in_profiles
                            else "✗ Not verified"
                        )
                        print(f"{i}. {profile} ({profile_info['email']}) - {status}")
                else:
                    print("\nNo profiles found.")

                # Modified menu with new options
                print("\n=== Menu ===")
                print("1. Use existing profile")
                print("2. Create new profile")
                print("3. Remove profile(s)")
                print("4. Show profile statistics")
                print("5. Show verified profiles")
                print("6. Show unverified profiles")
                print("7. Verify all profiles")
                print("8. Open Chrome with profile")
                print("9. Open Chrome with profile (no proxy)")
                print("10. Export profiles to JSON")
                print("11. Import profiles from JSON")
                print("12. Fix missing profile paths")
                print("13. Exit")

                choice = input("\nEnter choice (1-13): ").strip()

                # Validate choice
                if not choice.isdigit() or int(choice) < 1 or int(choice) > 13:
                    print("❌ Invalid choice. Please enter a number between 1 and 13.")
                    continue

                choice = int(choice)

                if choice == 1:
                    if not profiles:
                        print(
                            "No profiles available. Please create a new profile first."
                        )
                        continue

                    profile_index = profile_manager.validate_and_get_profile_selection(
                        profiles
                    )
                    if profile_index is not None:
                        selected_profile = profiles[profile_index]
                        print(f"✅ You selected profile: {selected_profile}")
                    else:
                        print("❌ Profile selection cancelled.")

                elif choice == 2:
                    # Create new profile with enhanced validation
                    print("\n🆕 Starting enhanced profile creation...")
                    if profile_manager.enhanced_add_profile():
                        print(f"\n🎉 Profile created successfully!")
                    else:
                        print(f"\n❌ Profile creation failed or cancelled")

                elif choice == 3:
                    # Remove multiple profiles
                    if not profiles:
                        print("No profiles available to remove.")
                        continue

                    print("\n" + "=" * 50)
                    print("🗑️  PROFILE REMOVAL")
                    print("=" * 50)
                    print("⚠️  WARNING: This will close ALL Chrome windows!")
                    print(
                        "💾 Make sure to save any important work in Chrome before proceeding."
                    )
                    print("=" * 50)

                    print(
                        "Enter profile numbers to remove (comma-separated, e.g., 1,2,3)"
                    )
                    print("Or type 'all' to remove all profiles")
                    selections = input(
                        f"Select profiles (1-{len(profiles)}) or 'all': "
                    ).strip()

                    to_remove = []

                    try:
                        if selections.lower() == "all":
                            to_remove = profiles.copy()
                            print(
                                f"🔍 Selected ALL {len(to_remove)} profiles for removal"
                            )
                        else:
                            selections_list = selections.split(",")
                            for selection in selections_list:
                                index = int(selection.strip()) - 1
                                if 0 <= index < len(profiles):
                                    to_remove.append(profiles[index])
                                else:
                                    print(f"❌ Invalid selection: {selection}")
                                    continue

                        if to_remove:
                            print(f"\n📋 Profiles selected for removal:")
                            for i, profile in enumerate(to_remove, 1):
                                profile_info = profile_manager.get_profile(profile)
                                status = (
                                    "✓ Verified"
                                    if profile in profile_manager.signed_in_profiles
                                    else "✗ Unverified"
                                )
                                print(
                                    f"   {i}. {profile} ({profile_info['email']}) - {status}"
                                )

                            print(f"\n⚠️  This action will:")
                            print(f"   • Close ALL Chrome windows on this machine")
                            print(
                                f"   • Permanently delete {len(to_remove)} profile(s)"
                            )
                            print(f"   • Remove all associated data")

                            confirm = input(
                                f"\n❓ Are you sure you want to proceed? (y/n): "
                            ).lower()

                            if confirm == "y":
                                print(f"\n🚀 Starting profile removal process...")
                                if profile_manager.remove_profiles(to_remove):
                                    print(
                                        f"\n🎉 Profile removal completed successfully!"
                                    )
                                else:
                                    print(
                                        f"\n⚠️  Profile removal completed with some errors. Check the log for details."
                                    )
                            else:
                                print("❌ Profile removal cancelled.")
                        else:
                            print("❌ No valid profiles selected.")

                    except ValueError:
                        print(
                            "❌ Invalid input. Please enter numbers separated by commas or 'all'."
                        )

                elif choice == 4:
                    stats = profile_manager.get_profile_stats()
                    print("\n=== Profile Statistics ===")
                    print(f"Total Profiles: {stats['total']}")
                    print(f"Verified Profiles: {stats['verified']}")
                    print(f"Unverified Profiles: {stats['unverified']}")

                elif choice == 5:
                    verified_profiles = profile_manager.get_verified_profiles()
                    print("\n=== Verified Profiles ===")
                    if verified_profiles:
                        for i, profile in enumerate(verified_profiles, 1):
                            profile_info = profile_manager.get_profile(profile)
                            print(f"{i}. {profile} ({profile_info['email']})")
                    else:
                        print("No verified profiles found.")

                elif choice == 6:
                    unverified_profiles = profile_manager.get_unverified_profiles()
                    print("\n=== Unverified Profiles ===")
                    if unverified_profiles:
                        for i, profile in enumerate(unverified_profiles, 1):
                            profile_info = profile_manager.get_profile(profile)
                            print(f"{i}. {profile} ({profile_info['email']})")
                    else:
                        print("No unverified profiles found.")

                elif choice == 7:
                    profile_manager.verify_all_profiles()
                    stats = profile_manager.get_profile_stats()
                    print("\n=== Updated Profile Statistics ===")
                    print(f"Total Profiles: {stats['total']}")
                    print(f"Verified Profiles: {stats['verified']}")
                    print(f"Unverified Profiles: {stats['unverified']}")

                elif choice == 8:
                    if not profiles:
                        print(
                            "No profiles available. Please create a new profile first."
                        )
                        continue
                    profile_index = profile_manager.validate_and_get_profile_selection(
                        profiles
                    )
                    if profile_index is not None:
                        selected_profile = profiles[profile_index]
                        print(f"✅ Opening profile: {selected_profile}")
                        profile_manager.open_profile(selected_profile)
                    else:
                        print("❌ Profile selection cancelled.")

                elif choice == 9:
                    if not profiles:
                        print(
                            "No profiles available. Please create a new profile first."
                        )
                        continue

                    profile_index = profile_manager.validate_and_get_profile_selection(
                        profiles
                    )
                    if profile_index is not None:
                        selected_profile = profiles[profile_index]
                        print(f"✅ Opening profile: {selected_profile} (NO PROXY)")
                        profile_manager.open_profile(
                            selected_profile, force_no_proxy=True
                        )
                    else:
                        print("❌ Profile selection cancelled.")

                elif choice == 10:
                    # Export profiles to JSON
                    default_export_path = os.path.join(
                        os.getcwd(), "exported_profiles.json"
                    )
                    export_path = input(
                        f"Enter export file path (default: {default_export_path}): "
                    ).strip()
                    if not export_path:
                        export_path = default_export_path

                    if profile_manager.export_profiles(export_path):
                        print(f"Profiles exported successfully to {export_path}")
                    else:
                        print("Failed to export profiles")

                elif choice == 11:
                    # Import profiles from JSON
                    import_path = input("Enter import file path: ").strip()
                    if not import_path:
                        print("No file path provided")
                        continue

                    if not os.path.exists(import_path):
                        print(f"File {import_path} does not exist")
                        continue

                    if profile_manager.import_profiles(import_path):
                        print(f"Profiles imported successfully from {import_path}")
                    else:
                        print("Failed to import profiles")

                elif choice == 12:
                    # Fix missing profile paths
                    print("Checking and fixing missing profile paths...")
                    if profile_manager.fix_missing_paths():
                        print("Profile paths have been checked and fixed if necessary.")
                    else:
                        print("Failed to fix profile paths.")

                elif choice == 13:
                    print("Exiting program.")
                    break

            except KeyboardInterrupt:
                print("\n\n❌ Operation cancelled by user (Ctrl+C)")
                break
            except Exception as e:
                print(f"❌ An error occurred: {e}")
                print("Please try again or contact support if the issue persists.")

    except Exception as e:
        print(f"❌ Critical error initializing profile manager: {e}")
        print("Please check your installation and try again.")
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")


if __name__ == "__main__":
    main()
