export default {
    name: "Doctype With Phone",
    actions: [],
    custom: 1,
    is_submittable: 1,
    autoid: "field:title",
    creation: "2022-03-30 06:29:07.215072",
    doctype: "DocType",
    engine: "InnoDB",
    fields: [
        {
            fieldname: "title",
            fieldtype: "Data",
            label: "title",
            unique: 1
        },
        {
            fieldname: "phone",
            fieldtype: "Phone",
            label: "Phone"
        }
    ],
    links: [],
    modified: "2019-03-30 14:40:53.127615",
    modified_by: "Administrator",
    naming_rule: "By fieldname",
    module: "Custom",
    owner: "Administrator",
    permissions: [
        {
            create: 1,
            delete: 1,
            email: 1,
            print: 1,
            read: 1,
            role: "System Manager",
            share: 1,
            write: 1,
            submit: 1,
            cancel: 1
        }
    ],
    sort_field: "modified",
    sort_order: "ASC",
    track_changes: 1
};
