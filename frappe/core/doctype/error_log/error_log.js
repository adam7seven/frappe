// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Error Log", {
	refresh: function (frm) {
		frm.disable_save();

		if (frm.doc.reference_doctype && frm.doc.reference_id) {
			frm.add_custom_button(__("Show Related Errors"), function () {
				frappe.set_route("List", "Error Log", {
					reference_doctype: frm.doc.reference_doctype,
					reference_id: frm.doc.reference_id,
				});
			});
		}
	},
});
