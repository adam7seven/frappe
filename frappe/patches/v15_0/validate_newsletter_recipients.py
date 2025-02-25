import frappe
from frappe.utils import validate_email_address


def execute():
    for id, email in frappe.get_all(
        "Email Group Member", fields=["id", "email"], as_list=True
    ):
        if not validate_email_address(email, throw=False):
            frappe.db.set_value("Email Group Member", id, "unsubscribed", 1)
            frappe.db.commit()
