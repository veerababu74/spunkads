# Main execution file using Google Apps Script (No Google Cloud needed!)
# Author: GitHub Copilot
# This method requires NO Google Cloud Console setup!

import os
import sys
import json
import glob
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from data_extraction import MainExtractor, ManyChat_CSV_Processor
from properties import Properties, MANYCHAT_TIMEZONE


def generate_unique_filename(base_name: str, file_type: str, extension: str) -> str:
    """Generate unique filename with datetime stamp and 8-character unique identifier"""
    # Current datetime stamp in ManyChat timezone
    datetime_stamp = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y%m%d_%H%M%S")

    # Generate 8-character unique identifier
    import random
    import string

    unique_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Combine all parts
    filename = f"{base_name}_{file_type}_{datetime_stamp}_{unique_id}.{extension}"

    return filename


class GoogleAppsScriptUploader:
    """Upload data using Google Apps Script Web App - No Google Cloud needed!"""

    def __init__(self, webapp_url: str = None):
        self.webapp_url = webapp_url or Properties.WEBAPP_URL
        self.config = Properties.get_apps_script_config()

        # Update with provided webapp_url if given
        if webapp_url:
            self.webapp_url = webapp_url
            self.config["webapp_url"] = webapp_url

    def test_connection(self):
        """Test connection to Google Apps Script"""
        if not self.webapp_url:
            print("❌ No Web App URL configured")
            return False

        print(f"🔍 Testing connection to Google Apps Script...")
        print(f"URL: {self.webapp_url}")

        # Test with minimal data
        test_payload = {
            "sheet_name": "test",
            "headers": ["test_column"],
            "rows": [["test_data"]],
            "append": True,
        }

        try:
            response = requests.post(
                self.webapp_url,
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=self.config["timeout_seconds"],
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("✅ Connection test successful!")
                    print(f"📊 Spreadsheet URL: {result.get('spreadsheet_url', 'N/A')}")
                    return True
                else:
                    print(
                        f"❌ Apps Script error: {result.get('error', 'Unknown error')}"
                    )
                    return False
            else:
                print(f"❌ HTTP error: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except requests.exceptions.Timeout:
            print("❌ Request timeout - Apps Script may be slow to respond")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def upload_csv_data(self, csv_file_path: str, sheet_name: str):
        """Upload CSV data to Google Apps Script"""
        if not self.webapp_url:
            print("❌ No Web App URL configured")
            return False

        try:
            import pandas as pd

            df = pd.read_csv(csv_file_path)

            print(f"📤 Uploading {len(df)} rows to sheet '{sheet_name}'...")

            # Handle NaN values which are not JSON serializable
            df = df.fillna("")  # Replace NaN with empty strings

            # Convert any remaining problematic values to strings
            for col in df.columns:
                if df[col].dtype == "object":
                    df[col] = df[col].astype(str)
                elif df[col].dtype in ["float64", "int64"]:
                    # Ensure numeric columns don't have any remaining NaN
                    df[col] = df[col].fillna(0)

            # Prepare data for Apps Script
            data_payload = {
                "sheet_name": sheet_name,
                "headers": df.columns.tolist(),
                "rows": df.values.tolist(),
                "append": True,
            }

            # Send to Apps Script with retries
            for attempt in range(self.config["retry_attempts"]):
                try:
                    response = requests.post(
                        self.webapp_url,
                        json=data_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=self.config["timeout_seconds"],
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            print(
                                f"✅ Successfully uploaded {result.get('rows_added', len(df))} rows"
                            )
                            print(
                                f"📊 Total rows in sheet: {result.get('total_rows_in_sheet', 'N/A')}"
                            )
                            if result.get("spreadsheet_url"):
                                print(
                                    f"🔗 Spreadsheet: {result.get('spreadsheet_url')}"
                                )
                            return True
                        else:
                            print(
                                f"❌ Apps Script error: {result.get('error', 'Unknown error')}"
                            )
                            return False
                    else:
                        print(f"❌ HTTP error {response.status_code}: {response.text}")
                        if attempt < self.config["retry_attempts"] - 1:
                            print(f"🔄 Retrying... (attempt {attempt + 2})")
                            continue
                        return False

                except requests.exceptions.Timeout:
                    print(f"⏱️ Request timeout (attempt {attempt + 1})")
                    if attempt < self.config["retry_attempts"] - 1:
                        print("🔄 Retrying...")
                        continue
                    print("❌ All retry attempts failed due to timeout")
                    return False
                except Exception as e:
                    print(f"❌ Upload error: {e}")
                    if attempt < self.config["retry_attempts"] - 1:
                        print(f"🔄 Retrying... (attempt {attempt + 2})")
                        continue
                    return False

            return False

        except Exception as e:
            print(f"❌ Error preparing CSV data: {e}")
            return False

    def upload_all_csv_files(self, csv_directory: str = "csv_output"):
        """Upload all CSV files to Google Apps Script"""
        if not self.webapp_url:
            print("❌ No Web App URL configured!")
            print("📋 Please run setup_webapp_url() first")
            return False

        if not os.path.exists(csv_directory):
            print(f"❌ CSV directory '{csv_directory}' not found")
            return False

        csv_files = glob.glob(os.path.join(csv_directory, "*.csv"))
        if not csv_files:
            print(f"❌ No CSV files found in '{csv_directory}'")
            return False

        print(f"📤 Uploading {len(csv_files)} CSV files to Google Apps Script...")
        success_count = 0

        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            print(f"\n📄 Processing: {filename}")

            # Determine target sheet based on filename
            if "detailed" in filename.lower():
                sheet_name = self.config["sheets_mapping"]["detailed"]
            elif "summary" in filename.lower():
                sheet_name = self.config["sheets_mapping"]["summary"]
            else:
                sheet_name = self.config["sheets_mapping"]["detailed"]  # Default

            if self.upload_csv_data(csv_file, sheet_name):
                success_count += 1
            else:
                print(f"❌ Failed to upload {filename}")

        print(
            f"\n📊 Upload Summary: {success_count}/{len(csv_files)} files uploaded successfully"
        )
        return success_count > 0

    def setup_webapp_url(self):
        """Interactive setup for Web App URL"""
        print("\n🔧 GOOGLE APPS SCRIPT SETUP")
        print("=" * 50)

        if self.webapp_url:
            print(f"Current Web App URL: {self.webapp_url}")
            change = input("Do you want to change it? (y/n): ").lower().strip()
            if change != "y":
                return True

        print("\n📋 Setup Instructions:")
        print("1. Go to https://script.google.com/")
        print("2. Create new project or open existing one")
        print("3. Copy the Google Apps Script code from ManyChat_GoogleAppsScript.js")
        print("4. Deploy as Web App (Deploy > New Deployment)")
        print("5. Set Execute as 'Me' and access to 'Anyone'")
        print("6. Copy the Web App URL")

        print(f"\n📜 Apps Script file: ManyChat_GoogleAppsScript.js")

        while True:
            webapp_url = input("\n🔗 Enter your Web App URL: ").strip()
            if not webapp_url:
                print("❌ URL cannot be empty")
                continue

            if not webapp_url.startswith("https://script.google.com/"):
                print("⚠️ URL should start with 'https://script.google.com/'")
                confirm = input("Continue anyway? (y/n): ").lower().strip()
                if confirm != "y":
                    continue

            # Save and test the URL
            self.webapp_url = webapp_url
            self.config["webapp_url"] = webapp_url

            print(f"\n🔍 Testing connection...")
            if self.test_connection():
                print("✅ Setup complete!")
                return True
            else:
                print("❌ Connection test failed")
                retry = input("Try a different URL? (y/n): ").lower().strip()
                if retry != "y":
                    return False

        return False


class AppsScriptDataPipeline:
    """Main pipeline using Google Apps Script"""

    def __init__(self, webapp_url: str = None):
        self.properties = Properties()
        self.uploader = GoogleAppsScriptUploader(webapp_url or Properties.WEBAPP_URL)

        # Configure logging directory
        os.makedirs(Properties.LOGS_DIRECTORY, exist_ok=True)

    def run_full_pipeline(self) -> Dict[str, Any]:
        """Run complete pipeline with Apps Script upload"""
        print("🚀 ManyChat → Google Apps Script Pipeline")
        print("=" * 60)

        # Print current configuration
        Properties.print_current_config()

        results = {
            "extraction_success": False,
            "upload_success": False,
            "cleanup_success": False,
            "csv_files_processed": [],
            "errors": [],
        }

        try:
            # Check if Web App URL is configured
            if not self.uploader.webapp_url:
                print("⚙️ Web App URL not configured. Starting setup...")
                if not self.uploader.setup_webapp_url():
                    results["errors"].append("Web App URL setup failed")
                    return results

            # Step 1: Extract data
            print("\n📡 Step 1: Extracting ManyChat data...")
            extraction_config = Properties.get_extraction_config()
            extractor = MainExtractor(extraction_config)
            extraction_results = extractor.run_extraction()

            if not extraction_results["success"]:
                results["errors"].extend(extraction_results.get("errors", []))
                return results

            results["extraction_success"] = True
            results["csv_files_processed"] = extraction_results.get("csv_files", [])

            print(
                f"✅ Extraction completed: {len(results['csv_files_processed'])} CSV files"
            )

            # Step 2: Upload via Apps Script
            print("\n📤 Step 2: Uploading via Google Apps Script...")
            upload_success = self.uploader.upload_all_csv_files()
            results["upload_success"] = upload_success

            if upload_success:
                print("✅ Upload completed successfully")

                # Step 3: Cleanup (based on configuration)
                should_cleanup = Properties.CLEAR_FILES

                if should_cleanup:
                    print("\n🧹 Step 3: Cleaning up temporary files...")
                    cleanup_success = self.cleanup_files()
                    results["cleanup_success"] = cleanup_success
                else:
                    print("\n💾 Step 3: Keeping files (cleanup disabled in config)")
                    print("📁 Files preserved in csv_output/ and json_output/")
                    results["cleanup_success"] = True  # Not cleaning is also "success"
            else:
                print("⚠️ Upload failed - keeping files for manual upload")
                results["errors"].append("Google Apps Script upload failed")

        except Exception as e:
            error_msg = f"Pipeline error: {e}"
            print(f"❌ {error_msg}")
            results["errors"].append(error_msg)

        return results

    def cleanup_files(self) -> bool:
        """Clean up temporary files based on configuration settings"""
        try:
            # Check if cleanup is enabled in configuration
            if not Properties.CLEAR_FILES:
                print("🔒 File cleanup disabled in configuration")
                return True

            # Clean CSV files
            csv_dir = Properties.CSV_OUTPUT_DIRECTORY
            csv_files = glob.glob(os.path.join(csv_dir, "*.csv"))

            deleted_count = 0
            for csv_file in csv_files:
                try:
                    os.remove(csv_file)
                    print(f"🗑️ Deleted: {os.path.basename(csv_file)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Could not delete {csv_file}: {e}")

            # Clean JSON files
            json_dir = "json_output"
            if os.path.exists(json_dir):
                json_files = glob.glob(os.path.join(json_dir, "*.json"))
                for json_file in json_files:
                    try:
                        os.remove(json_file)
                        print(f"🗑️ Deleted: {os.path.basename(json_file)}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"❌ Could not delete {json_file}: {e}")

            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} files")
            else:
                print("ℹ️ No files to clean up")
            return True

        except Exception as e:
            print(f"❌ Cleanup error: {e}")
            return False


def main():
    """Main execution function"""
    print("🔥 ManyChat Data Pipeline - Google Apps Script Integration")
    print("=" * 70)
    print("📋 No Google Cloud Console needed!")
    print("=" * 70)

    try:
        # Create and run pipeline using Properties
        pipeline = AppsScriptDataPipeline()
        results = pipeline.run_full_pipeline()

        # Save execution log
        log_filename = generate_unique_filename("apps_script", "log", "json")
        log_data = {
            "timestamp": datetime.now(MANYCHAT_TIMEZONE).isoformat(),
            "method": "google_apps_script",
            "config": Properties.get_apps_script_config(),
            "results": results,
        }

        log_file = os.path.join(Properties.LOGS_DIRECTORY, log_filename)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        # Print summary
        print("\n" + "=" * 70)
        print("🏁 PIPELINE EXECUTION SUMMARY")
        print("=" * 70)

        status_map = {True: "✅ SUCCESS", False: "❌ FAILED"}
        print(f"📡 Data Extraction: {status_map[results['extraction_success']]}")
        print(f"📤 Apps Script Upload: {status_map[results['upload_success']]}")
        print(f"🧹 File Cleanup: {status_map[results['cleanup_success']]}")

        if results["errors"]:
            print("\n❌ ERRORS:")
            for error in results["errors"]:
                print(f"   • {error}")

        print(f"\n📊 Files Processed: {len(results['csv_files_processed'])}")
        print(f"💾 Execution Log: {log_file}")

        if results["extraction_success"] and results["upload_success"]:
            print("\n🎉 Pipeline completed successfully!")
            print("📊 Check your Google Sheet for new data!")
            return 0
        else:
            print("\n💥 Pipeline completed with errors!")
            return 1

    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    input("\nPress Enter to exit...")
    sys.exit(exit_code)
