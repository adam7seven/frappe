import frappe
from frappe.model.reid_doc import reid_doc


def execute():
    if frappe.db.exists("DocType", "Client Script"):
        return

    frappe.flags.ignore_route_conflict_validation = True
    reid_doc("DocType", "Custom Script", "Client Script")
    frappe.flags.ignore_route_conflict_validation = False

    frappe.reload_doctype("Client Script", force=True)
