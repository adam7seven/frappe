# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.core.doctype.data_import.test_importer import create_doctype_if_not_exists
from frappe.tests import IntegrationTestCase, UnitTestCase

doctype_id = "DocType for Export"


class UnitTestDataImport(UnitTestCase):
    """
    Unit tests for DataImport.
    Use this class for testing individual functions and methods.
    """

    pass


class TestExporter(IntegrationTestCase):
    def setUp(self):
        create_doctype_if_not_exists(doctype_id)

    def test_exports_specified_fields(self):
        if not frappe.db.exists(doctype_id, "Test"):
            doc = frappe.get_doc(
                doctype=doctype_id,
                title="Test",
                description="Test Description",
                table_field_1=[
                    {
                        "child_title": "Child Title 1",
                        "child_description": "Child Description 1",
                    },
                    {
                        "child_title": "Child Title 2",
                        "child_description": "Child Description 2",
                    },
                ],
                table_field_2=[
                    {
                        "child_2_title": "Child Title 1",
                        "child_2_description": "Child Description 1",
                    },
                ],
                table_field_1_again=[
                    {
                        "child_title": "Child Title 1 Again",
                        "child_description": "Child Description 1 Again",
                    },
                ],
            ).insert()
        else:
            doc = frappe.get_doc(doctype_id, "Test")

        e = Exporter(
            doctype_id,
            export_fields={
                doctype_id: ["title", "description", "number", "another_number"],
                "table_field_1": ["id", "child_title", "child_description"],
                "table_field_2": ["child_2_date", "child_2_number"],
                "table_field_1_again": [
                    "child_title",
                    "child_date",
                    "child_number",
                    "child_another_number",
                ],
            },
            export_data=True,
        )
        csv_array = e.get_csv_array()
        header_row = csv_array[0]

        self.assertEqual(
            header_row,
            [
                "Title",
                "Description",
                "Number",
                "another_number",
                "ID (Table Field 1)",
                "Child Title (Table Field 1)",
                "Child Description (Table Field 1)",
                "Child 2 Date (Table Field 2)",
                "Child 2 Number (Table Field 2)",
                "Child Title (Table Field 1 Again)",
                "Child Date (Table Field 1 Again)",
                "Child Number (Table Field 1 Again)",
                "table_field_1_again.child_another_number",
            ],
        )

        table_field_1_row_1_id = doc.table_field_1[0].id
        table_field_1_row_2_id = doc.table_field_1[1].id
        # fmt: off
        self.assertEqual(
            csv_array[1],
            ["Test", "Test Description", 0, 0, table_field_1_row_1_id, "Child Title 1", "Child Description 1", None, 0, "Child Title 1 Again", None, 0, 0]
        )
        self.assertEqual(
            csv_array[2],
            ["", "", "", "", table_field_1_row_2_id, "Child Title 2", "Child Description 2", "", "", "", "", "", ""],
        )
        # fmt: on
        self.assertEqual(len(csv_array), 3)

    def test_export_csv_response(self):
        e = Exporter(
            doctype_id,
            export_fields={doctype_id: ["title", "description"]},
            export_data=True,
            file_type="CSV",
        )
        e.build_response()

        self.assertTrue(frappe.response["result"])
        self.assertEqual(frappe.response["doctype"], doctype_id)
        self.assertEqual(frappe.response["type"], "csv")
