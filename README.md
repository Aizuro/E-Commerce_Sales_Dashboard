# E-Commerce Sales, Delivery & Customer Analysis

Exploratory analysis and interactive dashboards built on a public Brazilian e-commerce dataset (about 99K orders, 2016–2018). The project answers two business questions and extends them with a customer (RFM) analysis, a delivery-route analysis and a seller concentration analysis.

**Live demo:** 
[Streamlit dashboard] https://e-commerce-salesdashboard.streamlit.app/ 
[Tableau Public] https://public.tableau.com/views/E-CommerceSalesDashboard_17930003761630/Penjualan?:language=en-US&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link

*(The dashboard interface is in Indonesian.)*

## Business questions

1. Which product categories sell the most, and how much do they contribute to total revenue?
2. Does delivery speed affect customer review scores?

Extensions: customer retention (RFM), delivery performance by route (seller state to customer state), and seller concentration (ABC analysis).

## Key findings

All figures use **delivered orders only** (96,478 of 99,441 orders, 97.0%). Revenue is the sum of item prices and excludes freight.

| Area | Finding |
|---|---|
| Categories | Total revenue is about R$13.2M across 72 categories. 18 categories generate 80% of revenue and the top 10 generate 62.4%. |
| Volume vs. revenue | `bed_bath_table` has the most orders (9,272), but `health_beauty` has the highest revenue (9.3%). `watches_gifts` ranks #2 by revenue (8.8%) with fewer orders (5,495) because its revenue per order is about R$212, roughly twice that of `bed_bath_table` (about R$110). |
| Geography | São Paulo (SP) contributes 38.3% of revenue; SP, RJ and MG together contribute 63.4%. SP has the lowest revenue per order among the top 10 states, so its share comes from volume. |
| Delivery and reviews | Average review score falls from 4.42 (delivered in 7 days or less) to 3.12 (more than 21 days). Orders delivered after the estimated date (8.0%) average 2.57 versus 4.29 for on-time orders; 54.0% of late orders have a 1–2 star review versus 9.2% of on-time orders. |
| Strength of the relationship | The overall Spearman correlation between delivery days and review score is weak (ρ = −0.235). The effect is concentrated in very slow or late orders, so it should not be read as a uniform effect of every extra day. |
| Routes | 64.0% of seller-to-customer shipments cross state lines. They take 15.1 days on average and are late 9.2% of the time, versus 7.9 days and 6.0% for same-state shipments. |
| Customers | Of 93,358 unique customers, 97.0% bought once. Excluding same-day re-orders, 2.13% came back. The "High-Value One-Timer" segment is 37.7% of customers and 71.2% of revenue, and 53.2% of it is already at risk or inactive. |
| Sellers | 533 of 2,970 sellers (17.9%) generate 80% of revenue and handle 74% of shipments. Their average review score (4.12) is slightly lower than that of the smallest sellers (4.22); this difference was not tested statistically. |

## Data and definitions

The dataset (Dicoding's "E-Commerce Public Dataset") has 9 tables: customers, geolocation, order items, payments, reviews, orders, product categories, products and sellers. Source: https://drive.google.com/drive/folders/16Niv1yxrBN4tN1vUvO9e0duYF7DYZ_wW?usp=drive_link

| Term | Definition used |
|---|---|
| Analysed orders | `order_status = delivered`. Orders that were canceled, unavailable or still in progress have empty delivery dates by nature, so they are excluded instead of filled. |
| Delivery time | Days from purchase timestamp to the date the customer received the order. |
| Late order | Delivered after the estimated delivery date. |
| Customer | `customer_unique_id`. In this dataset `customer_id` is created per order and cannot identify repeat buyers. |
| Returning customer | Bought again at least 1 day after a previous order. Same-day repeat orders are treated as a split basket, not as a return. This is an assumption. |
| Review score per order | Mean score when an order has more than one review. |
| RFM segments | Recency, frequency and monetary scores (quintiles for R and M), combined with fixed rules into five segments. |
| Customer status | Active (≤200 days since last purchase), at risk (201–280), inactive (>280). The limits are the 80th and 90th percentile of the observed gap between a customer's consecutive orders. |

## Method highlights

- **Explicit data rules instead of implicit row dropping.** The original cleaning step removed every row with any missing value (2,980 orders, including 23 delivered ones). This was replaced by two documented subsets: delivered orders for revenue, reviews and RFM, and delivered orders with a receipt date for delivery analysis.
- **Join validation.** Every merge uses `validate="m:1"` and row counts are checked against the source (110,197 item rows from 96,478 orders, no duplicate order-item pairs).
- **Statistics for ordinal data.** Review scores are 1–5, so the delivery analysis uses Spearman correlation and the Kruskal-Wallis test instead of Pearson or t-tests, and every group is shown with its sample size.
- **Reconciliation.** Total orders (96,478), revenue (R$13,221,498) and unique customers (93,358) match across the notebook, the Streamlit app and the Tableau workbook.

## Repository structure

```
├── Home.py                        # Streamlit dashboard
├── Proyek_Analisis_Data.ipynb     # Full analysis notebook
├── dashboard_items.csv            # One row per delivered item (revenue, category, customer)
├── dashboard_orders.csv           # One row per order (delivery time, lateness, review)
├── requirements.txt
└── .streamlit/config.toml         # Theme settings
```

The two CSV files are produced by the "Export Data" cells at the end of the notebook.

## Run locally

Python 3.11 is recommended.

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run Home.py
```

## Limitations

- Findings about delivery and reviews are associations. Product quality, seller behaviour and other factors were not controlled for.
- Revenue uses item prices only. Freight, discounts and payment values are not included.
- The data covers about two years. The first and last months are incomplete, so month-to-month changes at the edges should not be over-read.
- Customer status limits come from the small share of customers who returned, and long gaps are cut off by the end of the data, so the limits are approximations.
- The dataset has no campaign or promotion information. Win-back suggestions are hypotheses and their effect cannot be measured here.
- RFM segments are rule-based, not the output of a validated clustering model.
- The geolocation table was assessed and cleaned but is not used in the final analysis; route analysis is done at state level.

## Corrections made to the original course submission

This repository is a rebuild of an earlier version of the project. The review of that version found and fixed:

- Customers were identified by `customer_id` (unique per order), which made the RFM frequency almost always 1.
- Category revenue contribution was computed only among the top 5 categories by order count.
- The "highest revenue state" was selected by sorting state names alphabetically.
- Delivery-speed groups were not based on the observed distribution, and no sample sizes or statistical tests were reported.
- A many-to-many join was patched with `drop_duplicates` instead of being validated.
- The delivery map used about 700 of roughly 96K orders after a lossy merge, and the "active/inactive customer" label reflected a cleaning side effect rather than behaviour.

## Author

Abdul Azizur Rokhman — [LinkedIn]www.linkedin.com/in/abdul-azizur-rokhman · [GitHub]https://github.com/Aizuro
