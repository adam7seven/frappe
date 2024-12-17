# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DiscussionTopic(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        reference_docid: DF.DynamicLink | None
        reference_doctype: DF.Link | None
        title: DF.Data | None
    # end: auto-generated types
    pass


@frappe.whitelist()
def submit_discussion(doctype, docid, reply, title, topic_id=None, reply_id=None):
    if reply_id:
        doc = frappe.get_doc("Discussion Reply", reply_id)
        doc.reply = reply
        doc.save(ignore_permissions=True)
        return

    if topic_id:
        save_message(reply, topic_id)
        return topic_id

    topic = frappe.get_doc(
        {
            "doctype": "Discussion Topic",
            "title": title,
            "reference_doctype": doctype,
            "reference_docid": docid,
        }
    )
    topic.save(ignore_permissions=True)
    save_message(reply, topic.id)
    return topic.id


def save_message(reply, topic):
    frappe.get_doc(
        {"doctype": "Discussion Reply", "reply": reply, "topic": topic}
    ).save(ignore_permissions=True)
