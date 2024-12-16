import frappe
from frappe.model.iding import append_number_if_id_exists
from frappe.utils.dashboard import get_dashboards_with_link


def execute():
    if (
        not frappe.db.table_exists("Dashboard Chart")
        or not frappe.db.table_exists("Number Card")
        or not frappe.db.table_exists("Dashboard")
    ):
        return

    frappe.reload_doc("desk", "doctype", "dashboard_chart")
    frappe.reload_doc("desk", "doctype", "number_card")
    frappe.reload_doc("desk", "doctype", "dashboard")

    modified_charts = get_modified_docs("Dashboard Chart")
    modified_cards = get_modified_docs("Number Card")
    modified_dashboards = [doc.id for doc in get_modified_docs("Dashboard")]

    for chart in modified_charts:
        modified_dashboards += get_dashboards_with_link(chart.id, "Dashboard Chart")
        reid_modified_doc(chart.id, "Dashboard Chart")

    for card in modified_cards:
        modified_dashboards += get_dashboards_with_link(card.id, "Number Card")
        reid_modified_doc(card.id, "Number Card")

    modified_dashboards = list(set(modified_dashboards))

    for dashboard in modified_dashboards:
        reid_modified_doc(dashboard, "Dashboard")


def get_modified_docs(doctype):
    return frappe.get_all(
        doctype,
        filters={"owner": "Administrator", "modified_by": ["!=", "Administrator"]},
    )


def reid_modified_doc(docid, doctype):
    new_id = docid + " Custom"
    try:
        frappe.reid_doc(doctype, docid, new_id)
    except frappe.ValidationError:
        new_id = append_number_if_id_exists(doctype, new_id)
        frappe.reid_doc(doctype, docid, new_id)
