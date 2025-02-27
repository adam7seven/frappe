from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe import _
from frappe.apps import get_default_path
from frappe.auth import LoginManager
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_url
from frappe.utils.data import escape_html
import frappe.utils.data
from frappe.utils.html_utils import get_icon_html
from frappe.utils.jinja import guess_is_path
from frappe.utils.oauth import (
    get_oauth2_authorize_url,
    get_oauth_keys,
    redirect_post_login,
)
from frappe.utils.password import get_decrypted_password
from frappe.website.utils import get_home_page
from frappe.app_core import load_license_from_file, validate_license

import datetime

no_cache = True


def get_context(context):
    context.no_header = True
    context.for_test = "license.html"
    context["title"] = "Manage License"

    license = None
    if hasattr(frappe, "license"):
        license = frappe.license
        result = validate_license(license)
    else:
        result, license = load_license_from_file()
        frappe.license = license

    context["license_status"] = result
    if license:
        context["license_version"] = license.VERSION

        begin_date = datetime.datetime.strptime(license.get("BEGIN"), "%Y%m%d")
        context["license_begin_date"] = frappe.utils.data.format_date(begin_date)

        expire_date = datetime.datetime.strptime(license.get("EXPIRATION"), "%Y%m%d")
        context["license_expire_date"] = frappe.utils.data.format_date(expire_date)
