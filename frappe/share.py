# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import (
    enqueue_create_notification,
    get_title,
    get_title_html,
)
from frappe.desk.form.document_follow import follow_document
from frappe.utils import cint

if TYPE_CHECKING:
    from frappe.model.document import Document


@frappe.whitelist()
def add(doctype, id, user=None, read=1, write=0, submit=0, share=0, everyone=0, notify=0):
    """Expose function without flags to the client-side"""
    return add_docshare(
        doctype,
        id,
        user=user,
        read=read,
        write=write,
        submit=submit,
        share=share,
        everyone=everyone,
        notify=notify,
    )


def add_docshare(doctype, id, user=None, read=1, write=0, submit=0, share=0, everyone=0, flags=None, notify=0):
    """Share the given document with a user."""
    if not user:
        user = frappe.session.user

    if not (flags or {}).get("ignore_share_permission"):
        check_share_permission(doctype, id)

    share_id = get_share_id(doctype, id, user, everyone)

    if share_id:
        doc = frappe.get_doc("DocShare", share_id)
    else:
        doc = frappe.new_doc("DocShare")
        doc.update({"user": user, "share_doctype": doctype, "share_id": id, "everyone": cint(everyone)})

    if flags:
        doc.flags.update(flags)

    doc.update(
        {
            # always add read, since you are adding!
            "read": 1,
            "write": cint(write),
            "submit": cint(submit),
            "share": cint(share),
        }
    )

    doc.save(ignore_permissions=True)
    notify_assignment(user, doctype, id, everyone, notify=notify)

    if frappe.get_cached_value("User", user, "follow_shared_documents"):
        follow_document(doctype, id, user)

    return doc


def remove(doctype, id, user, flags=None):
    share_id = frappe.db.get_value("DocShare", {"user": user, "share_id": id, "share_doctype": doctype})

    if share_id:
        frappe.delete_doc("DocShare", share_id, flags=flags)


@frappe.whitelist()
def set_permission(doctype, id, user, permission_to, value=1, everyone=0):
    """Expose function without flags to the client-side"""
    return set_docshare_permission(doctype, id, user, permission_to, value=value, everyone=everyone)


def set_docshare_permission(doctype, id, user, permission_to, value=1, everyone=0, flags=None):
    """Set share permission."""
    if not (flags or {}).get("ignore_share_permission"):
        check_share_permission(doctype, id)

    share_id = get_share_id(doctype, id, user, everyone)
    value = int(value)

    if not share_id:
        if value:
            share = add_docshare(doctype, id, user, everyone=everyone, **{permission_to: 1}, flags=flags)
        else:
            # no share found, nothing to remove
            share = None

    else:
        share = frappe.get_doc("DocShare", share_id)
        if flags:
            share.flags.update(flags)
        share.flags.ignore_permissions = True
        share.set(permission_to, value)

        if not value:
            # un-set higher-order permissions too
            if permission_to == "read":
                share.read = share.write = share.submit = share.share = 0

        share.save()

        if not (share.read or share.write or share.submit or share.share):
            share.delete()
            share = None

    return share


@frappe.whitelist()
def get_users(doctype: str, id: str) -> list:
    """Get list of users with which this document is shared"""
    doc = frappe.get_doc(doctype, id)
    return _get_users(doc)


def _get_users(doc: "Document") -> list:
    from frappe.permissions import has_permission

    if not has_permission(doc.doctype, "read", doc, print_logs=False):
        return []

    return frappe.get_all(
        "DocShare",
        fields=[
            "id",
            "user",
            "read",
            "write",
            "submit",
            "share",
            "everyone",
            "owner",
            "creation",
        ],
        filters=dict(share_doctype=doc.doctype, share_id=doc.id),
    )


def get_shared(doctype, user=None, rights=None, *, filters=None, limit=None):
    """Get list of shared document ids for given user and DocType.

    :param doctype: DocType of which shared ids are queried.
    :param user: User for which shared ids are queried.
    :param rights: List of rights for which the document is shared. List of `read`, `write`, `share`"""

    if not user:
        user = frappe.session.user

    if not rights:
        rights = ["read"]

    share_filters = [[right, "=", 1] for right in rights]
    share_filters += [["share_doctype", "=", doctype]]
    if filters:
        share_filters += filters

    or_filters = [["user", "=", user]]
    if user != "Guest":
        or_filters += [["everyone", "=", 1]]

    shared_docs = frappe.get_all(
        "DocShare",
        fields=["share_id"],
        filters=share_filters,
        or_filters=or_filters,
        order_by=None,
        limit_page_length=limit,
    )

    return [doc.share_id for doc in shared_docs]


def get_shared_doctypes(user=None):
    """Return list of doctypes in which documents are shared for the given user."""
    if not user:
        user = frappe.session.user
    table = frappe.qb.DocType("DocShare")
    query = (
        frappe.qb.from_(table)
        .where((table.user == user) | (table.everyone == 1))
        .select(table.share_doctype)
        .distinct()
    )
    return query.run(pluck=True)


def get_share_id(doctype, id, user, everyone):
    if cint(everyone):
        share_id = frappe.db.get_value("DocShare", {"everyone": 1, "share_id": id, "share_doctype": doctype})
    else:
        share_id = frappe.db.get_value("DocShare", {"user": user, "share_id": id, "share_doctype": doctype})

    return share_id


def check_share_permission(doctype, id):
    """Check if the user can share with other users"""
    if not frappe.has_permission(doctype, ptype="share", doc=id):
        frappe.throw(_("No permission to {0} {1} {2}").format("share", _(doctype), id), frappe.PermissionError)


def notify_assignment(shared_by, doctype, doc_id, everyone, notify=0):
    if not (shared_by and doctype and doc_id) or everyone or not notify:
        return

    from frappe.utils import get_fullname

    title = get_title(doctype, doc_id)

    reference_user = get_fullname(frappe.session.user)
    notification_message = _("{0} shared a document {1} {2} with you").format(
        frappe.bold(reference_user), frappe.bold(_(doctype)), get_title_html(title)
    )

    notification_doc = {
        "type": "Share",
        "document_type": doctype,
        "subject": notification_message,
        "document_id": doc_id,
        "from_user": frappe.session.user,
    }

    enqueue_create_notification(shared_by, notification_doc)
