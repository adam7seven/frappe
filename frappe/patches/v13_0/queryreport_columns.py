# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe


def execute():
    """Convert Query Report json to support other content"""
    records = frappe.get_all(
        "Report", filters={"json": ["!=", ""]}, fields=["id", "json"]
    )
    for record in records:
        jstr = record["json"]
        data = json.loads(jstr)
        if isinstance(data, list):
            # double escape braces
            jstr = f'{{"columns":{jstr}}}'
            frappe.db.set_value("Report", record["id"], "json", jstr)
