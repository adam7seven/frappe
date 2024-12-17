import itertools

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.query_builder import Field
from frappe.query_builder.functions import Abs, Count, Ifnull, Max, Now, Timestamp
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.tests.utils import FrappeTestCase
from frappe.utils.nestedset import get_ancestors_of, get_descendants_of


def create_tree_docs():
    records = [
        {
            "some_fieldname": "Root Node",
            "parent_test_tree_doctype": None,
            "is_group": 1,
        },
        {
            "some_fieldname": "Parent 1",
            "parent_test_tree_doctype": "Root Node",
            "is_group": 1,
        },
        {
            "some_fieldname": "Parent 2",
            "parent_test_tree_doctype": "Root Node",
            "is_group": 1,
        },
        {
            "some_fieldname": "Child 1",
            "parent_test_tree_doctype": "Parent 1",
            "is_group": 0,
        },
        {
            "some_fieldname": "Child 2",
            "parent_test_tree_doctype": "Parent 1",
            "is_group": 0,
        },
        {
            "some_fieldname": "Child 3",
            "parent_test_tree_doctype": "Parent 2",
            "is_group": 0,
        },
    ]

    tree_doctype = new_doctype(
        "Test Tree DocType", is_tree=True, autoid="field:some_fieldname"
    )
    tree_doctype.insert()

    for record in records:
        d = frappe.new_doc("Test Tree DocType")
        d.update(record)
        d.insert()


class TestQuery(FrappeTestCase):
    @run_only_if(db_type_is.MARIADB)
    def test_multiple_tables_in_filters(self):
        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                ["*"],
                [
                    ["DocField", "id", "like", "f%"],
                    ["DocType", "parent", "=", "something"],
                ],
            ).get_sql(),
            "SELECT `tabDocType`.* FROM `tabDocType` LEFT JOIN `tabDocField` ON `tabDocField`.`parent`=`tabDocType`.`id` AND `tabDocField`.`parenttype`='DocType' WHERE `tabDocField`.`id` LIKE 'f%' AND `tabDocType`.`parent`='something'",
        )

    @run_only_if(db_type_is.MARIADB)
    def test_string_fields(self):
        self.assertEqual(
            frappe.qb.get_query(
                "User", fields="id, email", filters={"id": "Administrator"}
            ).get_sql(),
            frappe.qb.from_("User")
            .select(Field("id"), Field("email"))
            .where(Field("id") == "Administrator")
            .get_sql(),
        )
        self.assertEqual(
            frappe.qb.get_query(
                "User", fields=["`id`, `email`"], filters={"id": "Administrator"}
            ).get_sql(),
            frappe.qb.from_("User")
            .select(Field("id"), Field("email"))
            .where(Field("id") == "Administrator")
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields=["`tabUser`.`id`", "`tabUser`.`email`"],
                filters={"id": "Administrator"},
            ).run(),
            frappe.qb.from_("User")
            .select(Field("id"), Field("email"))
            .where(Field("id") == "Administrator")
            .run(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields=["`tabUser`.`id` as owner", "`tabUser`.`email`"],
                filters={"id": "Administrator"},
            ).run(as_dict=1),
            frappe.qb.from_("User")
            .select(Field("id").as_("owner"), Field("email"))
            .where(Field("id") == "Administrator")
            .run(as_dict=1),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields=["`tabUser`.`id`, Count(`id`) as count"],
                filters={"id": "Administrator"},
            ).run(),
            frappe.qb.from_("User")
            .select(Field("id"), Count("id").as_("count"))
            .where(Field("id") == "Administrator")
            .run(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields=["`tabUser`.`id`, Count(`id`) as `count`"],
                filters={"id": "Administrator"},
            ).run(),
            frappe.qb.from_("User")
            .select(Field("id"), Count("id").as_("count"))
            .where(Field("id") == "Administrator")
            .run(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields="`tabUser`.`id`, Count(`id`) as `count`",
                filters={"id": "Administrator"},
            ).run(),
            frappe.qb.from_("User")
            .select(Field("id"), Count("id").as_("count"))
            .where(Field("id") == "Administrator")
            .run(),
        )

    def test_functions_fields(self):
        self.assertEqual(
            frappe.qb.get_query("User", fields="Count(id)", filters={}).get_sql(),
            frappe.qb.from_("User").select(Count(Field("id"))).get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User", fields=["Count(id)", "Max(id)"], filters={}
            ).get_sql(),
            frappe.qb.from_("User")
            .select(Count(Field("id")), Max(Field("id")))
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User", fields=["abs(id-email)", "Count(id)"], filters={}
            ).get_sql(),
            frappe.qb.from_("User")
            .select(Abs(Field("id") - Field("email")), Count(Field("id")))
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query("User", fields=[Count("*")], filters={}).get_sql(),
            frappe.qb.from_("User").select(Count("*")).get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User", fields="timestamp(creation, modified)", filters={}
            ).get_sql(),
            frappe.qb.from_("User")
            .select(Timestamp(Field("creation"), Field("modified")))
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "User",
                fields="Count(id) as count, Max(email) as max_email",
                filters={},
            ).get_sql(),
            frappe.qb.from_("User")
            .select(
                Count(Field("id")).as_("count"), Max(Field("email")).as_("max_email")
            )
            .get_sql(),
        )

    def test_qb_fields(self):
        user_doctype = frappe.qb.DocType("User")
        self.assertEqual(
            frappe.qb.get_query(
                user_doctype, fields=[user_doctype.id, user_doctype.email], filters={}
            ).get_sql(),
            frappe.qb.from_(user_doctype)
            .select(user_doctype.id, user_doctype.email)
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                user_doctype, fields=user_doctype.email, filters={}
            ).get_sql(),
            frappe.qb.from_(user_doctype).select(user_doctype.email).get_sql(),
        )

    def test_aliasing(self):
        user_doctype = frappe.qb.DocType("User")
        self.assertEqual(
            frappe.qb.get_query(
                "User", fields=["id as owner", "email as id"], filters={}
            ).get_sql(),
            frappe.qb.from_(user_doctype)
            .select(user_doctype.id.as_("owner"), user_doctype.email.as_("id"))
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                user_doctype, fields="id as owner, email as id", filters={}
            ).get_sql(),
            frappe.qb.from_(user_doctype)
            .select(user_doctype.id.as_("owner"), user_doctype.email.as_("id"))
            .get_sql(),
        )

        self.assertEqual(
            frappe.qb.get_query(
                user_doctype, fields=["Count(id) as count", "email as id"], filters={}
            ).get_sql(),
            frappe.qb.from_(user_doctype)
            .select(Count(Field("id")).as_("count"), user_doctype.email.as_("id"))
            .get_sql(),
        )

    @run_only_if(db_type_is.MARIADB)
    def test_filters(self):
        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                fields=["id"],
                filters={"module.app_name": "frappe"},
            ).get_sql(),
            "SELECT `tabDocType`.`id` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`id`=`tabDocType`.`module` WHERE `tabModule Def`.`app_name`='frappe'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                fields=["id"],
                filters={"module.app_name": ("like", "frap%")},
            ).get_sql(),
            "SELECT `tabDocType`.`id` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`id`=`tabDocType`.`module` WHERE `tabModule Def`.`app_name` LIKE 'frap%'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                fields=["id"],
                filters={"permissions.role": "System Manager"},
            ).get_sql(),
            "SELECT `tabDocType`.`id` FROM `tabDocType` LEFT JOIN `tabDocPerm` ON `tabDocPerm`.`parent`=`tabDocType`.`id` AND `tabDocPerm`.`parenttype`='DocType' WHERE `tabDocPerm`.`role`='System Manager'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertRaisesRegex(
            frappe.ValidationError,
            "Invalid filter",
            lambda: frappe.qb.get_query(
                "DocType",
                fields=["id"],
                filters={"permissions.role": "System Manager"},
                validate_filters=True,
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                fields=["module"],
                filters="",
            ).get_sql(),
            "SELECT `module` FROM `tabDocType` WHERE `id`=''".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                filters=["ToDo", "Note"],
            ).get_sql(),
            "SELECT `id` FROM `tabDocType` WHERE `id` IN ('ToDo','Note')".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                filters={"id": ("in", [])},
            ).get_sql(),
            "SELECT `id` FROM `tabDocType` WHERE `id` IN ('')".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                filters=[1, 2, 3],
            ).get_sql(),
            "SELECT `id` FROM `tabDocType` WHERE `id` IN (1,2,3)".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                filters=[],
            ).get_sql(),
            "SELECT `id` FROM `tabDocType`".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

    def test_implicit_join_query(self):
        self.maxDiff = None

        self.assertEqual(
            frappe.qb.get_query(
                "Note",
                filters={"id": "Test Note Title"},
                fields=["id", "`tabNote Seen By`.`user` as seen_by"],
            ).get_sql(),
            "SELECT `tabNote`.`id`,`tabNote Seen By`.`user` `seen_by` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`id` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`id`='Test Note Title'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "Note",
                filters={"id": "Test Note Title"},
                fields=[
                    "id",
                    "`tabNote Seen By`.`user` as seen_by",
                    "`tabNote Seen By`.`idx` as idx",
                ],
            ).get_sql(),
            "SELECT `tabNote`.`id`,`tabNote Seen By`.`user` `seen_by`,`tabNote Seen By`.`idx` `idx` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`id` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`id`='Test Note Title'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "Note",
                filters={"id": "Test Note Title"},
                fields=[
                    "id",
                    "seen_by.user as seen_by",
                    "`tabNote Seen By`.`idx` as idx",
                ],
            ).get_sql(),
            "SELECT `tabNote`.`id`,`tabNote Seen By`.`user` `seen_by`,`tabNote Seen By`.`idx` `idx` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`id` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`id`='Test Note Title'".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

        self.assertEqual(
            frappe.qb.get_query(
                "DocType",
                fields=["id", "module.app_name as app_name"],
            ).get_sql(),
            "SELECT `tabDocType`.`id`,`tabModule Def`.`app_name` `app_name` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`id`=`tabDocType`.`module`".replace(
                "`", '"' if frappe.db.db_type == "postgres" else "`"
            ),
        )

    @run_only_if(db_type_is.MARIADB)
    def test_comment_stripping(self):
        self.assertNotIn(
            "email",
            frappe.qb.get_query("User", fields=["id", "#email"], filters={}).get_sql(),
        )

    def test_nestedset(self):
        frappe.db.sql("delete from `tabDocType` where `id` = 'Test Tree DocType'")
        frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")
        create_tree_docs()
        descendants_result = frappe.qb.get_query(
            "Test Tree DocType",
            fields=["id"],
            filters={"id": ("descendants of", "Parent 1")},
            order_by="modified desc",
        ).run(as_list=1)

        # Format decendants result
        descendants_result = list(itertools.chain.from_iterable(descendants_result))
        self.assertListEqual(
            descendants_result, get_descendants_of("Test Tree DocType", "Parent 1")
        )

        ancestors_result = frappe.qb.get_query(
            "Test Tree DocType",
            fields=["id"],
            filters={"id": ("ancestors of", "Child 2")},
            order_by="modified desc",
        ).run(as_list=1)

        # Format ancestors result
        ancestors_result = list(itertools.chain.from_iterable(ancestors_result))
        self.assertListEqual(
            ancestors_result, get_ancestors_of("Test Tree DocType", "Child 2")
        )

        not_descendants_result = frappe.qb.get_query(
            "Test Tree DocType",
            fields=["id"],
            filters={"id": ("not descendants of", "Parent 1")},
            order_by="modified desc",
        ).run(as_dict=1)

        self.assertListEqual(
            not_descendants_result,
            frappe.db.get_all(
                "Test Tree DocType",
                fields=["id"],
                filters={"id": ("not descendants of", "Parent 1")},
            ),
        )

        not_ancestors_result = frappe.qb.get_query(
            "Test Tree DocType",
            fields=["id"],
            filters={"id": ("not ancestors of", "Child 2")},
            order_by="modified desc",
        ).run(as_dict=1)

        self.assertListEqual(
            not_ancestors_result,
            frappe.db.get_all(
                "Test Tree DocType",
                fields=["id"],
                filters={"id": ("not ancestors of", "Child 2")},
            ),
        )

        frappe.db.sql("delete from `tabDocType` where `id` = 'Test Tree DocType'")
        frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")

    def test_child_field_syntax(self):
        note1 = frappe.get_doc(
            doctype="Note", title="Note 1", seen_by=[{"user": "Administrator"}]
        ).insert()
        note2 = frappe.get_doc(
            doctype="Note",
            title="Note 2",
            seen_by=[{"user": "Administrator"}, {"user": "Guest"}],
        ).insert()

        result = frappe.qb.get_query(
            "Note",
            filters={"id": ["in", [note1.id, note2.id]]},
            fields=["id", {"seen_by": ["*"]}],
            order_by="title asc",
        ).run(as_dict=1)

        self.assertTrue(isinstance(result[0].seen_by, list))
        self.assertTrue(isinstance(result[1].seen_by, list))
        self.assertEqual(len(result[0].seen_by), 1)
        self.assertEqual(len(result[1].seen_by), 2)
        self.assertEqual(result[0].seen_by[0].user, "Administrator")

        result = frappe.qb.get_query(
            "Note",
            filters={"id": ["in", [note1.id, note2.id]]},
            fields=["id", {"seen_by": ["user"]}],
            order_by="title asc",
        ).run(as_dict=1)

        self.assertEqual(len(result[0].seen_by[0].keys()), 1)
        self.assertEqual(result[1].seen_by[1].user, "Guest")

        note1.delete()
        note2.delete()
