// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.ReportFactory = class ReportFactory extends frappe.views.Factory {
	make(route) {
		const _route = ["List", route[1], "Report"];

		if (route[2]) {
			// custom report
			_route.push(route[2]);
		}

		frappe.route_flags.replace_route = true;
		frappe.set_route(_route);
	}
};
