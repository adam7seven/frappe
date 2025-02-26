// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

Object.assign(frappe.model, {
	docinfo: {},
	sync: function (r) {
		/* docs:
			extract docs, docinfo (attachments, comments, assignments)
			from incoming request and set in `locals` and `frappe.model.docinfo`
		*/
		var isPlain;
		if (!r.docs && !r.docinfo) r = { docs: r };

		isPlain = $.isPlainObject(r.docs);
		if (isPlain) r.docs = [r.docs];

		if (r.docs) {
			for (var i = 0, l = r.docs.length; i < l; i++) {
				var d = r.docs[i];

				if (locals[d.doctype] && locals[d.doctype][d.id]) {
					// update values
					frappe.model.update_in_locals(d);
				} else {
					frappe.model.add_to_locals(d);
				}

				d.__last_sync_on = new Date();

				if (d.doctype === "DocType") {
					frappe.meta.sync(d);
				}

				if (d.localid) {
					frappe.model.rename_after_save(d, i);
				}
			}
		}

		frappe.model.sync_docinfo(r);
		return r.docs;
	},

	rename_after_save: (d, i) => {
		frappe.model.new_ids[d.localid] = d.id;
		$(document).trigger("rename", [d.doctype, d.localid, d.id]);
		delete locals[d.doctype][d.localid];

		// update docinfo to new dict keys
		if (i === 0) {
			frappe.model.docinfo[d.doctype][d.id] = frappe.model.docinfo[d.doctype][d.localid];
			frappe.model.docinfo[d.doctype][d.localid] = undefined;
		}
	},

	sync_docinfo: (r) => {
		// set docinfo (comments, assign, attachments)
		if (r.docinfo) {
			const { doctype, id } = r.docinfo;
			if (!frappe.model.docinfo[doctype]) {
				frappe.model.docinfo[doctype] = {};
			}
			frappe.model.docinfo[doctype][id] = r.docinfo;

			// copy values to frappe.boot.user_info
			Object.assign(frappe.boot.user_info, r.docinfo.user_info);
		}

		return r.docs;
	},

	add_to_locals: function (doc) {
		if (!locals[doc.doctype]) locals[doc.doctype] = {};

		if (!doc.id && doc.__islocal) {
			// get id (local if required)
			if (!doc.parentfield) frappe.model.clear_doc(doc);

			doc.id = frappe.model.get_new_id(doc.doctype);

			if (!doc.parentfield)
				frappe.provide("frappe.model.docinfo." + doc.doctype + "." + doc.id);
		}

		locals[doc.doctype][doc.id] = doc;

		let meta = frappe.get_meta(doc.doctype);
		let is_table = meta ? meta.istable : doc.parentfield;
		// add child docs to locals
		if (!is_table) {
			for (var i in doc) {
				var value = doc[i];

				if ($.isArray(value)) {
					for (var x = 0, y = value.length; x < y; x++) {
						var d = value[x];

						if (typeof d == "object" && !d.parent) d.parent = doc.id;

						frappe.model.add_to_locals(d);
					}
				}
			}
		}
	},

	update_in_locals: function (doc) {
		// update values in the existing local doc instead of replacing
		let local_doc = locals[doc.doctype][doc.id];
		let clear_keys = function (source, target) {
			Object.keys(target).map((key) => {
				if (source[key] == undefined) delete target[key];
			});
		};

		for (let fieldname in doc) {
			let df = frappe.meta.get_field(doc.doctype, fieldname);
			if (df && frappe.model.table_fields.includes(df.fieldtype)) {
				// table
				if (!(doc[fieldname] instanceof Array)) {
					doc[fieldname] = [];
				}

				if (!(local_doc[fieldname] instanceof Array)) {
					local_doc[fieldname] = [];
				}

				// child table, override each row and append new rows if required
				for (let i = 0; i < doc[fieldname].length; i++) {
					let d = doc[fieldname][i];
					let local_d = local_doc[fieldname][i];
					if (local_d) {
						// deleted and added again
						if (!locals[d.doctype]) locals[d.doctype] = {};

						if (!d.id) {
							// incoming row is new, find a new id
							d.id = frappe.model.get_new_id(doc.doctype);
						}

						// if incoming row is not registered, register it
						if (!locals[d.doctype][d.id]) {
							// detach old key
							delete locals[d.doctype][local_d.id];

							// re-attach with new id
							locals[d.doctype][d.id] = local_d;
						}

						// row exists, just copy the values
						Object.assign(local_d, d);
						clear_keys(d, local_d);
					} else {
						local_doc[fieldname].push(d);
						if (!d.parent) d.parent = doc.id;
						frappe.model.add_to_locals(d);
					}
				}

				// remove extra rows
				if (local_doc[fieldname].length > doc[fieldname].length) {
					for (let i = doc[fieldname].length; i < local_doc[fieldname].length; i++) {
						// clear from local
						let d = local_doc[fieldname][i];
						if (locals[d.doctype] && locals[d.doctype][d.id]) {
							delete locals[d.doctype][d.id];
						}
					}
					local_doc[fieldname].length = doc[fieldname].length;
				}
			} else {
				// literal
				local_doc[fieldname] = doc[fieldname];
			}
		}

		// clear keys on parent
		clear_keys(doc, local_doc);
	},
});
