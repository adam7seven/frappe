// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.db = {
	get_list: function (doctype, args) {
		if (!args) {
			args = {};
		}
		args.doctype = doctype;
		if (!args.fields) {
			args.fields = ["id"];
		}
		if (!("limit" in args)) {
			args.limit = 20;
		}
		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.reportview.get_list",
				args: args,
				type: "GET",
				callback: function (r) {
					resolve(r.message);
				},
			});
		});
	},
	exists: function (doctype, idOrFilters) {
		return new Promise((resolve) => {
			let filters;
			if (typeof idOrFilters === "string") {
				// may be cached and more effecient
				frappe.db.get_value(doctype, { id: idOrFilters }, "id").then((r) => {
					r.message && r.message.id ? resolve(true) : resolve(false);
				});
			} else if (typeof idOrFilters === "object") {
				frappe.db.count(doctype, { filters: idOrFilters, limit: 1 }).then((count) => {
					resolve(count > 0);
				});
			}
		});
	},
	get_value: function (doctype, filters, fieldname, callback, parent_doc) {
		return frappe.call({
			method: "frappe.client.get_value",
			type: "GET",
			args: {
				doctype: doctype,
				fieldname: fieldname,
				filters: filters,
				parent: parent_doc,
			},
			callback: function (r) {
				callback && callback(r.message);
			},
		});
	},
	get_single_value: (doctype, field) => {
		return new Promise((resolve) => {
			frappe
				.call({
					method: "frappe.client.get_single_value",
					args: { doctype, field },
					type: "GET",
				})
				.then((r) => resolve(r ? r.message : null));
		});
	},
	set_value: function (doctype, docid, fieldname, value, callback) {
		return frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: doctype,
				id: docid,
				fieldname: fieldname,
				value: value,
			},
			callback: function (r) {
				callback && callback(r.message);
			},
		});
	},
	get_doc: function (doctype, id, filters) {
		return new Promise((resolve, reject) => {
			frappe
				.call({
					method: "frappe.client.get",
					type: "GET",
					args: { doctype, id, filters },
					callback: (r) => {
						frappe.model.sync(r.message);
						resolve(r.message);
					},
				})
				.fail(reject);
		});
	},
	insert: function (doc) {
		return frappe.xcall("frappe.client.insert", { doc });
	},
	delete_doc: function (doctype, id) {
		return new Promise((resolve) => {
			frappe.call("frappe.client.delete", { doctype, id }, (r) => resolve(r.message));
		});
	},
	count: function (doctype, args = {}, cache = false) {
		let filters = args.filters || {};
		let limit = args.limit;

		// has a filter with childtable?
		const distinct =
			Array.isArray(filters) &&
			filters.some((filter) => {
				return filter[0] !== doctype;
			});

		const fields = [];

		return frappe.xcall(
			"frappe.desk.reportview.get_count",
			{
				doctype,
				filters,
				fields,
				distinct,
				limit,
			},
			cache ? "GET" : "POST",
			{ cache }
		);
	},
	get_link_options(doctype, txt = "", filters = {}) {
		return new Promise((resolve) => {
			frappe.call({
				type: "GET",
				method: "frappe.desk.search.search_link",
				args: {
					doctype,
					txt,
					filters,
				},
				callback(r) {
					resolve(r.message);
				},
			});
		});
	},
};
