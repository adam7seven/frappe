import frappe


def execute():
    frappe.reload_doctype("Translation")
    frappe.db.sql(
        "UPDATE `tabTranslation` SET `translated_text`=`target_id`, `source_text`=`source_id`, `contributed`=0"
    )
