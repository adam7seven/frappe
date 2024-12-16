# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import shutil

import frappe
import frappe.defaults
import frappe.model.meta
from frappe import _, get_module_path
from frappe.desk.doctype.tag.tag import delete_tags_for_document
from frappe.model.docstatus import DocStatus
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.model.iding import revert_series_if_last
from frappe.model.utils import is_virtual_doctype
from frappe.utils.file_manager import remove_all
from frappe.utils.global_search import delete_for_document
from frappe.utils.password import delete_all_passwords_for


def delete_doc(
    doctype=None,
    id=None,
    force=0,
    ignore_doctypes=None,
    for_reload=False,
    ignore_permissions=False,
    flags=None,
    ignore_on_trash=False,
    ignore_missing=True,
    delete_permanently=False,
):
    """
    Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
    """
    if not ignore_doctypes:
        ignore_doctypes = []

    # get from form
    if not doctype:
        doctype = frappe.form_dict.get("dt")
        id = frappe.form_dict.get("dn")

    is_virtual = is_virtual_doctype(doctype)

    ids = id
    if isinstance(id, str) or isinstance(id, int):
        ids = [id]

    for id in ids or []:
        if is_virtual:
            frappe.get_doc(doctype, id).delete()
            continue

        # already deleted..?
        if not frappe.db.exists(doctype, id):
            if not ignore_missing:
                raise frappe.DoesNotExistError
            else:
                return False

        # delete passwords
        delete_all_passwords_for(doctype, id)

        doc = None
        if doctype == "DocType":
            if for_reload:
                try:
                    doc = frappe.get_doc(doctype, id)
                except frappe.DoesNotExistError:
                    pass
                else:
                    doc.run_method("before_reload")

            else:
                doc = frappe.get_doc(doctype, id)
                if not (
                    doc.custom
                    or frappe.conf.developer_mode
                    or frappe.flags.in_patch
                    or force
                ):
                    frappe.throw(_("Standard DocType can not be deleted."))

                update_flags(doc, flags, ignore_permissions)
                check_permission_and_not_submitted(doc)
                # delete custom table fields using this doctype.
                frappe.db.delete(
                    "Custom Field",
                    {"options": id, "fieldtype": ("in", frappe.model.table_fields)},
                )
                frappe.db.delete("__global_search", {"doctype": id})

            delete_from_table(doctype, id, ignore_doctypes, None)

            if (
                frappe.conf.developer_mode
                and not doc.custom
                and not (
                    for_reload
                    or frappe.flags.in_migrate
                    or frappe.flags.in_install
                    or frappe.flags.in_uninstall
                )
            ):
                try:
                    delete_controllers(id, doc.module)
                except (OSError, KeyError):
                    # in case a doctype doesnt have any controller code  nor any app and module
                    pass

        else:
            # Lock the doc without waiting
            try:
                frappe.db.get_value(doctype, id, for_update=True, wait=False)
            except frappe.QueryTimeoutError:
                frappe.throw(
                    _(
                        "This document can not be deleted right now as it's being modified by another user. Please try again after some time."
                    ),
                    exc=frappe.QueryTimeoutError,
                )
            doc = frappe.get_doc(doctype, id)

            if not for_reload:
                update_flags(doc, flags, ignore_permissions)
                check_permission_and_not_submitted(doc)

                if not ignore_on_trash:
                    doc.run_method("on_trash")
                    doc.flags.in_delete = True
                    doc.run_method("on_change")

                # check if links exist
                if not force:
                    try:
                        check_if_doc_is_linked(doc)
                        check_if_doc_is_dynamically_linked(doc)
                    except frappe.LinkExistsError as e:
                        if doc.meta.has_field("enabled") or doc.meta.has_field(
                            "disabled"
                        ):
                            frappe.throw(
                                _(
                                    "You can disable this {0} instead of deleting it."
                                ).format(_(doctype)),
                                frappe.LinkExistsError,
                            )
                        else:
                            raise e

            update_naming_series(doc)
            delete_from_table(doctype, id, ignore_doctypes, doc)
            doc.run_method("after_delete")

            # delete attachments
            remove_all(
                doctype, id, from_delete=True, delete_permanently=delete_permanently
            )

            if not for_reload:
                # Enqueued at the end, because it gets committed
                # All the linked docs should be checked beforehand
                frappe.enqueue(
                    "frappe.model.delete_doc.delete_dynamic_links",
                    doctype=doc.doctype,
                    id=doc.id,
                    now=frappe.flags.in_test,
                    enqueue_after_commit=True,
                )

        # clear cache for Document
        doc.clear_cache()
        # delete global search entry
        delete_for_document(doc)
        # delete tag link entry
        delete_tags_for_document(doc)

        if for_reload:
            delete_permanently = True

        if not delete_permanently:
            add_to_deleted_document(doc)

        if doc and not for_reload:
            if not frappe.flags.in_patch:
                try:
                    doc.notify_update()
                    insert_feed(doc)
                except ImportError:
                    pass


def add_to_deleted_document(doc):
    """Add this document to Deleted Document table. Called after delete"""
    if doc.doctype != "Deleted Document" and frappe.flags.in_install != "frappe":
        frappe.get_doc(
            dict(
                doctype="Deleted Document",
                deleted_doctype=doc.doctype,
                deleted_id=doc.id,
                data=doc.as_json(),
                owner=frappe.session.user,
            )
        ).db_insert()


def update_naming_series(doc):
    if doc.meta.autoid:
        if doc.meta.autoid.startswith("naming_series:") and getattr(
            doc, "naming_series", None
        ):
            revert_series_if_last(doc.naming_series, doc.id, doc)

        elif doc.meta.autoid.split(":", 1)[0] not in (
            "Prompt",
            "field",
            "hash",
            "autoincrement",
        ):
            revert_series_if_last(doc.meta.autoid, doc.id, doc)


def delete_from_table(doctype: str, id: str, ignore_doctypes: list[str], doc):
    if doctype != "DocType" and doctype == id:
        frappe.db.delete("Singles", {"doctype": id})
    else:
        frappe.db.delete(doctype, {"id": id})
    if doc:
        child_doctypes = [
            d.options
            for d in doc.meta.get_table_fields()
            if frappe.get_meta(d.options).is_virtual == 0
        ]

    else:
        child_doctypes = frappe.get_all(
            "DocField",
            fields="options",
            filters={"fieldtype": ["in", frappe.model.table_fields], "parent": doctype},
            pluck="options",
        )

    child_doctypes_to_delete = set(child_doctypes) - set(ignore_doctypes)
    for child_doctype in child_doctypes_to_delete:
        frappe.db.delete(child_doctype, {"parenttype": doctype, "parent": id})


def update_flags(doc, flags=None, ignore_permissions=False):
    if ignore_permissions:
        if not flags:
            flags = {}
        flags["ignore_permissions"] = ignore_permissions

    if flags:
        doc.flags.update(flags)


def check_permission_and_not_submitted(doc):
    # permission
    if (
        not doc.flags.ignore_permissions
        and frappe.session.user != "Administrator"
        and (
            not doc.has_permission("delete")
            or (doc.doctype == "DocType" and not doc.custom)
        )
    ):
        frappe.msgprint(
            _("User not allowed to delete {0}: {1}").format(doc.doctype, doc.id),
            raise_exception=frappe.PermissionError,
        )

    # check if submitted
    if doc.meta.is_submittable and doc.docstatus.is_submitted():
        frappe.msgprint(
            _(
                "{0} {1}: Submitted Record cannot be deleted. You must {2} Cancel {3} it first."
            ).format(
                _(doc.doctype),
                doc.id,
                "<a href='https://docs.erpnext.com//docs/user/manual/en/setting-up/articles/delete-submitted-document' target='_blank'>",
                "</a>",
            ),
            raise_exception=True,
        )


def check_if_doc_is_linked(doc, method="Delete"):
    """
    Raises excption if the given doc(dt, dn) is linked in another record.
    """
    from frappe.model.reid_doc import get_link_fields

    link_fields = get_link_fields(doc.doctype)
    ignored_doctypes = set()

    if method == "Cancel" and (doc_ignore_flags := doc.get("ignore_linked_doctypes")):
        ignored_doctypes.update(doc_ignore_flags)
    if method == "Delete":
        ignored_doctypes.update(frappe.get_hooks("ignore_links_on_delete"))

    for lf in link_fields:
        link_dt, link_field, issingle = lf["parent"], lf["fieldname"], lf["issingle"]
        if link_dt in ignored_doctypes or (
            link_field == "amended_from" and method == "Cancel"
        ):
            continue

        try:
            meta = frappe.get_meta(link_dt)
        except frappe.DoesNotExistError:
            frappe.clear_last_message()
            # This mostly happens when app do not remove their customizations, we shouldn't
            # prevent link checks from failing in those cases
            continue

        if issingle:
            if frappe.db.get_single_value(link_dt, link_field) == doc.id:
                raise_link_exists_exception(doc, link_dt, link_dt)
            continue

        fields = ["id", "docstatus"]

        if meta.istable:
            fields.extend(["parent", "parenttype"])

        for item in frappe.db.get_values(
            link_dt, {link_field: doc.id}, fields, as_dict=True
        ):
            # available only in child table cases
            item_parent = getattr(item, "parent", None)
            linked_parent_doctype = item.parenttype if item_parent else link_dt

            if linked_parent_doctype in ignored_doctypes:
                continue

            if method != "Delete" and (
                method != "Cancel" or not DocStatus(item.docstatus).is_submitted()
            ):
                # don't raise exception if not
                # linked to a non-cancelled doc when deleting or to a submitted doc when cancelling
                continue
            elif link_dt == doc.doctype and (item_parent or item.id) == doc.id:
                # don't raise exception if not
                # linked to same item or doc having same id as the item
                continue
            else:
                reference_docid = item_parent or item.id
                raise_link_exists_exception(doc, linked_parent_doctype, reference_docid)


def check_if_doc_is_dynamically_linked(doc, method="Delete"):
    """Raise `frappe.LinkExistsError` if the document is dynamically linked"""
    for df in get_dynamic_link_map().get(doc.doctype, []):
        ignore_linked_doctypes = doc.get("ignore_linked_doctypes") or []

        if df.parent in frappe.get_hooks("ignore_links_on_delete") or (
            df.parent in ignore_linked_doctypes and method == "Cancel"
        ):
            # don't check for communication and todo!
            continue

        meta = frappe.get_meta(df.parent)
        if meta.issingle:
            # dynamic link in single doc
            refdoc = frappe.db.get_singles_dict(df.parent)
            if (
                refdoc.get(df.options) == doc.doctype
                and refdoc.get(df.fieldname) == doc.id
                and (
                    # linked to an non-cancelled doc when deleting
                    (
                        method == "Delete"
                        and not DocStatus(refdoc.docstatus).is_cancelled()
                    )
                    # linked to a submitted doc when cancelling
                    or (
                        method == "Cancel"
                        and DocStatus(refdoc.docstatus).is_submitted()
                    )
                )
            ):
                raise_link_exists_exception(doc, df.parent, df.parent)
        else:
            # dynamic link in table
            df["table"] = ", `parent`, `parenttype`, `idx`" if meta.istable else ""
            for refdoc in frappe.db.sql(
                """select `id`, `docstatus` {table} from `tab{parent}` where
				`{options}`=%s and `{fieldname}`=%s""".format(
                    **df
                ),
                (doc.doctype, doc.id),
                as_dict=True,
            ):
                # linked to an non-cancelled doc when deleting
                # or linked to a submitted doc when cancelling
                if (
                    method == "Delete"
                    and not DocStatus(refdoc.docstatus).is_cancelled()
                ) or (
                    method == "Cancel" and DocStatus(refdoc.docstatus).is_submitted()
                ):
                    reference_doctype = refdoc.parenttype if meta.istable else df.parent
                    reference_docid = refdoc.parent if meta.istable else refdoc.id

                    if reference_doctype in frappe.get_hooks(
                        "ignore_links_on_delete"
                    ) or (
                        reference_doctype in ignore_linked_doctypes
                        and method == "Cancel"
                    ):
                        # don't check for communication and todo!
                        continue

                    at_position = f"at Row: {refdoc.idx}" if meta.istable else ""

                    raise_link_exists_exception(
                        doc, reference_doctype, reference_docid, at_position
                    )


def raise_link_exists_exception(doc, reference_doctype, reference_docid, row=""):
    doc_link = f'<a href="/app/Form/{doc.doctype}/{doc.id}">{doc.id}</a>'
    reference_link = f'<a href="/app/Form/{reference_doctype}/{reference_docid}">{reference_docid}</a>'

    # hack to display Single doctype only once in message
    if reference_doctype == reference_docid:
        reference_doctype = ""

    frappe.throw(
        _("Cannot delete or cancel because {0} {1} is linked with {2} {3} {4}").format(
            _(doc.doctype), doc_link, _(reference_doctype), reference_link, row
        ),
        frappe.LinkExistsError,
    )


def delete_dynamic_links(doctype, id):
    delete_references("ToDo", doctype, id, "reference_type")
    delete_references("Email Unsubscribe", doctype, id)
    delete_references("DocShare", doctype, id, "share_doctype", "share_id")
    delete_references("Version", doctype, id, "ref_doctype", "docid")
    delete_references("Comment", doctype, id)
    delete_references("View Log", doctype, id)
    delete_references("Document Follow", doctype, id, "ref_doctype", "ref_docid")
    delete_references("Notification Log", doctype, id, "document_type", "document_id")

    # unlink communications
    clear_timeline_references(doctype, id)
    clear_references("Communication", doctype, id)

    clear_references("Activity Log", doctype, id)
    clear_references("Activity Log", doctype, id, "timeline_doctype", "timeline_id")


def delete_references(
    doctype,
    reference_doctype,
    reference_id,
    reference_doctype_field="reference_doctype",
    reference_id_field="reference_id",
):
    frappe.db.delete(
        doctype,
        {
            reference_doctype_field: reference_doctype,
            reference_id_field: reference_id,
        },
    )


def clear_references(
    doctype,
    reference_doctype,
    reference_id,
    reference_doctype_field="reference_doctype",
    reference_id_field="reference_id",
):
    frappe.db.sql(
        f"""update
			`tab{doctype}`
		set
			{reference_doctype_field}=NULL, {reference_id_field}=NULL
		where
			{reference_doctype_field}=%s and {reference_id_field}=%s""",  # nosec
        (reference_doctype, reference_id),
    )


def clear_timeline_references(link_doctype, link_id):
    frappe.db.delete(
        "Communication Link", {"link_doctype": link_doctype, "link_id": link_id}
    )


def insert_feed(doc):
    if (
        frappe.flags.in_install
        or frappe.flags.in_uninstall
        or frappe.flags.in_import
        or getattr(doc, "no_feed_on_delete", False)
    ):
        return

    from frappe.utils import get_fullname

    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Deleted",
            "reference_doctype": doc.doctype,
            "subject": f"{_(doc.doctype)} {doc.id}",
            "full_name": get_fullname(doc.owner),
        }
    ).insert(ignore_permissions=True)


def delete_controllers(doctype, module):
    """
    Delete controller code in the doctype folder
    """
    module_path = get_module_path(module)
    dir_path = os.path.join(module_path, "doctype", frappe.scrub(doctype))

    shutil.rmtree(dir_path)
