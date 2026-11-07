import os
import secrets
from functools import wraps
import click
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request, session
from sqlalchemy import create_engine, event, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from .models import Base, Customer, Product, User, Order, OrderItem, StockMovement
from .services import (
    ValidationError,
    accessible_order,
    import_products,
    integer,
    master_values,
    movement,
    parse_date,
    required,
    save_order,
    transition,
)


def record(model):
    from datetime import date, datetime
    from decimal import Decimal

    result = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        if isinstance(value, Decimal):
            value = str(value)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        if column.name != "password_hash":
            result[column.name] = value
    if isinstance(model, Order):
        result["items"] = [record(item) for item in model.items]
    return result


def create_app(config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DATABASE_URL=os.getenv("DATABASE_URL"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.config.update(config or {})
    if not app.config["SECRET_KEY"] or not app.config["DATABASE_URL"]:
        raise RuntimeError("Set SECRET_KEY and DATABASE_URL in .env. See README.md.")
    if not app.config["TESTING"] and not app.config["DATABASE_URL"].startswith(
        "mysql+pymysql://"
    ):
        raise RuntimeError(
            "The application requires MySQL. SQLite is permitted only in tests."
        )
    options = {"pool_pre_ping": True}
    if app.config["DATABASE_URL"].startswith("mysql"):
        options["isolation_level"] = "READ COMMITTED"
    engine = create_engine(app.config["DATABASE_URL"], **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    app.extensions["engine"] = engine

    @app.before_request
    def open_request():
        g.db = Session(engine, expire_on_commit=False)
        g.user = (
            g.db.get(User, session.get("user_id")) if session.get("user_id") else None
        )
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            token = session.get("csrf_token", "")
            if not token or not secrets.compare_digest(
                token, request.headers.get("X-CSRF-Token", "")
            ):
                raise ValidationError("Invalid security token. Reload the page.", 403)

    @app.teardown_request
    def close_request(error):
        if hasattr(g, "db"):
            g.db.close()

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValidationError)
    def validation_error(error):
        g.db.rollback()
        return jsonify(error=str(error), details=error.details), error.status

    @app.errorhandler(IntegrityError)
    def constraint_error(error):
        g.db.rollback()
        return (
            jsonify(
                error="Duplicate value or referenced record. Check the inputs or deactivate the record."
            ),
            409,
        )

    @app.errorhandler(OperationalError)
    def database_error(error):
        g.db.rollback()
        app.logger.exception("Database operation failed")
        return (
            jsonify(
                error="Database temporarily unavailable or transaction conflicted. Please retry."
            ),
            503,
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        g.db.rollback()
        app.logger.exception("Unexpected request failure")
        return jsonify(error="Unexpected server error. Please try again."), 500

    def authenticated(admin=False):
        def decorate(function):
            @wraps(function)
            def wrapped(*args, **kwargs):
                if not g.user:
                    raise ValidationError("Please log in", 401)
                if admin and g.user.role != "Admin":
                    raise ValidationError("Administrator access required", 403)
                return function(*args, **kwargs)

            return wrapped

        return decorate

    def payload():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValidationError("JSON body must be an object")
        return data

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/session")
    def current_session():
        session.setdefault("csrf_token", secrets.token_hex(32))
        return jsonify(
            user=record(g.user) if g.user else None, csrf_token=session["csrf_token"]
        )

    @app.post("/api/login")
    def login():
        data = payload()
        email = required(data, "email", 254).lower()
        password = required(data, "password", 256)
        user = g.db.scalar(select(User).where(User.email == email))
        if not user or not check_password_hash(user.password_hash, password):
            raise ValidationError("Invalid email or password", 401)
        session.clear()
        session.update(user_id=user.id, csrf_token=secrets.token_hex(32))
        return jsonify(user=record(user), csrf_token=session["csrf_token"])

    @app.post("/api/logout")
    @authenticated()
    def logout():
        session.clear()
        return jsonify(message="Logged out")

    models = {"products": Product, "customers": Customer}

    @app.get("/api/<kind>")
    @authenticated()
    def list_master(kind):
        if kind not in models:
            raise ValidationError("Resource not found", 404)
        model = models[kind]
        query = select(model)
        status = "Active" if g.user.role == "Sales" else request.args.get("status")
        if status:
            query = query.where(model.status == status)
        search = request.args.get("search", "").strip()
        if search:
            fields = (
                [model.product_code, model.name]
                if kind == "products"
                else [model.name, model.email, model.mobile]
            )
            query = query.where(
                or_(*(field.contains(search, autoescape=True) for field in fields))
            )
        if kind == "products" and request.args.get("category"):
            query = query.where(Product.category == request.args["category"])
        page = integer(request.args.get("page", 1), "Page")
        size = integer(request.args.get("page_size", 25), "Page size", maximum=100)
        total = g.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = g.db.scalars(
            query.order_by(model.id).offset((page - 1) * size).limit(size)
        ).all()
        return jsonify(
            items=[record(row) for row in rows], total=total, page=page, page_size=size
        )

    @app.route("/api/<kind>", methods=["POST"])
    @app.route("/api/<kind>/<int:record_id>", methods=["PUT", "DELETE"])
    @authenticated(admin=True)
    def modify_master(kind, record_id=None):
        if kind not in models:
            raise ValidationError("Resource not found", 404)
        model = models[kind]
        obj = (
            g.db.scalar(select(model).where(model.id == record_id).with_for_update())
            if record_id
            else None
        )
        if record_id and obj is None:
            raise ValidationError("Record not found", 404)
        if request.method == "DELETE":
            g.db.delete(obj)
            g.db.commit()
            return "", 204
        data = payload()
        values = master_values(data, kind)
        if obj is None:
            obj = model(**values)
            if kind == "products":
                obj.stock_quantity = 0
            g.db.add(obj)
            g.db.flush()
            if kind == "products":
                stock = integer(data.get("stock_quantity", 0), "Stock", 0)
                movement(g.db, obj, stock, g.user.id, "Opening", "Opening stock")
        else:
            if kind == "products" and "stock_quantity" in data:
                raise ValidationError("Use stock adjustment to change stock")
            for key, value in values.items():
                setattr(obj, key, value)
        g.db.commit()
        return jsonify(record(obj)), 201 if request.method == "POST" else 200

    @app.post("/api/products/<int:product_id>/adjust")
    @authenticated(admin=True)
    def adjust_stock(product_id):
        data = payload()
        product = g.db.scalar(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        if not product:
            raise ValidationError("Product not found", 404)
        change = integer(data.get("quantity_change"), "Change", -2_000_000_000)
        if change == 0:
            raise ValidationError("Stock adjustment cannot be zero")
        movement(
            g.db,
            product,
            change,
            g.user.id,
            "Adjustment",
            required(data, "reason", 255),
        )
        g.db.commit()
        return jsonify(record(product))

    @app.get("/api/orders")
    @authenticated()
    def orders():
        query = select(Order)
        if g.user.role != "Admin":
            query = query.where(Order.created_by == g.user.id)
        return jsonify(
            items=[
                record(row)
                for row in g.db.scalars(query.order_by(Order.id.desc())).all()
            ]
        )

    @app.post("/api/orders")
    @authenticated()
    def create_order():
        order = save_order(g.db, payload(), g.user)
        g.db.commit()
        return jsonify(record(order)), 201

    @app.route("/api/orders/<int:order_id>", methods=["GET", "PUT"])
    @authenticated()
    def order_detail(order_id):
        order = accessible_order(g.db, order_id, g.user, request.method == "PUT")
        if request.method == "PUT":
            save_order(g.db, payload(), g.user, order)
            g.db.commit()
        return jsonify(record(order))

    @app.post("/api/orders/<int:order_id>/<action>")
    @authenticated()
    def change_order(order_id, action):
        if action not in ("confirm", "cancel"):
            raise ValidationError("Unknown action", 404)
        order = accessible_order(g.db, order_id, g.user, lock=True)
        transition(g.db, order, action, g.user)
        g.db.commit()
        return jsonify(record(order))

    @app.post("/api/products/import")
    @authenticated(admin=True)
    def csv_import():
        upload = request.files.get("file")
        if not upload:
            raise ValidationError("Select a CSV file")
        count = import_products(g.db, upload.read(), g.user)
        g.db.commit()
        return jsonify(imported=count), 201

    @app.get("/api/reports/<kind>")
    @authenticated(admin=True)
    def reports(kind):
        if kind == "customers":
            conditions = [Order.status == "Confirmed"]
            start, end = request.args.get("start"), request.args.get("end")
            if start:
                conditions.append(Order.order_date >= parse_date(start))
            if end:
                conditions.append(Order.order_date <= parse_date(end))
            if start and end and parse_date(start) > parse_date(end):
                raise ValidationError("Start date must precede end date")
            totals = (
                select(
                    Order.customer_id,
                    func.count(Order.id).label("order_count"),
                    func.sum(Order.grand_total).label("sales"),
                )
                .where(*conditions)
                .group_by(Order.customer_id)
                .subquery()
            )
            query = select(
                Customer.name,
                func.coalesce(totals.c.order_count, 0).label("orders"),
                func.coalesce(totals.c.sales, 0).label("sales"),
            ).outerjoin(totals, Customer.id == totals.c.customer_id)
        elif kind == "products":
            query = (
                select(
                    Product.product_code,
                    Product.name,
                    func.sum(OrderItem.quantity).label("quantity"),
                    func.sum(OrderItem.amount).label("gross_value"),
                )
                .join(OrderItem, Product.id == OrderItem.product_id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.status == "Confirmed")
                .group_by(Product.id, Product.product_code, Product.name)
            )
        elif kind == "low-stock":
            threshold = integer(request.args.get("threshold", 10), "Threshold", 0)
            query = select(
                Product.product_code, Product.name, Product.stock_quantity
            ).where(Product.stock_quantity < threshold)
        elif kind == "movements":
            query = (
                select(
                    Product.product_code,
                    StockMovement.movement_type,
                    StockMovement.quantity_change,
                    Order.order_number,
                    StockMovement.reason,
                    StockMovement.created_by,
                    StockMovement.timestamp,
                )
                .join(Product, Product.id == StockMovement.product_id)
                .outerjoin(Order, Order.id == StockMovement.order_id)
                .order_by(StockMovement.id.desc())
            )
        else:
            raise ValidationError("Report not found", 404)
        return jsonify(
            items=[
                {
                    key: str(value) if value is not None else ""
                    for key, value in row.items()
                }
                for row in g.db.execute(query).mappings()
            ]
        )

    @app.cli.command("init-db")
    def init_db():
        Base.metadata.create_all(engine)
        click.echo("Database tables created.")

    @app.cli.command("seed")
    def seed():
        passwords = [os.getenv("SEED_ADMIN_PASSWORD"), os.getenv("SEED_SALES_PASSWORD")]
        if any(not password or len(password) < 10 for password in passwords):
            raise click.ClickException(
                "Set both SEED passwords to at least 10 characters."
            )
        with Session(engine) as db, db.begin():
            for name, email, role, password in [
                ("Demo Admin", "admin@example.test", "Admin", passwords[0]),
                ("Demo Sales", "sales@example.test", "Sales", passwords[1]),
            ]:
                if not db.scalar(select(User).where(User.email == email)):
                    db.add(
                        User(
                            name=name,
                            email=email,
                            role=role,
                            password_hash=generate_password_hash(password),
                        )
                    )
            db.flush()
            admin = db.scalar(select(User).where(User.email == "admin@example.test"))
            if not db.scalar(select(Customer.id).limit(1)):
                db.add(
                    Customer(
                        name="Acme Traders",
                        email="buyer@example.test",
                        mobile="9000000000",
                        city="Mumbai",
                        status="Active",
                    )
                )
            for code, name, price, stock in [
                ("PRD-001", "Keyboard", 1500, 20),
                ("PRD-002", "Mouse", 500, 50),
            ]:
                if not db.scalar(
                    select(Product.id).where(Product.product_code == code)
                ):
                    product = Product(
                        product_code=code,
                        name=name,
                        category="Accessories",
                        price=price,
                        stock_quantity=0,
                        status="Active",
                    )
                    db.add(product)
                    db.flush()
                    movement(
                        db, product, stock, admin.id, "Opening", "Sample opening stock"
                    )
        click.echo("Sample data ready. Use the passwords you configured in .env.")

    return app
