// SIMPLE Google Apps Script for ManyChat Data Upload
// Use this version if you already created your spreadsheet manually
// 
// SETUP INSTRUCTIONS:
// 1. Create a Google Sheet named "manychat" with sheets "test" and "test1"
// 2. Go to https://script.google.com/
// 3. Create new project and paste this code
// 4. Update SPREADSHEET_ID below with your sheet's ID
// 5. Deploy as Web App
// 6. Use the Web App URL in Python

// CONFIGURATION - YOU MUST UPDATE THIS!
// To get your Spreadsheet ID:
// 1. Open your Google Sheet
// 2. Look at the URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
// 3. Copy the SPREADSHEET_ID part and paste it below
const SPREADSHEET_ID = "1czHZRmlp1Z03wTEZtKZNlOa7MVtucwtea5ed5p5FLSs";  // ⚠️ UPDATE THIS!

// Sheet names (these should match your sheet tabs)
const DETAILED_SHEET_NAME = "test";   // For detailed campaign data
const SUMMARY_SHEET_NAME = "test1";   // For summary data

// Main function to handle POST requests from Python
function doPost(e) {
    try {
        console.log("Received POST request");

        // Parse JSON data from Python
        const data = JSON.parse(e.postData.contents);
        const sheetName = data.sheet_name;
        const headers = data.headers;
        const rows = data.rows;
        const append = data.append !== false;

        console.log(`Processing ${rows.length} rows for sheet: ${sheetName}`);

        // Open the spreadsheet using ID (more reliable)
        let spreadsheet;
        try {
            spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
            console.log("Successfully opened spreadsheet");
        } catch (error) {
            throw new Error(`Cannot open spreadsheet with ID '${SPREADSHEET_ID}'. Please check the SPREADSHEET_ID in the script. Error: ${error.message}`);
        }

        // Get the target worksheet
        let worksheet;
        try {
            worksheet = spreadsheet.getSheetByName(sheetName);
            if (!worksheet) {
                // Create sheet if it doesn't exist
                worksheet = spreadsheet.insertSheet(sheetName);
                console.log(`Created new sheet: ${sheetName}`);
            }
        } catch (error) {
            throw new Error(`Cannot access sheet '${sheetName}': ${error.message}`);
        }

        // Add data to sheet with automatic column management
        let rowsAdded = 0;
        const lastRow = worksheet.getLastRow();

        if (lastRow === 0) {
            // Empty sheet - add headers first
            if (headers && headers.length > 0) {
                worksheet.getRange(1, 1, 1, headers.length).setValues([headers]);
                console.log("Added headers to empty sheet");
            }

            // Add data starting from row 2
            if (rows && rows.length > 0) {
                worksheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
                rowsAdded = rows.length;
                console.log(`Added ${rowsAdded} data rows`);
            }
        } else {
            // Sheet has data - check and manage columns
            const existingHeaders = worksheet.getRange(1, 1, 1, worksheet.getLastColumn()).getValues()[0];
            console.log(`Existing headers: ${existingHeaders.join(', ')}`);
            console.log(`New headers: ${headers.join(', ')}`);

            // Manage columns automatically
            const columnMapping = manageColumns(worksheet, existingHeaders, headers);

            // Add data using column mapping
            if (rows && rows.length > 0) {
                const mappedRows = mapDataToColumns(rows, headers, columnMapping);
                const startRow = lastRow + 1;

                if (mappedRows.length > 0 && mappedRows[0].length > 0) {
                    worksheet.getRange(startRow, 1, mappedRows.length, mappedRows[0].length).setValues(mappedRows);
                    rowsAdded = rows.length;
                    console.log(`Appended ${rowsAdded} rows starting from row ${startRow}`);
                }
            }
        }

        // Add timestamp note
        const timestamp = new Date().toISOString();
        worksheet.getRange(1, 1).setNote(`Last updated: ${timestamp} | Rows added: ${rowsAdded}`);

        // Return success response
        const response = {
            success: true,
            message: "Data uploaded successfully",
            sheet_name: sheetName,
            rows_added: rowsAdded,
            total_rows: worksheet.getLastRow(),
            spreadsheet_url: spreadsheet.getUrl(),
            timestamp: timestamp
        };

        console.log("Upload successful:", response);

        return ContentService
            .createTextOutput(JSON.stringify(response))
            .setMimeType(ContentService.MimeType.JSON);

    } catch (error) {
        console.error("Error:", error);

        const errorResponse = {
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        };

        return ContentService
            .createTextOutput(JSON.stringify(errorResponse))
            .setMimeType(ContentService.MimeType.JSON);
    }
}

// Helper function to manage columns automatically
function manageColumns(worksheet, existingHeaders, newHeaders) {
    const columnMapping = [];
    let needsUpdate = false;

    console.log("🔧 Managing columns automatically...");

    // Clean and normalize headers for comparison
    const normalizeHeader = (header) => {
        return String(header || '').toLowerCase().trim().replace(/[^a-z0-9]/g, '');
    };

    const normalizedExisting = existingHeaders.map(h => normalizeHeader(h));
    const normalizedNew = newHeaders.map(h => normalizeHeader(h));

    // Map new headers to existing column positions
    for (let i = 0; i < newHeaders.length; i++) {
        const newHeader = newHeaders[i];
        const normalizedNewHeader = normalizedNew[i];

        // Look for exact match first
        let foundIndex = existingHeaders.indexOf(newHeader);

        // If no exact match, look for normalized match
        if (foundIndex === -1) {
            foundIndex = normalizedExisting.indexOf(normalizedNewHeader);
        }

        if (foundIndex >= 0) {
            // Column exists - map to existing position
            columnMapping.push({
                newIndex: i,
                existingIndex: foundIndex,
                newHeader: newHeader,
                existingHeader: existingHeaders[foundIndex],
                action: 'mapped'
            });

            // Check if header name needs updating
            if (existingHeaders[foundIndex] !== newHeader) {
                console.log(`📝 Updating column ${foundIndex + 1}: "${existingHeaders[foundIndex]}" → "${newHeader}"`);
                worksheet.getRange(1, foundIndex + 1).setValue(newHeader);
                needsUpdate = true;
            }
        } else {
            // Column doesn't exist - add new column
            const newColumnIndex = existingHeaders.length;
            console.log(`➕ Adding new column ${newColumnIndex + 1}: "${newHeader}"`);

            // Add header to the sheet
            worksheet.getRange(1, newColumnIndex + 1).setValue(newHeader);
            existingHeaders.push(newHeader);

            columnMapping.push({
                newIndex: i,
                existingIndex: newColumnIndex,
                newHeader: newHeader,
                existingHeader: newHeader,
                action: 'added'
            });
            needsUpdate = true;
        }
    }

    if (needsUpdate) {
        console.log("✅ Column management completed");
    } else {
        console.log("✅ All columns already match");
    }

    return columnMapping;
}

// Helper function to map data to correct columns
function mapDataToColumns(rows, newHeaders, columnMapping) {
    console.log("🗂️ Mapping data to correct columns...");

    const mappedRows = [];
    const totalColumns = Math.max(...columnMapping.map(m => m.existingIndex)) + 1;

    for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
        const originalRow = rows[rowIndex];
        const mappedRow = new Array(totalColumns).fill(''); // Initialize with empty strings

        // Map each cell to correct column
        for (const mapping of columnMapping) {
            if (originalRow[mapping.newIndex] !== undefined) {
                mappedRow[mapping.existingIndex] = originalRow[mapping.newIndex];
            }
        }

        mappedRows.push(mappedRow);
    }

    console.log(`✅ Mapped ${mappedRows.length} rows to ${totalColumns} columns`);
    return mappedRows;
}

// Test function - run this to verify setup
function testSetup() {
    console.log("Testing Google Apps Script setup...");

    try {
        // Check if spreadsheet ID is configured
        if (SPREADSHEET_ID === "PASTE_YOUR_SPREADSHEET_ID_HERE") {
            throw new Error("❌ SPREADSHEET_ID not configured! Please update it in the script.");
        }

        // Try to open spreadsheet
        const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
        console.log(`✅ Successfully opened spreadsheet: ${spreadsheet.getName()}`);
        console.log(`📋 URL: ${spreadsheet.getUrl()}`);

        // List existing sheets
        const sheets = spreadsheet.getSheets();
        console.log(`📊 Found ${sheets.length} sheets:`);
        sheets.forEach(sheet => console.log(`   • ${sheet.getName()}`));

        // Check for required sheets
        const sheetNames = sheets.map(s => s.getName());
        if (!sheetNames.includes(DETAILED_SHEET_NAME)) {
            console.log(`⚠️ Creating missing sheet: ${DETAILED_SHEET_NAME}`);
            spreadsheet.insertSheet(DETAILED_SHEET_NAME);
        }
        if (!sheetNames.includes(SUMMARY_SHEET_NAME)) {
            console.log(`⚠️ Creating missing sheet: ${SUMMARY_SHEET_NAME}`);
            spreadsheet.insertSheet(SUMMARY_SHEET_NAME);
        }

        console.log("✅ Setup test completed successfully!");
        return true;

    } catch (error) {
        console.error("❌ Setup test failed:", error.message);
        return false;
    }
}

// Advanced test with column management
function testColumnManagement() {
    console.log("🧪 Testing automatic column management...");

    try {
        const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
        const testSheetName = "column_test";

        // Delete test sheet if it exists
        let testSheet = spreadsheet.getSheetByName(testSheetName);
        if (testSheet) {
            spreadsheet.deleteSheet(testSheet);
        }

        // Create new test sheet
        testSheet = spreadsheet.insertSheet(testSheetName);
        console.log(`✅ Created test sheet: ${testSheetName}`);

        // Test 1: Initial data with basic columns
        console.log("\n📝 Test 1: Adding initial data...");
        const initialData = {
            sheet_name: testSheetName,
            headers: ["page_name", "campaign_name", "sent_count"],
            rows: [
                ["Page 1", "Campaign A", 100],
                ["Page 2", "Campaign B", 200]
            ]
        };

        let mockEvent = {
            postData: { contents: JSON.stringify(initialData) }
        };

        let result = doPost(mockEvent);
        let response = JSON.parse(result.getContent());
        console.log(`Result: ${response.success ? '✅ Success' : '❌ Failed'}`);

        // Test 2: Add data with new columns
        console.log("\n➕ Test 2: Adding data with new columns...");
        const newColumnData = {
            sheet_name: testSheetName,
            headers: ["page_name", "campaign_name", "sent_count", "delivery_rate", "click_rate"],
            rows: [
                ["Page 3", "Campaign C", 300, "95%", "12%"],
                ["Page 4", "Campaign D", 400, "93%", "15%"]
            ]
        };

        mockEvent = {
            postData: { contents: JSON.stringify(newColumnData) }
        };

        result = doPost(mockEvent);
        response = JSON.parse(result.getContent());
        console.log(`Result: ${response.success ? '✅ Success' : '❌ Failed'}`);

        // Test 3: Add data with mismatched column names
        console.log("\n🔄 Test 3: Adding data with mismatched column names...");
        const mismatchedData = {
            sheet_name: testSheetName,
            headers: ["pagename", "campaignname", "sentcount", "deliveryrate", "clickrate"],
            rows: [
                ["Page 5", "Campaign E", 500, "97%", "18%"]
            ]
        };

        mockEvent = {
            postData: { contents: JSON.stringify(mismatchedData) }
        };

        result = doPost(mockEvent);
        response = JSON.parse(result.getContent());
        console.log(`Result: ${response.success ? '✅ Success' : '❌ Failed'}`);

        // Check final sheet structure
        const finalHeaders = testSheet.getRange(1, 1, 1, testSheet.getLastColumn()).getValues()[0];
        const finalRowCount = testSheet.getLastRow();

        console.log(`\n📊 Final Results:`);
        console.log(`   Headers: ${finalHeaders.join(', ')}`);
        console.log(`   Total rows: ${finalRowCount}`);
        console.log(`   Spreadsheet URL: ${spreadsheet.getUrl()}`);

        console.log("\n✅ Column management test completed!");
        return true;

    } catch (error) {
        console.error("❌ Column management test failed:", error);
        return false;
    }
}

// Simple test with sample data
function testDataUpload() {
    console.log("Testing data upload...");

    const testData = {
        sheet_name: DETAILED_SHEET_NAME,
        headers: ["test_pagename", "test_campaign", "test_sent", "test_timestamp"],
        rows: [
            ["Test Page", "Test Campaign", 100, new Date().toISOString()]
        ],
        append: true
    };

    const mockEvent = {
        postData: {
            contents: JSON.stringify(testData),
            type: "application/json"
        }
    };

    try {
        const result = doPost(mockEvent);
        const response = JSON.parse(result.getContent());

        if (response.success) {
            console.log("✅ Test data upload successful!");
            console.log(`📊 Rows added: ${response.rows_added}`);
            console.log(`🔗 Spreadsheet: ${response.spreadsheet_url}`);
        } else {
            console.log("❌ Test upload failed:", response.error);
        }

        return response.success;
    } catch (error) {
        console.error("❌ Test error:", error);
        return false;
    }
}

/*
ENHANCED GOOGLE APPS SCRIPT WITH AUTOMATIC COLUMN MANAGEMENT

✨ NEW FEATURES:
- 🔄 Automatic column detection and management
- ➕ Adds missing columns automatically
- 📝 Updates column names when mismatched
- 🗂️ Maps data to correct columns regardless of order

QUICK SETUP GUIDE:

1. CREATE YOUR SPREADSHEET:
   - Go to sheets.google.com
   - Create new spreadsheet named "manychat"
   - Create sheets named "test" and "test1"

2. GET SPREADSHEET ID:
   - Copy the ID from URL: https://docs.google.com/spreadsheets/d/YOUR_ID_HERE/edit
   - Paste it in SPREADSHEET_ID above

3. DEPLOY APPS SCRIPT:
   - Paste this code in script.google.com
   - Deploy as Web App (Execute as "Me", Access "Anyone")
   - Copy Web App URL

4. TEST SETUP:
   - Run "testSetup" function
   - Run "testDataUpload" function
   - Run "testColumnManagement" function (NEW!)
   - Check for success messages in logs

5. USE WITH PYTHON:
   - Run main_apps_script.py
   - Enter your Web App URL when prompted
   - Pipeline will upload data automatically

🔧 COLUMN MANAGEMENT FEATURES:

✅ AUTOMATIC COLUMN ADDITION:
   - Detects missing columns in your sheet
   - Adds them automatically with proper headers
   - No manual column setup required

✅ SMART COLUMN MATCHING:
   - Matches columns by exact name first
   - Falls back to normalized matching (ignores case, spaces, special chars)
   - Examples: "page_name" matches "pagename", "Page Name", "page-name"

✅ HEADER UPDATE:
   - Updates column headers to match your data
   - Keeps your sheet synchronized with data format

✅ DATA MAPPING:
   - Maps data to correct columns regardless of order
   - Handles missing columns gracefully
   - Fills empty cells for missing data

TROUBLESHOOTING:
- Make sure SPREADSHEET_ID is correct
- Verify sheet names match ("test" and "test1")
- Check Apps Script execution logs for errors
- Ensure proper deployment permissions
- Run testColumnManagement() to verify column features

COLUMN MATCHING EXAMPLES:
Your Data Header → Matches Sheet Column
"page_name"      → "page_name", "pagename", "Page Name", "page-name"
"campaign_name"  → "campaign_name", "campaignname", "Campaign Name"
"sent_count"     → "sent_count", "sentcount", "Sent Count", "sent-count"

The system will automatically handle all column variations and keep your sheets organized!
*/

//https://script.google.com/macros/s/AKfycbx2snqbNlsKuCG4ktdKWSU8XEaCzm3lamoqrAgxQ0AyAl3Qj3hk5MxccOrOsCIcXM9Srg/exec