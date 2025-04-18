frappe.listview_settings["Dashboard"] = {
	button: {
		show(doc) {
			return doc.id;
		},
		get_label() {
			return frappe.utils.icon("dashboard-list", "sm");
		},
		get_description(doc) {
			return __("View {0}", [`${doc.id}`]);
		},
		action(doc) {
			frappe.set_route("dashboard-view", doc.id);
		},
	},
};
