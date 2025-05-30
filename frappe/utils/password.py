# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from pypika.terms import Values

import frappe
from frappe import _
from frappe.query_builder import Table
from frappe.utils import cstr, encode

Auth = Table("__Auth")

passlibctx = CryptContext(
	schemes=[
		"pbkdf2_sha256",
		"argon2",
	],
)


def get_decrypted_password(doctype, id, fieldname="password", raise_exception=True):
	result = (
		frappe.qb.from_(Auth)
		.select(Auth.password)
		.where(
			(Auth.doctype == doctype)
			& (Auth.id == id)
			& (Auth.fieldname == fieldname)
			& (Auth.encrypted == 1)
		)
		.limit(1)
	).run()

	if result and result[0][0]:
		try:
			return decrypt(result[0][0], key=f"{doctype}.{id}.{fieldname}")
		except frappe.ValidationError as e:
			if raise_exception:
				raise e

			return None

	elif raise_exception:
		frappe.throw(
			_("Password not found for {0} {1} {2}").format(doctype, id, fieldname),
			frappe.AuthenticationError,
		)


def set_encrypted_password(doctype, id, pwd, fieldname="password"):
	query = frappe.qb.into(Auth).columns(Auth.doctype, Auth.id, Auth.fieldname, Auth.password, Auth.encrypted)

	# TODO: Simplify this via aliasing methods in `frappe.qb`
	if frappe.db.db_type == "mariadb":
		query = query.insert(doctype, id, fieldname, encrypt(pwd), 1).on_duplicate_key_update(
			Auth.password, Values(Auth.password)
		)
	elif frappe.db.db_type == "sqlite":
		query = query.insert_or_replace(doctype, id, fieldname, encrypt(pwd), 1)
	elif frappe.db.db_type == "postgres":
		query = (
			query.insert(doctype, id, fieldname, encrypt(pwd), 1)
			.on_conflict(Auth.doctype, Auth.id, Auth.fieldname)
			.do_update(Auth.password)
		)

	try:
		query.run()

	except frappe.db.DataError as e:
		if frappe.db.is_data_too_long(e):
			frappe.throw(_("Most probably your password is too long."), exc=e)
		raise e


def remove_encrypted_password(doctype, id, fieldname="password"):
	frappe.db.delete("__Auth", {"doctype": doctype, "id": id, "fieldname": fieldname})


def check_password(user, pwd, doctype="User", fieldname="password", delete_tracker_cache=True):
	"""Checks if user and password are correct, else raises frappe.AuthenticationError"""

	result = (
		frappe.qb.from_(Auth)
		.select(Auth.id, Auth.password)
		.where(
			(Auth.doctype == doctype)
			& (Auth.id == user)
			& (Auth.fieldname == fieldname)
			& (Auth.encrypted == 0)
		)
		.limit(1)
		.run(as_dict=True)
	)

	if not result or not passlibctx.verify(pwd, result[0].password):
		raise frappe.AuthenticationError(_("Incorrect User or Password"))

	# lettercase agnostic
	user = result[0].id

	# TODO: This need to be deleted after checking side effects of it.
	# We have a `LoginAttemptTracker` that can take care of tracking related cache.
	if delete_tracker_cache:
		delete_login_failed_cache(user)

	if passlibctx.needs_update(result[0].password):
		update_password(user, pwd, doctype, fieldname)

	return user


def delete_login_failed_cache(user):
	frappe.cache.hdel("login_failed_count", user)


def update_password(user, pwd, doctype="User", fieldname="password", logout_all_sessions=False):
	"""
	Update the password for the User

	:param user: username
	:param pwd: new password
	:param doctype: doctype id (for encryption)
	:param fieldname: fieldname (in given doctype) (for encryption)
	:param logout_all_session: delete all other session
	"""
	hashPwd = passlibctx.hash(pwd)

	query = frappe.qb.into(Auth).columns(Auth.doctype, Auth.id, Auth.fieldname, Auth.password, Auth.encrypted)

	# TODO: Simplify this via aliasing methods in `frappe.qb`
	if frappe.db.db_type == "mariadb":
		query = (
			query.insert(doctype, user, fieldname, hashPwd, 0)
			.on_duplicate_key_update(Auth.password, hashPwd)
			.on_duplicate_key_update(Auth.encrypted, 0)
		)
	elif frappe.db.db_type == "sqlite":
		query = query.insert_or_replace(doctype, user, fieldname, hashPwd, 0)

	elif frappe.db.db_type == "postgres":
		query = (
			query.insert(doctype, user, fieldname, hashPwd, 0)
			.on_conflict(Auth.doctype, Auth.id, Auth.fieldname)
			.do_update(Auth.password, hashPwd)
			.do_update(Auth.encrypted, 0)
		)

	query.run()

	# clear all the sessions except current
	if logout_all_sessions:
		from frappe.sessions import clear_sessions

		clear_sessions(user=user, keep_current=True, force=True)


def delete_all_passwords_for(doctype, id):
	try:
		frappe.db.delete("__Auth", {"doctype": doctype, "id": id})
	except Exception as e:
		if not frappe.db.is_missing_column(e):
			raise


def rename_password(doctype, old_id, new_id):
	# NOTE: fieldname is not considered, since the document is renamed
	frappe.qb.update(Auth).set(Auth.id, new_id).where((Auth.doctype == doctype) & (Auth.id == old_id)).run()


def rename_password_field(doctype, old_fieldname, new_fieldname):
	frappe.qb.update(Auth).set(Auth.fieldname, new_fieldname).where(
		(Auth.doctype == doctype) & (Auth.fieldname == old_fieldname)
	).run()


def create_auth_table():
	# same as Framework.sql
	frappe.db.create_auth_table()


def encrypt(txt, encryption_key=None):
	# Only use Fernet.generate_key().decode() to enter encyption_key value

	try:
		cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
	except Exception:
		# encryption_key is not in 32 url-safe base64-encoded format
		frappe.throw(_("Encryption key is in invalid format!"))

	return cstr(cipher_suite.encrypt(encode(txt)))


def decrypt(txt, encryption_key=None, key: str | None = None):
	# Only use encryption_key value generated with Fernet.generate_key().decode()

	try:
		cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
		return cstr(cipher_suite.decrypt(encode(txt)))
	except InvalidToken:
		# encryption_key in site_config is changed and not valid
		frappe.throw(
			(_("Failed to decrypt key {0}").format(key) + "<br><br>" if key else "")
			+ _("Encryption key is invalid! Please check site_config.json")
			+ "<br><br>"
			+ _(
				"If you have recently restored the site, you may need to copy the site_config.json containing the original encryption key."
			)
			+ "<br><br>"
			+ _(
				"Please visit https://frappecloud.com/docs/sites/migrate-an-existing-site#encryption-key for more information."
			),
		)


def get_encryption_key():
	if "encryption_key" not in frappe.local.conf:
		from frappe.installer import update_site_config

		encryption_key = Fernet.generate_key().decode()
		update_site_config("encryption_key", encryption_key)
		frappe.local.conf.encryption_key = encryption_key

	return frappe.local.conf.encryption_key


def get_password_reset_limit():
	return frappe.get_system_settings("password_reset_limit") or 3
