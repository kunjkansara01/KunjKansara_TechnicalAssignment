"""Login logic: check an email + password against the users table."""

import bcrypt

from app import models


def authenticate(email, password):
    # Normalise the email so "Admin@Example.com " still matches the stored row.
    email = (email or "").strip().lower()
    password = password or ""

    if email == "" or password == "":
        return None

    user = models.get_user_by_email(email)
    if user is None:
        return None

    # checkpw re-hashes the typed password with the salt stored inside the hash.
    stored_hash = user["password_hash"].encode("utf-8")
    if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
        return None

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
    }
