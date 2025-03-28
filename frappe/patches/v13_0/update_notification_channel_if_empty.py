# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	frappe.reload_doc("Email", "doctype", "Notification")

	notifications = frappe.get_all("Notification", {"is_standard": 1}, {"id", "channel"})
	for notification in notifications:
		if not notification.channel:
			frappe.db.set_value("Notification", notification.id, "channel", "Email", update_modified=False)
			frappe.db.commit()
