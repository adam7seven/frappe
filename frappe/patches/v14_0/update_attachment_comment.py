import frappe


def execute():
    frappe.db.auto_commit_on_many_writes = 1

    # Strip everything except link to attachment and icon from comments of type "Attached"
    for id, content in frappe.get_all(
        "Comment",
        filters={"comment_type": "Attachment"},
        fields=["id", "content"],
        as_list=True,
    ):
        if not content:
            continue

        start = content.find("<a href")
        if start != -1:
            content = content[start:]

        end = content.find("</i>")
        end = content.find("</a>") if end == -1 else end
        if end != -1:
            content = content[: end + 4]

        frappe.db.set_value("Comment", id, "content", content, update_modified=False)

    # Strip "Removed " from comments of type "Attachment Removed"
    for id, content in frappe.get_all(
        "Comment",
        filters={"comment_type": "Attachment Removed"},
        fields=["id", "content"],
        as_list=True,
    ):
        if content and content.startswith("Removed "):
            frappe.db.set_value(
                "Comment", id, "content", content[8:], update_modified=False
            )
