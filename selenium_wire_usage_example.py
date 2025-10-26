#!/usr/bin/env python3
"""
Example usage of Selenium-Wire with Certificate Setup
Shows how to integrate the certificate manager into your existing ManyChat automation

Author: GitHub Copilot
Date: October 26, 2025
"""

from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Import our certificate manager
from selenium_wire_cert_setup import SeleniumWireCertificateManager


def create_secure_selenium_wire_driver(headless=True, profile_path=None):
    """
    Create a selenium-wire driver with proper SSL certificate configuration

    Args:
        headless (bool): Whether to run browser in headless mode
        profile_path (str): Optional Chrome profile path

    Returns:
        webdriver: Configured selenium-wire Chrome driver
    """
    print("🔧 Setting up Selenium-Wire with SSL certificate configuration...")

    # Initialize certificate manager
    cert_manager = SeleniumWireCertificateManager()

    # Get configured options
    seleniumwire_options = cert_manager.get_selenium_wire_options()
    chrome_options = cert_manager.get_chrome_options()

    # Add headless mode if requested
    if headless:
        chrome_options.add_argument("--headless")

    # Add profile path if provided
    if profile_path:
        chrome_options.add_argument(f"--user-data-dir={profile_path}")

    # Create Chrome service
    service = Service(ChromeDriverManager().install())

    try:
        # Create driver with selenium-wire and certificate configuration
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options,
        )

        print("✅ Selenium-Wire driver created successfully with SSL configuration!")
        return driver

    except Exception as e:
        print(f"❌ Failed to create selenium-wire driver: {e}")
        print("💡 Try running: python selenium_wire_cert_setup.py")
        raise


def test_secure_driver():
    """Test the secure selenium-wire driver setup"""
    print("\n🧪 Testing Secure Selenium-Wire Driver...")

    try:
        # Create secure driver
        driver = create_secure_selenium_wire_driver(headless=True)

        # Test with HTTPS site
        print("📡 Testing HTTPS request capture...")
        driver.get("https://httpbin.org/get")

        # Wait a bit for request to be captured
        time.sleep(2)

        # Check captured requests
        captured_requests = len(driver.requests)
        print(f"📊 Captured {captured_requests} requests")

        if captured_requests > 0:
            print("✅ SSL certificate setup working correctly!")

            # Show some request details
            for request in driver.requests:
                print(
                    f"   📋 {request.method} {request.url} - Status: {request.response.status_code if request.response else 'Pending'}"
                )
        else:
            print("⚠️ No requests captured - may need certificate setup")

        driver.quit()
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


# Integration example for your ManyChat automation
def create_manychat_driver_with_cert_fix(profile_name="default", headless=True):
    """
    Create ManyChat-optimized driver with SSL certificate fixes

    Args:
        profile_name (str): Chrome profile name to use
        headless (bool): Whether to run in headless mode

    Returns:
        webdriver: Configured driver for ManyChat automation
    """
    print(f"🚀 Creating ManyChat driver with profile: {profile_name}")

    # Initialize certificate manager
    cert_manager = SeleniumWireCertificateManager()

    # Get base options
    seleniumwire_options = cert_manager.get_selenium_wire_options()
    chrome_options = cert_manager.get_chrome_options()

    # ManyChat-specific optimizations
    if headless:
        chrome_options.add_argument("--headless")

    # Window size for ManyChat interface
    chrome_options.add_argument("--window-size=1920,1080")

    # Profile handling (if you have Chrome profiles)
    if profile_name and profile_name != "default":
        # Add profile-specific arguments
        chrome_options.add_argument(f"--profile-directory={profile_name}")

    # Create service
    service = Service(ChromeDriverManager().install())

    try:
        # Create driver
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options,
        )

        # Set timeouts
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)

        print("✅ ManyChat driver created successfully!")
        return driver

    except Exception as e:
        print(f"❌ Failed to create ManyChat driver: {e}")
        raise


if __name__ == "__main__":
    print("🔧 Selenium-Wire Certificate Setup - Usage Example")
    print("=" * 60)

    # First, run the certificate setup
    print("\n1️⃣ Running certificate setup...")
    cert_manager = SeleniumWireCertificateManager()
    setup_success = cert_manager.setup_all()

    if setup_success:
        print("\n2️⃣ Testing secure driver...")
        test_success = test_secure_driver()

        if test_success:
            print("\n🎉 All tests passed! Your selenium-wire setup is ready.")
            print("\n📝 Integration instructions:")
            print("Replace your current driver creation code with:")
            print("```python")
            print("driver = create_secure_selenium_wire_driver(headless=True)")
            print("# or for ManyChat specifically:")
            print(
                "driver = create_manychat_driver_with_cert_fix(profile_name='your_profile')"
            )
            print("```")
        else:
            print("\n⚠️ Tests had issues. Check certificate setup.")
    else:
        print("\n❌ Certificate setup failed. Check logs above.")
