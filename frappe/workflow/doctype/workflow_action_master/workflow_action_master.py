# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class WorkflowActionMaster(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		workflow_action_name: DF.Data
	# end: auto-generated types

	def before_validate(self):
		if not self.workflow_action_name and self.id:
			self.workflow_action_name = self.id
