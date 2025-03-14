import os

import frappe.utils
import frappe.utils.data
from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Request

import frappe
from frappe import _
from frappe.auth import HTTPRequest
from frappe.utils import CallbackManager, cint, get_site_name
import datetime


def init_request(request, site, sites_path):
	frappe.local.request = request
	frappe.local.request.after_response = CallbackManager()

	frappe.local.is_ajax = frappe.get_request_header("X-Requested-With") == "XMLHttpRequest"

	site = site or request.headers.get("X-Frappe-Site-Name") or get_site_name(request.host)
	frappe.init(site=site, sites_path=sites_path, force=True)

	if not (frappe.local.conf and frappe.local.conf.db_name):
		# site does not exist
		raise NotFound

	if frappe.local.conf.maintenance_mode:
		frappe.connect()
		if frappe.local.conf.allow_reads_during_maintenance:
			setup_read_only_mode()
		else:
			raise frappe.SessionStopped("Session Stopped")
	else:
		frappe.connect(set_admin_as_user=False)
	if request.path.startswith("/api/method/upload_file"):
		from frappe.core.api.file import get_max_file_size

		request.max_content_length = get_max_file_size()
	else:
		request.max_content_length = cint(frappe.local.conf.get("max_file_size")) or 25 * 1024 * 1024
	make_form_dict(request)

	if request.method != "OPTIONS":
		frappe.local.http_request = HTTPRequest()

	for before_request_task in frappe.get_hooks("before_request"):
		frappe.call(before_request_task)

	check_license(request)


def setup_read_only_mode():
	"""During maintenance_mode reads to DB can still be performed to reduce downtime. This
	function sets up read only mode

	- Setting global flag so other pages, desk and database can know that we are in read only mode.
	- Setup read only database access either by:
	    - Connecting to read replica if one exists
	    - Or setting up read only SQL transactions.
	"""
	frappe.flags.read_only = True

	# If replica is available then just connect replica, else setup read only transaction.
	if frappe.conf.read_from_replica:
		frappe.connect_replica()
	else:
		frappe.db.begin(read_only=True)


def make_form_dict(request: Request):
	import json

	request_data = request.get_data(as_text=True)
	if request_data and request.is_json:
		args = json.loads(request_data)
	else:
		args = {}
		args.update(request.args or {})
		args.update(request.form or {})

	if isinstance(args, dict):
		frappe.local.form_dict = frappe._dict(args)
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		frappe.local.form_dict.pop("_", None)
	elif isinstance(args, list):
		frappe.local.form_dict["data"] = args
	else:
		frappe.throw(_("Invalid request arguments"))


def check_license(request):
	# Developer mode bypasses license check
	# if frappe.local.conf.get("developer_mode"):
	#     return

	# Only check for license if the request is an API request
	if not request.path.startswith("/api/"):
		return

	if request.path == "/api/method/logout":
		return

	result = None
	if hasattr(frappe, "license"):
		license = frappe.license
		result = validate_license(license)
	else:
		result, license = load_license_from_file()
		if license:
			frappe.license = license

	if result == "NotFound":
		raise frappe.LicenseNotFoundError
	elif result == "Invalid":
		raise frappe.LicenseInvalidError
	elif result == "Expired":
		raise frappe.LicenseExpiredError


def load_license_from_file():
	# Get the license file from the system
	license_file = frappe.get_site_path("license.lic")
	if not os.path.exists(license_file):
		return "NotFound", None

	content = ""
	with open(license_file, "r") as file:
		content = file.read()

	if not content:
		return "Invalid", None

	try:
		plain_content = decrypt_license(content)
		license = deserialize_license_content(plain_content)
		return validate_license(license), license
	except Exception:
		return "Invalid", None


def decrypt_license(encrypt_content):
	# TODO: decrypt the license content
	return encrypt_content


def deserialize_license_content(content):
	try:
		license = frappe.parse_json(content)
		return license
	except Exception:
		return None


def validate_license(license):
	if not license:
		return "Invalid"

	version = license.get("VERSION")
	if not version:
		return "Invalid"
	elif version not in [1]:
		return "Invalid"

	# TODO: check hardware information

	# Begin Date must before today
	begin = license.get("BEGIN")
	if not begin:
		return "Invalid"
	elif len(begin) != 8:
		return "Invalid"

	begin_date = datetime.datetime.strptime(begin, "%Y%m%d")
	if begin_date > frappe.utils.data.now_datetime():
		return "Invalid"

	# Expiration must after today
	expiration = license.get("EXPIRATION")
	if not expiration:
		return "Invalid"
	elif len(expiration) != 8:
		return "Invalid"

	expire_date = datetime.datetime.strptime(expiration, "%Y%m%d")
	if expire_date <= frappe.utils.data.now_datetime():
		return "Expired"

	return "Valid"


def get_mac_address():
	mac_address = None
	with open("/sys/class/net/eth0/address", "r") as f:
		mac_address = f.read().strip()
	return mac_address


@frappe.whitelist(allow_guest=True)
def generate_request_content():
	mac_address = get_mac_address()
	request = {
		"VERSION": 1,
		"MAC_ADDRESS": mac_address,
	}
	request_json = frappe.as_json(request, 0)
	return request_json


@frappe.whitelist(allow_guest=True)
def import_license(content):
	if not content:
		frappe.throw(_("Content cannot be empty"))

	plain_content = decrypt_license(content)
	license = deserialize_license_content(plain_content)
	result = validate_license(license)
	if result == "Invalid":
		frappe.throw(_("License file is invalid"))
	elif result == "Expired":
		frappe.throw(_("License file is expired"))

	frappe.license = license
	license_file = frappe.get_site_path("license.lic")
	with open(license_file, "w") as file:
		file.write(content)
