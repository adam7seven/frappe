import frappe

from ...user.user import desk_properties


def execute():
	for role in frappe.get_all("Role", ["id", "desk_access"]):
		role_doc = frappe.get_doc("Role", role.id)
		for key in desk_properties:
			role_doc.set(key, role_doc.desk_access)
		role_doc.save()
