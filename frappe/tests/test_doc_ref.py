import frappe
from frappe.model.document import Document, get_doc
from frappe.tests import IntegrationTestCase
from frappe.types import DocRef

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]


class TestDocRef(IntegrationTestCase):
	def test_doc_ref_get_doc(self):
		# Test using DocRef with get_doc
		doc_ref = DocRef("User", "test@example.com")
		user = get_doc(doc_ref)

		# Assert that user is an instance of both Document and DocRef
		self.assertIsInstance(user, Document)
		self.assertIsInstance(user, DocRef)

		# Check more attributes
		self.assertEqual(user.doctype, "User")
		self.assertEqual(user.name, "test@example.com")
		self.assertEqual(user.email, "test@example.com")
		self.assertEqual(user.first_name, "_Test")

	def test_doc_ref_in_query(self):
		# Test using DocRef in a database query
		user = frappe.get_doc("User", "test@example.com")

		# Assert that user is an instance of both Document and DocRef
		self.assertIsInstance(user, Document)
		self.assertIsInstance(user, DocRef)

		# Create a test document that references the user
		test_doc = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Test ToDo",
				"reference_type": "User",
				"reference_id": user,  # This should work with DocRef
			}
		).insert()

		# Getter using the DocRef
		result = frappe.db.get_value("ToDo", {"reference_id": user}, ["name", "description"])
		self.assertEqual(result[0], test_doc.name)
		self.assertEqual(result[1], "Test ToDo")
		# Setter using Document as DocRef
		frappe.db.set_value("ToDo", test_doc, "description", "Revised Test ToDo")
		test_doc.reload()
		self.assertEqual(test_doc.description, "Revised Test ToDo")

	def test_doc_ref_value_representation(self):
		# Test the value representation of DocRef
		doc_ref = DocRef("User", "test@example.com")
		self.assertEqual(doc_ref.__value__(), "test@example.com")

	def test_doc_ref_attributes(self):
		# Test DocRef attributes
		doc_ref = DocRef("User", "test@example.com")
		self.assertEqual(doc_ref.doctype, "User")
		self.assertEqual(doc_ref.name, "test@example.com")
