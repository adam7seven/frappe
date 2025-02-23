import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests.utils import FrappeTestCase


class TestRating(FrappeTestCase):
    def setUp(self):
        doc = new_doctype(
            fields=[
                {
                    "fieldname": "rating",
                    "fieldtype": "Rating",
                    "label": "rating",
                    "reqd": 1,  # mandatory
                },
            ],
        )
        doc.insert()
        self.doctype_id = doc.id

    def test_negative_rating(self):
        doc = frappe.new_doc(doctype=self.doctype_id, rating=-1)
        doc.insert()
        self.assertEqual(doc.rating, 0)

    def test_positive_rating(self):
        doc = frappe.new_doc(doctype=self.doctype_id, rating=5)
        doc.insert()
        self.assertEqual(doc.rating, 1)
