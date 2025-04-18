import frappe
from frappe.query_builder.functions import Coalesce, GroupConcat


def execute():
	frappe.reload_doc("desk", "doctype", "todo")

	ToDo = frappe.qb.DocType("ToDo")
	assignees = GroupConcat("owner").distinct().as_("assignees")

	assignments = (
		frappe.qb.from_(ToDo)
		.select(ToDo.id, ToDo.reference_type, assignees)
		.where(Coalesce(ToDo.reference_type, "") != "")
		.where(Coalesce(ToDo.reference_id, "") != "")
		.where(ToDo.status != "Cancelled")
		.groupby(ToDo.reference_type, ToDo.reference_id)
	).run(as_dict=True)

	for doc in assignments:
		assignments = doc.assignees.split(",")
		frappe.db.set_value(
			doc.reference_type,
			doc.reference_id,
			"_assign",
			frappe.as_json(assignments),
			update_modified=False,
		)
