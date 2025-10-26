# Configuration file for ManyChat Data Extractor
# User preferences and settings

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# Timezone configuration to match ManyChat (UTC-4:00)
MANYCHAT_TIMEZONE = timezone(timedelta(hours=-4))


class ExtractionConfig:
    """Configuration class for ManyChat data extraction"""

    def __init__(self):
        # User preferences - modify these values as needed
        self.user_preferences = {
            # Date configuration
            "extraction_mode": "today",  # Options: "today", "yesterday", "date_range", "specific_date"
            "specific_date": None,  # Format: "2025-09-27" (when extraction_mode = "specific_date")
            "date_range_start": None,  # Format: "2025-09-20" (when extraction_mode = "date_range")
            "date_range_end": None,  # Format: "2025-09-27" (when extraction_mode = "date_range")
            # Profile configuration
            "profile_name": "auto",  # Options: "auto" (best available), "specific_profile_name"
            # Extraction settings
            "headless_mode": True,  # True for faster execution, False to see browser
            "verbose": True,  # True for detailed logs, False for minimal output
            # Output configuration
            "delete_json_after_csv": True,  # True to delete JSON files after CSV creation
            "csv_output_directory": "./csv_output/",  # Directory for CSV files
            "include_summary_csv": True,  # True to create summary CSV file
            "include_detailed_csv": True,  # True to create detailed CSV file
            # File cleanup configuration
            "clear_files": False,  # True to delete CSV/JSON files after successful upload to Google Sheets
            # Campaign filtering configuration
            "exclude_campaign_names": [  # List of campaign names to exclude from CSV
                # Example excluded campaigns (case-insensitive matching):
                # "Test Campaign",
                # "Draft Message",
                # "Internal Testing",
                # "Duplicate Campaign",
                # Add campaign names you want to exclude here
            ],
        }

        # Available profiles - will be populated dynamically
        self.available_profiles = []

        # Page configuration - loaded from page_ids.json
        self.pages_config = None

    def get_date_range(self) -> tuple[Optional[str], Optional[str], str]:
        """
        Get date range based on user preferences
        Returns: (start_date, end_date, filter_type)
        """
        mode = self.user_preferences["extraction_mode"]

        if mode == "today":
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

        elif mode == "yesterday":
            yesterday = (datetime.now(MANYCHAT_TIMEZONE) - timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )
            return yesterday, yesterday, "yesterday_only"

        elif mode == "specific_date":
            specific_date = self.user_preferences["specific_date"]
            if specific_date:
                return specific_date, specific_date, "specific_date"
            else:
                # Fallback to today if no specific date provided
                today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
                return today, today, "today_only"

        elif mode == "date_range":
            start_date = self.user_preferences["date_range_start"]
            end_date = self.user_preferences["date_range_end"]
            if start_date and end_date:
                return start_date, end_date, "custom_range"
            else:
                # Fallback to today if date range not properly configured
                today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
                return today, today, "today_only"

        else:
            # Default to today
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            return today, today, "today_only"

    def get_profile_name(self) -> str:
        """Get profile name based on user preferences"""
        profile = self.user_preferences["profile_name"]
        if profile == "auto":
            return None  # Will auto-select best available
        return profile

    def get_extraction_settings(self) -> Dict[str, Any]:
        """Get extraction settings"""
        return {
            "headless": self.user_preferences["headless_mode"],
            "verbose": self.user_preferences["verbose"],
            "profile_name": self.get_profile_name(),
        }

    def get_output_settings(self) -> Dict[str, Any]:
        """Get output settings"""
        return {
            "delete_json_after_csv": self.user_preferences["delete_json_after_csv"],
            "csv_output_directory": self.user_preferences["csv_output_directory"],
            "clear_files": self.user_preferences["clear_files"],
            "include_summary_csv": self.user_preferences["include_summary_csv"],
            "include_detailed_csv": self.user_preferences["include_detailed_csv"],
        }

    def get_exclude_campaign_names(self) -> list:
        """Get list of campaign names to exclude from CSV"""
        return self.user_preferences.get("exclude_campaign_names", [])

    def should_exclude_campaign(self, campaign_name: str) -> bool:
        """Check if a campaign should be excluded based on its name (case-insensitive)"""
        if not campaign_name:
            return False

        exclude_list = self.get_exclude_campaign_names()
        campaign_name_lower = campaign_name.lower().strip()

        for exclude_name in exclude_list:
            if exclude_name.lower().strip() in campaign_name_lower:
                return True

        return False

    def update_preferences(self, **kwargs):
        """Update user preferences"""
        for key, value in kwargs.items():
            if key in self.user_preferences:
                self.user_preferences[key] = value
            else:
                raise ValueError(f"Unknown preference: {key}")

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate configuration settings"""
        errors = []

        # Validate extraction mode
        valid_modes = ["today", "date_range", "specific_date"]
        if self.user_preferences["extraction_mode"] not in valid_modes:
            errors.append(f"Invalid extraction_mode. Must be one of: {valid_modes}")

        # Validate dates if date_range mode
        if self.user_preferences["extraction_mode"] == "date_range":
            start_date = self.user_preferences["date_range_start"]
            end_date = self.user_preferences["date_range_end"]

            if not start_date or not end_date:
                errors.append(
                    "date_range_start and date_range_end must be provided for date_range mode"
                )
            else:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    if start_dt > end_dt:
                        errors.append(
                            "date_range_start must be earlier than or equal to date_range_end"
                        )
                except ValueError:
                    errors.append("Invalid date format. Use YYYY-MM-DD format")

        # Validate specific date
        if self.user_preferences["extraction_mode"] == "specific_date":
            specific_date = self.user_preferences["specific_date"]
            if not specific_date:
                errors.append("specific_date must be provided for specific_date mode")
            else:
                try:
                    datetime.strptime(specific_date, "%Y-%m-%d")
                except ValueError:
                    errors.append("Invalid specific_date format. Use YYYY-MM-DD format")

        # Validate output directory
        csv_dir = self.user_preferences["csv_output_directory"]
        if csv_dir and not csv_dir.endswith("/"):
            self.user_preferences["csv_output_directory"] = csv_dir + "/"

        return len(errors) == 0, errors

    def print_current_config(self):
        """Print current configuration"""
        print("\n" + "=" * 50)
        print("📋 CURRENT EXTRACTION CONFIGURATION")
        print("=" * 50)

        mode = self.user_preferences["extraction_mode"]
        print(f"📅 Extraction Mode: {mode}")

        if mode == "today":
            today = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d")
            print(f"   Target Date: {today} (today UTC-4)")
        elif mode == "yesterday":
            yesterday = (datetime.now(MANYCHAT_TIMEZONE) - timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )
            print(f"   Target Date: {yesterday} (yesterday UTC-4)")
        elif mode == "specific_date":
            date = self.user_preferences["specific_date"]
            print(f"   Target Date: {date}")
        elif mode == "date_range":
            start = self.user_preferences["date_range_start"]
            end = self.user_preferences["date_range_end"]
            print(f"   Date Range: {start} to {end}")

        profile = self.user_preferences["profile_name"]
        print(f"👤 Profile: {profile}")
        print(f"🎯 Headless Mode: {self.user_preferences['headless_mode']}")
        print(f"📢 Verbose Output: {self.user_preferences['verbose']}")
        print(f"📁 CSV Output Dir: {self.user_preferences['csv_output_directory']}")
        print(
            f"🗑️  Delete JSON after CSV: {self.user_preferences['delete_json_after_csv']}"
        )

        print("=" * 50)


# Example configurations for different use cases
class PresetConfigs:
    """Preset configurations for common use cases"""

    @staticmethod
    def today_extraction():
        """Configuration for extracting today's data"""
        config = ExtractionConfig()
        config.update_preferences(
            extraction_mode="today", headless_mode=True, verbose=True
        )
        return config

    @staticmethod
    def yesterday_extraction():
        """Configuration for extracting yesterday's data"""
        config = ExtractionConfig()
        config.update_preferences(
            extraction_mode="yesterday", headless_mode=True, verbose=True
        )
        return config

    @staticmethod
    def specific_date_extraction(date: str):
        """Configuration for extracting specific date data"""
        config = ExtractionConfig()
        config.update_preferences(
            extraction_mode="specific_date",
            specific_date=date,
            headless_mode=True,
            verbose=True,
        )
        return config

    @staticmethod
    def date_range_extraction(start_date: str, end_date: str):
        """Configuration for extracting date range data"""
        config = ExtractionConfig()
        config.update_preferences(
            extraction_mode="date_range",
            date_range_start=start_date,
            date_range_end=end_date,
            headless_mode=True,
            verbose=True,
        )
        return config

    @staticmethod
    def silent_extraction():
        """Configuration for silent extraction (minimal output)"""
        config = ExtractionConfig()
        config.update_preferences(
            extraction_mode="today", headless_mode=True, verbose=False
        )
        return config


# Default configuration instance
default_config = ExtractionConfig()

# Usage examples (commented out):
"""
# Example 1: Today's data
config = PresetConfigs.today_extraction()

# Example 2: Specific date
config = PresetConfigs.specific_date_extraction("2025-09-27")

# Example 3: Date range
config = PresetConfigs.date_range_extraction("2025-09-20", "2025-09-27")

# Example 4: Custom configuration
config = ExtractionConfig()
config.update_preferences(
    extraction_mode="specific_date",
    specific_date="2025-09-27",
    profile_name="veera",
    headless_mode=False,  # Show browser window
    verbose=True
)
"""
