## EGIS Integration

Frappe app for getting data from EGIS using its API.

#### License

MIT

# EGIS-app
 
## Purpose of this app:
Our app connects the German version of Synaxon's EGIS Business Connector to ERPNext.
Product data can be searched, filtered, selected, and then transferred to ERPNext as items.
Duplicate items are not imported but updated.
This also enables price updates.
All imported items are marked accordingly and can be used to quickly create quotes for customers.

Only the purchase prices is automatically transferred to QUOTATION when they enter all the needed items.
The EGIS retail prices are in the most cases too high.
They are therefore imported, but not used for quotations.
The final price is always manually editable in QUOTATION and SALES ORDER.

Purchase prices update on SALES ORDER:
There is a button at the top right corner of SALES ORDER. Clicking on this button will pull the retail prices of this SALES ORDER again.
Only the imported EGIS prices of/in this SALES ORDER will be updated.
These EGIS item prices remain manually adjustable afterwards.
Other items are not touched. 
When you push the button, the system takes time to update the prices. You will get a info box, how many prices still have to be updated while you are waiting.  

 
## Supported ERPNext versions:
This app is intended to be used with ERPNext 15. 
It is very likely that it can also be used with version 16, but this has not yet been tested.
 
## Supported EBC version:
Tests are conducted in December 2025/ January 20226. (EBC has no real version numbers.)
 
 
## Potential further development opportunities:
* The ordering process does not take place in ERPNext. There is no order export. The software is currently only designed for fast quotation creation.
* With minor changes, the UK version of the store can also be connected. (A different URL must be linked to achive this.)
