import frappe
from frappe.desk.utils import slug


def execute():
    for doctype in frappe.get_all("DocType", ["id", "route"], dict(istable=0)):
        if not doctype.route:
            frappe.db.set_value(
                "DocType", doctype.id, "route", slug(doctype.id), update_modified=False
            )
