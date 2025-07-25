# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import hashlib

import frappe
from frappe.tests import IntegrationTestCase


class TestTransactionLog(IntegrationTestCase):
	def test_validate_chaining(self):
		frappe.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_id": "Test Document 1",
				"data": "first_data",
			}
		).insert(ignore_permissions=True)

		second_log = frappe.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_id": "Test Document 2",
				"data": "second_data",
			}
		).insert(ignore_permissions=True)

		third_log = frappe.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_id": "Test Document 3",
				"data": "third_data",
			}
		).insert(ignore_permissions=True)

		sha = hashlib.sha256()
		sha.update(
			frappe.safe_encode(str(third_log.transaction_hash))
			+ frappe.safe_encode(str(second_log.chaining_hash))
		)

		self.assertEqual(sha.hexdigest(), third_log.chaining_hash)
