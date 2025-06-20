# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.page.permission_manager.permission_manager import add, reset, update
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.database.utils import DefaultOrderBy
from frappe.desk.reportview import get_filters_cond
from frappe.handler import execute_cmd
from frappe.model.db_query import DatabaseQuery, get_between_date_filter
from frappe.permissions import add_user_permission, clear_user_permissions_for_doctype
from frappe.query_builder import Column
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.testutils import add_custom_field, clear_custom_fields

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Blog Post", "Blog Category", "Blogger"]


@contextmanager
def setup_test_user(set_user=False):
	test_user = frappe.get_doc("User", "test@example.com")
	user_roles = frappe.get_roles()
	test_user.remove_roles(*user_roles)
	test_user.add_roles("Blogger")

	if set_user:
		frappe.set_user(test_user.id)

	yield test_user

	test_user.remove_roles("Blogger")
	test_user.add_roles(*user_roles)


@contextmanager
def setup_patched_blog_post():
	add_child_table_to_blog_post()
	make_property_setter("Blog Post", "published", "permlevel", 1, "Int")
	reset("Blog Post")
	add("Blog Post", "Website Manager", 1)
	update("Blog Post", "Website Manager", 1, "write", 1)
	yield


class TestDBQuery(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_basic(self):
		self.assertTrue({"id": "DocType"} in DatabaseQuery("DocType").execute(limit_page_length=None))

	def test_extract_tables(self):
		db_query = DatabaseQuery("DocType")
		add_custom_field("DocType", "test_tab_field", "Data")

		db_query.fields = [
			"tabNote.creation",
			"test_tab_field",
			"tabDocType.test_tab_field",
		]
		db_query.extract_tables()
		self.assertIn("`tabNote`", db_query.tables)
		self.assertIn("`tabDocType`", db_query.tables)
		self.assertNotIn("test_tab_field", db_query.tables)

		clear_custom_fields("DocType")

	def test_child_table_field_syntax(self):
		note = frappe.get_doc(
			doctype="Note",
			title=f"Test {frappe.utils.random_string(8)}",
			content="test",
			seen_by=[{"user": "Administrator"}],
		).insert()
		result = frappe.get_all(
			"Note",
			filters={"id": note.id},
			fields=["id", "seen_by.user as seen_by"],
			limit=1,
		)
		self.assertEqual(result[0].seen_by, "Administrator")
		note.delete()

	def test_child_table_join(self):
		frappe.delete_doc_if_exists("DocType", "Parent DocType 1")
		frappe.delete_doc_if_exists("DocType", "Parent DocType 2")
		frappe.delete_doc_if_exists("DocType", "Child DocType")
		# child table
		frappe.get_doc(
			{
				"doctype": "DocType",
				"id": "Child DocType",
				"module": "Custom",
				"custom": 1,
				"istable": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				],
			}
		).insert()
		# doctype 1
		frappe.get_doc(
			{
				"doctype": "DocType",
				"id": "Parent DocType 1",
				"module": "Custom",
				"autoname": "Prompt",
				"custom": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
					{
						"label": "Table Field 1",
						"fieldname": "child",
						"fieldtype": "Table",
						"options": "Child DocType",
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()
		# doctype 2
		frappe.get_doc(
			{
				"doctype": "DocType",
				"id": "Parent DocType 2",
				"autoname": "Prompt",
				"module": "Custom",
				"custom": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
					{
						"label": "Table Field 1",
						"fieldname": "child",
						"fieldtype": "Table",
						"options": "Child DocType",
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()

		# clear records
		frappe.db.delete("Parent DocType 1")
		frappe.db.delete("Parent DocType 2")
		frappe.db.delete("Child DocType")

		# insert records
		frappe.get_doc(
			doctype="Parent DocType 1",
			title="test",
			child=[
				{"title": "parent 1 child record 1"},
				{"title": "parent 1 child record 2"},
			],
			__newid="test_parent",
		).insert(ignore_if_duplicate=True)
		frappe.get_doc(
			doctype="Parent DocType 2",
			title="test",
			child=[{"title": "parent 2 child record 1"}],
			__newid="test_parent",
		).insert(ignore_if_duplicate=True)

		# test query
		results1 = frappe.get_all("Parent DocType 1", fields=["id", "child.title as child_title"])
		results2 = frappe.get_all("Parent DocType 2", fields=["id", "child.title as child_title"])
		# check both parents have same id
		self.assertEqual(results1[0].id, results2[0].id)
		# check both parents have different number of child records
		self.assertEqual(len(results1), 2)
		self.assertEqual(len(results2), 1)
		parent1_children = [result.child_title for result in results1]
		self.assertIn("parent 1 child record 1", parent1_children)
		self.assertIn("parent 1 child record 2", parent1_children)
		self.assertEqual(results2[0].child_title, "parent 2 child record 1")

	def test_link_field_syntax(self):
		todo = frappe.get_doc(doctype="ToDo", description="Test ToDo", allocated_to="Administrator").insert()
		result = frappe.get_all(
			"ToDo",
			filters={"id": todo.id},
			fields=["id", "allocated_to.email as allocated_user_email"],
			limit=1,
		)
		self.assertEqual(result[0].allocated_user_email, "admin@example.com")
		todo.delete()

	def test_build_match_conditions(self):
		clear_user_permissions_for_doctype("Blog Post", "test2@example.com")

		test2user = frappe.get_doc("User", "test2@example.com")
		test2user.add_roles("Blogger")
		frappe.set_user("test2@example.com")

		# this will get match conditions for Blog Post
		build_match_conditions = DatabaseQuery("Blog Post").build_match_conditions

		# Before any user permission is applied
		# get as filters
		self.assertEqual(build_match_conditions(as_condition=False), [])
		# get as conditions
		self.assertEqual(build_match_conditions(as_condition=True), "")

		add_user_permission("Blog Post", "-test-blog-post", "test2@example.com", True)
		add_user_permission("Blog Post", "-test-blog-post-1", "test2@example.com", True)

		# After applying user permission
		# get as filters
		self.assertTrue(
			{"Blog Post": ["-test-blog-post-1", "-test-blog-post"]}
			in build_match_conditions(as_condition=False)
		)
		# get as conditions
		if frappe.db.db_type == "mariadb":
			assertion_string = """(((ifnull(`tabBlog Post`.`id`, '')='' or `tabBlog Post`.`id` in ('-test-blog-post-1', '-test-blog-post'))))"""
		else:
			assertion_string = """(((ifnull(cast(`tabBlog Post`.`id` as varchar), '')='' or cast(`tabBlog Post`.`id` as varchar) in ('-test-blog-post-1', '-test-blog-post'))))"""

		self.assertEqual(build_match_conditions(as_condition=True), assertion_string)

		frappe.set_user("Administrator")

	def test_fields(self):
		self.assertTrue(
			{"id": "DocType", "issingle": 0}
			in DatabaseQuery("DocType").execute(fields=["id", "issingle"], limit_page_length=None)
		)

	def test_filters_1(self):
		self.assertFalse(
			{"id": "DocType"} in DatabaseQuery("DocType").execute(filters=[["DocType", "id", "like", "J%"]])
		)

	def test_filters_2(self):
		self.assertFalse(
			{"id": "DocType"} in DatabaseQuery("DocType").execute(filters=[{"id": ["like", "J%"]}])
		)

	def test_filters_3(self):
		self.assertFalse(
			{"id": "DocType"} in DatabaseQuery("DocType").execute(filters={"id": ["like", "J%"]})
		)

	def test_filters_4(self):
		self.assertTrue({"id": "DocField"} in DatabaseQuery("DocType").execute(filters={"id": "DocField"}))

	def test_in_not_in_filters(self):
		self.assertFalse(DatabaseQuery("DocType").execute(filters={"id": ["in", None]}))
		self.assertTrue(
			{"id": "DocType"} in DatabaseQuery("DocType").execute(filters={"id": ["not in", None]})
		)

		for result in [{"id": "DocType"}, {"id": "DocField"}]:
			self.assertTrue(
				result in DatabaseQuery("DocType").execute(filters={"id": ["in", "DocType,DocField"]})
			)

		for result in [{"id": "DocType"}, {"id": "DocField"}]:
			self.assertFalse(
				result in DatabaseQuery("DocType").execute(filters={"id": ["not in", "DocType,DocField"]})
			)

	def test_string_as_field(self):
		self.assertEqual(
			frappe.get_all("DocType", as_list=True), frappe.get_all("DocType", fields="id", as_list=True)
		)

	def test_none_filter(self):
		query = frappe.qb.get_query("DocType", fields="id", filters={"restrict_to_domain": None})
		sql = str(query).replace("`", "").replace('"', "")
		condition = "restrict_to_domain IS NULL"
		self.assertIn(condition, sql)

	def test_or_filters(self):
		data = DatabaseQuery("DocField").execute(
			filters={"parent": "DocType"},
			fields=["fieldname", "fieldtype"],
			or_filters=[{"fieldtype": "Table"}, {"fieldtype": "Select"}],
		)

		self.assertTrue({"fieldtype": "Table", "fieldname": "fields"} in data)
		self.assertTrue({"fieldtype": "Select", "fieldname": "document_type"} in data)
		self.assertFalse({"fieldtype": "Check", "fieldname": "issingle"} in data)

	def test_between_filters(self):
		"""test case to check between filter for date fields"""
		frappe.db.delete("Event")

		# create events to test the between operator filter
		todays_event = create_event()
		event1 = create_event(starts_on="2016-07-05 23:59:59")
		event2 = create_event(starts_on="2016-07-06 00:00:00")
		event3 = create_event(starts_on="2016-07-07 23:59:59")
		event4 = create_event(starts_on="2016-07-08 00:00:00")

		# if the values are not passed in filters then event should be filter as current datetime
		data = DatabaseQuery("Event").execute(filters={"starts_on": ["between", None]}, fields=["id"])

		self.assertTrue({"id": event1.id} not in data)

		# if both from and to_date values are passed
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-06", "2016-07-07"]]},
			fields=["id"],
		)

		self.assertIn({"id": event2.id}, data)
		self.assertIn({"id": event3.id}, data)
		self.assertNotIn({"id": event1.id}, data)
		self.assertNotIn({"id": event4.id}, data)

		# if only one value is passed in the filter
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-07"]]}, fields=["id"]
		)

		self.assertIn({"id": event3.id}, data)
		self.assertIn({"id": event4.id}, data)
		self.assertIn({"id": todays_event.id}, data)
		self.assertNotIn({"id": event1.id}, data)
		self.assertNotIn({"id": event2.id}, data)

		# test between is formatted for creation column
		data = DatabaseQuery("Event").execute(
			filters={"creation": ["between", ["2016-07-06", "2016-07-07"]]},
			fields=["id"],
		)

	def test_between_filters_date_bounds(self):
		date_df = frappe._dict(fieldtype="Date")
		datetime_df = frappe._dict(fieldtype="Datetime")
		today = frappe.utils.nowdate()

		# No filters -> assumes today
		cond = get_between_date_filter("", date_df)
		self.assertQueryEqual(cond, f"'{today}' AND '{today}'")

		# One filter assumes "from" bound and to is today
		start = "2021-01-01"
		cond = get_between_date_filter([start], date_df)
		self.assertQueryEqual(cond, f"'{start}' AND '{today}'")

		# both date filters are applied
		start = "2021-01-01"
		end = "2022-01-02"
		cond = get_between_date_filter([start, end], date_df)
		self.assertQueryEqual(cond, f"'{start}' AND '{end}'")

		# single date should include entire day
		start = "2021-01-01"
		cond = get_between_date_filter([start, start], datetime_df)
		self.assertQueryEqual(cond, f"'{start} 00:00:00.000000' AND '{start} 23:59:59.999999'")

		# datetime field on datetime type should remain same
		start = "2021-01-01 01:01:00"
		end = "2022-01-02 12:23:43"
		cond = get_between_date_filter([start, end], datetime_df)
		self.assertQueryEqual(cond, f"'{start}.000000' AND '{end}.000000'")

	def test_ignore_permissions_for_get_filters_cond(self):
		frappe.set_user("test2@example.com")
		self.assertRaises(frappe.PermissionError, get_filters_cond, "DocType", dict(istable=1), [])
		self.assertTrue(get_filters_cond("DocType", dict(istable=1), [], ignore_permissions=True))
		frappe.set_user("Administrator")

	def test_query_fields_sanitizer(self):
		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle, version()"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=[
				"id",
				"issingle, IF(issingle=1, (select id from tabUser), count(id))",
			],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle, (select count(*) from tabSessions)"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle, SELECT LOCATE('', `tabUser`.`user`) AS user;"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=[
				"id",
				"issingle, IF(issingle=1, (SELECT id from tabUser), count(*))",
			],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle ''"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle,'"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "select * from tabSessions"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle from --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "issingle from tabDocType order by 2 --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id", "1' UNION SELECT * FROM __Auth --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["@@version"],
			limit_start=0,
			limit_page_length=1,
		)

		data = DatabaseQuery("DocType").execute(
			fields=["count(`id`) as count"], limit_start=0, limit_page_length=1
		)
		self.assertTrue("count" in data[0])

		data = DatabaseQuery("DocType").execute(
			fields=["id", "issingle", "locate('', id) as _relevance"],
			limit_start=0,
			limit_page_length=1,
		)
		self.assertTrue("_relevance" in data[0])

		data = DatabaseQuery("DocType").execute(
			fields=["id", "issingle", "date(creation) as creation"],
			limit_start=0,
			limit_page_length=1,
		)
		self.assertTrue("creation" in data[0])

		if frappe.db.db_type != "postgres":
			# datediff function does not exist in postgres
			data = DatabaseQuery("DocType").execute(
				fields=[
					"id",
					"issingle",
					"datediff(modified, creation) as date_diff",
				],
				limit_start=0,
				limit_page_length=1,
			)
			self.assertTrue("date_diff" in data[0])

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"id",
					"issingle",
					"if (issingle=1, (select id from tabUser), count(id))",
				],
				limit_start=0,
				limit_page_length=1,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"id",
					"issingle",
					"if(issingle=1, (select id from tabUser), count(id))",
				],
				limit_start=0,
				limit_page_length=1,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"id",
					"issingle",
					"( select id from `tabUser` where `tabDocType`.owner = `tabUser`.id )",
				],
				limit_start=0,
				limit_page_length=1,
				ignore_permissions=True,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"id",
					"issingle",
					"(select id from `tabUser` where `tabDocType`.owner = `tabUser`.id )",
				],
				limit_start=0,
				limit_page_length=1,
			)

	def test_nested_permission(self):
		frappe.set_user("Administrator")
		create_nested_doctype()
		create_nested_doctype_records()
		clear_user_permissions_for_doctype("Nested DocType")

		# user permission for only one root folder
		add_user_permission("Nested DocType", "Level 1 A", "test2@example.com")

		from frappe.core.page.permission_manager.permission_manager import update

		# to avoid if_owner filter
		update("Nested DocType", "All", 0, "if_owner", 0)

		frappe.set_user("test2@example.com")
		data = DatabaseQuery("Nested DocType").execute()

		# children of root folder (for which we added user permission) should be accessible
		self.assertTrue({"id": "Level 2 A"} in data)
		self.assertTrue({"id": "Level 2 A"} in data)

		# other folders should not be accessible
		self.assertFalse({"id": "Level 1 B"} in data)
		self.assertFalse({"id": "Level 2 B"} in data)
		update("Nested DocType", "All", 0, "if_owner", 1)
		frappe.set_user("Administrator")

	def test_filter_sanitizer(self):
		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id"],
			filters={"istable,": 1},
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id"],
			filters={"editable_grid,": 1},
			or_filters={"istable,": 1},
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id"],
			filters={"editable_grid,": 1},
			or_filters=[["DocType", "istable,", "=", 1]],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["id"],
			filters={"editable_grid,": 1},
			or_filters=[
				["DocType", "istable", "=", 1],
				["DocType", "beta and 1=1", "=", 0],
			],
			limit_start=0,
			limit_page_length=1,
		)

		out = DatabaseQuery("DocType").execute(
			fields=["id"],
			filters={"editable_grid": 1, "module": "Core"},
			or_filters=[["DocType", "istable", "=", 1]],
			order_by="creation",
		)
		self.assertTrue("DocField" in [d["id"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["id"],
			filters={"issingle": 1},
			or_filters=[["DocType", "module", "=", "Core"]],
			order_by="creation",
		)
		self.assertTrue("Role Permission for Page and Report" in [d["id"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["id"],
			filters={"track_changes": 1, "module": "Core"},
			order_by="creation",
		)
		self.assertTrue("File" in [d["id"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["id"],
			filters=[
				["DocType", "ifnull(track_changes, 0)", "=", 0],
				["DocType", "module", "=", "Core"],
			],
			order_by="creation",
		)
		self.assertTrue("DefaultValue" in [d["id"] for d in out])

	def test_order_by_group_by_sanitizer(self):
		# order by with blacklisted function
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["id"],
				order_by="sleep (1) asc",
			)

		# group by with blacklisted function
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["id"],
				group_by="SLEEP(0)",
			)

		# sub query in order by
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["id"],
				order_by="(select rank from tabRankedDocTypes where tabRankedDocTypes.id = tabDocType.id) asc",
			)

		# validate allowed usage
		DatabaseQuery("DocType").execute(
			fields=["id"],
			order_by="id asc",
		)
		DatabaseQuery("DocType").execute(
			fields=["id"],
			order_by="id asc",
			group_by="id",
		)

		# check mariadb specific syntax
		if frappe.db.db_type == "mariadb":
			DatabaseQuery("DocType").execute(
				fields=["id"],
				order_by="timestamp(modified)",
			)

	def test_of_not_of_descendant_ancestors(self):
		frappe.set_user("Administrator")
		clear_user_permissions_for_doctype("Nested DocType")

		# in descendants filter
		data = frappe.get_all("Nested DocType", {"id": ("descendants of", "Level 2 A")})
		self.assertTrue({"id": "Level 3 A"} in data)

		data = frappe.get_all("Nested DocType", {"id": ("descendants of", "Level 1 A")})
		self.assertTrue({"id": "Level 3 A"} in data)
		self.assertTrue({"id": "Level 2 A"} in data)
		self.assertFalse({"id": "Level 2 B"} in data)
		self.assertFalse({"id": "Level 1 B"} in data)
		self.assertFalse({"id": "Level 1 A"} in data)
		self.assertFalse({"id": "Root"} in data)

		# in ancestors of filter
		data = frappe.get_all("Nested DocType", {"id": ("ancestors of", "Level 2 A")})
		self.assertFalse({"id": "Level 3 A"} in data)
		self.assertFalse({"id": "Level 2 A"} in data)
		self.assertFalse({"id": "Level 2 B"} in data)
		self.assertFalse({"id": "Level 1 B"} in data)
		self.assertTrue({"id": "Level 1 A"} in data)
		self.assertTrue({"id": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"id": ("ancestors of", "Level 1 A")})
		self.assertFalse({"id": "Level 3 A"} in data)
		self.assertFalse({"id": "Level 2 A"} in data)
		self.assertFalse({"id": "Level 2 B"} in data)
		self.assertFalse({"id": "Level 1 B"} in data)
		self.assertFalse({"id": "Level 1 A"} in data)
		self.assertTrue({"id": "Root"} in data)

		# not descendants filter
		data = frappe.get_all("Nested DocType", {"id": ("not descendants of", "Level 2 A")})
		self.assertFalse({"id": "Level 3 A"} in data)
		self.assertTrue({"id": "Level 2 A"} in data)
		self.assertTrue({"id": "Level 2 B"} in data)
		self.assertTrue({"id": "Level 1 A"} in data)
		self.assertTrue({"id": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"id": ("not descendants of", "Level 1 A")})
		self.assertFalse({"id": "Level 3 A"} in data)
		self.assertFalse({"id": "Level 2 A"} in data)
		self.assertTrue({"id": "Level 2 B"} in data)
		self.assertTrue({"id": "Level 1 B"} in data)
		self.assertTrue({"id": "Level 1 A"} in data)
		self.assertTrue({"id": "Root"} in data)

		# not ancestors of filter
		data = frappe.get_all("Nested DocType", {"id": ("not ancestors of", "Level 2 A")})
		self.assertTrue({"id": "Level 3 A"} in data)
		self.assertTrue({"id": "Level 2 A"} in data)
		self.assertTrue({"id": "Level 2 B"} in data)
		self.assertTrue({"id": "Level 1 B"} in data)
		self.assertTrue({"id": "Level 1 A"} not in data)
		self.assertTrue({"id": "Root"} not in data)

		data = frappe.get_all("Nested DocType", {"id": ("not ancestors of", "Level 1 A")})
		self.assertTrue({"id": "Level 3 A"} in data)
		self.assertTrue({"id": "Level 2 A"} in data)
		self.assertTrue({"id": "Level 2 B"} in data)
		self.assertTrue({"id": "Level 1 B"} in data)
		self.assertTrue({"id": "Level 1 A"} in data)
		self.assertFalse({"id": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"id": ("ancestors of", "Root")})
		self.assertTrue(len(data) == 0)
		self.assertTrue(
			len(frappe.get_all("Nested DocType", {"id": ("not ancestors of", "Root")}))
			== len(frappe.get_all("Nested DocType"))
		)

	def test_is_set_is_not_set(self):
		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "not set"]})
		self.assertTrue({"id": "Integration Request"} in res)
		self.assertTrue({"id": "User"} in res)
		self.assertFalse({"id": "Blogger"} in res)

		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "set"]})
		self.assertTrue({"id": "DocField"} in res)
		self.assertTrue({"id": "Prepared Report"} in res)
		self.assertFalse({"id": "Property Setter"} in res)

		frappe.db.set_value("DocType", "Property Setter", "autoname", None, update_modified=False)

		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "set"]})
		self.assertFalse({"id": "Property Setter"} in res)

	def test_set_field_tables(self):
		# Tests _in_standard_sql_methods method in test_set_field_tables
		# The following query will break if the above method is broken
		frappe.db.get_list(
			"Web Form",
			filters=[["Web Form Field", "reqd", "=", 1]],
			fields=["count(*) as count"],
			order_by="count desc",
			limit=50,
		)

	def test_virtual_field_get_list(self):
		try:
			frappe.get_list("Prepared Report", ["*"])
			frappe.get_list("Scheduled Job Type", ["*"])
		except Exception:
			print(frappe.get_traceback())
			self.fail("get_list not working with virtual field")

	def test_pluck_name(self):
		ids = DatabaseQuery("DocType").execute(filters={"id": "DocType"}, pluck="id")
		self.assertEqual(ids, ["DocType"])

	def test_pluck_any_field(self):
		owners = DatabaseQuery("DocType").execute(filters={"id": "DocType"}, pluck="owner")
		self.assertEqual(owners, ["Administrator"])

	def test_prepare_select_args(self):
		# frappe.get_all inserts modified field into order_by clause
		# test to make sure this is inserted into select field when postgres
		doctypes = frappe.get_all(
			"DocType",
			filters={"docstatus": 0, "document_type": ("!=", "")},
			group_by="document_type",
			fields=["document_type", "sum(is_submittable) as is_submittable"],
			limit=1,
			as_list=True,
		)
		if frappe.conf.db_type == "mariadb":
			self.assertTrue(len(doctypes[0]) == 2)
		else:
			self.assertTrue(len(doctypes[0]) == 3)
			self.assertTrue(isinstance(doctypes[0][2], datetime.datetime))

	def test_column_comparison(self):
		"""Test DatabaseQuery.execute to test column comparison"""
		users_unedited = frappe.get_all(
			"User",
			filters={"creation": Column("modified")},
			fields=["id", "creation", "modified"],
			limit=1,
		)
		users_edited = frappe.get_all(
			"User",
			filters={"creation": ("!=", Column("modified"))},
			fields=["id", "creation", "modified"],
			limit=1,
		)

		self.assertEqual(users_unedited[0].modified, users_unedited[0].creation)
		self.assertNotEqual(users_edited[0].modified, users_edited[0].creation)

	def test_permlevel_fields(self):
		with setup_patched_blog_post(), setup_test_user(set_user=True):
			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "published"],
				limit=1,
			)
			self.assertFalse("published" in data[0])
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "`published`"],
				limit=1,
			)
			self.assertFalse("published" in data[0])
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "`tabBlog Post`.`published`"],
				limit=1,
			)
			self.assertFalse("published" in data[0])
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "`tabTest Child`.`test_field`"],
				limit=1,
			)
			self.assertFalse("test_field" in data[0])
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "MAX(`published`)"],
				limit=1,
			)
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "LAST(published)"],
				limit=1,
			)
			self.assertTrue("id" in data[0])
			self.assertEqual(len(data[0]), 1)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "MAX(`modified`)"],
				limit=1,
				order_by=None,
				group_by="id",
			)
			self.assertEqual(len(data[0]), 2)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "now() abhi"],
				limit=1,
			)
			self.assertIsInstance(data[0]["abhi"], datetime.datetime)
			self.assertEqual(len(data[0]), 2)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "'LABEL'"],
				limit=1,
			)
			self.assertTrue("id" in data[0])
			self.assertTrue("LABEL" in data[0].values())
			self.assertEqual(len(data[0]), 2)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "COUNT(*) as count"],
				limit=1,
				order_by=None,
				group_by="id",
			)
			self.assertTrue("count" in data[0])
			self.assertEqual(len(data[0]), 2)

			data = frappe.get_list(
				"Blog Post",
				filters={"published": 1},
				fields=["id", "COUNT(*) count"],
				limit=1,
				order_by=None,
				group_by="id",
			)
			self.assertTrue("count" in data[0])
			self.assertEqual(len(data[0]), 2)

			data = frappe.get_list(
				"Blog Post",
				fields=[
					"id",
					"blogger.full_name as blogger_full_name",
					"blog_category.description",
				],
				limit=1,
			)
			self.assertTrue("id" in data[0])
			self.assertTrue("blogger_full_name" in data[0])
			self.assertTrue("description" in data[0])

	def test_cast_name(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "autoinc_dt_test")
		dt = new_doctype("autoinc_dt_test", autoname="autoincrement").insert(ignore_permissions=True)

		query = DatabaseQuery("autoinc_dt_test").execute(
			fields=[
				"locate('1', `tabautoinc_dt_test`.`id`)",
				"id",
				"locate('1', id)",
			],
			filters={"id": 1},
			run=False,
		)

		if frappe.db.db_type == "postgres":
			self.assertTrue('strpos( cast("tabautoinc_dt_test"."id" as varchar), \'1\')' in query)
			self.assertTrue("strpos( cast(id as varchar), '1')" in query)
			self.assertTrue('where cast("tabautoinc_dt_test"."id" as varchar) = \'1\'' in query)
		else:
			self.assertTrue("locate('1', `tabautoinc_dt_test`.`id`)" in query)
			self.assertTrue("locate('1', id)" in query)
			self.assertTrue("where `tabautoinc_dt_test`.`id` = 1" in query)

		dt.delete(ignore_permissions=True)

	def test_fieldname_starting_with_int(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "dt_with_int_named_fieldname")
		frappe.delete_doc_if_exists("DocType", "table_dt")

		table_dt = new_doctype(
			"table_dt",
			istable=1,
			fields=[{"label": "1field", "fieldname": "2field", "fieldtype": "Data"}],
		).insert()

		dt = new_doctype(
			"dt_with_int_named_fieldname",
			fields=[
				{"label": "1field", "fieldname": "1field", "fieldtype": "Data"},
				{
					"label": "2table_field",
					"fieldname": "2table_field",
					"fieldtype": "Table",
					"options": table_dt.id,
				},
			],
		).insert(ignore_permissions=True)

		dt_data = frappe.get_doc({"doctype": "dt_with_int_named_fieldname", "1field": "10"}).insert(
			ignore_permissions=True
		)

		query = DatabaseQuery("dt_with_int_named_fieldname")
		self.assertTrue(query.execute(filters={"1field": "10"}))
		self.assertTrue(query.execute(filters={"1field": ["like", "1%"]}))
		self.assertTrue(query.execute(filters={"1field": ["in", "1,2,10"]}))
		self.assertTrue(query.execute(filters={"1field": ["is", "set"]}))
		self.assertFalse(query.execute(filters={"1field": ["not like", "1%"]}))
		self.assertTrue(query.execute(filters=[["table_dt", "2field", "is", "not set"]]))

		frappe.get_doc(
			{
				"doctype": table_dt.id,
				"2field": "10",
				"parent": dt_data.id,
				"parenttype": dt_data.doctype,
				"parentfield": "2table_field",
			}
		).insert(ignore_permissions=True)

		self.assertTrue(query.execute(filters=[["table_dt", "2field", "is", "set"]]))

		# cleanup
		dt.delete()
		table_dt.delete()

	def test_permission_query_condition(self):
		from frappe.desk.doctype.dashboard_settings.dashboard_settings import (
			create_dashboard_settings,
		)

		self.doctype = "Dashboard Settings"
		self.user = "test'5@example.com"

		permission_query_conditions = DatabaseQuery.get_permission_query_conditions(self)

		create_dashboard_settings(self.user)

		dashboard_settings = frappe.db.sql(
			f"""
				SELECT id
				FROM `tabDashboard Settings`
				WHERE {permission_query_conditions}
			""",
			as_dict=1,
		)[0]

		self.assertTrue(dashboard_settings)

	def test_virtual_doctype(self):
		"""Test that virtual doctypes can be queried using get_all"""

		virtual_doctype = new_doctype("Virtual DocType")
		virtual_doctype.is_virtual = 1
		virtual_doctype.insert(ignore_if_duplicate=True)

		class VirtualDocType:
			@staticmethod
			def get_list(args=None, limit_page_length=0, doctype=None):
				from frappe.types.filter import FilterTuple

				# Backward compatibility
				self.assertEqual(
					args["filters"], [FilterTuple(doctype="Virtual DocType", fieldname="id", value="test")]
				)

				self.assertEqual(limit_page_length, 1)
				self.assertEqual(doctype, "Virtual DocType")

		with patch(
			"frappe.controllers",
			new={frappe.local.site: {"Virtual DocType": VirtualDocType}},
		):
			frappe.get_all("Virtual DocType", filters={"id": "test"}, fields=["id"], limit=1)

	def test_coalesce_with_in_ops(self):
		self.assertNotIn("ifnull", frappe.get_all("User", {"first_name": ("in", ["a", "b"])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("in", ["a", None])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("in", ["a", ""])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("in", [])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("not in", ["a"])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("not in", [])}, run=0))
		self.assertIn("ifnull", frappe.get_all("User", {"first_name": ("not in", [""])}, run=0))

		# primary key is never nullable
		self.assertNotIn("ifnull", frappe.get_all("User", {"id": ("in", ["a", None])}, run=0))
		self.assertNotIn("ifnull", frappe.get_all("User", {"id": ("in", ["a", ""])}, run=0))
		self.assertNotIn("ifnull", frappe.get_all("User", {"id": ("in", (""))}, run=0))
		self.assertNotIn("ifnull", frappe.get_all("User", {"id": ("in", ())}, run=0))

	def test_coalesce_with_datetime_ops(self):
		self.assertNotIn("ifnull", frappe.get_all("User", {"last_active": (">", "2022-01-01")}, run=0))
		self.assertNotIn("ifnull", frappe.get_all("User", {"creation": ("<", "2022-01-01")}, run=0))
		self.assertNotIn(
			"ifnull",
			frappe.get_all("User", {"last_active": ("between", ("2022-01-01", "2023-01-01"))}, run=0),
		)
		self.assertIn("ifnull", frappe.get_all("User", {"last_active": ("<", "2022-01-01")}, run=0))

	def test_ambiguous_linked_tables(self):
		from frappe.desk.reportview import get

		if not frappe.db.exists("DocType", "Related Todos"):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"custom": 1,
					"module": "Custom",
					"id": "Related Todos",
					"naming_rule": "Random",
					"autoname": "hash",
					"fields": [
						{
							"label": "Todo One",
							"fieldname": "todo_one",
							"fieldtype": "Link",
							"options": "ToDo",
							"reqd": 1,
						},
						{
							"label": "Todo Two",
							"fieldname": "todo_two",
							"fieldtype": "Link",
							"options": "ToDo",
							"reqd": 1,
						},
					],
				}
			).insert()
		else:
			frappe.db.delete("Related Todos")

		todo_one = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Todo One",
			}
		).insert()

		todo_two = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Todo Two",
			}
		).insert()

		frappe.get_doc(
			{
				"doctype": "Related Todos",
				"todo_one": todo_one.id,
				"todo_two": todo_two.id,
			}
		).insert()

		frappe.form_dict.doctype = "Related Todos"
		frappe.form_dict.fields = [
			"`tabRelated Todos`.`id`",
			"`tabRelated Todos`.`todo_one`",
			"`tabRelated Todos`.`todo_two`",
			# because ToDo.show_title_as_field_link = 1
			"todo_one.description as todo_one_description",
			"todo_two.description as todo_two_description",
		]

		# Shouldn't raise pymysql.err.OperationalError: (1066, "Not unique table/alias: 'tabToDo'")
		data = get()
		self.assertEqual(len(data["values"]), 1)

	def test_select_star_expansion(self):
		count = frappe.get_list("Language", ["SUM(1)", "COUNT(*)"], as_list=1, order_by=None)[0]
		self.assertEqual(count[0], frappe.db.count("Language"))
		self.assertEqual(count[1], frappe.db.count("Language"))

	def test_ifnull_none(self):
		query = frappe.get_all("DocField", {"fieldname": None}, run=0)
		self.assertIn("''", query)
		self.assertNotIn("\\'", query)
		self.assertNotIn("ifnull", query)
		self.assertFalse(frappe.get_all("DocField", {"id": None}))
		self.assertFalse(frappe.get_all("DocField", {"parent": None}))
		self.assertNotIn("0", frappe.get_all("DocField", {"parent": None}, run=0))

	def test_ifnull_fallback_types(self):
		query = frappe.get_all("DocField", {"fieldname": ("!=", None)}, run=0)
		# Fallbacks should always be of correct type
		self.assertIn("''", query)
		self.assertNotIn("0", query)
		self.assertNotIn("ifnull", query)


class TestReportView(IntegrationTestCase):
	@run_only_if(db_type_is.MARIADB)  # TODO: postgres name casting is messed up
	def test_get_count(self):
		frappe.local.request = frappe._dict()
		frappe.local.request.method = "GET"

		# test with data check field
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocType", "show_title_field_in_link", "=", 1]],
				"fields": [],
				"distinct": "false",
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": {"show_title_field_in_link": 1},
				"distinct": "true",
			}
		)
		dict_filter_response = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertEqual(count, dict_filter_response)

		# test with child table filter
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocField", "fieldtype", "=", "Data"]],
				"fields": [],
				"distinct": "true",
			}
		)
		child_filter_response = execute_cmd("frappe.desk.reportview.get_count")
		current_value = frappe.db.sql(
			# the below query is equivalent to the one in reportview.get_count
			"select distinct count(distinct `tabDocType`.id) as total_count"
			" from `tabDocType` left join `tabDocField`"
			" on (`tabDocField`.parenttype = 'DocType' and `tabDocField`.parent = `tabDocType`.id)"
			" where `tabDocField`.`fieldtype` = 'Data'"
		)[0][0]
		self.assertEqual(child_filter_response, current_value)

		# test with limit
		limit = 2
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocType", "is_virtual", "=", 1]],
				"fields": [],
				"distinct": "false",
				"limit": limit,
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertLessEqual(count, limit)

		# test with distinct
		limit = 2
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"fields": [],
				"distinct": "true",
				"limit": limit,
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertLessEqual(count, limit)

	def test_reportview_get(self):
		user = frappe.get_doc("User", "test@example.com")
		add_child_table_to_blog_post()

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Blogger")

		make_property_setter("Blog Post", "published", "permlevel", 1, "Int")
		reset("Blog Post")
		add("Blog Post", "Website Manager", 1)
		update("Blog Post", "Website Manager", 1, "write", 1)

		frappe.set_user(user.id)

		frappe.local.request = frappe._dict()
		frappe.local.request.method = "POST"

		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Blog Post",
				"fields": ["published", "title", "`tabTest Child`.`test_field`"],
			}
		)

		# even if * is passed, fields which are not accessible should be filtered out
		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["title"])
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Blog Post",
				"fields": ["*"],
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertNotIn("published", response["keys"])

		frappe.set_user("Administrator")
		user.add_roles("Website Manager")
		frappe.set_user(user.id)

		frappe.set_user("Administrator")

		# Admin should be able to see access all fields
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Blog Post",
				"fields": ["published", "title", "`tabTest Child`.`test_field`"],
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["published", "title", "test_field"])

		# reset user roles
		user.remove_roles("Blogger", "Website Manager")
		user.add_roles(*user_roles)

	def test_reportview_get_aggregation(self):
		# test aggregation based on child table field
		frappe.local.request = frappe._dict()
		frappe.local.request.method = "POST"
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"fields": """["`tabDocField`.`label` as field_label","`tabDocField`.`id` as field_name"]""",
				"filters": "[]",
				"order_by": "_aggregate_column desc",
				"start": 0,
				"page_length": 20,
				"view": "Report",
				"with_comment_count": 0,
				"group_by": "field_label, field_name",
				"aggregate_on_field": "columns",
				"aggregate_on_doctype": "DocField",
				"aggregate_function": "sum",
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["field_label", "field_name", "_aggregate_column"])

	def test_reportview_get_permlevel_system_users(self):
		with setup_patched_blog_post(), setup_test_user(set_user=True):
			frappe.local.request = frappe._dict()
			frappe.local.request.method = "POST"
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Blog Post",
					"fields": ["published", "title", "`tabTest Child`.`test_field`"],
				}
			)

			# even if * is passed, fields which are not accessible should be filtered out
			response = execute_cmd("frappe.desk.reportview.get")
			self.assertListEqual(response["keys"], ["title"])
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Blog Post",
					"fields": ["*"],
				}
			)

			response = execute_cmd("frappe.desk.reportview.get")
			self.assertNotIn("published", response["keys"])

			# If none of the fields are accessible then result should be empty
			self.assertEqual(frappe.get_list("Blog Post", "published"), [])

	def test_reportview_get_admin(self):
		# Admin should be able to see access all fields
		with setup_patched_blog_post():
			frappe.local.request = frappe._dict()
			frappe.local.request.method = "POST"
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Blog Post",
					"fields": ["published", "title", "`tabTest Child`.`test_field`"],
				}
			)
			response = execute_cmd("frappe.desk.reportview.get")
			self.assertListEqual(response["keys"], ["published", "title", "test_field"])

	def test_db_filter_not_set(self):
		"""
		Test if the 'not set' filter always translates correctly with/without qb under the hood.
		"""
		frappe.get_doc({"doctype": "ToDo", "description": "filter test"}).insert()
		frappe.get_doc({"doctype": "ToDo", "description": "filter test", "reference_id": ""}).insert()

		# `get_all` does not use QueryBuilder while `count` does. Both should return the same result.
		# `not set` must consider empty strings and NULL values both.
		self.assertEqual(
			len(frappe.get_all("ToDo", filters={"reference_id": ["is", "not set"]})),
			frappe.db.count("ToDo", {"reference_id": ["is", "not set"]}),
		)


def add_child_table_to_blog_post():
	child_table = frappe.get_doc(
		{
			"doctype": "DocType",
			"istable": 1,
			"custom": 1,
			"id": "Test Child",
			"module": "Custom",
			"autoname": "Prompt",
			"fields": [{"fieldname": "test_field", "fieldtype": "Data", "permlevel": 1}],
		}
	)

	child_table.insert(ignore_permissions=True, ignore_if_duplicate=True)
	clear_custom_fields("Blog Post")
	add_custom_field("Blog Post", "child_table", "Table", child_table.id)


def create_event(subject="_Test Event", starts_on=None):
	"""create a test event"""

	from frappe.utils import get_datetime

	return frappe.get_doc(
		{
			"doctype": "Event",
			"subject": subject,
			"event_type": "Public",
			"starts_on": get_datetime(starts_on),
		}
	).insert(ignore_permissions=True)


def create_nested_doctype():
	if frappe.db.exists("DocType", "Nested DocType"):
		return

	frappe.get_doc(
		{
			"doctype": "DocType",
			"id": "Nested DocType",
			"module": "Custom",
			"is_tree": 1,
			"custom": 1,
			"autoname": "Prompt",
			"fields": [{"label": "Description", "fieldname": "description"}],
			"permissions": [{"role": "Blogger"}],
		}
	).insert()


def create_nested_doctype_records():
	"""
	Create a structure like:
	- Root
	        - Level 1 A
	                - Level 2 A
	                        - Level 3 A
	        - Level 1 B
	                - Level 2 B
	"""
	records = [
		{"id": "Root", "is_group": 1},
		{"id": "Level 1 A", "parent_nested_doctype": "Root", "is_group": 1},
		{"id": "Level 2 A", "parent_nested_doctype": "Level 1 A", "is_group": 1},
		{"id": "Level 3 A", "parent_nested_doctype": "Level 2 A"},
		{"id": "Level 1 B", "parent_nested_doctype": "Root", "is_group": 1},
		{"id": "Level 2 B", "parent_nested_doctype": "Level 1 B"},
	]

	for r in records:
		d = frappe.new_doc("Nested DocType")
		d.update(r)
		d.insert(ignore_permissions=True, ignore_if_duplicate=True)
