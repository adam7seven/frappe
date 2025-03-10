// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address", {
	refresh: function (frm) {
		if (frm.doc.__islocal) {
			const last_doc = frappe.contacts.get_last_doc(frm);
			if (
				frappe.dynamic_link &&
				frappe.dynamic_link.doc &&
				frappe.dynamic_link.doc.id == last_doc.docid
			) {
				frm.set_value("links", "");
				frm.add_child("links", {
					link_doctype: frappe.dynamic_link.doctype,
					link_id: frappe.dynamic_link.doc[frappe.dynamic_link.fieldname],
				});
			}
		}
		frm.set_query("link_doctype", "links", function () {
			return {
				query: "frappe.contacts.address_and_contact.filter_dynamic_link_doctypes",
				filters: {
					fieldtype: "HTML",
					fieldname: "address_html",
				},
			};
		});
		frm.refresh_field("links");

		if (frm.doc.links) {
			for (let i in frm.doc.links) {
				let link = frm.doc.links[i];
				frm.add_custom_button(
					__("{0}: {1}", [__(link.link_doctype), __(link.link_id)]),
					function () {
						frappe.set_route("Form", link.link_doctype, link.link_id);
					},
					__("Links")
				);
			}
		}
	},
	validate: function (frm) {
		// clear linked customer / supplier / sales partner on saving...
		if (frm.doc.links) {
			frm.doc.links.forEach(function (d) {
				frappe.model.remove_from_locals(d.link_doctype, d.link_id);
			});
		}
	},
	after_save: function (frm) {
		frappe.run_serially([
			() => frappe.timeout(1),
			() => {
				const last_doc = frappe.contacts.get_last_doc(frm);
				if (
					frappe.dynamic_link &&
					frappe.dynamic_link.doc &&
					frappe.dynamic_link.doc.id == last_doc.docid
				) {
					for (let i in frm.doc.links) {
						let link = frm.doc.links[i];
						if (
							last_doc.doctype == link.link_doctype &&
							last_doc.docid == link.link_id
						) {
							frappe.set_route("Form", last_doc.doctype, last_doc.docid);
						}
					}
				}
			},
		]);
	},
});
