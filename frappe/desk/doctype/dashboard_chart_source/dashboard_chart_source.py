# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import os

import frappe
from frappe.model.document import Document
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import export_to_files


@frappe.whitelist()
def get_config(id):
    doc = frappe.get_doc("Dashboard Chart Source", id)
    with open(
        os.path.join(
            get_module_path(doc.module),
            "dashboard_chart_source",
            scrub(doc.id),
            scrub(doc.id) + ".js",
        ),
    ) as f:
        return f.read()


class DashboardChartSource(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        module: DF.Link
        timeseries: DF.Check

    # end: auto-generated types
    def on_update(self):
        export_to_files(
            record_list=[[self.doctype, self.id]],
            record_module=self.module,
            create_init=True,
        )
