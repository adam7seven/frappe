# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import getpass

import frappe
from frappe.database.db_manager import DbManager
from frappe.geo.doctype.country.country import import_country_and_currency
from frappe.utils import cint
from frappe.utils.password import update_password

import os


def before_install():
	frappe.reload_doc("core", "doctype", "doctype_state")
	frappe.reload_doc("core", "doctype", "docfield")
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "doctype_action")
	frappe.reload_doc("core", "doctype", "doctype_link")
	frappe.reload_doc("desk", "doctype", "form_tour_step")
	frappe.reload_doc("desk", "doctype", "form_tour")
	frappe.reload_doc("core", "doctype", "doctype")
	frappe.clear_cache()


def after_install():
	create_user_type()
	install_basic_docs()

	from frappe.core.doctype.file.utils import make_home_folder
	from frappe.core.doctype.language.language import sync_languages

	make_home_folder()
	import_country_and_currency()
	sync_languages()

	# save default print setting
	print_settings = frappe.get_doc("Print Settings")
	print_settings.save()

	# all roles to admin
	frappe.get_doc("User", "Administrator").add_roles(*frappe.get_all("Role", pluck="id"))

	# update admin password
	update_password("Administrator", get_admin_password())

	if not frappe.conf.skip_setup_wizard:
		# only set home_page if the value doesn't exist in the db
		if not frappe.db.get_default("desktop:home_page"):
			frappe.db.set_default("desktop:home_page", "setup-wizard")

	# clear test log
	from frappe.tests.utils.generators import _clear_test_log

	_clear_test_log()

	add_standard_navbar_items()

	frappe.db.commit()

	# Install sql scripts
	install_sql_scripts()


def create_user_type():
	for user_type in ["System User", "Website User"]:
		if not frappe.db.exists("User Type", user_type):
			frappe.get_doc({"doctype": "User Type", "id": user_type, "is_standard": 1}).insert(
				ignore_permissions=True
			)


def install_basic_docs():
	# core users / roles
	install_docs = [
		{
			"doctype": "User",
			"id": "Administrator",
			"first_name": "Administrator",
			"email": "admin@example.com",
			"enabled": 1,
			"is_admin": 1,
			"roles": [{"role": "Administrator"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{
			"doctype": "User",
			"id": "Guest",
			"first_name": "Guest",
			"email": "guest@example.com",
			"enabled": 1,
			"is_guest": 1,
			"roles": [{"role": "Guest"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{"doctype": "Role", "role_id": "Translator"},
		{
			"doctype": "Workflow State",
			"id": "Pending",
			"name": "Pending",
			"icon": "question-sign",
			"style": "",
		},
		{
			"doctype": "Workflow State",
			"id": "Approved",
			"name": "Approved",
			"icon": "ok-sign",
			"style": "Success",
		},
		{
			"doctype": "Workflow State",
			"id": "Rejected",
			"name": "Rejected",
			"icon": "remove",
			"style": "Danger",
		},
		{"doctype": "Workflow Action Master", "id": "Approve"},
		{"doctype": "Workflow Action Master", "id": "Reject"},
		{"doctype": "Workflow Action Master", "id": "Review"},
	]

	for d in install_docs:
		try:
			frappe.get_doc(d).insert(ignore_if_duplicate=True)
		except frappe.IDError:
			pass


def get_admin_password():
	return frappe.conf.get("admin_password") or getpass.getpass("Set Administrator password: ")


def before_tests():
	if len(frappe.get_installed_apps()) > 1:
		# don't run before tests if any other app is installed
		return

	frappe.db.truncate("Custom Field")
	frappe.db.truncate("Event")

	frappe.clear_cache()

	# complete setup if missing
	if not frappe.is_setup_complete():
		complete_setup_wizard()

	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
	frappe.db.commit()
	frappe.clear_cache()


def complete_setup_wizard():
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"email": "test@erpnext.com",
			"full_name": "Test User",
			"password": "test",
			"country": "United States",
			"timezone": "America/New_York",
			"currency": "USD",
			"enable_telemtry": 1,
		}
	)


def add_standard_navbar_items():
	navbar_settings = frappe.get_single("Navbar Settings")

	# don't add settings/help options if they're already present
	if navbar_settings.settings_dropdown and navbar_settings.help_dropdown:
		return

	navbar_settings.settings_dropdown = []
	navbar_settings.help_dropdown = []

	for item in frappe.get_hooks("standard_navbar_items"):
		navbar_settings.append("settings_dropdown", item)

	for item in frappe.get_hooks("standard_help_items"):
		navbar_settings.append("help_dropdown", item)

	navbar_settings.save()


def install_sql_scripts():
	base_path = os.path.dirname(__file__)
	source_sql = os.path.join(
		base_path, "core", "doctype", "quantity_complete_definition", "create_table.sql"
	)
	install_sql_scripts(source_sql)


def install_sql_script(source_sql: str, verbose: bool = False):
	if verbose:
		print("Installing sql script...")
	db_name = frappe.conf.db_name
	DbManager(frappe.local.db).restore_database(
		verbose, db_name, source_sql, frappe.conf.db_user, frappe.conf.db_password
	)
	if verbose:
		print("Installed sql script: {}".format(source_sql))
