# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.deprecations import deprecated
from frappe.utils.scheduler import is_scheduler_inactive


class BulkUpdate(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        condition: DF.SmallText | None
        document_type: DF.Link
        field: DF.Literal[None]
        limit: DF.Int
        update_value: DF.SmallText
    # end: auto-generated types

    @frappe.whitelist()
    def bulk_update(self):
        self.check_permission("write")
        limit = self.limit if self.limit and cint(self.limit) < 500 else 500

        condition = ""
        if self.condition:
            if ";" in self.condition:
                frappe.throw(_("; not allowed in condition"))

            condition = f" where {self.condition}"

        docids = frappe.db.sql_list(
            f"""select id from `tab{self.document_type}`{condition} limit {limit} offset 0"""
        )
        return submit_cancel_or_update_docs(
            self.document_type, docids, "update", {self.field: self.update_value}
        )


@frappe.whitelist()
def submit_cancel_or_update_docs(
    doctype, docids, action="submit", data=None, task_id=None
):
    if isinstance(docids, str):
        docids = frappe.parse_json(docids)

    if len(docids) < 20:
        return _bulk_action(doctype, docids, action, data, task_id)
    elif len(docids) <= 500:
        frappe.msgprint(_("Bulk operation is enqueued in background."), alert=True)
        frappe.enqueue(
            _bulk_action,
            doctype=doctype,
            docids=docids,
            action=action,
            data=data,
            task_id=task_id,
            queue="short",
            timeout=1000,
        )
    else:
        frappe.throw(
            _("Bulk operations only support up to 500 documents."),
            title=_("Too Many Documents"),
        )


def _bulk_action(doctype, docids, action, data, task_id=None):
    if data:
        data = frappe.parse_json(data)

    failed = []
    num_documents = len(docids)

    for idx, docid in enumerate(docids, 1):
        doc = frappe.get_doc(doctype, docid)
        try:
            message = ""
            if action == "submit" and doc.docstatus.is_draft():
                if doc.meta.queue_in_background and not is_scheduler_inactive():
                    queue_submission(doc, action)
                    message = _("Queuing {0} for Submission").format(doctype)
                else:
                    doc.submit()
                    message = _("Submitting {0}").format(doctype)
            elif action == "cancel" and doc.docstatus.is_submitted():
                doc.cancel()
                message = _("Cancelling {0}").format(doctype)
            elif action == "update" and not doc.docstatus.is_cancelled():
                doc.update(data)
                doc.save()
                message = _("Updating {0}").format(doctype)
            else:
                failed.append(docid)
            frappe.db.commit()
            frappe.publish_progress(
                percent=idx / num_documents * 100,
                title=message,
                description=docid,
                task_id=task_id,
            )

        except Exception:
            failed.append(docid)
            frappe.db.rollback()

    return failed


from frappe.deprecation_dumpster import show_progress
