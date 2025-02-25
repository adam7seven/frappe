frappe.listview_settings["Calendar View"] = {
	button: {
		show(doc) {
			return doc.id;
		},
		get_label() {
			return frappe.utils.icon("calendar", "sm");
		},
		get_description(doc) {
			return __("View {0}", [`${doc.id}`]);
		},
		action(doc) {
			frappe.set_route("List", doc.reference_doctype, "Calendar", doc.id);
		},
	},
};
