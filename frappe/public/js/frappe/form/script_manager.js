// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form.handlers");

window.extend_cscript = (cscript, controller_object) => {
	$.extend(cscript, controller_object);
	if (cscript && controller_object) {
		cscript.__proto__ = controller_object.__proto__;
	}
	return cscript;
};

frappe.ui.form.get_event_handler_list = function (doctype, fieldname) {
	if (!frappe.ui.form.handlers[doctype]) {
		frappe.ui.form.handlers[doctype] = {};
	}
	if (!frappe.ui.form.handlers[doctype][fieldname]) {
		frappe.ui.form.handlers[doctype][fieldname] = [];
	}
	return frappe.ui.form.handlers[doctype][fieldname];
};

frappe.ui.form.on = frappe.ui.form.on_change = function (doctype, fieldname, handler) {
	var add_handler = function (fieldname, handler) {
		var handler_list = frappe.ui.form.get_event_handler_list(doctype, fieldname);

		let _handler = (...args) => {
			try {
				return handler(...args);
			} catch (error) {
				console.error(handler);
				throw error;
			}
		};

		handler_list.push(_handler);

		// add last handler to events so it can be called as
		// frm.events.handler(frm)
		if (cur_frm && cur_frm.doctype === doctype) {
			cur_frm.events[fieldname] = _handler;
		}
	};

	if (!handler && $.isPlainObject(fieldname)) {
		// a dict of handlers {fieldname: handler, ...}
		for (var key in fieldname) {
			var fn = fieldname[key];
			if (typeof fn === "function") {
				add_handler(key, fn);
			}
		}
	} else {
		add_handler(fieldname, handler);
	}
};

// remove standard event handlers
frappe.ui.form.off = function (doctype, fieldname, handler) {
	var handler_list = frappe.ui.form.get_event_handler_list(doctype, fieldname);
	if (handler_list.length) {
		frappe.ui.form.handlers[doctype][fieldname] = [];
	}

	if (cur_frm && cur_frm.doctype === doctype && cur_frm.events[fieldname]) {
		delete cur_frm.events[fieldname];
	}

	if (cur_frm && cur_frm.cscript && cur_frm.cscript[fieldname]) {
		delete cur_frm.cscript[fieldname];
	}
};

frappe.ui.form.trigger = function (doctype, fieldname) {
	cur_frm.script_manager.trigger(fieldname, doctype);
};

frappe.ui.form.ScriptManager = class ScriptManager {
	constructor(opts) {
		$.extend(this, opts);
	}
	make(ControllerClass) {
		this.frm.cscript = extend_cscript(
			this.frm.cscript,
			new ControllerClass({ frm: this.frm })
		);
	}
	trigger(event_id, doctype, id) {
		// trigger all the form level events that
		// are bound to this event_id
		let me = this;
		doctype = doctype || this.frm.doctype;
		id = id || this.frm.docid;

		let tasks = [];
		let handlers = this.get_handlers(event_id, doctype);

		// helper for child table
		this.frm.selected_doc = frappe.get_doc(doctype, id);

		let runner = (_function, is_old_style) => {
			let _promise = null;
			if (is_old_style) {
				// old style arguments (doc, cdt, cdn)
				_promise = me.frm.cscript[_function](me.frm.doc, doctype, id);
			} else {
				// new style (frm, doctype, id)
				_promise = _function(me.frm, doctype, id);
			}

			// if the trigger returns a promise, return it,
			// or use the default promise frappe.after_ajax
			if (_promise && _promise.then) {
				return _promise;
			} else {
				return frappe.after_server_call();
			}
		};

		// make list of functions to be run serially
		handlers.new_style.forEach((_function) => {
			if (event_id === "setup") {
				// setup must be called immediately
				runner(_function, false);
			} else {
				tasks.push(() => runner(_function, false));
			}
		});

		handlers.old_style.forEach((_function) => {
			if (event_id === "setup") {
				// setup must be called immediately
				runner(_function, true);
			} else {
				tasks.push(() => runner(_function, true));
			}
		});

		// run them serially
		return frappe.run_serially(tasks);
	}
	has_handler(event_id) {
		// return true if there exist an event handler (new style only)
		return (
			frappe.ui.form.handlers[this.frm.doctype] &&
			frappe.ui.form.handlers[this.frm.doctype][event_id]
		);
	}
	has_handlers(event_id, doctype) {
		let handlers = this.get_handlers(event_id, doctype);
		return handlers && (handlers.old_style.length || handlers.new_style.length);
	}
	get_handlers(event_id, doctype) {
		// returns list of all functions to be called (old style and new style)
		let me = this;
		let handlers = {
			old_style: [],
			new_style: [],
		};
		if (frappe.ui.form.handlers[doctype] && frappe.ui.form.handlers[doctype][event_id]) {
			$.each(frappe.ui.form.handlers[doctype][event_id], function (i, fn) {
				handlers.new_style.push(fn);
			});
		}
		if (this.frm.cscript && this.frm.cscript[event_id]) {
			handlers.old_style.push(event_id);
		}
		if (this.frm.cscript && this.frm.cscript["custom_" + event_id]) {
			handlers.old_style.push("custom_" + event_id);
		}
		return handlers;
	}
	setup() {
		const doctype = this.frm.meta;
		const me = this;
		let client_script = doctype.__js;

		// append the custom script for this form's layout
		if (this.frm.doctype_layout?.client_script) {
			// add a newline to avoid conflict with doctype JS
			client_script += `\n${this.frm.doctype_layout.client_script}`;
		}

		if (client_script) {
			new Function(client_script)();
		}

		if (!this.frm.doctype_layout && doctype.__custom_js) {
			try {
				new Function(doctype.__custom_js)();
			} catch (e) {
				frappe.msgprint({
					title: __("Error in Client Script"),
					indicator: "orange",
					message: '<pre class="small"><code>' + e.stack + "</code></pre>",
				});
			}
		}

		function setup_add_fetch(df) {
			let is_read_only_field =
				[
					"Data",
					"Read Only",
					"Text",
					"Small Text",
					"Currency",
					"Check",
					"Text Editor",
					"Attach Image",
					"Code",
					"Link",
					"Float",
					"Int",
					"Date",
					"Datetime",
					"Select",
					"Duration",
					"Time",
				].includes(df.fieldtype) ||
				df.read_only == 1 ||
				df.is_virtual == 1;

			if (is_read_only_field && df.fetch_from && df.fetch_from.indexOf(".") != -1) {
				var parts = df.fetch_from.split(".");
				me.frm.add_fetch(parts[0], parts[1], df.fieldname, df.parent);
			}
		}

		// setup add fetch
		$.each(this.frm.fields, function (i, field) {
			setup_add_fetch(field.df);
			if (frappe.model.table_fields.includes(field.df.fieldtype)) {
				$.each(
					frappe.meta.get_docfields(field.df.options, me.frm.docid),
					function (i, df) {
						setup_add_fetch(df);
					}
				);
			}
		});

		// css
		doctype.__css && frappe.dom.set_style(doctype.__css);

		this.trigger("setup");
	}

	log_error(caller, e) {
		frappe.show_alert({ message: __("Error in Client Script."), indicator: "error" });
		console.group && console.group();
		console.log("----- error in client script -----");
		console.log("method: " + caller);
		console.log(e);
		console.log("error message: " + e.message);
		console.trace && console.trace();
		console.log("----- end of error message -----");
		console.group && console.groupEnd();
	}
	copy_from_first_row(parentfield, current_row, fieldnames) {
		var data = this.frm.doc[parentfield];
		if (data.length === 1 || data[0] === current_row) return;

		if (typeof fieldnames === "string") {
			fieldnames = [fieldnames];
		}

		$.each(fieldnames, function (i, fieldname) {
			frappe.model.set_value(
				current_row.doctype,
				current_row.id,
				fieldname,
				data[0][fieldname]
			);
		});
	}
};
