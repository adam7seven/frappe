# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from types import NoneType
from typing import TYPE_CHECKING

import frappe
from frappe import _, bold
from frappe.model.document import Document
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.model.iding import validate_id
from frappe.model.utils.user_settings import (
    sync_user_settings,
    update_user_settings_data,
)
from frappe.query_builder import Field
from frappe.utils.data import sbool
from frappe.utils.password import reid_password
from frappe.utils.scheduler import is_scheduler_inactive

if TYPE_CHECKING:
    from frappe.model.meta import Meta


@frappe.whitelist()
def update_document_title(
    *,
    doctype: str,
    docid: str,
    title: str | None = None,
    id: str | None = None,
    merge: bool = False,
    enqueue: bool = False,
    **kwargs,
) -> str:
    """
    Update the id or title of a document. Returns `id` if document was reided,
    `docid` if renaming operation was queued.

    :param doctype: DocType of the document
    :param docid: ID of the document
    :param title: New Title of the document
    :param id: New ID of the document
    :param merge: Merge the current Document with the existing one if exists
    :param enqueue: Enqueue the reid operation, title is updated in current process
    """

    # to maintain backwards API compatibility
    updated_title = kwargs.get("new_title") or title
    updated_id = kwargs.get("new_id") or id

    # TODO: omit this after runtime type checking (ref: https://github.com/frappe/frappe/pull/14927)
    for obj in [docid, updated_title, updated_id]:
        if not isinstance(obj, str | NoneType):
            frappe.throw(f"{obj=} must be of type str or None")

    # handle bad API usages
    merge = sbool(merge)
    enqueue = sbool(enqueue)
    action_enqueued = enqueue and not is_scheduler_inactive()

    doc = frappe.get_doc(doctype, docid)
    doc.check_permission(permtype="write")

    title_field = doc.meta.get_title_field()

    title_updated = (
        updated_title
        and (title_field != "id")
        and (updated_title != doc.get(title_field))
    )
    id_updated = updated_id and (updated_id != doc.id)

    queue = kwargs.get("queue") or "long"

    if id_updated:
        if action_enqueued:
            current_id = doc.id

            # before_id hook may have DocType specific validations or transformations
            transformed_id = doc.run_method(
                "before_reid", current_id, updated_id, merge
            )
            if isinstance(transformed_id, dict):
                transformed_id = transformed_id.get("new")
            transformed_id = transformed_id or updated_id

            # run reid validations before queueing
            # use savepoints to avoid partial reids / commits
            validate_reid(
                doctype=doctype,
                old=current_id,
                new=transformed_id,
                meta=doc.meta,
                merge=merge,
                save_point=True,
            )

            doc.queue_action(
                "reid", id=transformed_id, merge=merge, queue=queue, timeout=36000
            )
        else:
            doc.reid(updated_id, merge=merge)

    if title_updated:
        if action_enqueued and id_updated:
            frappe.enqueue(
                "frappe.client.set_value",
                doctype=doc.doctype,
                id=updated_id,
                fieldname=title_field,
                value=updated_title,
            )
        else:
            try:
                setattr(doc, title_field, updated_title)
                doc.save()
                frappe.msgprint(_("Saved"), alert=True, indicator="green")
            except Exception as e:
                if frappe.db.is_duplicate_entry(e):
                    frappe.throw(
                        _("{0} {1} already exists").format(doctype, frappe.bold(docid)),
                        title=_("Duplicate ID"),
                        exc=frappe.DuplicateEntryError,
                    )
                raise

    return doc.id


def reid_doc(
    doctype: str | None = None,
    old: str | None = None,
    new: str | None = None,
    force: bool = False,
    merge: bool = False,
    ignore_permissions: bool = False,
    ignore_if_exists: bool = False,
    show_alert: bool = True,
    rebuild_search: bool = True,
    doc: Document | None = None,
    validate: bool = True,
) -> str:
    """Reid a doc(dt, old) to doc(dt, new) and update all linked fields of type "Link".

    doc: Document object to be reided.
    new: New id for the record. If None, and doctype is specified, new id may be automatically generated via before_reid hooks.
    doctype: DocType of the document. Not required if doc is passed.
    old: Current id of the document. Not required if doc is passed.
    force: Allow even if document is not allowed to be reided.
    merge: Merge with existing document of new id.
    ignore_permissions: Ignore user permissions while renaming.
    ignore_if_exists: Don't raise exception if document with new id already exists. This will quietely overwrite the existing document.
    show_alert: Display alert if document is reided successfully.
    rebuild_search: Rebuild linked doctype search after renaming.
    validate: Validate before renaming. If False, it is assumed that the caller has already validated.
    """
    old_usage_style = doctype and old and new
    new_usage_style = doc and new

    if not (new_usage_style or old_usage_style):
        raise TypeError(
            "{doctype, old, new} or {doc, new} are required arguments for frappe.model.reid_doc"
        )

    old = old or doc.id
    doctype = doctype or doc.doctype
    force = sbool(force)
    merge = sbool(merge)
    meta = frappe.get_meta(doctype)

    if validate:
        old_doc = doc or frappe.get_doc(doctype, old)
        out = old_doc.run_method("before_reid", old, new, merge) or {}
        new = (out.get("new") or new) if isinstance(out, dict) else (out or new)
        new = validate_reid(
            doctype=doctype,
            old=old,
            new=new,
            meta=meta,
            merge=merge,
            force=force,
            ignore_permissions=ignore_permissions,
            ignore_if_exists=ignore_if_exists,
            old_doc=old_doc,
        )

    if not merge:
        reid_parent_and_child(doctype, old, new, meta)
    else:
        update_assignments(old, new, doctype)

    # update link fields' values
    link_fields = get_link_fields(doctype)
    update_link_field_values(link_fields, old, new, doctype)

    reid_dynamic_links(doctype, old, new)

    # save the user settings in the db
    update_user_settings(old, new, link_fields)

    if doctype == "DocType":
        reid_doctype(doctype, old, new)
        update_customizations(old, new)

    update_attachments(doctype, old, new)

    reid_versions(doctype, old, new)

    reid_eps_records(doctype, old, new)

    # call after_reid
    new_doc = frappe.get_doc(doctype, new)

    if validate:
        # copy any flags if required
        new_doc._local = getattr(old_doc, "_local", None)

    new_doc.run_method("after_reid", old, new, merge)

    if not merge:
        reid_password(doctype, old, new)

    if merge:
        new_doc.add_comment(
            "Edit", _("merged {0} into {1}").format(frappe.bold(old), frappe.bold(new))
        )
    else:
        new_doc.add_comment(
            "Edit",
            _("reided from {0} to {1}").format(frappe.bold(old), frappe.bold(new)),
        )

    if merge:
        frappe.delete_doc(doctype, old)

    new_doc.clear_cache()
    frappe.clear_cache()
    if rebuild_search:
        frappe.enqueue(
            "frappe.utils.global_search.rebuild_for_doctype", doctype=doctype
        )

    if show_alert:
        frappe.msgprint(
            _("Document reided from {0} to {1}").format(bold(old), bold(new)),
            alert=True,
            indicator="green",
        )

    return new


def update_assignments(old: str, new: str, doctype: str) -> None:
    old_assignments = (
        frappe.parse_json(frappe.db.get_value(doctype, old, "_assign")) or []
    )
    new_assignments = (
        frappe.parse_json(frappe.db.get_value(doctype, new, "_assign")) or []
    )
    common_assignments = list(set(old_assignments).intersection(new_assignments))

    for user in common_assignments:
        # delete todos linked to old doc
        todos = frappe.get_all(
            "ToDo",
            {
                "owner": user,
                "reference_type": doctype,
                "reference_id": old,
            },
            ["id", "description"],
        )

        for todo in todos:
            frappe.delete_doc("ToDo", todo.id)

    unique_assignments = list(set(old_assignments + new_assignments))
    frappe.db.set_value(
        doctype, new, "_assign", frappe.as_json(unique_assignments, indent=0)
    )


def update_user_settings(old: str, new: str, link_fields: list[dict]) -> None:
    """
    Update the user settings of all the linked doctypes while renaming.
    """

    # store the user settings data from the redis to db
    sync_user_settings()

    if not link_fields:
        return

    # find the user settings for the linked doctypes
    linked_doctypes = {d.parent for d in link_fields if not d.issingle}
    UserSettings = frappe.qb.Table("__UserSettings")

    user_settings_details = (
        frappe.qb.from_(UserSettings)
        .select("user", "doctype", "data")
        .where(UserSettings.data.like(old) & UserSettings.doctype.isin(linked_doctypes))
        .run(as_dict=True)
    )

    # create the dict using the doctype id as key and values as list of the user settings
    from collections import defaultdict

    user_settings_dict = defaultdict(list)
    for user_setting in user_settings_details:
        user_settings_dict[user_setting.doctype].append(user_setting)

    # update the id in linked doctype whose user settings exists
    for fields in link_fields:
        user_settings = user_settings_dict.get(fields.parent)
        if user_settings:
            for user_setting in user_settings:
                update_user_settings_data(
                    user_setting, "value", old, new, "docfield", fields.fieldname
                )
        else:
            continue


def update_customizations(old: str, new: str) -> None:
    frappe.db.set_value(
        "Custom DocPerm", {"parent": old}, "parent", new, update_modified=False
    )


def update_attachments(doctype: str, old: str, new: str) -> None:
    if doctype != "DocType":
        File = frappe.qb.DocType("File")

        frappe.qb.update(File).set(File.attached_to_id, new).where(
            (File.attached_to_id == old) & (File.attached_to_doctype == doctype)
        ).run()


def reid_versions(doctype: str, old: str, new: str) -> None:
    Version = frappe.qb.DocType("Version")

    frappe.qb.update(Version).set(Version.docid, new).where(
        (Version.docid == old) & (Version.ref_doctype == doctype)
    ).run()


def reid_eps_records(doctype: str, old: str, new: str) -> None:
    EPL = frappe.qb.DocType("Energy Point Log")

    frappe.qb.update(EPL).set(EPL.reference_id, new).where(
        (EPL.reference_doctype == doctype) & (EPL.reference_id == old)
    ).run()


def reid_parent_and_child(doctype: str, old: str, new: str, meta: "Meta") -> None:
    frappe.qb.update(doctype).set("id", new).where(Field("id") == old).run()

    update_autoid_field(doctype, new, meta)
    update_child_docs(old, new, meta)


def update_autoid_field(doctype: str, new: str, meta: "Meta") -> None:
    # update the value of the autoid field on reid of the docid
    if meta.get("autoid"):
        field = meta.get("autoid").split(":")
        if field and field[0] == "field":
            frappe.qb.update(doctype).set(field[1], new).where(Field("id") == new).run()


def validate_reid(
    doctype: str,
    old: str,
    new: str,
    meta: "Meta",
    merge: bool,
    force: bool = False,
    ignore_permissions: bool = False,
    ignore_if_exists: bool = False,
    save_point=False,
    old_doc: Document | None = None,
) -> str:
    # using for update so that it gets locked and someone else cannot edit it while this reid is going on!
    if save_point:
        _SAVE_POINT = f"validate_reid_{frappe.generate_hash(length=8)}"
        frappe.db.savepoint(_SAVE_POINT)

    exists = (
        frappe.qb.from_(doctype)
        .where(Field("id") == new)
        .for_update()
        .select("id")
        .run(pluck=True)
    )
    exists = exists[0] if exists else None

    if not frappe.db.exists(doctype, old):
        frappe.throw(
            _("Can't reid {0} to {1} because {0} doesn't exist.").format(old, new)
        )

    if old == new:
        frappe.throw(
            _("No changes made because old and new id are the same.").format(old, new)
        )

    if exists and exists != new:
        # for fixing case, accents
        exists = None

    if merge and not exists:
        frappe.throw(
            _("{0} {1} does not exist, select a new target to merge").format(
                doctype, new
            )
        )

    if not merge and exists and not ignore_if_exists:
        frappe.throw(
            _("Another {0} with id {1} exists, select another id").format(doctype, new)
        )

    kwargs = {"doctype": doctype, "ptype": "write", "raise_exception": False}
    if old_doc:
        kwargs["doc"] = old_doc

    if not (ignore_permissions or frappe.permissions.has_permission(**kwargs)):
        frappe.throw(
            _("You need write permission on {0} {1} to reid").format(doctype, old)
        )

    if merge:
        kwargs["doc"] = frappe.get_doc(doctype, new)
        if not (ignore_permissions or frappe.permissions.has_permission(**kwargs)):
            frappe.throw(
                _("You need write permission on {0} {1} to merge").format(doctype, new)
            )

    if not (force or ignore_permissions) and not meta.allow_reid:
        frappe.throw(_("{0} not allowed to be reided").format(_(doctype)))

    # validate naming like it's done in doc.py
    new = validate_id(doctype, new)

    if save_point:
        frappe.db.rollback(save_point=_SAVE_POINT)

    return new


def reid_doctype(doctype: str, old: str, new: str) -> None:
    # change options for fieldtype Table, Table MultiSelect and Link
    fields_with_options = ("Link", *frappe.model.table_fields)

    for fieldtype in fields_with_options:
        update_options_for_fieldtype(fieldtype, old, new)

    # change parenttype for fieldtype Table
    update_parenttype_values(old, new)


def update_child_docs(old: str, new: str, meta: "Meta") -> None:
    # update "parent"
    for df in meta.get_table_fields():
        (
            frappe.qb.update(df.options)
            .set("parent", new)
            .where((Field("parent") == old) & (Field("parenttype") == meta.id))
        ).run()


def update_link_field_values(
    link_fields: list[dict], old: str, new: str, doctype: str
) -> None:
    for field in link_fields:
        if field["issingle"]:
            try:
                single_doc = frappe.get_doc(field["parent"])
                if single_doc.get(field["fieldname"]) == old:
                    single_doc.set(field["fieldname"], new)
                    # update single docs using ORM rather then query
                    # as single docs also sometimes sets defaults!
                    single_doc.flags.ignore_mandatory = True
                    single_doc.flags.ignore_links = True
                    single_doc.save(ignore_permissions=True)
            except ImportError:
                # fails in patches where the doctype has been reided
                # or no longer exists
                pass
        else:
            parent = field["parent"]
            docfield = field["fieldname"]

            # Handles the case where one of the link fields belongs to
            # the DocType being reided.
            # Here this field could have the current DocType as its value too.

            # In this case while updating link field value, the field's parent
            # or the current DocType table name hasn't been renamed yet,
            # so consider it's old name.
            if parent == new and doctype == "DocType":
                parent = old

            frappe.db.set_value(
                parent, {docfield: old}, docfield, new, update_modified=False
            )

        # update cached link_fields as per new
        if doctype == "DocType" and field["parent"] == old:
            field["parent"] = new


def get_link_fields(doctype: str) -> list[dict]:
    # get link fields from tabDocField
    if not frappe.flags.link_fields:
        frappe.flags.link_fields = {}

    if doctype not in frappe.flags.link_fields:
        dt = frappe.qb.DocType("DocType")
        df = frappe.qb.DocType("DocField")
        cf = frappe.qb.DocType("Custom Field")
        ps = frappe.qb.DocType("Property Setter")

        standard_fields_query = (
            frappe.qb.from_(df)
            .inner_join(dt)
            .on(df.parent == dt.id)
            .select(df.parent, df.fieldname, dt.issingle.as_("issingle"))
            .where((df.options == doctype) & (df.fieldtype == "Link"))
        )

        if frappe.db.has_column("DocField", "is_virtual"):
            standard_fields_query = standard_fields_query.where(df.is_virtual == 0)

        virtual_doctypes = []
        if frappe.db.has_column("DocType", "is_virtual"):
            virtual_doctypes = frappe.get_all("DocType", {"is_virtual": 1}, pluck="id")
            standard_fields_query = standard_fields_query.where(dt.is_virtual == 0)

        standard_fields = standard_fields_query.run(as_dict=True)

        cf_issingle = (
            frappe.qb.from_(dt)
            .select(dt.issingle)
            .where(dt.id == cf.dt)
            .as_("issingle")
        )
        custom_fields = (
            frappe.qb.from_(cf)
            .select(cf.dt.as_("parent"), cf.fieldname, cf_issingle)
            .where((cf.options == doctype) & (cf.fieldtype == "Link"))
        )
        if virtual_doctypes:
            custom_fields = custom_fields.where(cf.dt.notin(virtual_doctypes))
        custom_fields = custom_fields.run(as_dict=True)

        ps_issingle = (
            frappe.qb.from_(dt)
            .select(dt.issingle)
            .where(dt.id == ps.doc_type)
            .as_("issingle")
        )
        property_setter_fields = (
            frappe.qb.from_(ps)
            .select(
                ps.doc_type.as_("parent"), ps.field_name.as_("fieldname"), ps_issingle
            )
            .where(
                (ps.property == "options")
                & (ps.value == doctype)
                & (ps.field_name.notnull())
            )
        )
        if virtual_doctypes:
            property_setter_fields = property_setter_fields.where(
                ps.doc_type.notin(virtual_doctypes)
            )
        property_setter_fields = property_setter_fields.run(as_dict=True)

        frappe.flags.link_fields[doctype] = (
            standard_fields + custom_fields + property_setter_fields
        )

    return frappe.flags.link_fields[doctype]


def update_options_for_fieldtype(fieldtype: str, old: str, new: str) -> None:
    CustomField = frappe.qb.DocType("Custom Field")
    PropertySetter = frappe.qb.DocType("Property Setter")

    if frappe.conf.developer_mode:
        for id in frappe.get_all("DocField", filters={"options": old}, pluck="parent"):
            if id in (old, new):
                continue

            doctype = frappe.get_doc("DocType", id)
            save = False
            for f in doctype.fields:
                if f.options == old:
                    f.options = new
                    save = True
            if save:
                doctype.save()

    DocField = frappe.qb.DocType("DocField")
    frappe.qb.update(DocField).set(DocField.options, new).where(
        (DocField.fieldtype == fieldtype) & (DocField.options == old)
    ).run()

    frappe.qb.update(CustomField).set(CustomField.options, new).where(
        (CustomField.fieldtype == fieldtype) & (CustomField.options == old)
    ).run()

    frappe.qb.update(PropertySetter).set(PropertySetter.value, new).where(
        (PropertySetter.property == "options") & (PropertySetter.value == old)
    ).run()


def get_select_fields(old: str, new: str) -> list[dict]:
    """
    get select type fields where doctype's id is hardcoded as
    new line separated list
    """
    df = frappe.qb.DocType("DocField")
    dt = frappe.qb.DocType("DocType")
    cf = frappe.qb.DocType("Custom Field")
    ps = frappe.qb.DocType("Property Setter")

    # get link fields from tabDocField
    st_issingle = (
        frappe.qb.from_(dt)
        .select(dt.issingle)
        .where(dt.id == df.parent)
        .as_("issingle")
    )
    standard_fields = (
        frappe.qb.from_(df)
        .select(df.parent, df.fieldname, st_issingle)
        .where(
            (df.parent != new)
            & (df.fieldname != "fieldtype")
            & (df.fieldtype == "Select")
            & (df.options.like(f"%{old}%"))
        )
        .run(as_dict=True)
    )

    # get link fields from tabCustom Field
    cf_issingle = (
        frappe.qb.from_(dt).select(dt.issingle).where(dt.id == cf.dt).as_("issingle")
    )
    custom_select_fields = (
        frappe.qb.from_(cf)
        .select(cf.dt.as_("parent"), cf.fieldname, cf_issingle)
        .where(
            (cf.dt != new) & (cf.fieldtype == "Select") & (cf.options.like(f"%{old}%"))
        )
        .run(as_dict=True)
    )

    # remove fields whose options have been changed using property setter
    ps_issingle = (
        frappe.qb.from_(dt)
        .select(dt.issingle)
        .where(dt.id == ps.doc_type)
        .as_("issingle")
    )
    property_setter_select_fields = (
        frappe.qb.from_(ps)
        .select(ps.doc_type.as_("parent"), ps.field_name.as_("fieldname"), ps_issingle)
        .where(
            (ps.doc_type != new)
            & (ps.property == "options")
            & (ps.field_name.notnull())
            & (ps.value.like(f"%{old}%"))
        )
        .run(as_dict=True)
    )

    return standard_fields + custom_select_fields + property_setter_select_fields


def update_select_field_values(old: str, new: str):
    from frappe.query_builder.functions import Replace

    DocField = frappe.qb.DocType("DocField")
    CustomField = frappe.qb.DocType("Custom Field")
    PropertySetter = frappe.qb.DocType("Property Setter")

    frappe.qb.update(DocField).set(
        DocField.options, Replace(DocField.options, old, new)
    ).where(
        (DocField.fieldtype == "Select")
        & (DocField.parent != new)
        & (DocField.options.like(f"%\n{old}%") | DocField.options.like(f"%{old}\n%"))
    ).run()

    frappe.qb.update(CustomField).set(
        CustomField.options, Replace(CustomField.options, old, new)
    ).where(
        (CustomField.fieldtype == "Select")
        & (CustomField.dt != new)
        & (
            CustomField.options.like(f"%\n{old}%")
            | CustomField.options.like(f"%{old}\n%")
        )
    ).run()

    frappe.qb.update(PropertySetter).set(
        PropertySetter.value, Replace(PropertySetter.value, old, new)
    ).where(
        (PropertySetter.property == "options")
        & (PropertySetter.field_name.notnull())
        & (PropertySetter.doc_type != new)
        & (
            PropertySetter.value.like(f"%\n{old}%")
            | PropertySetter.value.like(f"%{old}\n%")
        )
    ).run()


def update_parenttype_values(old: str, new: str):
    child_doctypes = frappe.get_all(
        "DocField",
        fields=["options", "fieldname"],
        filters={"parent": new, "fieldtype": ["in", frappe.model.table_fields]},
    )

    custom_child_doctypes = frappe.get_all(
        "Custom Field",
        fields=["options", "fieldname"],
        filters={"dt": new, "fieldtype": ["in", frappe.model.table_fields]},
    )

    child_doctypes += custom_child_doctypes
    fields = [d["fieldname"] for d in child_doctypes]

    property_setter_child_doctypes = frappe.get_all(
        "Property Setter",
        filters={"doc_type": new, "property": "options", "field_name": ("in", fields)},
        pluck="value",
    )

    child_doctypes = set(
        list(d["options"] for d in child_doctypes) + property_setter_child_doctypes
    )

    for doctype in child_doctypes:
        table = frappe.qb.DocType(doctype)
        frappe.qb.update(table).set(table.parenttype, new).where(
            table.parenttype == old
        ).run()


def reid_dynamic_links(doctype: str, old: str, new: str):
    Singles = frappe.qb.DocType("Singles")
    for df in get_dynamic_link_map().get(doctype, []):
        # dynamic link in single, just one value to check
        meta = frappe.get_meta(df.parent)
        if meta.is_virtual:
            continue
        if meta.issingle:
            refdoc = frappe.db.get_singles_dict(df.parent)
            if refdoc.get(df.options) == doctype and refdoc.get(df.fieldname) == old:
                frappe.qb.update(Singles).set(Singles.value, new).where(
                    (Singles.field == df.fieldname)
                    & (Singles.doctype == df.parent)
                    & (Singles.value == old)
                ).run()
        else:
            # because the table hasn't been reided yet!
            parent = df.parent if df.parent != new else old

            frappe.qb.update(parent).set(df.fieldname, new).where(
                (Field(df.options) == doctype) & (Field(df.fieldname) == old)
            ).run()


def bulk_reid(
    doctype: str, rows: list[list] | None = None, via_console: bool = False
) -> list[str] | None:
    """Bulk reid documents

    :param doctype: DocType to be reided
    :param rows: list of documents as `((oldid, newid, merge(optional)), ..)`"""
    if not rows:
        frappe.throw(_("Please select a valid csv file with data"))

    if not via_console:
        max_rows = 500
        if len(rows) > max_rows:
            frappe.throw(_("Maximum {0} rows allowed").format(max_rows))

    reid_log = []
    for row in rows:
        # if row has some content
        if len(row) > 1 and row[0] and row[1]:
            merge = len(row) > 2 and (row[2] == "1" or row[2].lower() == "true")
            try:
                if reid_doc(doctype, row[0], row[1], merge=merge, rebuild_search=False):
                    msg = _("Successful: {0} to {1}").format(row[0], row[1])
                    frappe.db.commit()
                else:
                    msg = None
            except Exception as e:
                msg = _("** Failed: {0} to {1}: {2}").format(row[0], row[1], repr(e))
                frappe.db.rollback()

            if msg:
                if via_console:
                    print(msg)
                else:
                    reid_log.append(msg)

    frappe.enqueue("frappe.utils.global_search.rebuild_for_doctype", doctype=doctype)

    if not via_console:
        return reid_log