# Copyright (c) 2025, Phamos and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.utils import flt
from egis_integration.egis_integration.doctype.egis_search_query.egis_search_query import (
	build_search_query_xml,
	parse_search_response_xml
)
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
	egis_items = []
	for item in sales_order.items:
		if item.get("is_egis_item"):
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

			if price_info and price_info.get("purchase_price"):
				# Update the rate in Sales Order
				item_row = item_info["row"]
				old_rate = item_row.rate
				new_rate = flt(price_info["purchase_price"])

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
			else:
				failed_items.append({
					"item_code": item_code,
					"reason": "Price not found in EGIS"
				})

		except Exception as e:
			failed_items.append({
				"item_code": item_code,
				"reason": str(e)
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


def get_egis_item_price(item_code, egis_settings):
	"""
	Query EGIS API to get the latest price for a specific item
	"""
	# Build endpoint URL
	base_url = egis_settings.url.rstrip('/')

	if 'egis-online.de' in base_url:
		component = "Artikelstamm"
	else:
		component = "ProductMaster"

	endpoint = f"{base_url}/{component}/searchQuery"

	# Build XML request to search by item code (ProprietaryProductNumber)
	xml_payload = build_search_query_xml(
		egis_settings.user,
		egis_settings.get_password("password"),
		item_code,  # Search for exact item code
		{},  # No additional search options
		1  # Start row
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
				f"EGIS API Error for item {item_code}: HTTP {response.status_code}",
				"EGIS Price Update Error"
			)
			return None

		# Parse response
		response_data = parse_search_response_xml(response.text)

		# Check for errors
		if response_data.get('error'):
			frappe.log_error(
				f"EGIS API Error for item {item_code}: {response_data.get('ErrorMessage')}",
				"EGIS Price Update Error"
			)
			return None

		# Get the first item from results
		if response_data.get('Body') and response_data['Body'].get('Item'):
			items = response_data['Body']['Item']

			# Find exact match by item code
			for item in items:
				prod_id = item.get('ProductIdentification', {})
				if prod_id.get('ProprietaryProductNumber') == item_code:
					unit_price = item.get('UnitPrice', {})
					return {
						"purchase_price": unit_price.get('PurchasePrice'),
						"currency": unit_price.get('CurrencyCode'),
						"retail_price": unit_price.get('RecommendedRetailPrice')
					}

		return None

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
