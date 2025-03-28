# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from frappe import _

no_cache = 1


def get_context(context):
	context.no_breadcrumbs = True
	context.parents = [{"id": "me", "title": _("My Account")}]
