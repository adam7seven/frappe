# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.desk.form.load import run_onload
from frappe.model.docstatus import DocStatus
from frappe.monitor import add_data_to_monitor
from frappe.utils.scheduler import is_scheduler_inactive
from frappe.utils.telemetry import capture_doc


@frappe.whitelist(methods=["POST", "PUT"])
def savedocs(doc, action):
	"""save / submit / update doclist"""
	doc = frappe.get_doc(json.loads(doc))
	capture_doc(doc, action)
	if doc.get("__islocal") and doc.id.startswith("new-" + doc.doctype.lower().replace(" ", "-")):
		# required to relink missing attachments if they exist.
		doc.__temporary_id = doc.id

	for child in doc.get_all_children():
		child.__temporary_id = child.id

	set_local_id(doc)

	# action
	doc.docstatus = {
		"Save": DocStatus.DRAFT,
		"Submit": DocStatus.SUBMITTED,
		"Update": DocStatus.SUBMITTED,
		"Cancel": DocStatus.CANCELLED,
	}[action]

	if doc.docstatus.is_submitted():
		if action == "Submit" and doc.meta.queue_in_background and not is_scheduler_inactive():
			queue_submission(doc, action)
			return
		doc.submit()
	else:
		doc.save()

	# update recent documents
	run_onload(doc)
	send_updated_docs(doc)

	add_data_to_monitor(doctype=doc.doctype, action=action)
	status_message = "Submitted" if doc.docstatus.is_submitted() else "Saved"
	frappe.msgprint(frappe._(status_message), indicator="green", alert=True)


@frappe.whitelist(methods=["POST", "PUT"])
def cancel(doctype=None, id=None, workflow_state_fieldname=None, workflow_state=None):
	"""cancel a doclist"""
	doc = frappe.get_doc(doctype, id)
	capture_doc(doc, "Cancel")

	if workflow_state_fieldname and workflow_state:
		doc.set(workflow_state_fieldname, workflow_state)
	doc.cancel()
	send_updated_docs(doc)
	frappe.msgprint(frappe._("Cancelled"), indicator="red", alert=True)


@frappe.whitelist(methods=["POST", "PUT"])
def discard(doctype: str, id: str | int):
	"""discard a draft document"""
	doc = frappe.get_doc(doctype, id)
	capture_doc(doc, "Discard")

	doc.discard()
	send_updated_docs(doc)
	frappe.msgprint(frappe._("Discarded"), indicator="red", alert=True)


def send_updated_docs(doc):
	from .load import get_docinfo

	get_docinfo(doc)
	doc.apply_fieldlevel_read_permissions()
	d = doc.as_dict()
	if hasattr(doc, "localid"):
		d["localid"] = doc.localid

	frappe.response.docs.append(d)


def set_local_id(doc):
	def _set_local_id(d):
		if doc.get("__islocal") or d.get("__islocal"):
			d.localid = d.id
			d.id = None

	_set_local_id(doc)
	for child in doc.get_all_children():
		_set_local_id(child)

	if doc.get("__newid"):
		doc.id = doc.get("__newid")
