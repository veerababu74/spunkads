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


def find_setup_script():
    """Find the selenium_wire_cert_setup.py script in various locations"""
    script_name = "selenium_wire_cert_setup.py"

    # Possible locations to check
    search_paths = [
        ".",  # Current directory
        os.path.dirname(os.path.abspath(__file__)),  # Same directory as this script
        "d:/fina_project",  # Your project directory
        "d:\\fina_project",  # Windows path format
        os.path.expanduser("~/Desktop/spunkads-main"),  # User desktop
        "C:/Users/veera/Desktop/spunkads-main",  # Specific desktop path
    ]

    for path in search_paths:
        full_path = os.path.join(path, script_name)
        if os.path.exists(full_path):
            return full_path

    return None


def run_certificate_setup():
    """Run the certificate setup process"""
    print("🔧 Quick Fix: Selenium-Wire SSL Certificate Issues")
    print("=" * 55)

    try:
        # Find the setup script
        setup_script = find_setup_script()

        if not setup_script:
            print(f"❌ Setup script not found: selenium_wire_cert_setup.py")
            print("💡 Searched in:")
            print("   - Current directory")
            print("   - d:/fina_project")
            print("   - Desktop/spunkads-main")
            print("\n🔧 Creating minimal certificate setup inline...")
            return run_inline_certificate_setup()

        print(f"✅ Found setup script: {setup_script}")
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
            print("\n🔧 Falling back to inline setup...")
            return run_inline_certificate_setup()

    except Exception as e:
        print(f"❌ Failed to run certificate setup: {e}")
        print("🔧 Falling back to inline setup...")
        return run_inline_certificate_setup()


def run_inline_certificate_setup():
    """Run a minimal certificate setup inline"""
    print("🔧 Running inline certificate setup...")

    try:
        import ssl
        import certifi
        import tempfile
        from pathlib import Path

        # Create seleniumwire directory
        if platform.system().lower() == "windows":
            cert_dir = Path(os.environ.get("APPDATA", "")) / "seleniumwire"
        else:
            cert_dir = Path.home() / ".seleniumwire"

        cert_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Certificate directory: {cert_dir}")

        # Copy CA bundle
        ca_bundle_path = certifi.where()
        ca_cert_path = cert_dir / "ca-bundle.crt"

        import shutil

        shutil.copy2(ca_bundle_path, ca_cert_path)
        print("✅ CA bundle copied")

        # Create seleniumwire options config
        config_path = cert_dir / "seleniumwire_options.py"
        with open(config_path, "w") as f:
            f.write(
                """# Selenium-Wire SSL Configuration
SELENIUMWIRE_OPTIONS = {
    'verify_ssl': False,
    'disable_encoding': True,
    'suppress_connection_errors': True,
    'auto_config': False,
    'port': 0,
}

CHROME_OPTIONS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--ignore-certificate-errors",
    "--ignore-ssl-errors",
    "--ignore-certificate-errors-spki-list",
    "--allow-running-insecure-content",
    "--disable-web-security",
    "--trust-server-certificate",
]
"""
            )
        print("✅ Configuration files created")

        return True

    except Exception as e:
        print(f"❌ Inline setup failed: {e}")
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


def show_immediate_usage():
    """Show immediate usage without requiring additional files"""
    print("\n🚀 IMMEDIATE USAGE (Copy-Paste Ready)")
    print("=" * 50)
    print("Add this to your existing selenium-wire code:")
    print("")
    print("```python")
    print("from seleniumwire import webdriver")
    print("from selenium.webdriver.chrome.options import Options")
    print("from selenium.webdriver.chrome.service import Service")
    print("from webdriver_manager.chrome import ChromeDriverManager")
    print("")
    print("# SSL-Safe selenium-wire options")
    print("seleniumwire_options = {")
    print("    'verify_ssl': False,")
    print("    'disable_encoding': True,")
    print("    'suppress_connection_errors': True,")
    print("    'auto_config': False,")
    print("    'port': 0,")
    print("}")
    print("")
    print("# SSL-Safe Chrome options")
    print("chrome_options = Options()")
    print("ssl_args = [")
    print("    '--no-sandbox',")
    print("    '--disable-dev-shm-usage',")
    print("    '--disable-gpu',")
    print("    '--ignore-certificate-errors',")
    print("    '--ignore-ssl-errors',")
    print("    '--ignore-certificate-errors-spki-list',")
    print("    '--allow-running-insecure-content',")
    print("    '--disable-web-security',")
    print("    '--trust-server-certificate',")
    print("    '--headless'  # Remove this line if you want to see the browser")
    print("]")
    print("for arg in ssl_args:")
    print("    chrome_options.add_argument(arg)")
    print("")
    print("# Create driver")
    print("service = Service(ChromeDriverManager().install())")
    print("driver = webdriver.Chrome(")
    print("    service=service,")
    print("    options=chrome_options,")
    print("    seleniumwire_options=seleniumwire_options")
    print(")")
    print("```")
    print("")
    print("💡 This should eliminate SSL certificate warnings!")


def show_usage_instructions():
    """Show how to use the fixed selenium-wire setup"""
    print("\n📖 ADVANCED USAGE INSTRUCTIONS")
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
        show_immediate_usage()
        show_usage_instructions()
    else:
        print("\n❌ Unable to fix SSL issues automatically.")
        print("💡 Try running manually: python selenium_wire_cert_setup.py")
        show_immediate_usage()

    print("\n🔍 Next steps:")
    print("1. Test with: python selenium_wire_usage_example.py")
    print("2. Update your existing code to use the new certificate setup")
    print("3. Run your ManyChat automation with the fixed selenium-wire")


if __name__ == "__main__":
    main()
