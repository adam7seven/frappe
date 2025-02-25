// bind events

frappe.ui.form.on("ToDo", {
	onload: function (frm) {
		frm.set_query("reference_type", function (txt) {
			return {
				filters: {
					issingle: 0,
				},
			};
		});
	},
	refresh: function (frm) {
		if (frm.doc.reference_type && frm.doc.reference_id) {
			frm.add_custom_button(__(frm.doc.reference_id), function () {
				frappe.set_route("Form", frm.doc.reference_type, frm.doc.reference_id);
			});
		}

		if (!frm.doc.__islocal) {
			if (frm.doc.status !== "Closed") {
				frm.add_custom_button(
					__("Close"),
					function () {
						frm.set_value("status", "Closed");
						frm.save(null, function () {
							// back to list
							frappe.set_route("List", "ToDo");
						});
					},
					"fa fa-check",
					"btn-success"
				);
			} else {
				frm.add_custom_button(
					__("Reopen"),
					function () {
						frm.set_value("status", "Open");
						frm.save();
					},
					null,
					"btn-default"
				);
			}
			frm.add_custom_button(
				__("New"),
				function () {
					frappe.new_doc("ToDo");
				},
				null,
				"btn-default"
			);
		}
	},
});
