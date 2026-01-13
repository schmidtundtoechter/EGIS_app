# EGIS Integration - Setup Instructions

## Changes Made

The EGIS Integration app has been updated to support configurable Price Lists and Item Groups, making it compatible with both German and English ERPNext systems.

### What Changed:

1. **New Configuration Fields in EGIS Settings**
   - Default Selling Price List (Required)
   - Retail Price List (Optional)
   - Parent Item Group (Required)

2. **Removed Hardcoded Values**
   - No longer assumes "Standard Selling" price list
   - No longer assumes "EGIS" item group
   - No longer assumes "EGIS Retail" price list

3. **Added Validation**
   - System now validates that configured price lists and item groups exist before import
   - Clear error messages guide users to create missing entities

---

## Setup Instructions for German Systems

### Step 1: Access EGIS Settings

Navigate to: **EGIS Integration > EGIS Settings**

### Step 2: Configure API Credentials (Already Done)


### Step 3: Create EGIS Item Group (Already Done ✓)

You've already created the EGIS item group:
- **Item Group Name**: `EGIS`
- **Parent**: All Item Groups

Perfect! All items imported from EGIS will be assigned to this item group.

### Step 4: Identify or Create Price Lists

**For Selling Prices:**
1. Go to **Stock > Price List**
2. Find your default selling price list (likely named "Standard-Verkauf" in German systems)
3. Note the exact name

**For Retail Prices (Optional):**
1. If you want to track EGIS retail prices separately, create a new price list:
   - **Price List Name**: `EGIS Retail` (or any name you prefer)
   - **Currency**: EUR
   - **Enabled**: Yes
   - **Buying/Selling**: Selling
2. Save

### Step 5: Configure EGIS Settings

Return to **EGIS Settings** and fill in the "Item Import Settings" section:

1. **Default Selling Price List**: Select your selling price list (e.g., "Standard-Verkauf")
2. **Retail Price List (Optional)**: Leave empty or select the retail price list if created
3. **Item Group**: Select "EGIS"
4. Save

---

## Using the Integration

### Search and Import Items

1. Go to **EGIS Integration > EGIS Search Query**
2. Enter search criteria
3. Click **Make Request** to search EGIS catalog
4. Review results
5. Click **Import Items** to import into ERPNext

### What Happens During Import:

- **New Items**: Creates items with all EGIS data
- **Existing Items**: Updates product information and prices
- **Prices**:
  - Purchase price from EGIS → Your configured selling price list
  - Retail price from EGIS → Your configured retail price list (if set)
- **Item Group**: All imported items assigned to your configured item group (EGIS)
- **Brands**: Auto-created from manufacturer names

---

## Error Messages You Might See

### "Price List '{name}' does not exist"
**Solution**: Create the price list in Stock > Price List, or select a different one in EGIS Settings

### "Item Group '{name}' does not exist"
**Solution**: Create the item group in Stock > Item Group, or select a different one in EGIS Settings

### "Configuration Missing"
**Solution**: Fill in all required fields in EGIS Settings (marked with red asterisk)

---

## Benefits of This Update

✅ **Multi-language Support**: Works with German, English, or any language system
✅ **Flexible Configuration**: Use your existing price lists and item groups
✅ **Better Validation**: Clear error messages prevent import failures
✅ **Backward Compatible**: Existing EGIS items continue to work

---

## Technical Details

### Files Modified:
- `egis_settings.json` - Added new configuration fields
- `egis_search_query.py` - Updated to use configurable values with validation

### Database Changes:
- Three new fields added to EGIS Settings doctype
- No data migration needed
- Existing items unaffected

---

## Support

For issues or questions:
1. Check Error Log in ERPNext
2. Verify all required fields are filled in EGIS Settings
3. Ensure price lists and item groups exist in your system
4. Contact your developer if problems persist
