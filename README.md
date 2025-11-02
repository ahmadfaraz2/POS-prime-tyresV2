# ShopProject (Django 5)

Monolithic Django web app with apps: accounts, products, customers, sales, dashboard. Session cart checkout creates persistent Sales with optional installment plans.

## Requirements
- Python 3.11+
- Django >= 5.0 (installed via requirements.txt)

## Quickstart with uv (Windows PowerShell)

```powershell
# Install uv if needed (pick one):
# pip install uv
# winget install --id Astral-Software.uv -e

# Create an isolated environment and install deps
uv venv
uv pip install -r requirements.txt

# Run Django commands via uv (no manual activation needed)
uv run python shopproject/manage.py makemigrations
uv run python shopproject/manage.py migrate
uv run python shopproject/manage.py createsuperuser
uv run python shopproject/manage.py runserver
```

### Fallback with pip/venv

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python shopproject/manage.py migrate
python shopproject/manage.py runserver
```

Open http://127.0.0.1:8000/ and log in.

## Apps overview
- accounts: Register/Login/Logout (built-in forms)
- products: CRUD, session cart, checkout (FULL/INSTALLMENT)
- customers: CRUD
- sales: Sale/SaleItem/InstallmentPlan/InstallmentPayment, receipts, installment payments
- dashboard: KPIs for sales, revenue, products, customers, outstanding installments

## Session cart shape
`request.session['cart'] = { product_id_str: { product_id: int, name: str, price: str, quantity: int, subtotal: str } }`
- Prices/subtotals stored as strings for JSON serialization; converted to Decimal for calculations.

## Key helper
`sales.utils.create_sale_from_cart(user, customer_id, cart, payment_type, installment_data=None)` performs atomic stock decrement and creates records. Raises ValueError on insufficient stock or missing installment data.

## Notes
- Tailwind via CDN in `templates/base.html`.
- All views require auth and use Django messages.
- Form field styling via `core/templatetags/form_tags.py` filter `add_class`.
- Session cart uses JSON-serializable strings; Decimal math is applied when computing totals.
