# Copyright (c) 2013, Frappe and contributors
# License: MIT. See LICENSE

import frappe
from frappe.website.doctype.help_article.help_article import clear_knowledge_base_cache
from frappe.website.website_generator import WebsiteGenerator


class HelpCategory(WebsiteGenerator):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        category_description: DF.Text | None
        category_id: DF.Data
        help_articles: DF.Int
        published: DF.Check
        route: DF.Data | None
    # end: auto-generated types

    website = frappe._dict(condition_field="published", page_title_field="category_id")

    def before_insert(self):
        self.published = 1

    def autoid(self):
        self.id = self.category_id

    def validate(self):
        self.set_route()

        # disable help articles of this category
        if not self.published:
            for d in frappe.get_all("Help Article", dict(category=self.id)):
                frappe.db.set_value("Help Article", d.id, "published", 0)

    def set_route(self):
        if not self.route:
            self.route = "kb/" + self.scrub(self.category_id)

    def clear_cache(self):
        clear_knowledge_base_cache()
        return super().clear_cache()
