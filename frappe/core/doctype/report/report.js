// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Report", {
	refresh: function (frm) {
		if (frm.doc.is_standard === "Yes" && !frappe.boot.developer_mode) {
			// make the document read-only
			frm.disable_form();
		} else {
			frm.enable_save();
		}

		let doc = frm.doc;
		if (!doc.__islocal) {
			frm.add_custom_button(
				__("Show Report"),
				function () {
					switch (doc.report_type) {
						case "Report Builder":
							frappe.set_route("List", doc.ref_doctype, "Report", doc.id);
							break;
						case "Query Report":
							frappe.set_route("query-report", doc.id);
							break;
						case "Script Report":
							frappe.set_route("query-report", doc.id);
							break;
						case "Custom Report":
							frappe.set_route("query-report", doc.id);
							break;
					}
				},
				"fa fa-table"
			);
		}

		if (doc.is_standard === "Yes" && frm.perm[0].write) {
			frm.add_custom_button(
				doc.disabled ? __("Enable Report") : __("Disable Report"),
				function () {
					frm.call("toggle_disable", {
						disable: doc.disabled ? 0 : 1,
					}).then(() => {
						frm.reload_doc();
					});
				},
				doc.disabled ? "fa fa-check" : "fa fa-off"
			);
		}

		frm.set_query("ref_doctype", () => {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		if (["en", "en-GB", "en-US"].includes(frappe.boot.lang)) {
			frm.set_df_property("add_translate_data", "hidden", 1);
		} else {
			frm.set_df_property("add_translate_data", "hidden", 0);
		}
	},

	ref_doctype: function (frm) {
		if (frm.doc.ref_doctype) {
			frm.trigger("set_doctype_roles");
		}
	},

	set_doctype_roles: function (frm) {
		return frm.call("set_doctype_roles").then(() => {
			frm.refresh_field("roles");
		});
	},
});
