import frappe
from frappe import _


def get_modules_from_all_apps_for_user(user: str | None = None) -> list[dict]:
	user = user or frappe.session.user
	all_modules = get_modules_from_all_apps()
	global_blocked_modules = frappe.get_doc("User", "Administrator").get_blocked_modules()
	user_blocked_modules = frappe.get_doc("User", user).get_blocked_modules()
	blocked_modules = global_blocked_modules + user_blocked_modules
	allowed_modules_list = [m for m in all_modules if m.get("id") not in blocked_modules]

	empty_tables_by_module = get_all_empty_tables_by_module()

	for module in allowed_modules_list:
		module_id = module.get("module_id")

		# Apply onboarding status
		if module_id in empty_tables_by_module:
			module["onboard_present"] = 1

	return allowed_modules_list


def get_modules_from_all_apps():
	modules_list = []
	for app in frappe.get_installed_apps():
		modules_list += get_modules_from_app(app)
	return modules_list


def get_modules_from_app(app):
	return frappe.get_all("Module Def", filters={"app_name": app}, fields=["id", "app_name as app"])


def get_all_empty_tables_by_module():
	table_rows = frappe.qb.Field("table_rows")
	table_name = frappe.qb.Field("table_name")
	information_schema = frappe.qb.Schema("information_schema")

	empty_tables = (
		frappe.qb.from_(information_schema.tables).select(table_name).where(table_rows == 0)
	).run()

	empty_tables = {r[0] for r in empty_tables}

	results = frappe.get_all("DocType", fields=["id", "module"])
	empty_tables_by_module = {}

	for doctype, module in results:
		if f"tab{doctype}" in empty_tables:
			if module in empty_tables_by_module:
				empty_tables_by_module[module].append(doctype)
			else:
				empty_tables_by_module[module] = [doctype]
	return empty_tables_by_module


def is_domain(module):
	return module.get("category") == "Domains"


def is_module(module):
	return module.get("type") == "module"
