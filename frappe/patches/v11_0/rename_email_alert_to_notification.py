import frappe
from frappe.model.reid_doc import reid_doc


def execute():
    if frappe.db.table_exists("Email Alert Recipient") and not frappe.db.table_exists(
        "Notification Recipient"
    ):
        reid_doc("DocType", "Email Alert Recipient", "Notification Recipient")
        frappe.reload_doc("email", "doctype", "notification_recipient")

    if frappe.db.table_exists("Email Alert") and not frappe.db.table_exists(
        "Notification"
    ):
        reid_doc("DocType", "Email Alert", "Notification")
        frappe.reload_doc("email", "doctype", "notification")
