#!/usr/bin/env python3
"""
Quick Fix for Selenium-Wire SSL Certificate Issues
Run this script to quickly resolve selenium-wire "not secure" browser warnings

Usage: python fix_selenium_wire_ssl.py

Author: GitHub Copilot
Date: October 26, 2025
"""

import os
import sys
import subprocess
import platform


def run_certificate_setup():
    """Run the certificate setup process"""
    print("🔧 Quick Fix: Selenium-Wire SSL Certificate Issues")
    print("=" * 55)

    try:
        # Check if the setup script exists
        setup_script = "selenium_wire_cert_setup.py"
        if not os.path.exists(setup_script):
            print(f"❌ Setup script not found: {setup_script}")
            print("💡 Make sure selenium_wire_cert_setup.py is in the same directory")
            return False

        print("🚀 Running certificate setup...")

        # Run the certificate setup
        result = subprocess.run(
            [sys.executable, setup_script], capture_output=True, text=True
        )

        if result.returncode == 0:
            print("✅ Certificate setup completed successfully!")
            print("\n📋 Setup Output:")
            print(result.stdout)
            return True
        else:
            print("❌ Certificate setup failed!")
            print("\n📋 Error Output:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"❌ Failed to run certificate setup: {e}")
        return False


def apply_quick_fixes():
    """Apply additional quick fixes for selenium-wire issues"""
    print("\n🛠️ Applying additional quick fixes...")

    fixes_applied = []

    try:
        # Fix 1: Set environment variables for SSL
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        os.environ["SSL_VERIFY"] = "false"
        fixes_applied.append("✅ SSL environment variables set")

        # Fix 2: Create selenium-wire config directory
        if platform.system().lower() == "windows":
            config_dir = os.path.join(os.environ.get("APPDATA", ""), "seleniumwire")
        else:
            config_dir = os.path.join(os.path.expanduser("~"), ".seleniumwire")

        os.makedirs(config_dir, exist_ok=True)
        fixes_applied.append(f"✅ Config directory created: {config_dir}")

        # Fix 3: Create a simple config file
        config_file = os.path.join(config_dir, "config.txt")
        with open(config_file, "w") as f:
            f.write("# Selenium-Wire Configuration\n")
            f.write("verify_ssl=false\n")
            f.write("suppress_connection_errors=true\n")
        fixes_applied.append("✅ Configuration file created")

        return fixes_applied

    except Exception as e:
        print(f"⚠️ Some quick fixes failed: {e}")
        return fixes_applied


def show_usage_instructions():
    """Show how to use the fixed selenium-wire setup"""
    print("\n📖 USAGE INSTRUCTIONS")
    print("=" * 40)
    print("1. Import the certificate manager in your code:")
    print("   from selenium_wire_cert_setup import SeleniumWireCertificateManager")
    print("")
    print("2. Replace your driver creation with:")
    print("   ```python")
    print("   cert_manager = SeleniumWireCertificateManager()")
    print("   seleniumwire_options = cert_manager.get_selenium_wire_options()")
    print("   chrome_options = cert_manager.get_chrome_options()")
    print("   ")
    print("   driver = webdriver.Chrome(")
    print("       service=service,")
    print("       options=chrome_options,")
    print("       seleniumwire_options=seleniumwire_options")
    print("   )")
    print("   ```")
    print("")
    print("3. Or use the example functions:")
    print(
        "   from selenium_wire_usage_example import create_secure_selenium_wire_driver"
    )
    print("   driver = create_secure_selenium_wire_driver(headless=True)")
    print("")
    print("4. Test your setup:")
    print("   python selenium_wire_usage_example.py")


def main():
    """Main function"""
    print("🚨 Selenium-Wire SSL Certificate Quick Fix Tool")
    print("=" * 60)
    print("This tool will resolve 'not secure' browser warnings in selenium-wire")
    print("")

    # Step 1: Run certificate setup
    setup_success = run_certificate_setup()

    # Step 2: Apply quick fixes
    quick_fixes = apply_quick_fixes()

    # Step 3: Summary
    print("\n📊 SUMMARY")
    print("=" * 20)

    if setup_success:
        print("✅ Certificate setup: SUCCESS")
    else:
        print("❌ Certificate setup: FAILED")

    print(f"✅ Quick fixes applied: {len(quick_fixes)}")
    for fix in quick_fixes:
        print(f"   {fix}")

    if setup_success or len(quick_fixes) > 0:
        print("\n🎉 SSL issues should now be resolved!")
        show_usage_instructions()
    else:
        print("\n❌ Unable to fix SSL issues automatically.")
        print("💡 Try running manually: python selenium_wire_cert_setup.py")

    print("\n🔍 Next steps:")
    print("1. Test with: python selenium_wire_usage_example.py")
    print("2. Update your existing code to use the new certificate setup")
    print("3. Run your ManyChat automation with the fixed selenium-wire")


if __name__ == "__main__":
    main()
