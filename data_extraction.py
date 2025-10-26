# Main ManyChat Data Extractor with CSV Export
# Extracts data based on user preferences and converts to CSV

import os
import json
import csv
import glob
import random
import string
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd

# Import our custom modules
from app_ultra_fast_oop import ManyChatExtractorOOP
from properties import Properties, MANYCHAT_TIMEZONE


def generate_unique_filename(base_name: str, file_type: str, extension: str) -> str:
    """Generate unique filename with datetime stamp and 8-character unique identifier"""
    # Current datetime stamp in ManyChat timezone
    datetime_stamp = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y%m%d_%H%M%S")

    # Generate 8-character unique identifier
    unique_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Combine all parts
    filename = f"{base_name}_{file_type}_{datetime_stamp}_{unique_id}.{extension}"

    return filename


def generate_post_url(page_id: str, post_id: str) -> str:
    """Generate ManyChat post URL from page_id and post_id"""
    # Ensure page_id has 'fb' prefix
    if not str(page_id).startswith("fb"):
        page_id = f"fb{page_id}"

    # Clean post_id (remove any prefixes if present)
    clean_post_id = str(post_id).replace("post_", "").replace("fb", "")

    # Generate the URL
    post_url = f"https://app.manychat.com/{page_id}/posting/history/{clean_post_id}"

    return post_url


class ManyChat_CSV_Processor:
    """Handles JSON to CSV conversion for ManyChat data"""

    def __init__(self, config: dict):
        self.config = config
        self.output_settings = Properties.get_output_settings()

        # Get the extraction date to match ManyChat data
        start_date, end_date, filter_type = Properties.get_date_range()
        self.extraction_date = start_date  # Use the same date as ManyChat extraction

        # Load page data from page_ids.json
        self.page_data = self.load_page_data()

        # Create output directory if it doesn't exist
        self.csv_dir = self.output_settings["csv_output_directory"]
        if not os.path.exists(self.csv_dir):
            os.makedirs(self.csv_dir)

        # Create json output directory for consolidated data
        self.json_dir = self.output_settings["json_output_directory"]
        if not os.path.exists(self.json_dir):
            os.makedirs(self.json_dir)

    def load_page_data(self) -> dict:
        """Load page data from page_ids.json file"""
        try:
            page_ids_file = os.path.join(os.path.dirname(__file__), "page_ids.json")
            with open(page_ids_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Store full page data for API calls and revenue lookup
            self.pages_full_data = data.get("pages", [])

            # Create a lookup dictionary by page_id for quick access
            page_lookup = {}
            for page in data.get("pages", []):
                page_id = str(page.get("id", "")).replace("fb", "")
                page_lookup[page_id] = {
                    "account_name": page.get("account_name", "Unknown"),
                    "user": page.get("user", "Unknown"),
                    "tl": page.get("tl", "Unknown"),
                    "name": page.get("name", "Unknown"),
                }

            print(
                f"📊 Loaded {len(page_lookup)} page configurations from page_ids.json"
            )

            # Initialize empty revenue data - will be populated after ManyChat extraction
            self.revenue_data = {}
            self.revenue_timestamp = "N/A"

            return page_lookup
        except Exception as e:
            print(f"⚠️ Warning: Could not load page_ids.json: {e}")
            self.pages_full_data = []
            self.revenue_data = {}
            self.revenue_timestamp = "N/A"
            return {}

    def fetch_revenue_for_extracted_pages(self, extracted_page_ids: list) -> dict:
        """Fetch revenue data from SpunkStats API for pages that were actually extracted AND unmatched utm_s sources"""
        print(
            "🔄 Fetching revenue data from SpunkStats API for extracted pages and unmatched utm_s sources..."
        )
        revenue_data = {}

        # Match extracted page IDs with page_ids.json data
        pages_to_process = []
        known_page_names = (
            set()
        )  # Track ALL page names from page_ids.json to identify unmatched utm_s

        for page in self.pages_full_data:
            page_id = str(page.get("id", "")).replace("fb", "")
            page_name = page.get("name", "")

            # Add ALL page names from page_ids.json as "known" (to exclude from unmatched utm_s)
            known_page_names.add(page_name)

            if page_id in extracted_page_ids:
                pages_to_process.append(page)
                if self.config.get("verbose", True):
                    print(f"   📋 Found match: {page_name} (ID: {page_id})")

        # Store known page names for later filtering
        self.known_page_names = known_page_names

        if self.config.get("verbose", True):
            print(f"   📋 Total pages in page_ids.json: {len(self.pages_full_data)}")
            print(f"   📋 Actually extracted pages: {len(pages_to_process)}")
            print(
                f"   📋 ALL known page names (to exclude from unmatched): {len(known_page_names)}"
            )
            print(
                f"   📋 Sample known page names: {sorted(list(known_page_names))[:10]}"
            )

        if not pages_to_process and not known_page_names:
            print("⚠️ No page data available for SpunkStats API calls")
            return revenue_data

        # Get shared SpunkStats API credentials from Properties
        spunkstats_config = Properties.get_spunkstats_config()
        user_id = spunkstats_config.get("user_id", "")
        api_key = spunkstats_config.get("api_key", "")

        if not user_id or not api_key:
            print("⚠️ Missing SpunkStats API credentials in properties.py")
            for page in self.pages_full_data:
                page_name = page.get("name", "")
                revenue_data[page_name] = {
                    "revenue": "0.00",
                    "timestamp": "N/A",
                    "offer": "",
                    "utm_medium": "",
                    "conversion_count": "",
                    "clicks": "",
                    "leads": "",
                }
            return revenue_data

        try:
            if self.config.get("verbose", True):
                print(
                    f"   🌐 Calling SpunkStats API once for all pages (user: {user_id[:8]}...)"
                )

            # Make a single API call with shared credentials
            api_revenue_data = self.call_spunkstats_api(user_id, api_key)

            if api_revenue_data:
                if self.config.get("verbose", True):
                    print(
                        f"   📊 Processing API response for ALL {len(self.pages_full_data)} pages in page_ids.json..."
                    )
                    # Show available utm_s values in API response for debugging
                    data_array = api_revenue_data.get("data", [])
                    if data_array:
                        unique_utm_s = set()
                        for row in data_array[:50]:  # Sample first 50 rows
                            if isinstance(row, dict):
                                utm_s = str(row.get("utm_s", "")).strip()
                                if utm_s:
                                    unique_utm_s.add(utm_s)
                        print(
                            f"   📋 Sample utm_s values in API response: {list(unique_utm_s)[:10]}"
                        )

                # Extract revenue for each page from the single API response
                # Process ALL pages from page_ids.json, not just extracted ones
                for page in self.pages_full_data:
                    page_name = page.get("name", "")

                    revenue_info = self.extract_revenue_and_timestamp_for_page(
                        api_revenue_data, page_name
                    )

                    if revenue_info:
                        revenue_data[page_name] = revenue_info
                        if self.config.get("verbose", True):
                            revenue = revenue_info.get("revenue", "0.00")
                            conversions = revenue_info.get("conversion_count", "0")
                            print(
                                f"   💰 {page_name}: ${revenue} (Conversions: {conversions}, Date: {revenue_info.get('timestamp', 'N/A')})"
                            )
                    else:
                        # Set default empty values when page not found in API response
                        revenue_data[page_name] = {
                            "revenue": "0.00",
                            "timestamp": "N/A",
                            "offer": "",
                            "utm_medium": "",
                            "conversion_count": "",
                            "clicks": "",
                            "leads": "",
                        }
                        if self.config.get("verbose", True):
                            print(f"   💰 {page_name}: $0.00 (not found in response)")

                # NEW: Extract unmatched utm_s sources from API response
                unmatched_revenue_data = self.extract_unmatched_utm_sources(
                    api_revenue_data
                )
                revenue_data.update(unmatched_revenue_data)
            else:
                # API call failed, set all pages to default empty values
                for page in self.pages_full_data:
                    page_name = page.get("name", "")
                    revenue_data[page_name] = {
                        "revenue": "0.00",
                        "timestamp": "N/A",
                        "offer": "",
                        "utm_medium": "",
                        "conversion_count": "",
                        "clicks": "",
                        "leads": "",
                    }
                if self.config.get("verbose", True):
                    print(f"   💰 API call failed - all pages set to default values")

        except Exception as e:
            print(f"❌ Error fetching revenue data: {e}")
            # Set all pages to default empty values on error
            for page in self.pages_full_data:
                page_name = page.get("name", "")
                revenue_data[page_name] = {
                    "revenue": "0.00",
                    "timestamp": "N/A",
                    "offer": "",
                    "utm_medium": "",
                    "conversion_count": "",
                    "clicks": "",
                    "leads": "",
                }

        print(
            f"✅ Revenue data fetched for {len(revenue_data)} total entries (matched + unmatched utm_s)"
        )
        return revenue_data

    def extract_unmatched_utm_sources(self, api_data: dict) -> dict:
        """Extract revenue data for utm_s sources that don't match any known page names"""
        if self.config.get("verbose", True):
            print("   🔍 Extracting unmatched utm_s sources from API response...")

        unmatched_revenue = {}
        data_array = api_data.get("data", [])

        if self.config.get("verbose", True):
            # Show sample utm_s values for debugging
            sample_utm_s = set()
            for row in data_array[:50]:  # Sample first 50 rows
                if isinstance(row, dict):
                    utm_s = str(row.get("utm_s", "")).strip()
                    if utm_s:
                        sample_utm_s.add(utm_s)
            print(
                f"   📋 Sample utm_s values in API: {sorted(list(sample_utm_s))[:10]}"
            )
            print(
                f"   📋 Known page names to exclude: {sorted(list(self.known_page_names))}"
            )

        # Collect all unique utm_s values from API response
        utm_s_revenue_map = {}
        skipped_known = set()
        skipped_empty = 0

        for row in data_array:
            if isinstance(row, dict):
                utm_s = str(row.get("utm_s", "")).strip()

                # Skip empty utm_s
                if not utm_s:
                    skipped_empty += 1
                    continue

                # Skip known page names (already processed)
                if utm_s in self.known_page_names:
                    skipped_known.add(utm_s)
                    continue

                # Initialize if not seen before
                if utm_s not in utm_s_revenue_map:
                    utm_s_revenue_map[utm_s] = {
                        "total_revenue": 0.00,
                        "timestamp": "N/A",
                        "row_count": 0,
                    }

                # Add revenue for this utm_s
                try:
                    revenue = float(row.get("a", 0))
                except (ValueError, TypeError):
                    revenue = 0.00

                utm_s_revenue_map[utm_s]["total_revenue"] += revenue
                utm_s_revenue_map[utm_s]["row_count"] += 1

                # Capture timestamp from first occurrence
                if utm_s_revenue_map[utm_s]["timestamp"] == "N/A":
                    utm_s_revenue_map[utm_s]["timestamp"] = str(row.get("dt", "N/A"))

        # Convert to revenue_data format (simplified - no extra columns for unmatched)
        for utm_s, data in utm_s_revenue_map.items():
            if data["total_revenue"] > 0 or self.config.get(
                "include_zero_revenue", True
            ):
                unmatched_revenue[utm_s] = {
                    "revenue": f"{data['total_revenue']:.2f}",
                    "timestamp": data["timestamp"],
                    # No extra columns for unmatched utm_s sources
                    "offer": "",
                    "utm_medium": "",
                    "conversion_count": "",
                    "clicks": "",
                    "leads": "",
                }

                if self.config.get("verbose", True):
                    print(
                        f"   🆕 Unmatched utm_s '{utm_s}': ${data['total_revenue']:.2f} from {data['row_count']} rows"
                    )

        if self.config.get("verbose", True):
            print(
                f"   ⏭️  Skipped {len(skipped_known)} known page names: {sorted(list(skipped_known))}"
            )
            print(f"   ⏭️  Skipped {skipped_empty} empty utm_s values")
            print(
                f"   ✅ Found {len(unmatched_revenue)} unmatched utm_s sources with revenue data"
            )

        return unmatched_revenue

    def add_unmatched_utm_summary_rows(
        self, existing_summary_data: List[Dict]
    ) -> List[Dict]:
        """Add summary rows for unmatched utm_s sources from SpunkStats API"""
        enhanced_summary_data = existing_summary_data.copy()

        if not hasattr(self, "known_page_names") or not self.revenue_data:
            return enhanced_summary_data

        if self.config.get("verbose", True):
            print("   📊 Adding unmatched utm_s sources to summary data...")

        # Current timestamp in ManyChat timezone
        timestamp = datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S UTC-4")

        # Find unmatched utm_s sources in revenue_data
        for utm_s, revenue_info in self.revenue_data.items():
            # Skip if this utm_s is already a known page name
            if utm_s in self.known_page_names:
                continue

            # Skip if revenue is 0 (optional - can be configured)
            revenue_amount = float(revenue_info.get("revenue", "0"))
            if revenue_amount <= 0 and not self.config.get(
                "include_zero_revenue", True
            ):
                continue

            # Create summary row for unmatched utm_s
            unmatched_summary_row = {
                "pagename": utm_s,  # Use utm_s as page name
                "page_id": f"utm_{utm_s}",  # Generate unique page_id
                "timestamp": timestamp,
                "totalCampaigns": 0,  # No campaign data for unmatched sources
                "totalSent": 0,
                "totalDelivered": 0,
                "totalRead": 0,
                "totalClicked": 0,
                "account_name": "SpunkStats Only",  # Indicate this is from SpunkStats only
                "user": "",
                "tl": "",
                "revenue": revenue_info.get("revenue", "0.00"),
                "revenue_timestamp": revenue_info.get("timestamp", "N/A"),
            }

            enhanced_summary_data.append(unmatched_summary_row)

            if self.config.get("verbose", True):
                print(
                    f"   ➕ Added unmatched utm_s '{utm_s}': ${revenue_info.get('revenue', '0.00')}"
                )

        if self.config.get("verbose", True):
            original_count = len(existing_summary_data)
            new_count = len(enhanced_summary_data)
            added_count = new_count - original_count
            print(
                f"   ✅ Summary enhanced: {original_count} + {added_count} = {new_count} total rows"
            )

        return enhanced_summary_data

    def call_spunkstats_api(self, user_id: str, api_key: str) -> dict:
        """Call SpunkStats API with authentication"""
        url = "https://dashboard.spunkstats.net/api/v1/SPK/report/yesterday/yesterday/?groupBy=date,offer,utm_source,utm_medium&limit=1000000"

        headers = {
            "x-api-key": api_key,
            "x-user-id": user_id,
            "Content-Type": "application/json",
        }

        try:
            if self.config.get("verbose", True):
                print(f"   🌐 Calling SpunkStats API for user {user_id[:8]}...")

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            # New API returns array directly, not wrapped in status object
            if isinstance(data, list):
                # Add detailed debugging of API response
                if self.config.get("verbose", True):
                    print(f"   📊 API Response: {len(data)} rows of data")
                    if data:
                        print(
                            f"   🔍 Sample data structure: {data[0] if len(data) > 0 else 'No data'}"
                        )
                        print(f"   📝 utm_s and revenue in response:")
                        for i, row in enumerate(data[:10]):  # Show first 10 rows
                            if isinstance(row, dict):
                                print(
                                    f"     Row {i}: Date={row.get('dt')} | utm_s='{row.get('utm_s')}' | Revenue={row.get('a')}"
                                )
                        if len(data) > 10:
                            print(f"     ... and {len(data) - 10} more rows")
                return {"data": data, "status": 200}
            else:
                print(f"⚠️ SpunkStats API returned unexpected format: {type(data)}")
                return {}

        except requests.exceptions.RequestException as e:
            print(f"❌ SpunkStats API request failed: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse SpunkStats API response: {e}")
            return {}

    def extract_revenue_and_timestamp_for_page(
        self, api_data: dict, page_name: str
    ) -> dict:
        """Extract revenue and enhanced data for specific page from SpunkStats API response"""
        try:
            data_array = api_data.get("data", [])

            if self.config.get("verbose", True):
                print(f"   🔍 Searching for '{page_name}' in {len(data_array)} rows")

            # Collect all revenue values and additional data for this page name
            total_revenue = 0.00
            total_conversions = 0
            total_clicks = 0
            total_leads = 0
            timestamp = "N/A"
            offer_name = ""
            utm_medium = ""
            matching_rows = []

            # Look for all matching page names in the data array
            for i, row in enumerate(data_array):
                if isinstance(row, dict):
                    # New API format: row is a dictionary with keys like 'dt', 'utm_s', 'a', etc.
                    utm_s = str(row.get("utm_s", "")).strip()

                    if self.config.get("verbose", True) and i < 10:
                        print(
                            f"     Row {i}: utm_s='{utm_s}' | Date='{row.get('dt')}' | Revenue='{row.get('a')}' | Offer='{row.get('o', '')}'"
                        )

                    # Check if the page name matches utm_s
                    if utm_s == page_name:
                        # Revenue is in the 'a' key (Total payout to the affiliate)
                        try:
                            revenue = float(row.get("a", 0))
                        except (ValueError, TypeError):
                            revenue = 0.00

                        total_revenue += revenue

                        # Additional SpunkStatus API fields
                        try:
                            conversions = int(row.get("c", 0))  # Conversion count
                            clicks = int(row.get("cl", 0))  # Click count
                            leads = int(row.get("l", 0))  # Lead count
                        except (ValueError, TypeError):
                            conversions = clicks = leads = 0

                        total_conversions += conversions
                        total_clicks += clicks
                        total_leads += leads

                        # Capture additional metadata (use first match found)
                        if not offer_name:
                            offer_name = str(row.get("o", ""))  # Offer name
                        if not utm_medium:
                            utm_medium = str(row.get("utm_m", ""))  # UTM medium

                        # Date is in the 'dt' key
                        if timestamp == "N/A":
                            timestamp = str(row.get("dt", "N/A"))

                        matching_rows.append(
                            {
                                "row": i,
                                "revenue": revenue,
                                "conversions": conversions,
                                "clicks": clicks,
                                "leads": leads,
                                "data": row,
                            }
                        )

                        if self.config.get("verbose", True):
                            print(
                                f"   ✅ MATCH FOUND! '{page_name}' matches utm_s '{utm_s}' at row {i}: revenue=${revenue}, conversions={conversions}, clicks={clicks}, leads={leads}"
                            )

            if matching_rows:
                if self.config.get("verbose", True):
                    print(
                        f"   📊 Total for {page_name}: Revenue=${total_revenue:.2f}, Conversions={total_conversions}, Clicks={total_clicks}, Leads={total_leads} from {len(matching_rows)} rows"
                    )
                    print(f"   📅 Using timestamp: {timestamp}")

                return {
                    "revenue": f"{total_revenue:.2f}",
                    "timestamp": timestamp,
                    "offer": offer_name,
                    "utm_medium": utm_medium,
                    "conversion_count": str(total_conversions),
                    "clicks": str(total_clicks),
                    "leads": str(total_leads),
                }

            # If no match found, return None to indicate not found
            if self.config.get("verbose", True):
                print(f"   ❌ NO MATCH: '{page_name}' not found in any utm_s values")
                print(
                    f"     Available utm_s values (first 5): {[row.get('utm_s', 'Invalid') if isinstance(row, dict) else 'Invalid' for row in data_array[:5]]}"
                )
            return None

        except Exception as e:
            if self.config.get("verbose", True):
                print(f"⚠️ Error extracting revenue for {page_name}: {e}")
            return None

    def get_page_details(self, page_id: str) -> dict:
        """Get page details (account_name, user, tl, revenue info) for a given page_id"""
        clean_page_id = str(page_id).replace("fb", "")

        # Handle special utm_* page IDs for unmatched sources
        if clean_page_id.startswith("utm_"):
            utm_s = clean_page_id.replace("utm_", "")
            return {
                "account_name": "SpunkStats Only",
                "user": "",
                "tl": "",
                "name": utm_s,
                "revenue_info": self.revenue_data.get(
                    utm_s,
                    {
                        "revenue": "0.00",
                        "timestamp": "N/A",
                        "offer": "",
                        "utm_medium": "",
                        "conversion_count": "",
                        "clicks": "",
                        "leads": "",
                    },
                ),
            }

        page_details = self.page_data.get(
            clean_page_id,
            {
                "account_name": "Unknown",
                "user": "Unknown",
                "tl": "Unknown",
                "name": "Unknown",
            },
        )

        # Add revenue data and enhanced info from SpunkStats API
        page_name = page_details.get("name", "Unknown")
        revenue_info = self.revenue_data.get(
            page_name, {"revenue": "0.00", "timestamp": "N/A"}
        )

        # Handle enhanced revenue info format
        if isinstance(revenue_info, dict):
            # New enhanced format with additional SpunkStatus fields
            page_details["revenue_info"] = revenue_info
            page_details["revenue"] = revenue_info.get("revenue", "0.00")
            page_details["revenue_timestamp"] = revenue_info.get("timestamp", "N/A")
        else:
            # Fallback for old string format
            page_details["revenue"] = str(revenue_info)
            page_details["revenue_timestamp"] = getattr(
                self, "revenue_timestamp", "N/A"
            )
            # Create empty enhanced info for consistency
            page_details["revenue_info"] = {
                "revenue": str(revenue_info),
                "timestamp": getattr(self, "revenue_timestamp", "N/A"),
                "offer": "",
                "utm_medium": "",
                "conversion_count": "",
                "clicks": "",
                "leads": "",
            }

        return page_details

    def save_consolidated_json(
        self, all_data: List[Dict], data_type: str = "consolidated"
    ) -> str:
        """Save consolidated data as JSON file"""
        filename = generate_unique_filename("manychat", data_type, "json")
        filepath = os.path.join(self.json_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False, default=str)

            print(f"💾 Saved consolidated JSON: {filename}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving JSON file: {e}")
            return ""

    def process_json_to_csv(self, json_files: List[str]) -> Dict[str, Any]:
        """
        Convert JSON files to CSV format
        Returns: Dictionary with results and file paths
        """
        results = {
            "detailed_csv_files": [],
            "summary_csv_files": [],
            "total_campaigns": 0,
            "total_pages": 0,
            "processed_files": [],
            "errors": [],
        }

        all_detailed_data = []
        all_summary_data = []

        for json_file in json_files:
            try:
                print(f"\n📄 Processing: {json_file}")

                # Read JSON data
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract detailed and summary data
                detailed_data, summary_data = self.extract_data_from_json(
                    data, json_file
                )

                all_detailed_data.extend(detailed_data)
                all_summary_data.extend(summary_data)

                results["processed_files"].append(json_file)

            except Exception as e:
                error_msg = f"Error processing {json_file}: {e}"
                results["errors"].append(error_msg)
                print(f"❌ {error_msg}")

        # Save consolidated JSON files
        json_files = []
        if all_detailed_data:
            detailed_json = self.save_consolidated_json(all_detailed_data, "detailed")
            if detailed_json:
                json_files.append(detailed_json)

        if all_summary_data:
            summary_json = self.save_consolidated_json(all_summary_data, "summary")
            if summary_json:
                json_files.append(summary_json)

        results["json_files"] = json_files

        # Generate CSV files
        if all_detailed_data and self.output_settings["include_detailed_csv"]:
            detailed_file = self.create_detailed_csv(all_detailed_data)
            results["detailed_csv_files"].append(detailed_file)

        if all_summary_data and self.output_settings["include_summary_csv"]:
            # Add unmatched utm_s sources as additional summary rows
            enhanced_summary_data = self.add_unmatched_utm_summary_rows(
                all_summary_data
            )
            summary_file = self.create_summary_csv(enhanced_summary_data)
            results["summary_csv_files"].append(summary_file)

        results["total_campaigns"] = len(all_detailed_data)
        results["total_pages"] = len(set(item["page_id"] for item in all_detailed_data))

        return results

    def extract_data_from_json(
        self, data: Dict, source_file: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract detailed and summary data from JSON"""
        detailed_data = []
        summary_data = []

        # Handle different JSON structures
        if "_extraction_summary" in data:
            # Handle multi-page extraction format
            extraction_summary = data["_extraction_summary"]

            for page_name, page_data in data.items():
                if page_name.startswith("_"):  # Skip metadata
                    continue

                if "posts" in page_data and "page_info" in page_data:
                    page_info = page_data["page_info"]
                    posts = page_data["posts"]

                    # Process detailed data for each post
                    for post in posts:
                        detailed_row = self.create_detailed_row(page_info, post)
                        if detailed_row:
                            detailed_data.append(detailed_row)

                    # Create summary data for this page
                    summary_row = self.create_summary_row(page_info, posts)
                    if summary_row:
                        summary_data.append(summary_row)

        else:
            # Handle single page format or direct posts array
            posts = data.get("posts", [])
            if isinstance(data, list):
                posts = data

            # Try to extract page info from filename or data
            page_name = "Unknown"
            page_id = "unknown"

            for post in posts:
                detailed_row = self.create_detailed_row(
                    {"page_name": page_name, "page_id": page_id}, post
                )
                if detailed_row:
                    detailed_data.append(detailed_row)

            if posts:
                summary_row = self.create_summary_row(
                    {"page_name": page_name, "page_id": page_id}, posts
                )
                if summary_row:
                    summary_data.append(summary_row)

        return detailed_data, summary_data

    def create_detailed_row(self, page_info: Dict, post: Dict) -> Optional[Dict]:
        """Create detailed CSV row from post data"""
        try:
            # Extract page information
            page_name = page_info.get("page_name", "Unknown")
            page_id = str(page_info.get("page_id", "")).replace("fb", "")

            # Extract post information
            post_id = post.get("post_id", post.get("id", ""))

            # Get campaign name from multiple possible locations
            name = ""
            if "flow" in post and "name" in post["flow"]:
                name = post["flow"]["name"]
            elif "name" in post:
                name = post["name"]
            elif "preview" in post:
                name = post["preview"]
            elif "namespace" in post:
                name = post["namespace"]

            # Check if this campaign should be excluded
            if name.lower() in [
                exclude.lower() for exclude in Properties.EXCLUDE_CAMPAIGN_NAMES
            ]:
                if self.config.get("verbose", True):
                    print(f"   [EXCLUDED] Campaign '{name}' matches exclude list")
                return None

            timestamp = ""
            time_scheduled = ""

            # Handle timestamp - convert to ManyChat timezone (UTC-4)
            if "timestamp" in post:
                timestamp = datetime.fromtimestamp(
                    post["timestamp"], tz=MANYCHAT_TIMEZONE
                ).strftime("%Y-%m-%d %H:%M:%S UTC-4")

            if "scheduled_time" in post:
                time_scheduled = datetime.fromtimestamp(
                    post["scheduled_time"], tz=MANYCHAT_TIMEZONE
                ).strftime("%Y-%m-%d %H:%M:%S UTC-4")
            elif "created_at" in post:
                time_scheduled = datetime.fromtimestamp(
                    post["created_at"], tz=MANYCHAT_TIMEZONE
                ).strftime("%Y-%m-%d %H:%M:%S UTC-4")
            else:
                time_scheduled = timestamp

            # Extract statistics
            stats = post.get("stats", {})
            sent = stats.get("sent", 0) or 0
            delivered = stats.get("delivered", 0) or 0
            read = (stats.get("read", 0) or 0) or (stats.get("opened", 0) or 0)
            clicked = stats.get("clicked", 0) or 0

            # Get page details from page_ids.json
            page_details = self.get_page_details(page_id)
            account_name = page_details["account_name"]
            user = page_details["user"]
            tl = page_details["tl"]

            # Extract status
            status = post.get("status", "unknown")
            if status == "sent":
                status = "published"

            # Generate post URL
            post_url = generate_post_url(page_id, post_id)

            return {
                "pagename": page_name,
                "page_id": page_id,
                "campaign_name": name,
                "timestamp": timestamp,
                "time_scheduled": time_scheduled,
                "sent": sent,
                "delivered": delivered,
                "read": read,
                "clicked": clicked,
                "account_name": account_name,
                "user": user,
                "tl": tl,
                "post_id": post_id,
                "post_url": post_url,
                "status": status,
            }

        except Exception as e:
            print(f"Warning: Error creating detailed row: {e}")
            return None

    def create_summary_row(self, page_info: Dict, posts: List[Dict]) -> Optional[Dict]:
        """Create summary CSV row from page data"""
        try:
            page_name = page_info.get("page_name", "Unknown")
            page_id = page_info.get("page_id", "unknown")

            # Make sure page_id has 'fb' prefix for summary
            if not str(page_id).startswith("fb"):
                page_id = f"fb{page_id}"

            # Calculate totals
            total_campaigns = len(posts)
            total_sent = 0
            total_delivered = 0
            total_read = 0
            total_clicked = 0

            for post in posts:
                stats = post.get("stats", {})
                total_sent += stats.get("sent", 0) or 0
                total_delivered += stats.get("delivered", 0) or 0
                total_read += (stats.get("read", 0) or 0) or (
                    stats.get("opened", 0) or 0
                )
                total_clicked += stats.get("clicked", 0) or 0

            # Get page details from page_ids.json
            page_details = self.get_page_details(page_id)
            account_name = page_details["account_name"]
            user = page_details["user"]
            tl = page_details["tl"]

            # Get revenue data from SpunkStatus API - enhanced with additional fields
            revenue_info = page_details.get("revenue_info", {})
            revenue = (
                revenue_info.get("revenue", "0.00")
                if isinstance(revenue_info, dict)
                else page_details.get("revenue", "0.00")
            )
            revenue_timestamp = (
                revenue_info.get("timestamp", "N/A")
                if isinstance(revenue_info, dict)
                else page_details.get("revenue_timestamp", "N/A")
            )

            # Current timestamp in ManyChat timezone
            timestamp = datetime.now(MANYCHAT_TIMEZONE).strftime(
                "%Y-%m-%d %H:%M:%S UTC-4"
            )

            return {
                "pagename": page_name,
                "page_id": page_id,
                "timestamp": timestamp,
                "totalCampaigns": total_campaigns,
                "totalSent": total_sent,
                "totalDelivered": total_delivered,
                "totalRead": total_read,
                "totalClicked": total_clicked,
                "account_name": account_name,
                "user": user,
                "tl": tl,
                "revenue": revenue,
                "revenue_timestamp": revenue_timestamp,
            }

        except Exception as e:
            print(f"Warning: Error creating summary row: {e}")
            return None

    def sanitize_csv_data(self, data: List[Dict]) -> List[Dict]:
        """Sanitize data to prevent NaN and None values in CSV"""
        sanitized_data = []
        for row in data:
            sanitized_row = {}
            for key, value in row.items():
                if value is None:
                    sanitized_row[key] = ""
                elif isinstance(value, float) and (value != value):  # Check for NaN
                    sanitized_row[key] = ""
                elif isinstance(value, (int, float)) and abs(value) == float("inf"):
                    sanitized_row[key] = ""
                else:
                    sanitized_row[key] = value
            sanitized_data.append(sanitized_row)
        return sanitized_data

    def create_detailed_csv(self, data: List[Dict]) -> str:
        """Create detailed CSV file"""
        filename = generate_unique_filename("manychat", "detailed", "csv")
        filepath = os.path.join(self.csv_dir, filename)

        # Define column order (without revenue columns)
        columns = [
            "pagename",
            "page_id",
            "campaign_name",
            "timestamp",
            "time_scheduled",
            "sent",
            "delivered",
            "read",
            "clicked",
            "account_name",
            "user",
            "tl",
            "post_id",
            "post_url",
            "status",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            # Sanitize data before writing
            sanitized_data = self.sanitize_csv_data(data)
            writer.writerows(sanitized_data)

        print(f"✅ Detailed CSV saved: {filepath}")
        print(f"   📊 {len(data)} campaigns exported")

        return filepath

    def create_summary_csv(self, data: List[Dict]) -> str:
        """Create summary CSV file"""
        filename = generate_unique_filename("manychat", "summary", "csv")
        filepath = os.path.join(self.csv_dir, filename)

        # Define column order - including enhanced SpunkStatus API fields
        columns = [
            "pagename",
            "page_id",
            "timestamp",
            "totalCampaigns",
            "totalSent",
            "totalDelivered",
            "totalRead",
            "totalClicked",
            "account_name",
            "user",
            "tl",
            "revenue",
            "revenue_timestamp",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            # Sanitize data before writing
            sanitized_data = self.sanitize_csv_data(data)
            writer.writerows(sanitized_data)

        print(f"✅ Summary CSV saved: {filepath}")
        print(f"   📋 {len(data)} pages summarized")

        return filepath


class MainExtractor:
    """Main class for ManyChat data extraction and CSV conversion"""

    def __init__(self, config: dict = None):
        self.config = config or Properties.get_extraction_config()
        self.extractor = ManyChatExtractorOOP(verbose=self.config.get("verbose", True))
        self.csv_processor = ManyChat_CSV_Processor(self.config)

    def run_extraction(self) -> Dict[str, Any]:
        """Run the complete extraction and CSV conversion process"""
        print("\n🚀 Starting ManyChat Data Extraction")
        print("=" * 60)

        # Print current configuration
        Properties.print_current_config()

        # Run extraction with current configuration
        print(
            f"\n🎯 Using extraction mode: {self.config.get('extraction_mode', 'specific_date')}"
        )

        # Initialize extractor
        if not self.extractor.initialize():
            return {"success": False, "errors": ["Failed to initialize extractor"]}

        # Get extraction parameters
        start_date, end_date, filter_type = Properties.get_date_range()
        extraction_settings = {
            "profile_name": Properties.get_profile_name(),
            "headless_mode": self.config.get("headless_mode", True),
            "verbose": self.config.get("verbose", True),
        }

        print(f"\n📅 Extraction Parameters:")
        print(f"   Date Range: {start_date} to {end_date}")
        print(f"   Profile: {extraction_settings['profile_name'] or 'Auto-select'}")
        print(f"   Headless: {extraction_settings['headless_mode']}")

        try:
            # Perform extraction
            print(f"\n⏳ Starting data extraction...")

            if filter_type == "today_only" or filter_type == "specific_date":
                if start_date == datetime.now(MANYCHAT_TIMEZONE).strftime("%Y-%m-%d"):
                    result = self.extractor.quick_extract_today(
                        profile_name=extraction_settings["profile_name"],
                        headless=extraction_settings["headless_mode"],
                    )
                else:
                    result = self.extractor.extract_with_custom_range(
                        start_date=start_date,
                        end_date=end_date,
                        profile_name=extraction_settings["profile_name"],
                        headless=extraction_settings["headless_mode"],
                    )
            else:
                result = self.extractor.extract_with_custom_range(
                    start_date=start_date,
                    end_date=end_date,
                    profile_name=extraction_settings["profile_name"],
                    headless=extraction_settings["headless_mode"],
                )

            if not result["success"]:
                return {"success": False, "errors": [result["error"]]}

            print(f"\n✅ Extraction completed successfully!")
            print(f"   📊 {result['total_posts']} posts extracted")
            print(f"   📁 {len(result['files'])} JSON files created")

            # Extract page IDs from the extraction results for revenue fetching
            extracted_page_ids = []
            if "page_ids" in result:
                extracted_page_ids = result["page_ids"]
            else:
                # Fallback: extract page IDs from file data if available
                try:
                    for file_path in result["files"]:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_data = json.load(f)

                            # Handle the nested structure where pages are keys with 'posts' arrays
                            if isinstance(file_data, dict):
                                for page_name, page_data in file_data.items():
                                    if (
                                        isinstance(page_data, dict)
                                        and "posts" in page_data
                                    ):
                                        posts = page_data["posts"]
                                        for post in posts:
                                            if (
                                                isinstance(post, dict)
                                                and "flow" in post
                                            ):
                                                flow = post["flow"]
                                                if isinstance(flow, dict):
                                                    page_id = str(
                                                        flow.get("page_id", "")
                                                    )
                                                    if (
                                                        page_id
                                                        and page_id
                                                        not in extracted_page_ids
                                                    ):
                                                        extracted_page_ids.append(
                                                            page_id
                                                        )
                                                        if self.config.get(
                                                            "verbose", True
                                                        ):
                                                            print(
                                                                f"   📋 Found page ID: {page_id} from {page_name}"
                                                            )

                            # Also handle if the JSON contains a simple list of posts
                            elif isinstance(file_data, list):
                                for post in file_data:
                                    if isinstance(post, dict):
                                        page_id = str(post.get("page_id", ""))
                                        if (
                                            page_id
                                            and page_id not in extracted_page_ids
                                        ):
                                            extracted_page_ids.append(page_id)
                except Exception as e:
                    print(
                        f"⚠️ Warning: Could not extract page IDs for revenue fetching: {e}"
                    )
                    import traceback

                    if self.config.get("verbose", True):
                        traceback.print_exc()

            # Fetch revenue data for extracted pages
            if extracted_page_ids:
                print(
                    f"\n💰 Fetching revenue data for {len(extracted_page_ids)} extracted pages..."
                )
                self.csv_processor.revenue_data = (
                    self.csv_processor.fetch_revenue_for_extracted_pages(
                        extracted_page_ids
                    )
                )
                # Update the revenue timestamp
                self.csv_processor.revenue_timestamp = datetime.now(
                    MANYCHAT_TIMEZONE
                ).strftime("%Y-%m-%d %H:%M:%S UTC-4")
            else:
                print("\n⚠️ No page IDs found for revenue fetching")

            # Convert to CSV
            print(f"\n🔄 Converting to CSV format...")
            csv_results = self.csv_processor.process_json_to_csv(result["files"])

            # Clean up JSON files if requested
            if self.config.get("delete_json_after_csv", True):
                self.cleanup_json_files(result["files"])

            # Prepare final results
            final_results = {
                "success": True,
                "extraction_results": result,
                "csv_results": csv_results,
                "total_campaigns": csv_results["total_campaigns"],
                "total_pages": csv_results["total_pages"],
                "csv_files": csv_results["detailed_csv_files"]
                + csv_results["summary_csv_files"],
            }

            self.print_final_summary(final_results)
            return final_results

        except Exception as e:
            error_msg = f"Extraction failed: {e}"
            print(f"\n❌ {error_msg}")
            import traceback

            traceback.print_exc()
            return {"success": False, "errors": [error_msg]}

    def cleanup_json_files(self, json_files: List[str]):
        """Delete JSON files after CSV conversion"""
        print(f"\n🗑️  Cleaning up JSON files...")
        deleted_count = 0

        for json_file in json_files:
            try:
                if os.path.exists(json_file):
                    os.remove(json_file)
                    deleted_count += 1
                    print(f"   ✅ Deleted: {json_file}")
            except Exception as e:
                print(f"   ❌ Failed to delete {json_file}: {e}")

        print(f"   📝 {deleted_count} JSON files deleted")

    def print_final_summary(self, results: Dict[str, Any]):
        """Print final summary of the extraction and conversion process"""
        print(f"\n" + "=" * 60)
        print("📋 EXTRACTION AND CONVERSION SUMMARY")
        print("=" * 60)

        print(f"✅ Status: {'SUCCESS' if results['success'] else 'FAILED'}")
        print(f"📊 Total Campaigns: {results['total_campaigns']}")
        print(f"📄 Total Pages: {results['total_pages']}")
        print(f"📁 CSV Files Created: {len(results['csv_files'])}")

        print(f"\n📂 Generated Files:")
        for csv_file in results["csv_files"]:
            print(f"   📄 {csv_file}")

        extraction_time = results["extraction_results"].get("extraction_time", 0)
        print(f"\n⏱️  Total Time: {extraction_time:.1f} seconds")

        if results["total_campaigns"] > 0 and extraction_time > 0:
            print(
                f"🚀 Performance: {results['total_campaigns']/extraction_time:.1f} campaigns/second"
            )

        print("=" * 60)


def main():
    """Main function - entry point for the application"""
    print("🎯 ManyChat Data Extractor - Main Application")
    print("=" * 60)

    # Example configurations - uncomment the one you want to use:

    # Option 1: Today's data (default)
    # Use the new Properties configuration
    Properties.print_current_config()

    # Create extraction configuration from Properties
    extraction_config = Properties.get_extraction_config()
    # Run extraction using Properties
    extractor = MainExtractor(extraction_config)
    results = extractor.run_extraction()

    if results["success"]:
        print(f"\n🎉 Process completed successfully!")
        return 0
    else:
        print(f"\n❌ Process failed!")
        for error in results.get("errors", []):
            print(f"   - {error}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
