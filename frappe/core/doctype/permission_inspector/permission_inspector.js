// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

const call_debug = (frm) => {
	frm.trigger("debug");
};

frappe.ui.form.on("Permission Inspector", {
	refresh(frm) {
		frm.disable_save();
	},
	docid: call_debug,
	ref_doctype(frm) {
		frm.doc.docid = ""; // Usually doctype change invalidates docid
		call_debug(frm);
	},
	user: call_debug,
	permission_type: call_debug,
	debug(frm) {
		if (frm.doc.ref_doctype && frm.doc.user) {
			frm.call("debug");
		}
	},
});
