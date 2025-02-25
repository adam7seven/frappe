# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


@frappe.whitelist()
def get(id):
    """
    Return the :term:`doclist` of the `Page` specified by `id`
    """
    page = frappe.get_doc("Page", id)
    if page.is_permitted():
        page.load_assets()
        docs = frappe._dict(page.as_dict())
        if getattr(page, "_dynamic_page", None):
            docs["_dynamic_page"] = 1

        return docs
    else:
        frappe.response["403"] = 1
        raise frappe.PermissionError(
            "No read permission for Page %s" % (page.title or id)
        )


@frappe.whitelist(allow_guest=True)
def getpage(id: str):
    """
    Load the page from `frappe.form` and send it via `frappe.response`
    """

    doc = get(id)
    frappe.response.docs.append(doc)
