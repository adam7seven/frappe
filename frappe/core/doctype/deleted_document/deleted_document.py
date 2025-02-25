# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name


class DeletedDocument(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        data: DF.Code | None
        deleted_doctype: DF.Data | None
        deleted_id: DF.Data | None
        new_id: DF.ReadOnly | None
        restored: DF.Check
    # end: auto-generated types

    no_feed_on_delete = True

    @staticmethod
    def clear_old_logs(days=180):
        from frappe.query_builder import Interval
        from frappe.query_builder.functions import Now

        table = frappe.qb.DocType("Deleted Document")
        frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
def restore(id, alert=True):
    deleted = frappe.get_doc("Deleted Document", id)

    if deleted.restored:
        frappe.throw(_("Document {0} Already Restored").format(id), exc=frappe.DocumentAlreadyRestored)

    doc = frappe.get_doc(json.loads(deleted.data))

    try:
        doc.insert()
    except frappe.DocstatusTransitionError:
        frappe.msgprint(_("Cancelled Document restored as Draft"))
        doc.docstatus = 0
        active_workflow = get_workflow_name(doc.doctype)
        if active_workflow:
            workflow_state_fieldname = frappe.get_value("Workflow", active_workflow, "workflow_state_field")
            if doc.get(workflow_state_fieldname):
                doc.set(workflow_state_fieldname, None)
        doc.insert()

    doc.add_comment("Edit", _("restored {0} as {1}").format(deleted.deleted_id, doc.id))

    deleted.new_id = doc.id
    deleted.restored = 1
    deleted.db_update()

    if alert:
        frappe.msgprint(_("Document Restored"))


@frappe.whitelist()
def bulk_restore(docids):
    docids = frappe.parse_json(docids)
    message = _("Restoring Deleted Document")
    restored, invalid, failed = [], [], []

    for i, d in enumerate(docids):
        try:
            show_progress(docids, message, i + 1, d)
            restore(d, alert=False)
            frappe.db.commit()
            restored.append(d)

        except frappe.DocumentAlreadyRestored:
            frappe.clear_last_message()
            invalid.append(d)

        except Exception:
            frappe.clear_last_message()
            failed.append(d)
            frappe.db.rollback()

    return {"restored": restored, "invalid": invalid, "failed": failed}
