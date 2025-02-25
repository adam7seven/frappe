import frappe


def execute():
    for web_form_id in frappe.get_all("Web Form", pluck="id"):
        web_form = frappe.get_doc("Web Form", web_form_id)
        doctype_layout = frappe.get_doc(
            doctype="DocType Layout",
            document_type=web_form.doc_type,
            id=web_form.title,
            route=web_form.route,
            fields=[
                dict(fieldname=d.fieldname, label=d.label)
                for d in web_form.web_form_fields
                if d.fieldname
            ],
        ).insert()
        print(doctype_layout.id)
