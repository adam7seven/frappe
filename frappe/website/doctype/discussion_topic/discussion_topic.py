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
def submit_discussion(doctype, docid, reply, title, topic_name=None, reply_name=None):
	if reply_name:
		doc = frappe.get_doc("Discussion Reply", reply_name)
		doc.reply = reply
		doc.save(ignore_permissions=True)
		return

	if topic_name:
		save_message(reply, topic_name)
		return topic_name

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
	frappe.get_doc({"doctype": "Discussion Reply", "reply": reply, "topic": topic}).save(
		ignore_permissions=True
	)
