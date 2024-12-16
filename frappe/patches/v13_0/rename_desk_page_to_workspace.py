import frappe
from frappe.model.reid_doc import reid_doc


def execute():
    if frappe.db.exists("DocType", "Desk Page"):
        if frappe.db.exists("DocType", "Workspace"):
            # this patch was not added initially, so this page might still exist
            frappe.delete_doc("DocType", "Desk Page")
        else:
            frappe.flags.ignore_route_conflict_validation = True
            reid_doc("DocType", "Desk Page", "Workspace")
            frappe.flags.ignore_route_conflict_validation = False

    reid_doc("DocType", "Desk Chart", "Workspace Chart", ignore_if_exists=True)
    reid_doc("DocType", "Desk Shortcut", "Workspace Shortcut", ignore_if_exists=True)
    reid_doc("DocType", "Desk Link", "Workspace Link", ignore_if_exists=True)

    frappe.reload_doc("desk", "doctype", "workspace", force=True)
    frappe.reload_doc("desk", "doctype", "workspace_link", force=True)
    frappe.reload_doc("desk", "doctype", "workspace_chart", force=True)
    frappe.reload_doc("desk", "doctype", "workspace_shortcut", force=True)
