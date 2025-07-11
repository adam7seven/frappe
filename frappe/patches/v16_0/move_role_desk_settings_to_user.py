# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.core.doctype.user.user import desk_properties


def execute():
	roles = {role.id: role for role in frappe.get_all("Role", fields=["*"])}

	for user in frappe.get_list("User"):
		user_desk_settings = {}
		for role_id in frappe.get_roles(username=user.id):
			if role := roles.get(role_id):
				for key in desk_properties:
					if role.get(key) is None:
						role[key] = 1
					user_desk_settings[key] = user_desk_settings.get(key) or role.get(key)

		frappe.db.set_value("User", user.id, user_desk_settings)
