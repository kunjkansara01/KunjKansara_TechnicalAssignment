"""Database access functions: one plain function per query.

Each function gets the request's connection from db.get_db(), runs one SQL
statement, and returns plain Python values (dicts or lists of dicts).
No business rules live here; those belong in app/services/.
"""

from app.db import get_db


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def get_user_by_email(email):
    """Return the user row for this email (including password_hash), or None."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, password_hash, role FROM users WHERE email = %s",
        (email,),
    )
    user = cursor.fetchone()
    cursor.close()
    return user


def get_user_by_id(user_id):
    """Return the user row for this id without the password hash, or None."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, role FROM users WHERE id = %s",
        (user_id,),
    )
    user = cursor.fetchone()
    cursor.close()
    return user
