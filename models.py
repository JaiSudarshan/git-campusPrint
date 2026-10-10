from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

RATES = {"bw": 2, "color": 10}  # rupees per page
STATUSES = ("pending", "printing", "delivered")


def utcnow():
    return datetime.now(timezone.utc)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20))
    classroom = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )

    @property
    def total_cost(self):
        return sum(i.cost for i in self.items)

    @property
    def total_sheets(self):
        return sum(i.pages * i.copies for i in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(300), nullable=False)
    thumb_key = db.Column(db.String(300))
    content_type = db.Column(db.String(50), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    pages = db.Column(db.Integer, nullable=False, default=1)
    print_type = db.Column(db.String(10), nullable=False)  # "bw" or "color"
    copies = db.Column(db.Integer, nullable=False, default=1)

    @property
    def cost(self):
        return RATES[self.print_type] * self.pages * self.copies

    @property
    def print_label(self):
        return "Color" if self.print_type == "color" else "B/W"

    @property
    def ext(self):
        return self.filename.rsplit(".", 1)[-1].upper() if "." in self.filename else "FILE"
