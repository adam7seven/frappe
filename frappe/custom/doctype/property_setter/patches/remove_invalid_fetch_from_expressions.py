from contextlib import suppress

import frappe


def execute():
    """Remove invalid fetch from expressions"""
    with suppress(Exception):
        property_setters = frappe.get_all(
            "Property Setter", {"doctype_or_field": "DocField", "property": "fetch_from"}, ["id", "value"]
        )
        for ps in property_setters:
            if not is_valid_expression(ps.value):
                frappe.db.delete("Property Setter", {"id": ps.id})

        custom_fields = frappe.get_all("Custom Field", {"fetch_from": ("is", "set")}, ["id", "fetch_from"])
        for cf in custom_fields:
            if not is_valid_expression(cf.fetch_from):
                frappe.db.set_value("Custom Field", cf.id, "fetch_from", "")


def is_valid_expression(expr) -> bool:
    if not expr or "." not in expr:
        return False
    source_field, target_field = expr.split(".", maxsplit=1)
    if not source_field or not target_field:
        return False
    return True
