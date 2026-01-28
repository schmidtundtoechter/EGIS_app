# Copyright (c) 2023, Phamos and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
import requests, json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from frappe.model.document import Document

class EGISSearchQuery(Document):
	pass

def build_search_query_xml(username, password, search_term, search_options, start_row):
	"""Build XML document for SearchQuery according to SYNAXON developer's working format"""

	# Create root element
	root = ET.Element('SearchQuery')
	root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
	root.set('xmlns', 'http://www.egis-online.de/EBC/schema/SearchQuery')
	root.set('xsi:schemaLocation', 'http://www.egis-online.de/EBC/schema/SearchQuery SearchQuery.xsd')

	# Transaction Header
	header = ET.SubElement(root, 'TransactionHeader')
	ET.SubElement(header, 'VersionId').text = '1.00'
	ET.SubElement(header, 'GenerationDateTime').text = frappe.utils.now()
	ET.SubElement(header, 'ERP').text = 'ERPNext'
	ET.SubElement(header, 'Login').text = username
	ET.SubElement(header, 'Password').text = password

	# Create Search > Query structure as per developer's working example
	search_elem = ET.SubElement(root, 'Search')
	query_elem = ET.SubElement(search_elem, 'Query')

	# Search Term inside Query
	if search_term:
		ET.SubElement(query_elem, 'SearchTerm').text = search_term

	# Search Options inside Query
	options_elem = ET.SubElement(query_elem, 'SearchOptions')

	if search_options:
		if search_options.get('OnlyActive') is not None:
			ET.SubElement(options_elem, 'OnlyActive').text = str(search_options['OnlyActive']).lower()
		else:
			ET.SubElement(options_elem, 'OnlyActive').text = 'false'

		if search_options.get('OnlyStocked') is not None:
			ET.SubElement(options_elem, 'OnlyStocked').text = str(search_options['OnlyStocked']).lower()
		else:
			ET.SubElement(options_elem, 'OnlyStocked').text = 'false'

		if search_options.get('OnlyInDescription') is not None:
			ET.SubElement(options_elem, 'OnlyInDescription').text = str(search_options['OnlyInDescription']).lower()
		else:
			ET.SubElement(options_elem, 'OnlyInDescription').text = 'false'

		# MinPrice and MaxPrice - always include as per developer's example
		min_price = search_options.get('MinPrice', '')
		ET.SubElement(options_elem, 'MinPrice').text = str(min_price) if min_price else ''

		max_price = search_options.get('MaxPrice', '')
		ET.SubElement(options_elem, 'MaxPrice').text = str(max_price) if max_price else ''
	else:
		# Default values when no options provided
		ET.SubElement(options_elem, 'OnlyActive').text = 'false'
		ET.SubElement(options_elem, 'OnlyStocked').text = 'false'
		ET.SubElement(options_elem, 'OnlyInDescription').text = 'false'
		ET.SubElement(options_elem, 'MinPrice').text = ''
		ET.SubElement(options_elem, 'MaxPrice').text = ''

	# DistributorName, ManufacturerName, ProductGroupId inside Query but OUTSIDE SearchOptions
	if search_options:
		if search_options.get('DistributorName'):
			for dist in search_options['DistributorName']:
				ET.SubElement(query_elem, 'DistributorName').text = dist if dist else ''
		else:
			ET.SubElement(query_elem, 'DistributorName').text = ''
			ET.SubElement(query_elem, 'DistributorName').text = ''

		if search_options.get('ManufacturerName'):
			for mfr in search_options['ManufacturerName']:
				ET.SubElement(query_elem, 'ManufacturerName').text = mfr if mfr else ''
		else:
			ET.SubElement(query_elem, 'ManufacturerName').text = ''

		if search_options.get('ProductGroupId'):
			for group in search_options['ProductGroupId']:
				ET.SubElement(query_elem, 'ProductGroupId').text = group if group else ''
		else:
			ET.SubElement(query_elem, 'ProductGroupId').text = ''
	else:
		# Add empty tags as in developer's example
		ET.SubElement(query_elem, 'DistributorName').text = ''
		ET.SubElement(query_elem, 'DistributorName').text = ''
		ET.SubElement(query_elem, 'ManufacturerName').text = ''
		ET.SubElement(query_elem, 'ProductGroupId').text = ''

	# Sorting inside Query (optional - for sorting by price)
	if search_options and search_options.get('SortOrder'):
		sorting = ET.SubElement(query_elem, 'Sorting')
		ET.SubElement(sorting, 'SortOrder').text = search_options['SortOrder']

	# Pagination inside Query
	pagination = ET.SubElement(query_elem, 'Pagination')
	ET.SubElement(pagination, 'StartRow').text = str(start_row) if start_row else '1'

	# Convert to string with proper formatting
	xml_str = ET.tostring(root, encoding='utf-8', method='xml')
	return xml_str.decode('utf-8')

def parse_search_response_xml(xml_response):
	"""Parse XML response from SearchQuery according to EBC documentation"""
	try:
		root = ET.fromstring(xml_response)

		# Define namespace
		ns = {'ns': 'http://www.egis-online.de/EBC/schema/SearchQueryResponse'}

		# Check for errors in TransactionHeader
		header = root.find('ns:TransactionHeader', ns)
		if header is not None:
			exception = header.find('ns:Exception', ns)
			if exception is not None:
				error_num = exception.find('ns:ErrorNumber', ns)
				error_msg = exception.find('ns:ErrorMessage', ns)
				error_desc = exception.find('ns:ErrorDescription', ns)

				error_info = {
					'error': True,
					'ErrorNumber': error_num.text if error_num is not None else '',
					'ErrorMessage': error_msg.text if error_msg is not None else '',
					'ErrorDescription': error_desc.text if error_desc is not None else ''
				}
				return error_info

		# Parse successful response
		result = {
			'Header': {},
			'Body': {'Item': []}
		}

		# Parse Header - look for Search/Header
		search_elem = root.find('ns:Search', ns)
		if search_elem is not None:
			query_header = search_elem.find('ns:Header', ns)
			if query_header is not None:
				total = query_header.find('ns:TotalResults', ns)
				first = query_header.find('ns:FirstResult', ns)
				last = query_header.find('ns:LastResult', ns)

				if total is not None:
					result['Header']['TotalResults'] = total.text
				if first is not None:
					result['Header']['FirstResult'] = first.text
				if last is not None:
					result['Header']['LastResult'] = last.text

		# Parse Items
		items = root.findall('.//ns:Item', ns)
		for item in items:
			item_data = {}

			# Product Identification
			prod_id = item.find('ns:ProductIdentification', ns)
			if prod_id is not None:
				item_data['ProductIdentification'] = {}

				prop_num = prod_id.find('ns:ProprietaryProductNumber', ns)
				if prop_num is not None:
					item_data['ProductIdentification']['ProprietaryProductNumber'] = prop_num.text

				prop_desc = prod_id.find('ns:ProprietaryProductDescription', ns)
				if prop_desc is not None:
					item_data['ProductIdentification']['ProprietaryProductDescription'] = prop_desc.text

				mfr_name = prod_id.find('ns:ManufacturerName', ns)
				if mfr_name is not None:
					item_data['ProductIdentification']['ManufacturerName'] = {
						'@id': mfr_name.get('id', ''),
						'@text': mfr_name.text or ''
					}

				mfr_prod_num = prod_id.find('ns:ManufacturerProductNumber', ns)
				if mfr_prod_num is not None:
					item_data['ProductIdentification']['ManufacturerProductNumber'] = mfr_prod_num.text

				global_prod_num = prod_id.find('ns:GlobalProductNumber', ns)
				if global_prod_num is not None:
					item_data['ProductIdentification']['GlobalProductNumber'] = global_prod_num.text

				prod_group = prod_id.find('ns:ProductGroupId', ns)
				if prod_group is not None:
					item_data['ProductIdentification']['ProductGroupId'] = prod_group.text

			# Unit Price
			unit_price = item.find('ns:UnitPrice', ns)
			if unit_price is not None:
				item_data['UnitPrice'] = {}

				purchase_price = unit_price.find('ns:PurchasePrice', ns)
				if purchase_price is not None:
					item_data['UnitPrice']['PurchasePrice'] = purchase_price.text or ''

				currency = unit_price.find('ns:CurrencyCode', ns)
				if currency is not None:
					item_data['UnitPrice']['CurrencyCode'] = currency.text

				date_time = unit_price.find('ns:DateTime', ns)
				if date_time is not None:
					item_data['UnitPrice']['DateTime'] = date_time.text

				rrp = unit_price.find('ns:RecommendedRetailPrice', ns)
				if rrp is not None:
					item_data['UnitPrice']['RecommendedRetailPrice'] = rrp.text or ''

			# Image URL
			image_url = item.find('ns:ImageUrl', ns)
			if image_url is not None:
				item_data['ImageUrl'] = image_url.text or ''

			result['Body']['Item'].append(item_data)

		return result

	except ET.ParseError as e:
		frappe.log_error(f"XML Parse Error: {str(e)}\nResponse: {xml_response}", "EGIS XML Parse Error")
		return {'error': True, 'ErrorMessage': 'Invalid XML response', 'ErrorDescription': str(e)}

def build_product_specification_xml(username, password, product_number):
	"""Build XML document for ProductSpecificationQuery to get full description

	According to EGIS EBC documentation, this is the correct API for getting
	product descriptions including:
	- ShortDesc (from CNET or ICECAT)
	- ShortSummaryDescription
	- LongSummaryDescription
	- MarketingText
	- Feature specifications
	"""
	root = ET.Element('ProductSpecificationQuery')
	root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
	root.set('xmlns', 'http://www.egis-online.de/EBC/schema/ProductSpecificationQuery')
	root.set('xsi:schemaLocation', 'http://www.egis-online.de/EBC/schema/ProductSpecificationQuery ProductSpecificationQuery.xsd')

	# Transaction Header
	header = ET.SubElement(root, 'TransactionHeader')
	ET.SubElement(header, 'VersionId').text = '1.00'
	ET.SubElement(header, 'GenerationDateTime').text = frappe.utils.now()
	ET.SubElement(header, 'ERP').text = 'ERPNext'
	ET.SubElement(header, 'Login').text = username
	ET.SubElement(header, 'Password').text = password

	# ProductSpecification > Query > ProductReference > ProprietaryProductIdentifier > ProprietaryProductNumber
	spec_elem = ET.SubElement(root, 'ProductSpecification')
	query_elem = ET.SubElement(spec_elem, 'Query')
	prod_ref = ET.SubElement(query_elem, 'ProductReference')
	prop_id = ET.SubElement(prod_ref, 'ProprietaryProductIdentifier')
	ET.SubElement(prop_id, 'ProprietaryProductNumber').text = product_number

	xml_str = ET.tostring(root, encoding='utf-8', method='xml')
	return xml_str.decode('utf-8')

def fetch_product_detail(product_number):
	"""Fetch full product details including long description and Features from EGIS

	Uses the productSpecificationQuery API which returns:
	- LongSummaryDescription (preferred)
	- ShortSummaryDescription
	- ShortDesc (from CNET or ICECAT)
	- MarketingText
	- Feature (multiple) with FeatureGroup, Key, Value
	"""
	try:
		egis_settings = frappe.get_doc("EGIS Settings")
		base_url = egis_settings.url.rstrip('/')

		# Determine component name based on URL
		if 'egis-online.de' in base_url:
			component = "Artikelstamm"
		else:
			component = "ProductMaster"

		# Use productSpecificationQuery endpoint (correct API per EGIS documentation)
		endpoint = f"{base_url}/{component}/productSpecificationQuery"

		xml_payload = build_product_specification_xml(
			egis_settings.user,
			egis_settings.get_password("password"),
			product_number
		)

		headers = {'Content-Type': 'text/xml; charset=utf-8'}
		response = requests.post(endpoint, data=xml_payload.encode('utf-8'), headers=headers, timeout=30)

		if response.status_code == 200:
			# Check for error response
			if 'Exception' in response.text or 'ErrorNumber' in response.text:
				frappe.log_error(
					f"EGIS returned error for {product_number}:\n{response.text[:500]}",
					"EGIS ProductSpecification Error"
				)
				return None

			# Parse the response to extract descriptions
			root = ET.fromstring(response.text)
			ns = {'ns': 'http://www.egis-online.de/EBC/schema/ProductSpecificationQueryResponse'}

			description_parts = []

			# 1. First add any text descriptions (LongSummaryDescription, MarketingText, etc.)
			long_summary = root.find('.//ns:LongSummaryDescription', ns)
			if long_summary is None:
				long_summary = root.find('.//LongSummaryDescription')
			if long_summary is not None and long_summary.text and long_summary.text.strip():
				# Format the description with HTML line breaks after each sentence
				# EGIS returns specs like "Name. Key1: Val1, Key2: Val2. Key3: Val3."
				formatted_desc = long_summary.text.strip()
				# Split on ". " and rejoin with <br> for HTML display
				sentences = formatted_desc.split('. ')
				if len(sentences) > 1:
					formatted_desc = '.<br>'.join(sentences)
					# Fix the last sentence if it didn't end with a period
					if not formatted_desc.endswith('.'):
						formatted_desc += '.'
				description_parts.append(formatted_desc)

			marketing_text = root.find('.//ns:MarketingText', ns)
			if marketing_text is None:
				marketing_text = root.find('.//MarketingText')
			if marketing_text is not None and marketing_text.text and marketing_text.text.strip():
				# Format with HTML line breaks
				formatted_marketing = marketing_text.text.strip()
				sentences = formatted_marketing.split('. ')
				if len(sentences) > 1:
					formatted_marketing = '.<br>'.join(sentences)
					if not formatted_marketing.endswith('.'):
						formatted_marketing += '.'
				# Only add if different from long_summary
				if not description_parts or formatted_marketing != description_parts[0]:
					description_parts.append(formatted_marketing)

			# 2. Extract all Feature elements and format as "Key:\nValue"
			# Skip certain fields that are not useful for product description
			skip_keys = [
				'url', 'image', 'bild', 'picture', 'foto', 'photo',
				'link', 'href', 'datasheet', 'datenblatt'
			]

			features = root.findall('.//ns:Feature', ns)
			if not features:
				features = root.findall('.//Feature')

			feature_texts = []
			for feature in features:
				key_elem = feature.find('ns:Key', ns)
				if key_elem is None:
					key_elem = feature.find('Key')

				value_elem = feature.find('ns:Value', ns)
				if value_elem is None:
					value_elem = feature.find('Value')

				if key_elem is not None and value_elem is not None:
					key = key_elem.text.strip() if key_elem.text else ''
					value = value_elem.text.strip() if value_elem.text else ''

					# Skip if key contains any of the skip words (case-insensitive)
					if key and value:
						key_lower = key.lower()
						value_lower = value.lower()
						should_skip = False
						for skip_word in skip_keys:
							if skip_word in key_lower or (value_lower.startswith('http') and 'image' in value_lower):
								should_skip = True
								break

						if not should_skip:
							feature_texts.append(f"<b>{key}:</b> {value}")

			# 3. Combine description and features
			if feature_texts:
				description_parts.append("<br>".join(feature_texts))

			if description_parts:
				return "<br><br>".join(description_parts)

			# Fallback to short descriptions if no long description or features
			short_summary = root.find('.//ns:ShortSummaryDescription', ns)
			if short_summary is None:
				short_summary = root.find('.//ShortSummaryDescription')
			if short_summary is not None and short_summary.text and short_summary.text.strip():
				return short_summary.text.strip()

			short_desc = root.find('.//ns:ShortDesc', ns)
			if short_desc is None:
				short_desc = root.find('.//ShortDesc')
			if short_desc is not None and short_desc.text and short_desc.text.strip():
				return short_desc.text.strip()

	except ET.ParseError as e:
		frappe.log_error(f"XML Parse Error for {product_number}: {str(e)}", "EGIS ProductSpecification Parse Error")
		return None
	except Exception as e:
		frappe.log_error(f"Error fetching ProductSpecification for {product_number}: {str(e)}", "EGIS ProductSpecification Error")
		return None

	return None

@frappe.whitelist()
def make_request(search_term, search_options, start_row):
	search_options = json.loads(search_options or '{}')
	egis_settings = frappe.get_doc("EGIS Settings")

	# Build correct endpoint URL according to EBC documentation
	# Format: https://www.egis-online.de/cgi-bin/WebObjects/EBC.woa/wa/<component>/<function>
	# Note: German accounts use .de URL with "Artikelstamm", English accounts use .co.uk with "ProductMaster"
	base_url = egis_settings.url.rstrip('/')

	# Determine component name based on URL (German vs English)
	if 'egis-online.de' in base_url:
		# German EGIS - use German component name
		component = "Artikelstamm"
	else:
		# English EGIS - use English component name
		component = "ProductMaster"

	endpoint = f"{base_url}/{component}/searchQuery"

	# Build XML request body
	xml_payload = build_search_query_xml(
		egis_settings.user,
		egis_settings.get_password("password"),
		search_term,
		search_options,
		start_row
	)

	# Headers must include Content-Type: text/xml and charset UTF-8
	headers = {
		'Content-Type': 'text/xml; charset=utf-8'
	}

	try:
		response = requests.post(endpoint, data=xml_payload.encode('utf-8'), headers=headers, timeout=30)

		# Check HTTP status
		if response.status_code != 200:
			frappe.log_error(
				f"HTTP {response.status_code}\nURL: {endpoint}\nResponse: {response.text}",
				"EGIS API HTTP Error"
			)
			frappe.throw(
				f"API returned HTTP {response.status_code}. Please check the URL and credentials in EGIS Settings.\n\nCheck Error Log for details.",
				title="EGIS API Error"
			)

		response_text = response.text

		# Check if response is empty
		if not response_text or len(response_text.strip()) == 0:
			frappe.log_error("Empty response from EGIS API", "EGIS Empty Response")
			frappe.throw(
				"Received empty response from EGIS API. Please check your connection and credentials.",
				title="EGIS API Error"
			)

	except requests.exceptions.Timeout:
		frappe.log_error(f"Timeout connecting to {endpoint}", "EGIS Timeout Error")
		frappe.throw(
			"Connection to EGIS API timed out. Please try again.",
			title="EGIS Connection Timeout"
		)
	except requests.exceptions.RequestException as e:
		frappe.log_error(f"Network error: {str(e)}\nURL: {endpoint}", "EGIS Network Error")
		frappe.throw(
			f"Network error connecting to EGIS API: {str(e)}",
			title="EGIS Connection Error"
		)

	# Parse XML response
	response_data = parse_search_response_xml(response_text)

	# Check for errors
	if response_data.get('error'):
		error_msg = f"Error {response_data.get('ErrorNumber', '')}: {response_data.get('ErrorMessage', '')}"
		if response_data.get('ErrorDescription'):
			error_msg += f"\n{response_data.get('ErrorDescription')}"
		frappe.throw(error_msg, title="EGIS API Error")

	# Check if items exist in the system
	if "Body" in response_data and response_data["Body"].get("Item"):
		for item in response_data["Body"]["Item"]:
			item_code = item.get("ProductIdentification", {}).get("ProprietaryProductNumber")
			item_exists = 0
			if item_code and frappe.db.exists("Item", item_code):
				item_exists = 1
			item["item_exists"] = item_exists
	else:
		# No items found
		frappe.msgprint("No products found matching your search criteria.", title="No Results")
		response_data = {'Header': {}, 'Body': {'Item': []}}

	return json.dumps(response_data)

@frappe.whitelist()
def import_items(items):
	items = items.replace("&quot;", "'")
	items = json.loads(items)

	# Get EGIS settings for configurable values
	egis_settings = frappe.get_doc("EGIS Settings")

	# Validate required settings
	if not egis_settings.default_selling_price_list:
		frappe.throw("Please configure 'Default Selling Price List' in EGIS Settings before importing items.", title="Configuration Missing")

	if not egis_settings.parent_item_group:
		frappe.throw("Please configure 'Item Group' in EGIS Settings before importing items.", title="Configuration Missing")

	# Verify price list exists
	if not frappe.db.exists("Price List", egis_settings.default_selling_price_list):
		frappe.throw(f"Price List '{egis_settings.default_selling_price_list}' does not exist. Please create it first or select a different price list in EGIS Settings.", title="Price List Not Found")

	# Verify parent item group exists
	if not frappe.db.exists("Item Group", egis_settings.parent_item_group):
		frappe.throw(f"Item Group '{egis_settings.parent_item_group}' does not exist. Please create it first or select a different item group in EGIS Settings.", title="Item Group Not Found")

	for item in items:
		if item.get("item_exists"):
			update_item(item, egis_settings)
			continue

		# Fetch full long description from EGIS ProductDetail API
		product_number = item.get("proprietary_product_number")
		long_description = fetch_product_detail(product_number)
		if not long_description:
			# Fallback to short description if long description not available
			long_description = item.get("proprietary_product_description")

		brand = get_brand(item)
		item_group = get_item_group(item, egis_settings)
		item_doc = frappe.new_doc("Item")
		item_doc.item_code = product_number
		item_doc.item_name = item.get("proprietary_product_description")
		item_doc.description = long_description
		item_doc.item_group = item_group
		item_doc.brand = brand
		item_doc.manufacturer_product_number = item.get("manufacturer_product_number")
		item_doc.global_product_number = item.get("global_product_number")
		item_doc.website_image = item.get("image_url")
		# Use purchase price as standard rate (for Quotations/Sales Orders)
		# Retail prices are unrealistic and too high
		if item.get("purchase_price"):
			item_doc.standard_rate = flt(item.get("purchase_price"))
		item_doc.default_currency = item.get("currency_code")
		# Mark as EGIS item and store EGIS product number for API queries
		item_doc.is_egis_item = 1
		item_doc.custom_egis_product_number = product_number
		item_doc.save()

		# Create Item Price for selling (Quotations/Sales Orders) using purchase price
		if item.get("purchase_price"):
			# Check if price already exists
			existing_price = frappe.db.exists("Item Price", {
				"item_code": item_doc.name,
				"price_list": egis_settings.default_selling_price_list
			})

			if not existing_price:
				frappe.get_doc({
					"doctype": "Item Price",
					"item_code": item_doc.name,
					"price_list": egis_settings.default_selling_price_list,
					"price_list_rate": flt(item.get("purchase_price"))
				}).insert()
			else:
				# Update existing price
				frappe.db.set_value("Item Price", existing_price, "price_list_rate", flt(item.get("purchase_price")))

		# Store retail price separately if available (for reference only)
		if item.get("recommended_retail_price") and egis_settings.retail_price_list:
			# Use configured retail price list if specified
			if frappe.db.exists("Price List", egis_settings.retail_price_list):
				existing_retail_price = frappe.db.exists("Item Price", {
					"item_code": item_doc.name,
					"price_list": egis_settings.retail_price_list
				})

				if not existing_retail_price:
					frappe.get_doc({
						"doctype": "Item Price",
						"item_code": item_doc.name,
						"price_list": egis_settings.retail_price_list,
						"price_list_rate": flt(item.get("recommended_retail_price"))
					}).insert()
				else:
					# Update existing retail price
					frappe.db.set_value("Item Price", existing_retail_price, "price_list_rate", flt(item.get("recommended_retail_price")))

def get_brand(item):
	brand = item.get("manufacturer_name")
	if not frappe.db.exists("Brand", brand):
		brand = frappe.get_doc({
			"doctype": "Brand",
			"brand": brand,
			"id": item.get("manufacturer_id")
		})
		brand.insert()
		brand = brand.name
	return brand

def get_item_group(item, egis_settings):
	# Use the configured item group from EGIS Settings for all items
	return egis_settings.parent_item_group

def update_item(item, egis_settings):
	item_erpnext = frappe.get_doc("Item", item.get("proprietary_product_number"))
	changed = False

	# Fetch full long description from EGIS ProductDetail API
	product_number = item.get("proprietary_product_number")
	long_description = fetch_product_detail(product_number)
	if not long_description:
		# Fallback to short description if long description not available
		long_description = item.get("proprietary_product_description")

	if item_erpnext.item_name != item.get("proprietary_product_description"):
		item_erpnext.item_name = item.get("proprietary_product_description")
		changed = True
	if item_erpnext.description != long_description:
		item_erpnext.description = long_description
		changed = True
	if item_erpnext.manufacturer_product_number != item.get("manufacturer_product_number"):
		item_erpnext.manufacturer_product_number = item.get("manufacturer_product_number")
		changed = True
	if item_erpnext.global_product_number != item.get("global_product_number"):
		item_erpnext.global_product_number = item.get("global_product_number")
		changed = True

	brand = get_brand(item)
	if item_erpnext.brand != brand:
		item_erpnext.brand = brand
		changed = True

	item_group = get_item_group(item, egis_settings)
	if item_erpnext.item_group != item_group:
		item_erpnext.item_group = item_group
		changed = True

	# Mark as EGIS item if not already marked
	if not item_erpnext.is_egis_item:
		item_erpnext.is_egis_item = 1
		changed = True

	# Store EGIS product number for API queries (in case item_code is different)
	if item_erpnext.custom_egis_product_number != product_number:
		item_erpnext.custom_egis_product_number = product_number
		changed = True

	if changed:
		item_erpnext.save()

	# Only update Selling price (we don't need Buying price for EGIS items)
	update_item_price(item, egis_settings)

def update_item_price(item, egis_settings):
	"""
	Update Item Price for EGIS items
	Uses configured price lists from EGIS Settings
	"""
	# Use purchase price for selling (requirement: don't use high retail prices)
	purchase_price = flt(item.get("purchase_price"))

	if not purchase_price:
		# Log diagnostic information to understand why price is missing
		frappe.log_error(
			f"Item Code: {item.get('proprietary_product_number')}\n"
			f"Purchase Price Value: {item.get('purchase_price')}\n"
			f"Purchase Price (after flt): {purchase_price}\n"
			f"Full Item Data: {json.dumps(item, indent=2, default=str)}",
			"EGIS Price Update Failed - Missing Purchase Price"
		)
		frappe.throw(
			f"Cannot update price for item {item.get('proprietary_product_number')}: "
			f"Purchase price not available in EGIS response. Check Error Log for details."
		)
		return

	# Update or create Selling price using configured price list
	selling_prices = frappe.db.get_list("Item Price",
		filters={
			"item_code": item.get("proprietary_product_number"),
			"price_list": egis_settings.default_selling_price_list
		},
		fields=["name", "price_list_rate"]
	)

	if selling_prices:
		# Update existing price if different
		if selling_prices[0].price_list_rate != purchase_price:
			frappe.db.set_value("Item Price", selling_prices[0].name, "price_list_rate", purchase_price)
	else:
		# Create new price
		frappe.get_doc({
			"doctype": "Item Price",
			"item_code": item.get("proprietary_product_number"),
			"price_list": egis_settings.default_selling_price_list,
			"price_list_rate": purchase_price
		}).insert()

	# Also store retail price for reference if retail price list is configured
	if item.get("recommended_retail_price") and egis_settings.retail_price_list:
		if frappe.db.exists("Price List", egis_settings.retail_price_list):
			retail_price = flt(item.get("recommended_retail_price"))
			retail_price_list = frappe.db.get_list("Item Price",
				filters={
					"item_code": item.get("proprietary_product_number"),
					"price_list": egis_settings.retail_price_list
				},
				fields=["name", "price_list_rate"]
			)

			if retail_price_list:
				if retail_price_list[0].price_list_rate != retail_price:
					frappe.db.set_value("Item Price", retail_price_list[0].name, "price_list_rate", retail_price)
			else:
				frappe.get_doc({
					"doctype": "Item Price",
					"item_code": item.get("proprietary_product_number"),
					"price_list": egis_settings.retail_price_list,
					"price_list_rate": retail_price
				}).insert()
