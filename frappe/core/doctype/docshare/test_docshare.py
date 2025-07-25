# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.share
from frappe.automation.doctype.auto_repeat.test_auto_repeat import create_submittable_doctype
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]


class TestDocShare(IntegrationTestCase):
	def setUp(self):
		self.user = "test@example.com"
		self.event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test share event",
				"starts_on": "2015-01-01 10:00:00",
				"event_type": "Private",
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.event.delete()

	def test_add(self):
		# user not shared
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", self.user))
		frappe.share.add("Event", self.event.id, self.user)
		self.assertTrue(self.event.id in frappe.share.get_shared("Event", self.user))

	def test_doc_permission(self):
		frappe.set_user(self.user)

		self.assertFalse(self.event.has_permission())

		frappe.set_user("Administrator")
		frappe.share.add("Event", self.event.id, self.user)

		frappe.set_user(self.user)
		# PERF: All share permission check should happen with maximum 1 query.
		with self.assertRowsRead(1):
			self.assertTrue(self.event.has_permission())

		second_event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test share event 2",
				"starts_on": "2015-01-01 10:00:00",
				"event_type": "Private",
			}
		).insert()
		frappe.share.add("Event", second_event.id, self.user)
		with self.assertRowsRead(1):
			self.assertTrue(self.event.has_permission())

	def test_list_permission(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Web Page")

		frappe.set_user("Administrator")
		doc = frappe.new_doc("Web Page")
		doc.update({"title": "test document for docshare permissions"})
		doc.insert()
		frappe.share.add("Web Page", doc.id, self.user)

		frappe.set_user(self.user)
		self.assertEqual(len(frappe.get_list("Web Page")), 1)

		doc.delete(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Web Page")

	def test_share_permission(self):
		frappe.share.add("Event", self.event.id, self.user, write=1, share=1)

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

		# test cascade
		self.assertTrue(self.event.has_permission("read"))
		self.assertTrue(self.event.has_permission("write"))

	def test_set_permission(self):
		frappe.share.add("Event", self.event.id, self.user)

		frappe.set_user(self.user)
		self.assertFalse(self.event.has_permission("share"))

		frappe.set_user("Administrator")
		frappe.share.set_permission("Event", self.event.id, self.user, "share")

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

	def test_permission_to_share(self):
		frappe.set_user(self.user)
		self.assertRaises(frappe.PermissionError, frappe.share.add, "Event", self.event.id, self.user)

		frappe.set_user("Administrator")
		frappe.share.add("Event", self.event.id, self.user, write=1, share=1)

		# test not raises
		frappe.set_user(self.user)
		frappe.share.add("Event", self.event.id, "test1@example.com", write=1, share=1)

	def test_remove_share(self):
		frappe.share.add("Event", self.event.id, self.user, write=1, share=1)

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

		frappe.set_user("Administrator")
		frappe.share.remove("Event", self.event.id, self.user)

		frappe.set_user(self.user)
		self.assertFalse(self.event.has_permission("share"))

	def test_share_with_everyone(self):
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", self.user))

		frappe.share.set_permission("Event", self.event.id, None, "read", everyone=1)
		self.assertTrue(self.event.id in frappe.share.get_shared("Event", self.user))
		self.assertTrue(self.event.id in frappe.share.get_shared("Event", "test1@example.com"))
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", "Guest"))

		frappe.share.set_permission("Event", self.event.id, None, "read", value=0, everyone=1)
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", self.user))
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", "test1@example.com"))
		self.assertTrue(self.event.id not in frappe.share.get_shared("Event", "Guest"))

	def test_share_with_submit_perm(self):
		doctype = "Test DocShare with Submit"
		create_submittable_doctype(doctype, submit_perms=0)

		submittable_doc = frappe.get_doc(doctype=doctype, test="test docshare with submit").insert()

		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission(doctype, "submit", user=self.user))

		frappe.set_user("Administrator")
		frappe.share.add(doctype, submittable_doc.id, self.user, submit=1)

		frappe.set_user(self.user)
		self.assertTrue(frappe.has_permission(doctype, "submit", doc=submittable_doc.id, user=self.user))

		# test cascade
		self.assertTrue(frappe.has_permission(doctype, "read", doc=submittable_doc.id, user=self.user))
		self.assertTrue(frappe.has_permission(doctype, "write", doc=submittable_doc.id, user=self.user))

		frappe.share.remove(doctype, submittable_doc.id, self.user)

	def test_share_int_pk(self):
		test_doc = frappe.new_doc("Console Log")

		test_doc.insert()
		frappe.share.add("Console Log", test_doc.id, self.user)

		frappe.set_user(self.user)
		self.assertIn(str(test_doc.id), [str(id) for id in frappe.get_list("Console Log", pluck="id")])

		test_doc.reload()
		self.assertTrue(test_doc.has_permission("read"))

	@IntegrationTestCase.change_settings("System Settings", {"disable_document_sharing": 1})
	def test_share_disabled_add(self):
		"Test if user loses share access on disabling share globally."
		frappe.share.add("Event", self.event.id, self.user, share=1)  # Share as admin
		frappe.set_user(self.user)

		# User does not have share access although given to them
		self.assertFalse(self.event.has_permission("share"))
		self.assertRaises(
			frappe.PermissionError, frappe.share.add, "Event", self.event.id, "test1@example.com"
		)

	@IntegrationTestCase.change_settings("System Settings", {"disable_document_sharing": 1})
	def test_share_disabled_add_with_ignore_permissions(self):
		frappe.share.add("Event", self.event.id, self.user, share=1)
		frappe.set_user(self.user)

		# User does not have share access although given to them
		self.assertFalse(self.event.has_permission("share"))

		# Test if behaviour is consistent for developer overrides
		frappe.share.add_docshare(
			"Event", self.event.id, "test1@example.com", flags={"ignore_share_permission": True}
		)

	@IntegrationTestCase.change_settings("System Settings", {"disable_document_sharing": 1})
	def test_share_disabled_set_permission(self):
		frappe.share.add("Event", self.event.id, self.user, share=1)
		frappe.set_user(self.user)

		# User does not have share access although given to them
		self.assertFalse(self.event.has_permission("share"))
		self.assertRaises(
			frappe.PermissionError,
			frappe.share.set_permission,
			"Event",
			self.event.id,
			"test1@example.com",
			"read",
		)

	@IntegrationTestCase.change_settings("System Settings", {"disable_document_sharing": 1})
	def test_share_disabled_assign_to(self):
		"""
		Assigning a document to a user without access must not share the document,
		if sharing disabled.
		"""
		from frappe.desk.form.assign_to import add

		frappe.share.add("Event", self.event.id, self.user, share=1)
		frappe.set_user(self.user)

		self.assertRaises(
			frappe.ValidationError,
			add,
			{"doctype": "Event", "id": self.event.id, "assign_to": ["test1@example.com"]},
		)
