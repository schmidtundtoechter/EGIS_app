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

@frappe.whitelist()
def make_request(search_term, search_options, start_row):
	search_options = json.loads(search_options or {})
	print(search_options, type(search_options))
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

	print("XML Payload:", xml_payload)

	# Headers must include Content-Type: text/xml and charset UTF-8
	headers = {
		'Content-Type': 'text/xml; charset=utf-8'
	}

	try:
		response = requests.post(endpoint, data=xml_payload.encode('utf-8'), headers=headers, timeout=30)

		# Log response details for debugging
		print("Response Status Code:", response.status_code)
		print("Response Headers:", dict(response.headers))
		print("Raw Response:", response.text[:500])  # First 500 chars

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
	for item in items:
		if item.get("item_exists"):
			update_item(item)
			continue
		brand = get_brand(item)
		item_group = get_item_group(item)
		item_doc = frappe.new_doc("Item")
		item_doc.item_code = item.get("proprietary_product_number")
		item_doc.item_name = item.get("proprietary_product_description")
		item_doc.description = item.get("proprietary_product_description")
		item_doc.item_group = item_group
		item_doc.brand = brand
		item_doc.manufacturer_product_number = item.get("manufacturer_product_number")
		item_doc.global_product_number = item.get("global_product_number")
		item_doc.website_image = item.get("image_url")
		if item.get("recommended_retail_price"):
			item_doc.standard_rate = flt(item.get("recommended_retail_price"))
		item_doc.default_currency = item.get("currency_code")
		item_doc.save()

		if item.get("purchase_price"):
			frappe.get_doc({
				"doctype": "Item Price",
				"item_code": item_doc.name,
				"price_list": "Standard Buying",
				"price_list_rate": flt(item.get("purchase_price"))
			}).insert()

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

def get_item_group(item):
	item_group = item.get("product_group_id")
	if not frappe.db.exists("Item Group", item_group):
		item_group = frappe.get_doc({
			"doctype": "Item Group",
			"parent_item_group": "EGIS",
			"item_group_name": item_group
		})
		item_group.insert()
		item_group = item_group.name
	return item_group

def update_item(item):
	item_erpnext = frappe.get_doc("Item", item.get("proprietary_product_number"))
	changed = False
	if item_erpnext.item_name != item.get("proprietary_product_description"):
		item_erpnext.item_name = item.get("proprietary_product_description")
		changed = True
	if item_erpnext.description != item.get("proprietary_product_description"):
		item_erpnext.description = item.get("proprietary_product_description")
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

	item_group = get_item_group(item)
	if item_erpnext.item_group != item_group:
		item_erpnext.item_group = item_group
		changed = True

	if changed:
		item_erpnext.save()

	update_item_price(item, "Buying")
	update_item_price(item, "Selling")

def update_item_price(item, buying_or_selling):
	if buying_or_selling == "Buying":
		operation = "Buying"
		price_field_name = "purchase_price"
	elif buying_or_selling == "Selling":
		operation = "Selling"
		price_field_name = "recommended_retail_price"
	item_price_list = frappe.db.get_list("Item Price",
						filters={"item_code": item.get("proprietary_product_number"), operation: 1},
						fields=["name", "price_list_rate"])
	if len(item_price_list) > 0:
		name = item_price_list[0]["name"]
		price = item_price_list[0]["price_list_rate"]
		if price != flt(item.get(price_field_name)):
			frappe.db.set_value("Item Price", name, "price_list_rate", flt(item.get(price_field_name)))
	else:
		if item.get(price_field_name):
			frappe.get_doc({
				"doctype": "Item Price",
				"item_code": item.get("proprietary_product_number"),
				"price_list": "Standard {}".format(operation),
				"price_list_rate": flt(item.get(price_field_name))
			}).insert()
