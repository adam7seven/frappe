import frappe


def execute():
	frappe.db.delete("DocType", {"id": "Feedback Request"})
