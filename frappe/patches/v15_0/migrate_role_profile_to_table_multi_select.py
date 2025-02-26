import frappe
from frappe.model.document import bulk_insert


def execute():
    users = frappe.get_all("User", filters={"role_profile_id": ["is", "set"]}, fields=["id", "role_profile_id"])
    user_profiles = get_records_to_insert(users)
    bulk_insert("User Role Profile", user_profiles, ignore_duplicates=True)


def get_records_to_insert(users):
    user_profiles = []
    for user in users:
        profiles = frappe.get_doc(
            {
                "doctype": "User Role Profile",
                "role_profile": user.role_profile_id,
                "parent": user.id,
                "parenttype": "User",
                "parentfield": "role_profiles",
            }
        )
        profiles.set_new_id()
        user_profiles.append(profiles)
    return user_profiles
