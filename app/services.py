import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select
from .models import Customer, Product, Order, OrderItem, StockMovement


class ValidationError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status = status
        self.details = details


def integer(value, field, minimum=1, maximum=2_000_000_000):
    if isinstance(value, bool) or not re.fullmatch(r'-?\d+', str(value)):
        raise ValidationError(f'{field} must be a whole number')
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValidationError(f'{field} must be between {minimum} and {maximum}')
    return number


def decimal_value(value, field, maximum=Decimal('999999999999.99')):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(f'{field} must be numeric')
    if not number.is_finite() or number < 0 or number > maximum:
        raise ValidationError(f'{field} must be between 0 and {maximum}')
    if number != number.quantize(Decimal('.01')):
        raise ValidationError(f'{field} allows at most two decimal places')
    return number


def money(value):
    return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def required(data, name, limit=120):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValidationError(f'{name} is required and must be at most {limit} characters')
    return value.strip()


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError('Date must use YYYY-MM-DD')


def master_values(data, kind):
    values = {'name': required(data, 'name'), 'status': data.get('status', 'Active')}
    if values['status'] not in ('Active', 'Inactive'):
        raise ValidationError('Status must be Active or Inactive')
    if kind == 'products':
        values.update(product_code=required(data, 'product_code', 50).upper(),
                      category=required(data, 'category', 100), price=decimal_value(data.get('price'), 'Price'))
    else:
        values.update(email=required(data, 'email', 254), mobile=required(data, 'mobile', 30),
                      city=required(data, 'city', 100))
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['email']):
            raise ValidationError('Enter a valid email address')
    return values


def movement(db, product, change, user_id, kind, reason, order_id=None):
    new_stock = product.stock_quantity + change
    if not 0 <= new_stock <= 2_000_000_000:
        raise ValidationError(f'Insufficient stock or stock limit exceeded for {product.product_code}', 409)
    product.stock_quantity = new_stock
    db.add(StockMovement(product_id=product.id, quantity_change=change, created_by=user_id,
                         movement_type=kind, reason=reason, order_id=order_id))


def accessible_order(db, order_id, user, lock=False):
    query = select(Order).where(Order.id == order_id)
    if lock:
        query = query.with_for_update()
    order = db.scalar(query)
    if order is None:
        raise ValidationError('Order not found', 404)
    if user.role != 'Admin' and order.created_by != user.id:
        raise ValidationError('You cannot access this order', 403)
    return order


def save_order(db, data, user, order=None):
    if order is not None and order.status != 'Draft':
        raise ValidationError('Only Draft orders can be edited', 409)
    customer = db.get(Customer, integer(data.get('customer_id'), 'Customer'))
    if not customer or customer.status != 'Active':
        raise ValidationError('Select an active customer')
    rows = data.get('items')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValidationError('An order needs between 1 and 100 items')
    discount = decimal_value(data.get('discount_percentage', 0), 'Discount', Decimal('20'))
    old_rates = {item.product_id: item.rate for item in order.items} if order else {}
    items, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError('Each item must be an object')
        product_id = integer(row.get('product_id'), 'Product')
        if product_id in seen:
            raise ValidationError('Duplicate products are not allowed')
        seen.add(product_id)
        product = db.get(Product, product_id)
        if not product or product.status != 'Active':
            raise ValidationError('Select active products')
        quantity = integer(row.get('quantity'), 'Quantity')
        rate = old_rates.get(product_id, product.price)
        amount = money(rate * quantity)
        items.append(OrderItem(product_id=product_id, quantity=quantity, rate=rate, amount=amount))
    subtotal = sum((item.amount for item in items), Decimal('0'))
    if subtotal > Decimal('99999999999999.99'):
        raise ValidationError('Order total exceeds the supported limit')
    discount_amount = money(subtotal * discount / 100)
    if order is None:
        order = Order(order_number=f'SO-{uuid4().hex[:24].upper()}', created_by=user.id, status='Draft')
        db.add(order)
    else:
        order.items.clear()
        db.flush()
    order.customer_id = customer.id
    order.order_date = parse_date(data.get('order_date', date.today().isoformat()))
    order.discount_percentage = discount
    order.subtotal = subtotal
    order.discount_amount = discount_amount
    order.grand_total = subtotal - discount_amount
    order.items = items
    db.flush()
    return order


def transition(db, order, action, user):
    target = 'Confirmed' if action == 'confirm' else 'Cancelled'
    if order.status == target:
        return order
    if order.status == 'Cancelled':
        raise ValidationError('Cancelled orders cannot change status', 409)
    if action == 'confirm' or order.status == 'Confirmed':
        # Every caller locks the order first, then products in ascending ID order.
        products = db.scalars(select(Product).where(Product.id.in_([i.product_id for i in order.items]))
                              .order_by(Product.id).with_for_update()).all()
        by_id = {product.id: product for product in products}
        if action == 'confirm':
            customer = db.get(Customer, order.customer_id)
            if customer.status != 'Active' or any(p.status != 'Active' for p in products):
                raise ValidationError('Customer and products must be active to confirm', 409)
        for item in order.items:
            change = -item.quantity if action == 'confirm' else item.quantity
            movement(db, by_id[item.product_id], change, user.id,
                     'Sale' if action == 'confirm' else 'Cancellation', target, order.id)
    order.status = target
    db.flush()
    return order


def import_products(db, content, user):
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''), strict=True)
        columns = ['product_code', 'product_name', 'category', 'price', 'stock_quantity', 'status']
        if reader.fieldnames != columns:
            raise ValidationError('CSV headers must match the supplied sample exactly')
        existing = set(db.scalars(select(Product.product_code)).all())
        seen, errors, valid = set(), [], []
        for row in reader:
            try:
                if None in row:
                    raise ValidationError('Too many columns')
                values = master_values(dict(row, name=row.get('product_name')), 'products')
                code = values['product_code']
                if code in seen or code in existing:
                    raise ValidationError('Duplicate product code')
                seen.add(code)
                stock = integer(row.get('stock_quantity'), 'Stock', 0)
                valid.append((values, stock))
            except ValidationError as error:
                errors.append({'row': reader.line_num, 'reason': str(error)})
        if errors:
            raise ValidationError('Import rejected. No products were imported.', details=errors)
        if not valid:
            raise ValidationError('CSV contains no products')
        for values, stock in valid:
            product = Product(**values, stock_quantity=0)
            db.add(product)
            db.flush()
            movement(db, product, stock, user.id, 'Opening', 'CSV opening stock')
        return len(valid)
    except (UnicodeDecodeError, csv.Error):
        raise ValidationError('Upload a valid UTF-8 CSV file')
