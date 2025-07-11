// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.pageview");
frappe.provide("frappe.standard_pages");

frappe.views.pageview = {
	with_page: function (id, callback) {
		if (frappe.standard_pages[id]) {
			if (!frappe.pages[id]) {
				frappe.standard_pages[id]();
			}
			callback();
			return;
		}

		if ((locals.Page && locals.Page[id] && locals.Page[id].script) || id == window.page_id) {
			// already loaded
			callback();
		} else if (localStorage["_page:" + id] && frappe.boot.developer_mode != 1) {
			// cached in local storage
			frappe.model.sync(JSON.parse(localStorage["_page:" + id]));
			callback();
		} else if (id) {
			// get fresh
			return frappe.call({
				method: "frappe.desk.desk_page.getpage",
				args: { id: id },
				callback: function (r) {
					if (!r.docs._dynamic_page) {
						try {
							localStorage["_page:" + id] = JSON.stringify(r.docs);
						} catch (e) {
							console.warn(e);
						}
					}
					callback();
				},
				freeze: true,
			});
		}
	},

	show: function (id) {
		if (!id) {
			id = frappe.boot ? frappe.boot.home_page : window.page_id;
		}
		frappe.model.with_doctype("Page", function () {
			frappe.views.pageview.with_page(id, function (r) {
				if (r && r.exc) {
					if (!r["403"]) frappe.show_not_found(id);
				} else if (!frappe.pages[id]) {
					new frappe.views.Page(id);
				}
				frappe.container.change_to(id);
			});
		});
	},
};

frappe.views.Page = class Page {
	constructor(id) {
		this.id = id;
		var me = this;

		// web home page
		if (id == window.page_id) {
			this.wrapper = document.getElementById("page-" + id);
			this.wrapper.label = document.title || window.page_id;
			this.wrapper.page_id = window.page_id;
			frappe.pages[window.page_id] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.id];
			if (!this.pagedoc) {
				frappe.show_not_found(id);
				return;
			}
			this.wrapper = frappe.container.add_page(this.id);
			this.wrapper.page_id = this.pagedoc.id;

			// set content, script and style
			if (this.pagedoc.content) this.wrapper.innerHTML = this.pagedoc.content;
			frappe.dom.eval(this.pagedoc.__script || this.pagedoc.script || "");
			frappe.dom.set_style(this.pagedoc.style || "");

			// set breadcrumbs
			frappe.breadcrumbs.add(this.pagedoc.module || null);
		}

		this.trigger_page_event("on_page_load");

		// set events
		$(this.wrapper).on("show", function () {
			window.cur_frm = null;
			me.trigger_page_event("on_page_show");
			me.trigger_page_event("refresh");
		});
	}

	trigger_page_event(eventname) {
		var me = this;
		if (me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
};

frappe.show_not_found = function (page_id) {
	frappe.show_message_page({
		page_id: page_id,
		message: __("Sorry! I could not find what you were looking for."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg",
	});
};

frappe.show_not_permitted = function (page_id) {
	frappe.show_message_page({
		page_id: page_id,
		message: __("Sorry! You are not permitted to view this page."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg",
		// icon: "octicon octicon-circle-slash"
	});
};

frappe.show_message_page = function (opts) {
	// opts can include `page_id`, `message`, `icon` or `img`
	if (!opts.page_id) {
		opts.page_id = frappe.get_route_str();
	}

	if (opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = frappe.pages[opts.page_id] || frappe.container.add_page(opts.page_id);
	$(page).html(
		repl(
			'<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="/app">%(home)s</a>\
			</div>\
		</div>',
			{
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home"),
			}
		)
	);

	frappe.container.change_to(opts.page_id);
};
