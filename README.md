## EGIS Integration

Frappe app for getting data from EGIS using its API.

#### License

MIT

# EGIS-app
 
# Purpose of this app:
Our app connects the German version of Synaxon's EGIS Business Connector to ERPNext.
Product data can be searched, filtered, selected, and then transferred to ERPNext as items.
Duplicate items are not imported but updated.
This also enables price updates.
All imported items are marked accordingly and can be used to quickly create quotes for customers.
 
Supported ERPNext versions:
This app is intended to be used with ERPNext 15. 
It is very likely that it can also be used with version 16, but this has not yet been tested.
 
Supported EBC version:
Tests are conducted in December 2025/ January 20226. (EBC has no real version numbers.)
 
 
# Potential further development opportunities:
* The ordering process does not take place in ERPNext. There is no order export. The software is currently only designed for fast quotation creation.
* Prices are currently only adjusted on quotations/sales orders/sales invoices if the items are re-imported and then re-entered there.
* With minor changes, the UK version of the store can also be connected. (A different URL must be linked to achive this.)