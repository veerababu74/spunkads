#!/usr/bin/env python3
"""
Standalone Selenium-Wire SSL Fix
Copy this file anywhere and run it to fix selenium-wire SSL issues

Usage: python standalone_selenium_wire_fix.py

Author: GitHub Copilot
Date: October 26, 2025
"""

import os
import sys
import platform


def main():
    """Standalone selenium-wire SSL fix"""
    print("🔧 Standalone Selenium-Wire SSL Fix")
    print("=" * 40)

    try:
        # Set environment variables
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        os.environ["SSL_VERIFY"] = "false"
        print("✅ SSL environment variables set")

        # Create seleniumwire config directory
        if platform.system().lower() == "windows":
            config_dir = os.path.join(os.environ.get("APPDATA", ""), "seleniumwire")
        else:
            config_dir = os.path.join(os.path.expanduser("~"), ".seleniumwire")

        os.makedirs(config_dir, exist_ok=True)
        print(f"✅ Config directory created: {config_dir}")

        # Create config file
        config_file = os.path.join(config_dir, "config.txt")
        with open(config_file, "w") as f:
            f.write("verify_ssl=false\n")
            f.write("suppress_connection_errors=true\n")
        print("✅ Configuration file created")

        print("\n🎉 SSL issues should now be resolved!")

        print("\n📋 USE THIS CODE IN YOUR SELENIUM-WIRE SCRIPTS:")
        print("=" * 55)
        print(
            """
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# SSL-Safe selenium-wire options
seleniumwire_options = {
    'verify_ssl': False,
    'disable_encoding': True,
    'suppress_connection_errors': True,
    'auto_config': False,
    'port': 0,
}

# SSL-Safe Chrome options
chrome_options = Options()
ssl_args = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--ignore-certificate-errors',
    '--ignore-ssl-errors',
    '--ignore-certificate-errors-spki-list',
    '--allow-running-insecure-content',
    '--disable-web-security',
    '--trust-server-certificate',
    '--headless'  # Remove this line if you want to see the browser
]
for arg in ssl_args:
    chrome_options.add_argument(arg)

# Create driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(
    service=service,
    options=chrome_options,
    seleniumwire_options=seleniumwire_options
)

# Now use driver normally - SSL warnings should be gone!
driver.get("https://example.com")
print(f"Captured {len(driver.requests)} requests")
driver.quit()
"""
        )

        print(
            "\n💡 Copy the code above and replace your current selenium-wire driver creation!"
        )

    except Exception as e:
        print(f"❌ Fix failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
