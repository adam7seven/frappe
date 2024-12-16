import frappe
from frappe.model.reid_doc import reid_doc


def execute():
    if frappe.db.table_exists("Workflow Action") and not frappe.db.table_exists(
        "Workflow Action Master"
    ):
        reid_doc("DocType", "Workflow Action", "Workflow Action Master")
        frappe.reload_doc("workflow", "doctype", "workflow_action_master")
