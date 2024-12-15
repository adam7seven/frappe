// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Addresses And Contacts"] = {
	filters: [
		{
			reqd: 1,
			fieldname: "reference_doctype",
			label: __("Entity Type"),
			fieldtype: "Link",
			options: "DocType",
			get_query: function () {
				return {
					filters: {
						id: ["in", "Contact, Address"],
					},
				};
			},
		},
		{
			fieldname: "reference_id",
			label: __("Entity ID"),
			fieldtype: "Dynamic Link",
			get_options: function () {
				let reference_doctype = frappe.query_report.get_filter_value("reference_doctype");
				if (!reference_doctype) {
					frappe.throw(__("Please select Entity Type first"));
				}
				return reference_doctype;
			},
		},
	],
};
