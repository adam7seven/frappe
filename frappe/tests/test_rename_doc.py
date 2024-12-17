# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from random import choice, sample
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.exceptions import DoesNotExistError
from frappe.model.base_document import get_controller
from frappe.model.reid_doc import bulk_reid, update_document_title
from frappe.modules.utils import get_doc_path
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now


@contextmanager
def patch_db(endpoints: list[str] | None = None):
    patched_endpoints = []

    for point in endpoints:
        x = patch(f"frappe.db.{point}", new=lambda: True)
        patched_endpoints.append(x)

    savepoint = "SAVEPOINT_for_test_bulk_reid"
    frappe.db.savepoint(save_point=savepoint)
    try:
        for x in patched_endpoints:
            x.start()
        yield
    finally:
        for x in patched_endpoints:
            x.stop()
        frappe.db.rollback(save_point=savepoint)


class TestReidDoc(FrappeTestCase):
    @classmethod
    def setUpClass(self):
        """Setting Up data for the tests defined under TestReidDoc"""
        # set developer_mode to reid doc controllers
        super().setUpClass()
        self._original_developer_flag = frappe.conf.developer_mode
        frappe.conf.developer_mode = 1

        # data generation: for base and merge tests
        self.available_documents = []
        self.test_doctype = "ToDo"

        for num in range(1, 5):
            doc = frappe.get_doc(
                {
                    "doctype": self.test_doctype,
                    "date": add_to_date(now(), days=num),
                    "description": f"this is todo #{num}",
                }
            ).insert()
            self.available_documents.append(doc.id)

        #  data generation: for controllers tests
        self.doctype = frappe._dict(
            {
                "old": "Test Reid Document Old",
                "new": "Test Reid Document New",
            }
        )

        frappe.get_doc(
            {
                "doctype": "DocType",
                "module": "Custom",
                "id": self.doctype.old,
                "custom": 0,
                "fields": [
                    {
                        "label": "Some Field",
                        "fieldname": "some_fieldname",
                        "fieldtype": "Data",
                    }
                ],
                "permissions": [{"role": "System Manager", "read": 1}],
            }
        ).insert()

    @classmethod
    def tearDownClass(self):
        """Deleting data generated for the tests defined under TestReidDoc"""
        # delete_doc doesnt drop tables
        # this is done to bypass inconsistencies in the db
        frappe.delete_doc_if_exists("DocType", "Reidd Doc")
        frappe.db.sql_ddl("drop table if exists `tabReidd Doc`")

        # delete the documents created
        for docid in self.available_documents:
            frappe.delete_doc(self.test_doctype, docid)

        for dt in self.doctype.values():
            if frappe.db.exists("DocType", dt):
                frappe.delete_doc("DocType", dt)
                frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{dt}`")

        # reset original value of developer_mode conf
        frappe.conf.developer_mode = self._original_developer_flag

    def setUp(self):
        frappe.flags.link_fields = {}
        if self._testMethodName == "test_doc_reid_method":
            self.property_setter = frappe.get_doc(
                {
                    "doctype": "Property Setter",
                    "doctype_or_field": "DocType",
                    "doc_type": self.test_doctype,
                    "property": "allow_reid",
                    "property_type": "Check",
                    "value": "1",
                }
            ).insert()

        super().setUp()

    def tearDown(self) -> None:
        if self._testMethodName == "test_doc_reid_method":
            self.property_setter.delete()
        return super().tearDown()

    def test_reid_doc(self):
        """Reid an existing document via frappe.reid_doc"""
        old_id = choice(self.available_documents)
        new_id = old_id + ".new"
        self.assertEqual(
            new_id,
            frappe.reid_doc(self.test_doctype, old_id, new_id, force=True),
        )
        self.available_documents.remove(old_id)
        self.available_documents.append(new_id)

    def test_merging_docs(self):
        """Merge two documents via frappe.reid_doc"""
        first_todo, second_todo = sample(self.available_documents, 2)

        second_todo_doc = frappe.get_doc(self.test_doctype, second_todo)
        second_todo_doc.priority = "High"
        second_todo_doc.save()

        merged_todo = frappe.reid_doc(
            self.test_doctype, first_todo, second_todo, merge=True, force=True
        )
        merged_todo_doc = frappe.get_doc(self.test_doctype, merged_todo)
        self.available_documents.remove(first_todo)

        with self.assertRaises(DoesNotExistError):
            frappe.get_doc(self.test_doctype, first_todo)

        self.assertEqual(merged_todo_doc.priority, second_todo_doc.priority)

    def test_reid_controllers(self):
        """Reid doctypes with controller code paths"""
        # check if module exists exists;
        # if custom, get_controller will return Document class
        # if not custom, a different class will be returned
        self.assertNotEqual(
            get_controller(self.doctype.old), frappe.model.document.Document
        )

        old_doctype_path = get_doc_path("Custom", "DocType", self.doctype.old)

        # reid doc via wrapper API accessible via /desk
        frappe.reid_doc("DocType", self.doctype.old, self.doctype.new)

        # check if database and controllers are updated
        self.assertTrue(frappe.db.exists("DocType", self.doctype.new))
        self.assertFalse(frappe.db.exists("DocType", self.doctype.old))
        self.assertFalse(os.path.exists(old_doctype_path))

    def test_reid_doctype(self):
        """Reid DocType via frappe.reid_doc"""
        from frappe.core.doctype.doctype.test_doctype import new_doctype

        if not frappe.db.exists("DocType", "Reid This"):
            new_doctype(
                "Reid This",
                fields=[
                    {
                        "label": "Linked To",
                        "fieldname": "linked_to_doctype",
                        "fieldtype": "Link",
                        "options": "DocType",
                        "unique": 0,
                    }
                ],
            ).insert()

        to_reid_record = frappe.get_doc(
            {"doctype": "Reid This", "linked_to_doctype": "Reid This"}
        ).insert()

        # Reid doctype
        self.assertEqual(
            "Reidd Doc",
            frappe.reid_doc("DocType", "Reid This", "Reidd Doc", force=True),
        )

        # Test if Doctype value has changed in Link field
        linked_to_doctype = frappe.db.get_value(
            "Reidd Doc", to_reid_record.id, "linked_to_doctype"
        )
        self.assertEqual(linked_to_doctype, "Reidd Doc")

        # Test if there are conflicts between a record and a DocType
        # having the same id
        old_id = to_reid_record.id
        new_id = "ToDo"
        self.assertEqual(
            new_id, frappe.reid_doc("Reidd Doc", old_id, new_id, force=True)
        )

    def test_update_document_title_api(self):
        test_doctype = "Module Def"
        test_doc = frappe.get_doc(
            {
                "doctype": test_doctype,
                "module_name": f"Test-test_update_document_title_api-{frappe.generate_hash()}",
                "custom": True,
            }
        )
        test_doc.insert(ignore_mandatory=True)

        dt = test_doc.doctype
        dn = test_doc.id
        new_id = f"{dn}-new"

        # pass invalid types to API
        with self.assertRaises(TypeError):
            update_document_title(doctype=dt, docid=dn, title={}, id={"hack": "this"})

        doc_before = frappe.get_doc(test_doctype, dn)
        return_value = update_document_title(doctype=dt, docid=dn, new_id=new_id)
        doc_after = frappe.get_doc(test_doctype, return_value)

        doc_before_dict = doc_before.as_dict(no_nulls=True, no_default_fields=True)
        doc_after_dict = doc_after.as_dict(no_nulls=True, no_default_fields=True)
        doc_before_dict.pop("module_name")
        doc_after_dict.pop("module_name")

        self.assertEqual(new_id, return_value)
        self.assertDictEqual(doc_before_dict, doc_after_dict)
        self.assertEqual(doc_after.module_name, return_value)

        test_doc.delete()

    def test_bulk_reid(self):
        input_data = [[x, f"{x}-new"] for x in self.available_documents]

        with patch_db(["commit", "rollback"]), patch("frappe.enqueue") as enqueue:
            message_log = bulk_reid(self.test_doctype, input_data, via_console=False)
            self.assertEqual(len(message_log), len(self.available_documents))
            self.assertIsInstance(message_log, list)
            enqueue.assert_called_with(
                "frappe.utils.global_search.rebuild_for_doctype",
                doctype=self.test_doctype,
            )

    def test_doc_reid_method(self):
        id = choice(self.available_documents)
        new_id = f"{id}-{frappe.generate_hash(length=4)}"
        doc = frappe.get_doc(self.test_doctype, id)
        doc.reid(new_id, merge=frappe.db.exists(self.test_doctype, new_id))
        self.assertEqual(doc.id, new_id)
        self.available_documents.append(new_id)
        self.available_documents.remove(id)

    def test_parenttype(self):
        child = new_doctype(istable=1).insert()
        table_field = {
            "label": "Test Table",
            "fieldname": "test_table",
            "fieldtype": "Table",
            "options": child.id,
        }

        parent_a = new_doctype(
            fields=[table_field], allow_reid=1, autoid="Prompt"
        ).insert()
        parent_b = new_doctype(
            fields=[table_field], allow_reid=1, autoid="Prompt"
        ).insert()

        parent_a_instance = frappe.get_doc(
            doctype=parent_a.id, test_table=[{"some_fieldname": "x"}], id="XYZ"
        ).insert()

        parent_b_instance = frappe.get_doc(
            doctype=parent_b.id, test_table=[{"some_fieldname": "x"}], id="XYZ"
        ).insert()

        parent_b_instance.reid("ABC")
        parent_a_instance.reload()

        self.assertEqual(len(parent_a_instance.test_table), 1)
        self.assertEqual(len(parent_b_instance.test_table), 1)
