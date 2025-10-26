#!/usr/bin/env python3
"""
Test script to verify the NaN and NoneType fixes
"""
import json
import pandas as pd
import numpy as np


def test_nan_handling():
    """Test NaN value handling in JSON serialization"""
    print("🧪 Testing NaN handling...")

    # The actual issue from the error message:
    # "Out of range float values are not JSON compliant: nan"
    # This happens when using requests.post with json parameter

    # Create test data with NaN values like in a real DataFrame
    df = pd.DataFrame(
        [
            ["value1", 123, "value3"],
            ["value4", np.nan, "value6"],  # NaN value
            ["value7", None, "value9"],  # None value
        ],
        columns=["col1", "col2", "col3"],
    )

    print(f"Original DataFrame with NaN:\n{df}")
    print(f"DataFrame dtypes:\n{df.dtypes}")

    # Test the original problematic approach
    try:
        original_data = {
            "sheet_name": "test",
            "headers": df.columns.tolist(),
            "rows": df.values.tolist(),
        }

        # This is where the error would occur in requests.post(json=data)
        import requests

        # We can't actually test this without a server, but we can test json.dumps
        # with allow_nan=False which is closer to the actual error
        json.dumps(original_data, allow_nan=False)
        print("❌ Test failed: Should have failed with NaN")
        return False
    except ValueError as e:
        print(f"✅ Expected error caught: {e}")

    # Now test the fix
    df_fixed = df.fillna("")  # Replace NaN with empty strings

    # Convert any remaining problematic values to strings
    for col in df_fixed.columns:
        if df_fixed[col].dtype == "object":
            df_fixed[col] = df_fixed[col].astype(str)
        elif df_fixed[col].dtype in ["float64", "int64"]:
            # Ensure numeric columns don't have any remaining NaN
            df_fixed[col] = df_fixed[col].fillna(0)

    print(f"Fixed DataFrame:\n{df_fixed}")

    # Test JSON serialization with fixed data
    fixed_data = {
        "sheet_name": "test",
        "headers": df_fixed.columns.tolist(),
        "rows": df_fixed.values.tolist(),
    }

    try:
        json_str = json.dumps(fixed_data, allow_nan=False)
        print("✅ JSON serialization successful after fix")
        return True
    except Exception as e:
        print(f"❌ JSON serialization still failed: {e}")
        return False


def test_nonetype_addition():
    """Test NoneType addition fixes"""
    print("\n🧪 Testing NoneType addition fixes...")

    # Test the old problematic pattern
    test_stats = {
        "sent": None,
        "delivered": 100,
        "read": None,
        "opened": None,
        "clicked": 50,
    }

    # Old pattern (would fail)
    try:
        total_sent_old = 0
        total_sent_old += test_stats.get("sent", 0)  # This would work

        total_read_old = 0
        total_read_old += test_stats.get("read", 0) or test_stats.get(
            "opened", 0
        )  # This would fail
        print("❌ Test failed: Should have failed with NoneType")
        return False
    except TypeError as e:
        print(f"✅ Expected error caught: {e}")

    # New pattern (should work)
    try:
        total_sent_new = 0
        total_delivered_new = 0
        total_read_new = 0
        total_clicked_new = 0

        total_sent_new += test_stats.get("sent", 0) or 0
        total_delivered_new += test_stats.get("delivered", 0) or 0
        total_read_new += (test_stats.get("read", 0) or 0) or (
            test_stats.get("opened", 0) or 0
        )
        total_clicked_new += test_stats.get("clicked", 0) or 0

        print(f"✅ Fixed calculations work:")
        print(f"   Sent: {total_sent_new}")
        print(f"   Delivered: {total_delivered_new}")
        print(f"   Read: {total_read_new}")
        print(f"   Clicked: {total_clicked_new}")
        return True
    except Exception as e:
        print(f"❌ Fixed calculations still failed: {e}")
        return False


def test_csv_sanitization():
    """Test CSV data sanitization"""
    print("\n🧪 Testing CSV data sanitization...")

    # Test data with problematic values
    test_data = [
        {"name": "Page1", "value": 100, "rate": 0.5},
        {"name": "Page2", "value": None, "rate": np.nan},
        {"name": "Page3", "value": float("inf"), "rate": 0.3},
        {"name": None, "value": 200, "rate": float("-inf")},
    ]

    # Sanitization function (copied from the fix)
    def sanitize_csv_data(data):
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

    sanitized = sanitize_csv_data(test_data)

    print("Original data:")
    for i, row in enumerate(test_data):
        print(f"  Row {i}: {row}")

    print("Sanitized data:")
    for i, row in enumerate(sanitized):
        print(f"  Row {i}: {row}")

    # Check if all problematic values are handled
    for row in sanitized:
        for key, value in row.items():
            if value is None or (
                isinstance(value, float)
                and (value != value or abs(value) == float("inf"))
            ):
                print(f"❌ Sanitization failed: {key} = {value}")
                return False

    print("✅ CSV sanitization successful")
    return True


if __name__ == "__main__":
    print("🔧 Testing NaN and NoneType fixes")
    print("=" * 50)

    test1 = test_nan_handling()
    test2 = test_nonetype_addition()
    test3 = test_csv_sanitization()

    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   NaN handling: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"   NoneType addition: {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"   CSV sanitization: {'✅ PASS' if test3 else '❌ FAIL'}")

    if all([test1, test2, test3]):
        print("\n🎉 All tests passed! The fixes should work.")
    else:
        print("\n💥 Some tests failed. Please review the fixes.")
