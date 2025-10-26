#!/usr/bin/env python3
"""
Test script to verify sheet name configuration changes
"""
import sys
import os

# Add the project directory to path to import properties
sys.path.append(os.path.dirname(__file__))

from properties import Properties


def test_sheet_configuration():
    """Test that sheet names have been updated correctly"""
    print("🧪 Testing Sheet Name Configuration")
    print("=" * 50)

    # Get the Apps Script configuration
    config = Properties.get_apps_script_config()

    print(f"📋 Configuration:")
    print(f"   Detailed Sheet Name: {config['sheets_mapping']['detailed']}")
    print(f"   Summary Sheet Name: {config['sheets_mapping']['summary']}")

    # Verify the changes
    detailed_name = config["sheets_mapping"]["detailed"]
    summary_name = config["sheets_mapping"]["summary"]

    if detailed_name == "source" and summary_name == "total_report":
        print("\n✅ SUCCESS: Sheet names have been updated correctly!")
        print("   ✅ Detailed sheet: 'test' → 'source'")
        print("   ✅ Summary sheet: 'test1' → 'total_report'")
        return True
    else:
        print("\n❌ FAILURE: Sheet names were not updated correctly!")
        print(f"   Expected: detailed='source', summary='total_report'")
        print(f"   Actual: detailed='{detailed_name}', summary='{summary_name}'")
        return False


def print_next_steps():
    """Print the remaining manual steps"""
    print("\n" + "=" * 50)
    print("📋 REMAINING MANUAL STEPS:")
    print("=" * 50)
    print("1. 📊 Update your Google Sheet:")
    print("   • Rename 'test' tab → 'source'")
    print("   • Rename 'test1' tab → 'total_report'")
    print()
    print("2. 🔄 Update Google Apps Script:")
    print("   • Go to https://script.google.com/")
    print("   • Open your existing project")
    print("   • Replace code with updated Simple_GoogleAppsScript.js")
    print("   • Save and redeploy")
    print()
    print("3. 🧪 Test the pipeline:")
    print("   • Run your main pipeline script")
    print("   • Verify data uploads to new sheet names")


if __name__ == "__main__":
    success = test_sheet_configuration()
    print_next_steps()

    if success:
        print("\n🎉 Configuration update completed successfully!")
        print("📝 Complete the manual steps above to finish the process.")
    else:
        print("\n💥 Configuration update failed!")
        print("❗ Please check the properties.py file.")
