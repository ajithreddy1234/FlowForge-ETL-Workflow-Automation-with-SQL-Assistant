"""Create a deterministic retail demo database (works on SQLite, PostgreSQL, MySQL).

    python -m scripts.demo_retail                       # ./demo/retail.db
    python -m scripts.demo_retail postgresql+psycopg2://user:pass@localhost/retail
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import (Column, Date, DateTime, ForeignKey, Integer, MetaData, Numeric, String, Table,
                        create_engine)

metadata = MetaData()

customers = Table("customers", metadata,
                  Column("id", Integer, primary_key=True),
                  Column("name", String(80), nullable=False),
                  Column("city", String(40), nullable=False),
                  Column("segment", String(20), nullable=False),  # consumer | business
                  Column("signup_date", Date, nullable=False))

products = Table("products", metadata,
                 Column("id", Integer, primary_key=True),
                 Column("name", String(80), nullable=False),
                 Column("category", String(40), nullable=False),
                 Column("price", Numeric(10, 2), nullable=False))

orders = Table("orders", metadata,
               Column("id", Integer, primary_key=True),
               Column("customer_id", Integer, ForeignKey("customers.id"), nullable=False),
               Column("order_date", Date, nullable=False),
               Column("status", String(20), nullable=False),
               Column("updated_at", DateTime, nullable=False))

order_items = Table("order_items", metadata,
                    Column("id", Integer, primary_key=True),
                    Column("order_id", Integer, ForeignKey("orders.id"), nullable=False),
                    Column("product_id", Integer, ForeignKey("products.id"), nullable=False),
                    Column("quantity", Integer, nullable=False),
                    Column("unit_price", Numeric(10, 2), nullable=False))

CITIES = ["Hyderabad", "Bengaluru", "Mumbai", "Delhi", "Chennai", "Pune", "Kolkata", "Ahmedabad"]
CATEGORIES = {
    "Dairy": ["Toned Milk 1L", "Full Cream Milk 1L", "Curd 500g", "Paneer 200g", "Butter 100g", "Ghee 500ml",
              "Cheese Slices", "Buttermilk 500ml"],
    "Fruits": ["Bananas 1kg", "Apples 1kg", "Mangoes 1kg", "Papaya", "Pomegranate 500g", "Grapes 500g"],
    "Vegetables": ["Tomatoes 1kg", "Onions 1kg", "Potatoes 1kg", "Spinach", "Carrots 500g", "Capsicum 500g"],
    "Bakery": ["Brown Bread", "White Bread", "Multigrain Bread", "Pav 6pc", "Cookies 200g"],
    "Beverages": ["Orange Juice 1L", "Coconut Water", "Cold Coffee", "Lassi 200ml", "Green Tea 25pc"],
    "Staples": ["Basmati Rice 5kg", "Atta 5kg", "Toor Dal 1kg", "Sugar 1kg", "Sunflower Oil 1L", "Salt 1kg"],
}
STATUSES = ["delivered"] * 14 + ["shipped"] * 2 + ["pending"] + ["cancelled"] * 2 + ["returned"]
FIRST = ["Aarav", "Diya", "Ishaan", "Ananya", "Kabir", "Meera", "Rohan", "Sneha", "Vikram", "Priya", "Arjun",
         "Kavya", "Nikhil", "Pooja", "Rahul", "Divya", "Siddharth", "Lakshmi", "Varun", "Neha"]
LAST = ["Reddy", "Sharma", "Iyer", "Patel", "Gupta", "Nair", "Rao", "Singh", "Menon", "Das", "Kumar", "Joshi"]


def build(url: str = "sqlite:///./runtime/retail.db", seed: int = 42) -> None:
    rng = random.Random(seed)
    engine = create_engine(url)
    metadata.drop_all(engine)
    metadata.create_all(engine)

    cust_rows = [{
        "id": i, "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "city": rng.choice(CITIES),
        "segment": "business" if rng.random() < 0.2 else "consumer",
        "signup_date": date(2024, 1, 1) + timedelta(days=rng.randint(0, 600)),
    } for i in range(1, 201)]

    prod_rows, pid = [], 1
    base_price = {"Dairy": 60, "Fruits": 120, "Vegetables": 45, "Bakery": 50, "Beverages": 80, "Staples": 250}
    for cat, names in CATEGORIES.items():
        for n in names:
            prod_rows.append({"id": pid, "name": n, "category": cat,
                              "price": round(base_price[cat] * rng.uniform(0.6, 2.2), 2)})
            pid += 1
    prices = {p["id"]: p["price"] for p in prod_rows}

    order_rows, item_rows, item_id = [], [], 1
    for oid in range(1, 1501):
        c = rng.choice(cust_rows)
        start = max(c["signup_date"], date(2025, 1, 1))
        od = start + timedelta(days=rng.randint(0, max(0, (date(2026, 10, 31) - start).days)))
        order_rows.append({"id": oid, "customer_id": c["id"], "order_date": od, "status": rng.choice(STATUSES),
                           "updated_at": datetime.combine(od, datetime.min.time())
                           + timedelta(hours=rng.randint(1, 72), seconds=oid)})  # unique: timestamp checkpoints
        for p in rng.sample(range(1, pid), rng.randint(1, 4)):
            item_rows.append({"id": item_id, "order_id": oid, "product_id": p, "quantity": rng.randint(1, 5),
                              "unit_price": prices[p]})
            item_id += 1

    with engine.begin() as conn:
        conn.execute(customers.insert(), cust_rows)
        conn.execute(products.insert(), prod_rows)
        conn.execute(orders.insert(), order_rows)
        conn.execute(order_items.insert(), item_rows)
    print(f"Seeded {engine.url.render_as_string(hide_password=True)}: {len(cust_rows)} customers, {len(prod_rows)} products, "
          f"{len(order_rows)} orders, {len(item_rows)} order items")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "sqlite:///./runtime/retail.db")
