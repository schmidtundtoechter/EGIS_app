# Copyright (c) 2025, Phamos and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.utils import flt
import requests


@frappe.whitelist()
def update_egis_prices_in_sales_order(sales_order_name):
	"""
	Update EGIS item prices in a Sales Order
	Only updates items that were originally imported from EGIS
	"""
	# Get the Sales Order
	sales_order = frappe.get_doc("Sales Order", sales_order_name)

	# Check if user has permission
	if not frappe.has_permission("Sales Order", "write", sales_order_name):
		frappe.throw("You don't have permission to update this Sales Order")

	# Get EGIS settings
	egis_settings = frappe.get_doc("EGIS Settings")

	# Find all EGIS items in the Sales Order
	# is_egis_item is fetched from Item master via fetch_from in Custom Field
	# But also check Item master as fallback for older Sales Orders
	egis_items = []
	for item in sales_order.items:
		is_egis = item.get("is_egis_item") or frappe.db.get_value("Item", item.item_code, "is_egis_item")
		if is_egis:
			egis_items.append({
				"idx": item.idx,
				"item_code": item.item_code,
				"qty": item.qty,
				"row": item
			})

	if not egis_items:
		return {
			"success": False,
			"message": "No EGIS items found in this Sales Order"
		}

	# Query EGIS API for latest prices
	updated_items = []
	failed_items = []

	for item_info in egis_items:
		item_code = item_info["item_code"]

		try:
			# Search for the item in EGIS by item code
			price_info = get_egis_item_price(item_code, egis_settings)

			# Validate price info
			if not price_info:
				# Item not found in EGIS at all
				frappe.log_error(
					f"Item Code: {item_code}\n"
					f"Reason: Item not found in EGIS search results\n"
					f"This usually means the item is discontinued or no longer available.",
					"EGIS Sales Order Price Update - Item Not Found"
				)
				failed_items.append({
					"item_code": item_code,
					"reason": "Item not found in EGIS catalog (may be discontinued)"
				})
				continue

			purchase_price_str = price_info.get("purchase_price")

			# Validate purchase price exists and is not zero/empty
			if not purchase_price_str or purchase_price_str == "" or purchase_price_str == "0" or purchase_price_str == "0.00":
				# Log diagnostic information
				frappe.log_error(
					f"Item Code: {item_code}\n"
					f"Purchase Price from EGIS: {repr(purchase_price_str)}\n"
					f"Full Price Info: {json.dumps(price_info, indent=2, default=str)}",
					"EGIS Sales Order Price Update - Zero/Empty Price"
				)

				# Determine reason
				if purchase_price_str == "" or not purchase_price_str:
					reason = "Price not available in EGIS (empty price field)"
				else:
					reason = f"Price is zero in EGIS (cannot use zero price)"

				failed_items.append({
					"item_code": item_code,
					"reason": reason
				})
				continue

			# Convert price to float
			new_rate = flt(purchase_price_str)

			# Double-check the converted price is valid
			if not new_rate or new_rate <= 0:
				frappe.log_error(
					f"Item Code: {item_code}\n"
					f"Purchase Price String: {repr(purchase_price_str)}\n"
					f"After flt() conversion: {new_rate}\n"
					f"Full Price Info: {json.dumps(price_info, indent=2, default=str)}",
					"EGIS Sales Order Price Update - Invalid Price After Conversion"
				)
				failed_items.append({
					"item_code": item_code,
					"reason": f"Invalid price after conversion: {purchase_price_str} -> {new_rate}"
				})
				continue

			# All validations passed - update the rate in Sales Order
			item_row = item_info["row"]
			old_rate = item_row.rate

			# Clear any margins to ensure rate equals price_list_rate
			item_row.margin_type = None
			item_row.margin_rate_or_amount = 0
			item_row.discount_percentage = 0
			item_row.discount_amount = 0

			# Update all rate-related fields
			item_row.price_list_rate = new_rate
			item_row.rate = new_rate
			item_row.amount = new_rate * item_row.qty
			item_row.net_rate = new_rate
			item_row.net_amount = new_rate * item_row.qty

			# Also update base currency fields if exchange rate exists
			if hasattr(item_row, 'conversion_factor') and item_row.conversion_factor:
				item_row.base_rate = new_rate * item_row.conversion_factor
				item_row.base_amount = item_row.amount * item_row.conversion_factor
				item_row.base_net_rate = new_rate * item_row.conversion_factor
				item_row.base_net_amount = item_row.net_amount * item_row.conversion_factor

			updated_items.append({
				"item_code": item_code,
				"old_rate": old_rate,
				"new_rate": new_rate
			})

		except Exception as e:
			frappe.log_error(
				f"Item Code: {item_code}\n"
				f"Exception: {str(e)}\n"
				f"Full Traceback: {frappe.get_traceback()}",
				"EGIS Sales Order Price Update - Exception"
			)
			failed_items.append({
				"item_code": item_code,
				"reason": f"Error: {str(e)}"
			})

	if updated_items:
		# Recalculate taxes and totals
		sales_order.calculate_taxes_and_totals()
		sales_order.save()

		return {
			"success": True,
			"updated_count": len(updated_items),
			"failed_count": len(failed_items),
			"updated_items": updated_items,
			"failed_items": failed_items,
			"message": f"Successfully updated {len(updated_items)} item(s). {len(failed_items)} item(s) could not be updated."
		}
	else:
		return {
			"success": False,
			"message": "No items could be updated. All items failed.",
			"failed_items": failed_items
		}


def build_bestprice_query_xml(username, password, product_number):
	"""
	Build XML document for BestpriceQuery to get the best price for a specific item.

	According to EGIS EBC documentation, bestpriceQuery accepts ProprietaryProductNumber
	and returns the best available price from distributors.
	"""
	import xml.etree.ElementTree as ET

	root = ET.Element('BestpriceQuery')
	root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
	root.set('xmlns', 'http://www.egis-online.de/EBC/schema/BestpriceQuery')
	root.set('xsi:schemaLocation', 'http://www.egis-online.de/EBC/schema/BestpriceQuery BestpriceQuery.xsd')

	# Transaction Header
	header = ET.SubElement(root, 'TransactionHeader')
	ET.SubElement(header, 'VersionId').text = '1.00'
	ET.SubElement(header, 'GenerationDateTime').text = frappe.utils.now()
	ET.SubElement(header, 'ERP').text = 'ERPNext'
	ET.SubElement(header, 'Login').text = username
	ET.SubElement(header, 'Password').text = password

	# Bestprice > Query > ProductReference > ProprietaryProductIdentifier > ProprietaryProductNumber
	bestprice_elem = ET.SubElement(root, 'Bestprice')
	query_elem = ET.SubElement(bestprice_elem, 'Query')
	prod_ref = ET.SubElement(query_elem, 'ProductReference')
	prop_id = ET.SubElement(prod_ref, 'ProprietaryProductIdentifier')
	ET.SubElement(prop_id, 'ProprietaryProductNumber').text = product_number

	# Include items with zero stock (so we can still get prices for out-of-stock items)
	ET.SubElement(query_elem, 'IncludeZeroStock').text = 'true'

	xml_str = ET.tostring(root, encoding='utf-8', method='xml')
	return xml_str.decode('utf-8')


def parse_bestprice_response_xml(xml_response):
	"""
	Parse XML response from BestpriceQuery.
	Returns price info or error details.
	"""
	import xml.etree.ElementTree as ET

	try:
		root = ET.fromstring(xml_response)
		ns = {'ns': 'http://www.egis-online.de/EBC/schema/BestpriceQueryResponse'}

		# Check for errors in TransactionHeader
		header = root.find('ns:TransactionHeader', ns)
		if header is not None:
			exception = header.find('ns:Exception', ns)
			if exception is not None:
				error_num = exception.find('ns:ErrorNumber', ns)
				error_msg = exception.find('ns:ErrorMessage', ns)
				error_desc = exception.find('ns:ErrorDescription', ns)
				return {
					'error': True,
					'ErrorNumber': error_num.text if error_num is not None else '',
					'ErrorMessage': error_msg.text if error_msg is not None else '',
					'ErrorDescription': error_desc.text if error_desc is not None else ''
				}

		# Parse successful response - find Bestprice element
		bestprice = root.find('ns:Bestprice', ns)
		if bestprice is None:
			# Try without namespace
			bestprice = root.find('.//Bestprice')

		if bestprice is not None:
			# Get Body > DistributorProductItem > UnitPrice
			body = bestprice.find('ns:Body', ns)
			if body is None:
				body = bestprice.find('Body')

			if body is not None:
				dist_item = body.find('ns:DistributorProductItem', ns)
				if dist_item is None:
					dist_item = body.find('DistributorProductItem')

				if dist_item is not None:
					unit_price = dist_item.find('ns:UnitPrice', ns)
					if unit_price is None:
						unit_price = dist_item.find('UnitPrice')

					if unit_price is not None:
						# Extract prices
						purchase_price = unit_price.find('ns:PurchasePrice', ns)
						if purchase_price is None:
							purchase_price = unit_price.find('PurchasePrice')

						currency = unit_price.find('ns:CurrencyCode', ns)
						if currency is None:
							currency = unit_price.find('CurrencyCode')

						retail_price = unit_price.find('ns:RetailPrice', ns)
						if retail_price is None:
							retail_price = unit_price.find('RetailPrice')

						return {
							'purchase_price': purchase_price.text if purchase_price is not None else None,
							'currency': currency.text if currency is not None else 'EUR',
							'retail_price': retail_price.text if retail_price is not None else None
						}

		return None

	except ET.ParseError as e:
		frappe.log_error(f"XML Parse Error: {str(e)}\nResponse: {xml_response}", "EGIS Bestprice XML Parse Error")
		return {'error': True, 'ErrorMessage': 'Invalid XML response', 'ErrorDescription': str(e)}


def get_egis_item_price(item_code, egis_settings):
	"""
	Query EGIS API to get the latest best price for a specific item.
	Uses bestpriceQuery API which is designed for single-item price lookup.
	"""
	# Build endpoint URL
	base_url = egis_settings.url.rstrip('/')

	if 'egis-online.de' in base_url:
		component = "Artikelstamm"
	else:
		component = "ProductMaster"

	endpoint = f"{base_url}/{component}/bestpriceQuery"

	# Build XML request for bestpriceQuery
	xml_payload = build_bestprice_query_xml(
		egis_settings.user,
		egis_settings.get_password("password"),
		item_code
	)

	# Send request
	headers = {'Content-Type': 'text/xml; charset=utf-8'}

	try:
		response = requests.post(
			endpoint,
			data=xml_payload.encode('utf-8'),
			headers=headers,
			timeout=30
		)

		if response.status_code != 200:
			frappe.log_error(
				f"EGIS API Error for item {item_code}: HTTP {response.status_code}\nResponse: {response.text[:500]}",
				"EGIS Price Update Error"
			)
			return None

		# Parse response
		result = parse_bestprice_response_xml(response.text)

		# Check for errors
		if result and result.get('error'):
			frappe.log_error(
				f"EGIS API Error for item {item_code}: {result.get('ErrorNumber')} - {result.get('ErrorMessage')}\n{result.get('ErrorDescription')}",
				"EGIS Price Update Error"
			)
			return None

		return result

	except requests.exceptions.Timeout:
		frappe.log_error(
			f"Timeout querying EGIS for item {item_code}",
			"EGIS Price Update Timeout"
		)
		return None
	except Exception as e:
		frappe.log_error(
			f"Error querying EGIS for item {item_code}: {str(e)}",
			"EGIS Price Update Error"
		)
		return None
