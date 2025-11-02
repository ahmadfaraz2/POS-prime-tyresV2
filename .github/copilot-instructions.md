# Copilot instructions for this repo (bootstrap)

This repository is intended to host a Django 5+ monolithic web app named `shopproject` with apps: `accounts`, `products`, `customers`, `sales`, `dashboard`. No code exists yet; follow these conventions and workflows when generating files so future contributors and AI agents stay aligned.

## Architecture at a glance
- Project: `shopproject/` using SQLite, Django templates (no DRF).
- Apps: `accounts`, `products`, `customers`, `sales`, `dashboard` (each with models, views, urls, templates/<app_name>/*.html).
- Global: `templates/base.html` (Tailwind via CDN, navbar + sidebar, messages region), and a `templatetags/form_tags.py` providing `add_class` filter.
- Auth: all views wrapped with `@login_required`; use Django messages everywhere.
- Checkout: product-centric session cart in `products` → persisted sale via `sales.utils.create_sale_from_cart` (atomic stock decrement).
- Payments: support FULL and INSTALLMENT via `Sale`, `SaleItem`, `InstallmentPlan` (OneToOne with `Sale`), `InstallmentPayment`.

## Key contracts and data shapes
- Session cart: `request.session['cart']` is a dict keyed by product id with values `{product_id: int, name: str, price: str, quantity: int, subtotal: str}` (strings for JSON serialization; parse to Decimal for math).
- Sales utility: `create_sale_from_cart(user, customer_id, cart, payment_type, installment_data=None)` must:
  - Validate non-empty cart; wrap in `transaction.atomic()`.
  - Sum totals from `cart.values()` and create `Sale(is_completed=True)`.
  - For each item: `Product.objects.select_for_update()`, check stock, create `SaleItem`, decrement `product.stock_quantity`.
  - If INSTALLMENT: create `InstallmentPlan` with `installment_amount = (total / total_installments).quantize(Decimal('0.01'))`; handle remainder in last installment.
  - Return the created `Sale`.

## Project-specific conventions
- Monetary values: always `Decimal`; never float.
- Currency display: use "Rs " prefix in all templates (Pakistani Rupees).
- Relations: set `related_name` on every FK/OneToOne; `InstallmentPlan.sale` is `OneToOneField` with `related_name='installment_plan'`.
- Templates: load `form_tags` and apply `|add_class` to form inputs for Tailwind styling.
- URLs: each app is namespaced (`app_name = 'products'`, etc.) and included in `shopproject/urls.py`; root redirects to dashboard.
- Messages: success/errors for cart changes, sale creation, login/logout/register, and installment payments.

## Expected file anchors (create these paths)
- `shopproject/` (settings.py with LOGIN_URL='accounts:login', urls.py, asgi.py, wsgi.py, manage.py)
- `templates/base.html` (Tailwind CDN, navbar with username + logout, sidebar links to all apps)
- `core/templatetags/form_tags.py` (or place in one app) exposing `add_class(field, classes)`
- `accounts/` (login, register, logout views/templates using Django auth forms)
- `products/` (Product model; CRUD; cart views: add, remove, update, view; `checkout_view` calling sales utils)
- `customers/` (Customer model; CRUD)
- `sales/` (Sale, SaleItem, InstallmentPlan, InstallmentPayment; listing/detail/receipt; `utils.py` with `create_sale_from_cart`)
- `dashboard/` (cards for today’s sales, revenue, products, customers, outstanding installments)

## Workflows (PowerShell-friendly)
- Create venv, install, run:
  - `uv add -r requirements.txt`
  - `uv run manage.py makemigrations; uv run manage.py migrate`
  - `uv run manage.py createsuperuser`
  - `uv run manage.py runserver`
- Tests to include: 
  - Unit test ensuring `create_sale_from_cart` reduces stock and creates `Sale`/`SaleItem`.
  - Session cart add/remove behavior.

## Implementation tips for agents
- Use pagination on list views; wrap all views with `@login_required`.
- On stock insufficiency, raise `ValueError` in utils and surface via `messages.error`.
- Make `receipt.html` print-friendly with a simple `window.print()` button.
- Keep settings compatible with Django 5+; no DRF.

If parts of the spec are missing or differ from generated files, prefer the behavior defined above and update this document accordingly after changes.