# ManyChat Data Extraction Properties
# Single configuration file for all settings
# Author: GitHub Copilot

from datetime import datetime, timedelta, timezone

# Timezone configuration to match ManyChat (UTC-4:00)
MANYCHAT_TIMEZONE = timezone(timedelta(hours=-4))


class Properties:
    """
    Centralized configuration properties for ManyChat data extraction
    All settings are defined here in one place
    """

    # ================================================
    # MAIN EXTRACTION PROPERTIES
    # ================================================

    # Execution Mode Options: "today", "yesterday", "specific_date", "date_range"
    EXECUTION_MODE = "yesterday"

    # Specific Date (when EXECUTION_MODE = "specific_date")
    # Format: "YYYY-MM-DD"
    SPECIFIC_DATE = "2025-09-27"

    # Date Range (when EXECUTION_MODE = "date_range")
    DATE_RANGE_START = "2025-09-20"
    DATE_RANGE_END = "2025-09-27"

    # Chrome Profile Name
    # Options: "auto" (auto-select), "veera", or any profile name
    PROFILE_NAME = "auto"

    # Exclude Campaign Names (case-insensitive matching)
    # Add campaign names you want to exclude from extraction
    EXCLUDE_CAMPAIGN_NAMES = [
        "test",
        "draft",
        "sample",
        "copy",
        # Add more campaign names here as needed
    ]

    # ================================================
    # GOOGLE APPS SCRIPT CONFIGURATION
    # ================================================

    # Google Apps Script Web App URL
    WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhICMU9P1YEZLL8mN_USrHXqHp9pq4tipwYJ8EpO0rasnVSOXoE9KK47ge7CIs9rwagg/exec"

    # Google Spreadsheet Name
    SPREADSHEET_NAME = "manychat"

    # Sheet Mapping
    DETAILED_SHEET_NAME = "test"  # For detailed campaign data
    SUMMARY_SHEET_NAME = "test1"  # For summary data

    # Apps Script Settings
    TIMEOUT_SECONDS = 30
    RETRY_ATTEMPTS = 3

    # ================================================
    # SPUNKSTATS API CONFIGURATION
    # ================================================

    # SpunkStats API Credentials (Shared for all accounts)
    SPUNKSTATS_USER_ID = "018e50b6-fd26-7c7f-a3c6-62bf4fc59314"
    SPUNKSTATS_API_KEY = "SPK2afce2786ec350bc30c118a8887cfb5970c153f3"

    # ================================================
    # FILE MANAGEMENT PROPERTIES
    # ================================================

    # Clear Files After Upload
    # True = Delete CSV/JSON files after successful upload
    # False = Keep files for inspection
    CLEAR_FILES = True

    # Directory Settings
    CSV_OUTPUT_DIRECTORY = "./csv_output/"
    JSON_OUTPUT_DIRECTORY = "./json_output/"
    LOGS_DIRECTORY = "./logs/"

    # ================================================
    # EXECUTION SETTINGS
    # ================================================

    # Browser Settings
    HEADLESS_MODE = True  # True = faster, False = visible browser
    VERBOSE_OUTPUT = True  # True = detailed logs, False = minimal output

    # Output Settings
    DELETE_JSON_AFTER_CSV = False  # Delete original JSON files after CSV creation
    INCLUDE_SUMMARY_CSV = True  # Generate summary CSV
    INCLUDE_DETAILED_CSV = True  # Generate detailed CSV

    # ================================================
    # HELPER METHODS
    # ================================================

    @classmethod
    def get_date_range(cls):
        """Get date range based on execution mode"""
        if cls.EXECUTION_MODE == "today":
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

        elif cls.EXECUTION_MODE == "yesterday":
            yesterday = (datetime.now(MANYCHAT_TIMEZONE) - timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )
            return yesterday, yesterday, "yesterday_only"

        elif cls.EXECUTION_MODE == "specific_date":
            if cls.SPECIFIC_DATE:
                return cls.SPECIFIC_DATE, cls.SPECIFIC_DATE, "specific_date"
            else:
                # Fallback to today
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                return today, today, "today_only"

        elif cls.EXECUTION_MODE == "date_range":
            if cls.DATE_RANGE_START and cls.DATE_RANGE_END:
                return cls.DATE_RANGE_START, cls.DATE_RANGE_END, "custom_range"
            else:
                # Fallback to today
                today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
                return today, today, "today_only"

        else:
            # Default to today
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

    @classmethod
    def get_profile_name(cls):
        """Get profile name for Chrome"""
        return None if cls.PROFILE_NAME == "auto" else cls.PROFILE_NAME

    @classmethod
    def get_extraction_config(cls):
        """Get extraction configuration dictionary"""
        return {
            "extraction_mode": cls.EXECUTION_MODE,
            "specific_date": cls.SPECIFIC_DATE,
            "date_range_start": cls.DATE_RANGE_START,
            "date_range_end": cls.DATE_RANGE_END,
            "profile_name": cls.PROFILE_NAME,
            "headless_mode": cls.HEADLESS_MODE,
            "verbose": cls.VERBOSE_OUTPUT,
            "exclude_campaign_names": cls.EXCLUDE_CAMPAIGN_NAMES,
            "delete_json_after_csv": cls.DELETE_JSON_AFTER_CSV,
            "csv_output_directory": cls.CSV_OUTPUT_DIRECTORY,
            "include_summary_csv": cls.INCLUDE_SUMMARY_CSV,
            "include_detailed_csv": cls.INCLUDE_DETAILED_CSV,
            "clear_files": cls.CLEAR_FILES,
        }

    @classmethod
    def get_apps_script_config(cls):
        """Get Google Apps Script configuration dictionary"""
        return {
            "webapp_url": cls.WEBAPP_URL,
            "spreadsheet_name": cls.SPREADSHEET_NAME,
            "sheets_mapping": {
                "detailed": cls.DETAILED_SHEET_NAME,
                "summary": cls.SUMMARY_SHEET_NAME,
            },
            "timeout_seconds": cls.TIMEOUT_SECONDS,
            "retry_attempts": cls.RETRY_ATTEMPTS,
            "clear_files": cls.CLEAR_FILES,
        }

    @classmethod
    def get_output_settings(cls):
        """Get output settings dictionary"""
        return {
            "delete_json_after_csv": cls.DELETE_JSON_AFTER_CSV,
            "csv_output_directory": cls.CSV_OUTPUT_DIRECTORY,
            "json_output_directory": cls.JSON_OUTPUT_DIRECTORY,
            "logs_directory": cls.LOGS_DIRECTORY,
            "include_summary_csv": cls.INCLUDE_SUMMARY_CSV,
            "include_detailed_csv": cls.INCLUDE_DETAILED_CSV,
            "clear_files": cls.CLEAR_FILES,
        }

    @classmethod
    def get_spunkstats_config(cls):
        """Get SpunkStats API configuration dictionary"""
        return {
            "user_id": cls.SPUNKSTATS_USER_ID,
            "api_key": cls.SPUNKSTATS_API_KEY,
        }

    @classmethod
    def print_current_config(cls):
        """Print current configuration for verification"""
        print("📋 CURRENT CONFIGURATION")
        print("=" * 50)
        print(f"🎯 Execution Mode: {cls.EXECUTION_MODE}")
        print(f"📅 Specific Date: {cls.SPECIFIC_DATE}")
        print(f"👤 Profile Name: {cls.PROFILE_NAME}")
        print(f"🚫 Exclude Campaigns: {len(cls.EXCLUDE_CAMPAIGN_NAMES)} items")
        print(f"🔗 Web App URL: {cls.WEBAPP_URL[:50]}...")
        print(f"📊 Spreadsheet: {cls.SPREADSHEET_NAME}")
        print(f"🗑️ Clear Files: {cls.CLEAR_FILES}")
        print(f"👁️ Headless Mode: {cls.HEADLESS_MODE}")
        print(f"📢 Verbose Output: {cls.VERBOSE_OUTPUT}")
        print("=" * 50)


# ================================================
# QUICK ACCESS INSTANCES (for backward compatibility)
# ================================================

# Create an instance for easier access
props = Properties()

# Export commonly used configurations
EXECUTION_MODE = Properties.EXECUTION_MODE
SPECIFIC_DATE = Properties.SPECIFIC_DATE
PROFILE_NAME = Properties.PROFILE_NAME
EXCLUDE_CAMPAIGN_NAMES = Properties.EXCLUDE_CAMPAIGN_NAMES
WEBAPP_URL = Properties.WEBAPP_URL
CLEAR_FILES = Properties.CLEAR_FILES

if __name__ == "__main__":
    # Test the properties when run directly
    Properties.print_current_config()

    print("\n🧪 Testing helper methods:")
    start_date, end_date, filter_type = Properties.get_date_range()
    print(f"📅 Date Range: {start_date} to {end_date} ({filter_type})")
    print(f"👤 Profile: {Properties.get_profile_name()}")

    print("\n⚙️ Configuration dictionaries generated successfully!")
