# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model import is_default_field
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.query_builder.terms import SubQuery
from frappe.query_builder.utils import DocType


@frappe.whitelist()
def get_list_settings(doctype):
    try:
        return frappe.get_cached_doc("List View Settings", doctype)
    except frappe.DoesNotExistError:
        frappe.clear_messages()


@frappe.whitelist()
def set_list_settings(doctype, values):
    try:
        doc = frappe.get_doc("List View Settings", doctype)
    except frappe.DoesNotExistError:
        doc = frappe.new_doc("List View Settings")
        doc.id = doctype
        frappe.clear_messages()
    doc.update(frappe.parse_json(values))
    doc.save()


@frappe.whitelist()
def get_group_by_count(doctype: str, current_filters: str, field: str) -> list[dict]:
    current_filters = frappe.parse_json(current_filters)

    if field == "assigned_to":
        ToDo = DocType("ToDo")
        User = DocType("User")
        count = Count("*").as_("count")
        filtered_records = frappe.qb.get_query(
            doctype,
            filters=current_filters,
            fields=["id"],
            validate_filters=True,
        )

        return (
            frappe.qb.from_(ToDo)
            .from_(User)
            .select(ToDo.allocated_to.as_("id"), count)
            .where(
                (ToDo.status != "Cancelled")
                & (ToDo.allocated_to == User.id)
                & (User.user_type == "System User")
                & (ToDo.reference_id.isin(SubQuery(filtered_records)))
            )
            .groupby(ToDo.allocated_to)
            .orderby(count, order=Order.desc)
            .limit(50)
            .run(as_dict=True)
        )

    if not frappe.get_meta(doctype).has_field(field) and not is_default_field(field):
        raise ValueError("Field does not belong to doctype")

    data = frappe.get_list(
        doctype,
        filters=current_filters,
        group_by=f"`tab{doctype}`.{field}",
        fields=["count(*) as count", f"`{field}` as id"],
        order_by="count desc",
    )

    if field == "owner":
        owner_idx = None

        for idx, item in enumerate(data):
            if item.id == frappe.session.user:
                owner_idx = idx
                break

        if owner_idx:
            data = [data.pop(owner_idx)] + data[0:49]
        else:
            data = data[0:50]
    else:
        data = data[0:50]

    return data
