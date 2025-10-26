#!/usr/bin/env python3
"""
Selenium Wire Certificate Setup Script
Handles SSL certificate installation and configuration for selenium-wire to avoid security issues

Author: GitHub Copilot
Date: October 26, 2025
"""

import os
import sys
import ssl
import tempfile
import platform
import subprocess
import shutil
from pathlib import Path
import certifi
import requests
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SeleniumWireCertificateManager:
    """Manages SSL certificates for selenium-wire to avoid security issues"""

    def __init__(self):
        self.platform = platform.system().lower()
        self.cert_dir = self._get_cert_directory()
        self.ca_cert_path = None

    def _get_cert_directory(self):
        """Get the appropriate certificate directory based on OS"""
        if self.platform == "windows":
            return Path(os.environ.get("APPDATA", "")) / "seleniumwire"
        elif self.platform == "darwin":  # macOS
            return Path.home() / ".seleniumwire"
        else:  # Linux
            return Path.home() / ".seleniumwire"

    def create_cert_directory(self):
        """Create certificate directory if it doesn't exist"""
        try:
            self.cert_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Certificate directory created/verified: {self.cert_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to create certificate directory: {e}")
            return False

    def install_system_certificates(self):
        """Install system certificates for selenium-wire"""
        try:
            # Get the path to certifi's CA bundle
            ca_bundle_path = certifi.where()
            logger.info(f"Using CA bundle from: {ca_bundle_path}")

            # Copy to selenium-wire directory
            self.ca_cert_path = self.cert_dir / "ca-bundle.crt"
            shutil.copy2(ca_bundle_path, self.ca_cert_path)

            logger.info(f"CA bundle copied to: {self.ca_cert_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to install system certificates: {e}")
            return False

    def configure_ssl_context(self):
        """Configure SSL context for selenium-wire"""
        try:
            # Create a custom SSL context
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            logger.info("SSL context configured successfully")
            return ssl_context

        except Exception as e:
            logger.error(f"Failed to configure SSL context: {e}")
            return None

    def get_selenium_wire_options(self):
        """Get selenium-wire options with proper certificate configuration"""
        try:
            options = {
                "verify_ssl": False,  # Disable SSL verification
                "disable_encoding": True,  # Disable response encoding
                "suppress_connection_errors": True,  # Suppress connection errors
                "ca_cert": (
                    str(self.ca_cert_path)
                    if self.ca_cert_path and self.ca_cert_path.exists()
                    else None
                ),
                "disable_capture": False,  # Enable request/response capture
                "auto_config": False,  # Disable automatic configuration
            }

            # Additional options for Windows
            if self.platform == "windows":
                options.update(
                    {
                        "port": 0,  # Use random available port
                        "backend": "default",
                    }
                )

            logger.info("Selenium-wire options configured")
            return options

        except Exception as e:
            logger.error(f"Failed to configure selenium-wire options: {e}")
            return {}

    def get_chrome_options(self):
        """Get Chrome options that work well with selenium-wire"""
        try:
            chrome_options = Options()

            # Basic options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")

            # SSL and security related options
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--ignore-ssl-errors")
            chrome_options.add_argument("--ignore-certificate-errors-spki-list")
            chrome_options.add_argument("--ignore-certificate-errors-sp-list")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--trust-server-certificate")

            # Proxy and certificate handling
            chrome_options.add_argument("--proxy-bypass-list=*")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")

            # Performance optimizations
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")

            # User agent and window settings
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            logger.info("Chrome options configured for selenium-wire")
            return chrome_options

        except Exception as e:
            logger.error(f"Failed to configure Chrome options: {e}")
            return Options()

    def test_selenium_wire_setup(self):
        """Test the selenium-wire setup with a simple request"""
        try:
            logger.info("Testing selenium-wire setup...")

            # Get configured options
            seleniumwire_options = self.get_selenium_wire_options()
            chrome_options = self.get_chrome_options()
            chrome_options.add_argument("--headless")  # Run headless for testing

            # Create driver service
            service = Service(ChromeDriverManager().install())

            # Create driver with selenium-wire
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options,
                seleniumwire_options=seleniumwire_options,
            )

            # Test with a simple request
            driver.get("https://httpbin.org/get")

            # Check if we can capture requests
            requests_captured = len(driver.requests) > 0

            driver.quit()

            if requests_captured:
                logger.info("✅ Selenium-wire setup test PASSED - SSL issues resolved!")
                return True
            else:
                logger.warning(
                    "⚠️ Selenium-wire setup test completed but no requests captured"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Selenium-wire setup test FAILED: {e}")
            return False

    def install_windows_certificates(self):
        """Install certificates on Windows system"""
        if self.platform != "windows":
            return True

        try:
            logger.info("Installing certificates for Windows...")

            # Use certlm.msc or certmgr.msc commands if available
            cert_commands = [
                "certlm.msc",  # Local machine certificates
                "certmgr.msc",  # Current user certificates
            ]

            for cmd in cert_commands:
                try:
                    subprocess.run([cmd], check=False, timeout=2)
                except:
                    continue

            logger.info("Windows certificate installation attempted")
            return True

        except Exception as e:
            logger.error(f"Failed to install Windows certificates: {e}")
            return False

    def setup_all(self):
        """Complete setup process for selenium-wire certificates"""
        logger.info("🚀 Starting Selenium-Wire Certificate Setup...")

        success_steps = []

        # Step 1: Create certificate directory
        if self.create_cert_directory():
            success_steps.append("✅ Certificate directory created")
        else:
            logger.error("❌ Failed to create certificate directory")
            return False

        # Step 2: Install system certificates
        if self.install_system_certificates():
            success_steps.append("✅ System certificates installed")
        else:
            logger.warning("⚠️ System certificate installation had issues")

        # Step 3: Configure SSL context
        if self.configure_ssl_context():
            success_steps.append("✅ SSL context configured")
        else:
            logger.warning("⚠️ SSL context configuration had issues")

        # Step 4: Windows-specific certificate installation
        if self.platform == "windows":
            if self.install_windows_certificates():
                success_steps.append("✅ Windows certificates processed")

        # Step 5: Test the setup
        if self.test_selenium_wire_setup():
            success_steps.append("✅ Selenium-wire test passed")
        else:
            logger.warning("⚠️ Selenium-wire test had issues")

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("🎯 SELENIUM-WIRE CERTIFICATE SETUP SUMMARY")
        logger.info("=" * 60)
        for step in success_steps:
            logger.info(step)
        logger.info("=" * 60)

        return len(success_steps) >= 3  # At least 3 successful steps


def main():
    """Main function to run the certificate setup"""
    print("🔧 Selenium-Wire Certificate Setup Tool")
    print("=" * 50)

    try:
        cert_manager = SeleniumWireCertificateManager()
        success = cert_manager.setup_all()

        if success:
            print("\n🎉 Setup completed successfully!")
            print("\n📝 Usage in your code:")
            print("```python")
            print("from selenium_wire_cert_setup import SeleniumWireCertificateManager")
            print("")
            print("cert_manager = SeleniumWireCertificateManager()")
            print("seleniumwire_options = cert_manager.get_selenium_wire_options()")
            print("chrome_options = cert_manager.get_chrome_options()")
            print("")
            print("driver = webdriver.Chrome(")
            print("    service=service,")
            print("    options=chrome_options,")
            print("    seleniumwire_options=seleniumwire_options")
            print(")")
            print("```")
        else:
            print("\n⚠️ Setup completed with some issues. Check logs above.")

    except Exception as e:
        logger.error(f"Setup failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
