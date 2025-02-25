frappe.listview_settings["Deleted Document"] = {
	onload: function (doclist) {
		const action = () => {
			const selected_docs = doclist.get_checked_items();
			if (selected_docs.length > 0) {
				let docids = selected_docs.map((doc) => doc.id);
				frappe.call({
					method: "frappe.core.doctype.deleted_document.deleted_document.bulk_restore",
					args: { docids },
					callback: function (r) {
						if (r.message) {
							let body = (docids) => {
								const html = docids.map((docid) => {
									return `<li><a href='/app/deleted-document/${docid}'>${docid}</a></li>`;
								});
								return "<br><ul>" + html.join("");
							};

							let message = (title, docids) => {
								return docids.length > 0 ? title + body(docids) + "</ul>" : "";
							};

							const { restored, invalid, failed } = r.message;
							const restored_summary = message(
								__("Documents restored successfully"),
								restored
							);
							const invalid_summary = message(
								__("Documents that were already restored"),
								invalid
							);
							const failed_summary = message(
								__("Documents that failed to restore"),
								failed
							);
							const summary = restored_summary + invalid_summary + failed_summary;

							frappe.msgprint(summary, __("Document Restoration Summary"), true);

							if (restored.length > 0) {
								doclist.refresh();
							}
						}
					},
				});
			}
		};
		doclist.page.add_actions_menu_item(__("Restore"), action, false);
	},
};
