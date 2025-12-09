// EGIS Integration - Sales Order customizations

frappe.ui.form.on('Sales Order', {
	refresh: function(frm) {
		// Add EGIS Price Update button if Sales Order has EGIS items
		if (frm.doc.docstatus === 0) {  // Only for draft Sales Orders
			// Check if there are any EGIS items
			let has_egis_items = false;
			if (frm.doc.items) {
				for (let item of frm.doc.items) {
					if (item.is_egis_item) {
						has_egis_items = true;
						break;
					}
				}
			}

			if (has_egis_items) {
				frm.add_custom_button(__('EGIS Preisupdate'), function() {
					update_egis_prices(frm);
				}, __('Actions'));
			}
		}
	}
});

function update_egis_prices(frm) {
	// Show confirmation dialog
	frappe.confirm(
		__('This will update the purchase prices for all EGIS items in this Sales Order from the latest EGIS catalog. Do you want to continue?'),
		function() {
			// User confirmed - proceed with update
			frappe.dom.freeze(__('Updating EGIS prices...'));

			frappe.call({
				method: 'egis_integration.egis_integration.sales_order_price_update.update_egis_prices_in_sales_order',
				args: {
					sales_order_name: frm.doc.name
				},
				callback: function(r) {
					frappe.dom.unfreeze();

					if (r.message && r.message.success) {
						// Show success message
						let message = r.message.message;

						// Show details of updated items
						if (r.message.updated_items && r.message.updated_items.length > 0) {
							message += '<br><br><b>' + __('Updated Items:') + '</b><ul>';
							for (let item of r.message.updated_items) {
								message += '<li>' + item.item_code + ': ';
								message += frappe.format(item.old_rate, {fieldtype: 'Currency'}) + ' → ';
								message += frappe.format(item.new_rate, {fieldtype: 'Currency'}) + '</li>';
							}
							message += '</ul>';
						}

						// Show failed items if any
						if (r.message.failed_items && r.message.failed_items.length > 0) {
							message += '<br><b>' + __('Failed Items:') + '</b><ul>';
							for (let item of r.message.failed_items) {
								message += '<li>' + item.item_code + ': ' + item.reason + '</li>';
							}
							message += '</ul>';
						}

						frappe.msgprint({
							title: __('EGIS Price Update Complete'),
							message: message,
							indicator: 'green'
						});

						// Reload the form to show updated prices
						frm.reload_doc();

					} else {
						// Show error message
						frappe.msgprint({
							title: __('EGIS Price Update Failed'),
							message: r.message ? r.message.message : __('An error occurred while updating prices'),
							indicator: 'red'
						});

						// Show failed items if available
						if (r.message && r.message.failed_items && r.message.failed_items.length > 0) {
							let fail_message = '<b>' + __('Failed Items:') + '</b><ul>';
							for (let item of r.message.failed_items) {
								fail_message += '<li>' + item.item_code + ': ' + item.reason + '</li>';
							}
							fail_message += '</ul>';

							frappe.msgprint({
								title: __('Details'),
								message: fail_message,
								indicator: 'orange'
							});
						}
					}
				},
				error: function(r) {
					frappe.dom.unfreeze();
					frappe.msgprint({
						title: __('Error'),
						message: __('An error occurred while communicating with the server'),
						indicator: 'red'
					});
				}
			});
		},
		function() {
			// User cancelled
			return;
		}
	);
}
