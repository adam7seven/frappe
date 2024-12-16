import frappe
from frappe.model.reid_doc import reid_doc


def execute():
    if frappe.db.table_exists("Standard Reply") and not frappe.db.table_exists(
        "Email Template"
    ):
        reid_doc("DocType", "Standard Reply", "Email Template")
        frappe.reload_doc("email", "doctype", "email_template")
