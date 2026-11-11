"""Customer rules: validation, create, edit, activate, delete."""

import mysql.connector

from app import models
from app.db import get_db


def validate_customer_form(form):
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    mobile = (form.get("mobile") or "").strip()
    city = (form.get("city") or "").strip()

    errors = []

    if name == "":
        errors.append("Name is required.")
    elif len(name) > 150:
        errors.append("Name must be 150 characters or fewer.")

    if email != "":
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Email address is not valid.")
        elif len(email) > 150:
            errors.append("Email must be 150 characters or fewer.")

    if mobile != "":
        if not mobile.isdigit():
            errors.append("Mobile must contain digits only.")
        elif len(mobile) < 10 or len(mobile) > 15:
            errors.append("Mobile must be between 10 and 15 digits.")

    if len(city) > 100:
        errors.append("City must be 100 characters or fewer.")

    clean_data = {
        "name": name,
        # Store NULL instead of an empty string for optional fields.
        "email": email if email != "" else None,
        "mobile": mobile if mobile != "" else None,
        "city": city if city != "" else None,
    }
    return clean_data, errors


def create_customer(clean_data):
    """Insert a validated customer. Returns the new id."""
    new_id = models.insert_customer(
        clean_data["name"], clean_data["email"], clean_data["mobile"], clean_data["city"]
    )
    get_db().commit()
    return new_id


def update_customer(customer_id, clean_data):
    models.update_customer(
        customer_id,
        clean_data["name"], clean_data["email"], clean_data["mobile"], clean_data["city"],
    )
    get_db().commit()


def set_active(customer_id, is_active):
    models.set_customer_active(customer_id, is_active)
    get_db().commit()


def delete_customer(customer):
    order_count = models.count_orders_for_customer(customer["id"])
    if order_count > 0:
        return False, (
            "%s cannot be deleted because %d order(s) reference this customer. "
            "Deactivate the customer instead." % (customer["name"], order_count)
        )

    db = get_db()
    try:
        models.delete_customer(customer["id"])
        db.commit()
    except mysql.connector.IntegrityError:
        db.rollback()
        return False, (
            "%s cannot be deleted because other records reference this customer. "
            "Deactivate the customer instead." % customer["name"]
        )

    return True, "%s was deleted." % customer["name"]
