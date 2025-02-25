frappe.listview_settings["Workflow Action"] = {
	get_form_link: (doc) => {
		let doctype = "";
		let docid = "";
		if (doc.status === "Open") {
			doctype = doc.reference_doctype;
			docid = doc.reference_name;
		} else {
			doctype = "Workflow Action";
			docid = doc.name;
		}
		docid = docid.match(/[%'"]/) ? encodeURIComponent(docid) : docid;

		return "/app/" + frappe.router.slug(doctype) + "/" + docid;
	},
};
