frappe.listview_settings["ToDo"] = {
	hide_id_column: true,
	add_fields: ["reference_type", "reference_id"],

	onload: function (me) {
		me.page.set_title(__("To Do"));
	},

	button: {
		show: function (doc) {
			return doc.reference_id;
		},
		get_label: function () {
			return __("Open", null, "Access");
		},
		get_description: function (doc) {
			return __("Open {0}", [`${__(doc.reference_type)}: ${doc.reference_id}`]);
		},
		action: function (doc) {
			frappe.set_route("Form", doc.reference_type, doc.reference_id);
		},
	},
};
