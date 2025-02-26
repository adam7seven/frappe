// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.formview");

frappe.views.FormFactory = class FormFactory extends frappe.views.Factory {
	make(route) {
		var doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype;

		if (!frappe.views.formview[doctype_layout]) {
			frappe.model.with_doctype(doctype, () => {
				this.page = frappe.container.add_page(doctype_layout);
				frappe.views.formview[doctype_layout] = this.page;
				this.make_and_show(doctype, route);
			});
		} else {
			this.show_doc(route);
		}

		this.setup_events();
	}

	make_and_show(doctype, route) {
		if (frappe.router.doctype_layout) {
			frappe.model.with_doc("DocType Layout", frappe.router.doctype_layout, () => {
				this.make_form(doctype);
				this.show_doc(route);
			});
		} else {
			this.make_form(doctype);
			this.show_doc(route);
		}
	}

	make_form(doctype) {
		this.page.frm = new frappe.ui.form.Form(
			doctype,
			this.page,
			true,
			frappe.router.doctype_layout
		);
	}

	setup_events() {
		if (!this.initialized) {
			$(document).on("page-change", function () {
				frappe.ui.form.close_grid_form();
			});
		}
		this.initialized = true;
	}

	show_doc(route) {
		var doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype,
			id = route.slice(2).join("/");

		if (frappe.model.new_ids[id]) {
			// document has been renamed, reroute
			id = frappe.model.new_ids[id];
			frappe.set_route("Form", doctype_layout, id);
			return;
		}

		const doc = frappe.get_doc(doctype, id);
		if (
			doc &&
			frappe.model.get_docinfo(doctype, id) &&
			(doc.__islocal || frappe.model.is_fresh(doc))
		) {
			// is document available and recent?
			this.render(doctype_layout, id);
		} else {
			this.fetch_and_render(doctype, id, doctype_layout);
		}
	}

	fetch_and_render(doctype, id, doctype_layout) {
		frappe.model.with_doc(doctype, id, (id, r) => {
			if (r && r["403"]) return; // not permitted

			if (!(locals[doctype] && locals[doctype][id])) {
				if (id && id.substr(0, 3) === "new") {
					this.render_new_doc(doctype, id, doctype_layout);
				} else {
					frappe.show_not_found();
				}
				return;
			}
			this.render(doctype_layout, id);
		});
	}

	render_new_doc(doctype, id, doctype_layout) {
		const new_id = frappe.model.make_new_doc_and_get_id(doctype, true);
		if (new_id === id) {
			this.render(doctype_layout, id);
		} else {
			frappe.route_flags.replace_route = true;
			frappe.set_route("Form", doctype_layout, new_id);
		}
	}

	render(doctype_layout, id) {
		frappe.container.change_to(doctype_layout);
		frappe.views.formview[doctype_layout].frm.refresh(id);
	}
};
