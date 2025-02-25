# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_export.exporter import DataExporter
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestDataExport(UnitTestCase):
	"""
	Unit tests for DataExport.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestDataExporter(IntegrationTestCase):
	def setUp(self):
		self.doctype_id = "Test DocType for Export Tool"
		self.doc_id = "Test Data for Export Tool"
		self.create_doctype_if_not_exists(doctype_id=self.doctype_id)
		self.create_test_data()

    def create_doctype_if_not_exists(self, doctype_id, force=False):
        """
        Helper Function for setting up doctypes
        """
        if force:
            frappe.delete_doc_if_exists("DocType", doctype_id)
            frappe.delete_doc_if_exists("DocType", "Child 1 of " + doctype_id)

        if frappe.db.exists("DocType", doctype_id):
            return

        # Child Table 1
        table_1_id = "Child 1 of " + doctype_id
        frappe.get_doc(
            {
                "doctype": "DocType",
                "id": table_1_id,
                "module": "Custom",
                "custom": 1,
                "istable": 1,
                "fields": [
                    {
                        "label": "Child Title",
                        "fieldname": "child_title",
                        "reqd": 1,
                        "fieldtype": "Data",
                    },
                    {
                        "label": "Child Number",
                        "fieldname": "child_number",
                        "fieldtype": "Int",
                    },
                ],
            }
        ).insert()

        # Main Table
        frappe.get_doc(
            {
                "doctype": "DocType",
                "id": doctype_id,
                "module": "Custom",
                "custom": 1,
                "autoid": "field:title",
                "fields": [
                    {
                        "label": "Title",
                        "fieldname": "title",
                        "reqd": 1,
                        "fieldtype": "Data",
                    },
                    {"label": "Number", "fieldname": "number", "fieldtype": "Int"},
                    {
                        "label": "Table Field 1",
                        "fieldname": "table_field_1",
                        "fieldtype": "Table",
                        "options": table_1_id,
                    },
                ],
                "permissions": [{"role": "System Manager"}],
            }
        ).insert()

    def create_test_data(self, force=False):
        """
        Helper Function creating test data
        """
        if force:
            frappe.delete_doc(self.doctype_id, self.doc_id)

        if not frappe.db.exists(self.doctype_id, self.doc_id):
            self.doc = frappe.get_doc(
                doctype=self.doctype_id,
                title=self.doc_id,
                number="100",
                table_field_1=[
                    {"child_title": "Child Title 1", "child_number": "50"},
                    {"child_title": "Child Title 2", "child_number": "51"},
                ],
            ).insert()
        else:
            self.doc = frappe.get_doc(self.doctype_id, self.doc_id)

    def test_export_content(self):
        exp = DataExporter(doctype=self.doctype_id, file_type="CSV")
        exp.build_response()

        self.assertEqual(frappe.response["type"], "csv")
        self.assertEqual(frappe.response["doctype"], self.doctype_id)
        self.assertTrue(frappe.response["result"])
        self.assertRegex(frappe.response["result"], r"Child Title 1.*?,50")
        self.assertRegex(frappe.response["result"], r"Child Title 2.*?,51")

    def test_export_type(self):
        for type in ["csv", "Excel"]:
            with self.subTest(type=type):
                exp = DataExporter(doctype=self.doctype_id, file_type=type)
                exp.build_response()

                self.assertEqual(frappe.response["doctype"], self.doctype_id)
                self.assertTrue(frappe.response["result"])

                if type == "csv":
                    self.assertEqual(frappe.response["type"], "csv")
                elif type == "Excel":
                    self.assertEqual(frappe.response["type"], "binary")
                    self.assertEqual(
                        frappe.response["filename"], self.doctype_id + ".xlsx"
                    )  # 'Test DocType for Export Tool.xlsx')
                    self.assertTrue(frappe.response["filecontent"])

    def tearDown(self):
        pass
