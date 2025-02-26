import frappe


def execute():
    frappe.delete_doc_if_exists("DocType", "Tag Category")
    frappe.delete_doc_if_exists("DocType", "Tag Doc Category")

    frappe.reload_doc("desk", "doctype", "tag")
    frappe.reload_doc("desk", "doctype", "tag_link")

    tag_list = []
    tag_links = []
    time = frappe.utils.get_datetime()

    for doctype in frappe.get_list("DocType", filters={"istable": 0, "issingle": 0, "is_virtual": 0}):
        if not frappe.db.count(doctype.id) or not frappe.db.has_column(doctype.id, "_user_tags"):
            continue

        for _user_tags in frappe.db.sql(f"select `id`, `_user_tags` from `tab{doctype.id}`", as_dict=True):
            if not _user_tags.get("_user_tags"):
                continue

            for tag in _user_tags.get("_user_tags").split(",") if _user_tags.get("_user_tags") else []:
                if not tag:
                    continue

                tag_list.append((tag.strip(), time, time, "Administrator"))

                tag_link_id = frappe.generate_hash(length=10)
                tag_links.append((tag_link_id, doctype.id, _user_tags.id, tag.strip(), time, time, "Administrator"))

    frappe.db.bulk_insert(
        "Tag",
        fields=["id", "creation", "modified", "modified_by"],
        values=set(tag_list),
        ignore_duplicates=True,
    )
    frappe.db.bulk_insert(
        "Tag Link",
        fields=["id", "document_type", "document_id", "tag", "creation", "modified", "modified_by"],
        values=set(tag_links),
        ignore_duplicates=True,
    )
