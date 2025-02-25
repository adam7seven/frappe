import frappe


def execute():
    for id in ("desktop", "space"):
        frappe.delete_doc("Page", id)
