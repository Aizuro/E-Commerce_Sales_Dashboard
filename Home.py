"""Dashboard E-Commerce: penjualan, pengiriman, dan pelanggan (hanya order berstatus delivered).

Data berasal dari notebook Proyek_Analisis_Data.ipynb:
- dashboard_items.csv  : satu baris per item terjual (revenue, kategori, pelanggan)
- dashboard_orders.csv : satu baris per order (durasi pengiriman, keterlambatan, review)
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dashboard E-Commerce", page_icon="🛒", layout="wide",
                   initial_sidebar_state="collapsed")

DATA_DIR = Path(__file__).parent
ACCENT = "#72BCD4"  # satu warna aksen untuk seluruh dashboard
MUTED = "#C5CDD5"   # warna netral untuk data pembanding
BIN_LABELS = ["≤7 hari", "8-14 hari", "15-21 hari", ">21 hari"]
# Batas status pelanggan berasal dari jeda pembelian ulang (persentil 80 dan 90) di notebook
ACTIVE_MAX, RISK_MAX = 200, 280
STATUS_LABELS = [
    f"Aktif (≤{ACTIVE_MAX} hari)",
    f"Berisiko ({ACTIVE_MAX + 1}-{RISK_MAX} hari)",
    f"Tidak aktif (>{RISK_MAX} hari)",
]
SEGMENT_ORDER = ["High-Value One-Timer", "Hibernating", "New Customer", "Loyal", "At Risk (repeat)"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

# Warna latar dan garis memakai transparansi agar tetap terbaca di tema terang maupun gelap
st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 4.5rem; padding-bottom: 3rem;}
    #MainMenu, footer {visibility: hidden;}
    h1 {font-size: 1.9rem !important; font-weight: 700 !important; letter-spacing: -0.01em; padding-bottom: 0 !important;}
    [data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: 14px 16px;
                              background: rgba(128,128,128,.05);}
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {font-size: .82rem; opacity: .85;
        overflow: visible !important; text-overflow: clip !important; white-space: normal !important;}
    [data-testid="stMetricValue"] {font-size: clamp(1.25rem, 1.9vw, 1.6rem); font-weight: 650; line-height: 1.25;}
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        overflow: visible !important; text-overflow: clip !important; white-space: normal !important;}
    .summary {border-left: 3px solid #72BCD4; background: rgba(114,188,212,.12); padding: .85rem 1.1rem;
              border-radius: 0 10px 10px 0; margin: .4rem 0 1.4rem 0; font-size: .95rem; line-height: 1.6;}
    .summary ul {margin: .35rem 0 0 0; padding-left: 1.1rem;}
    .section-title {font-size: 1.05rem; font-weight: 650; margin: .6rem 0 0 0;}
    .hint {font-size: .85rem; opacity: .65; margin: .1rem 0 .3rem 0;}
    .takeaway {font-size: .95rem; margin: .4rem 0 .6rem 0;}
    button[data-baseweb="tab"] {font-size: .95rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------------
def brl(x):
    return "R$ " + f"{x:,.0f}".replace(",", ".")


def num(x):
    return f"{x:,.0f}".replace(",", ".")


def dec(x, d=1):
    """Angka desimal gaya Indonesia: 1.234,5"""
    return f"{x:,.{d}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def bulan_id(ts):
    return f"{BULAN[ts.month - 1]} {ts.year}"


def section(title, hint=None):
    """Judul grafik dan satu kalimat cara membacanya (tanda $ di-escape agar tidak dibaca sebagai rumus)."""
    html = f'<div class="section-title">{title}</div>'
    if hint:
        html += f'<div class="hint">{hint}</div>'
    st.markdown(html.replace("$", "&#36;"), unsafe_allow_html=True)


def takeaway(text):
    """Satu kalimat kesimpulan yang dihitung dari data pada rentang yang dipilih."""
    st.markdown(f'<div class="takeaway">{text.replace("$", "&#36;")}</div>', unsafe_allow_html=True)


def style(fig, height=320, legend=False):
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=0, r=12, t=8, b=0), title=None,
        bargap=0.3, separators=",.", font=dict(size=13), showlegend=legend,
    )
    fig.update_xaxes(zeroline=False, title=None)
    fig.update_yaxes(zeroline=False, title=None, gridcolor="rgba(128,128,128,.18)")
    if legend:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""))
    return fig


@st.cache_data
def load_items():
    return pd.read_csv(
        DATA_DIR / "dashboard_items.csv",
        parse_dates=["order_purchase_timestamp"],
        dtype={"category": "category", "customer_state": "category"},
    )


@st.cache_data
def load_orders():
    return pd.read_csv(
        DATA_DIR / "dashboard_orders.csv",
        parse_dates=["order_purchase_timestamp"],
        dtype={"customer_state": "category"},
    )


def filter_by_date(df, start, end):
    """Filter inklusif: seluruh hari pada tanggal akhir ikut dihitung."""
    ts = df["order_purchase_timestamp"]
    return df.loc[(ts >= start) & (ts < end + pd.Timedelta(days=1))]


@st.cache_data
def compute_rfm(start, end):
    df = filter_by_date(load_items(), start, end)
    if df["customer_unique_id"].nunique() < 100:
        return None

    snapshot = df["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
    rfm = df.groupby("customer_unique_id").agg(
        last_purchase=("order_purchase_timestamp", "max"),
        frequency=("order_id", "nunique"),
        monetary=("price", "sum"),
    ).reset_index()
    rfm["recency"] = (snapshot - rfm["last_purchase"]).dt.days

    rfm["R"] = pd.qcut(rfm["recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.cut(rfm["frequency"], [0, 1, 2, np.inf], labels=[1, 2, 3]).astype(int)
    rfm["M"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

    # Aturan diperiksa berurutan, sama dengan notebook
    conditions = [
        (rfm["F"] >= 2) & (rfm["R"] >= 3),
        (rfm["F"] >= 2) & (rfm["R"] <= 2),
        (rfm["F"] == 1) & (rfm["M"] >= 4),
        (rfm["F"] == 1) & (rfm["R"] >= 4),
    ]
    names = ["Loyal", "At Risk (repeat)", "High-Value One-Timer", "New Customer"]
    rfm["segment"] = np.select(conditions, names, default="Hibernating")
    rfm["status"] = pd.cut(rfm["recency"], [0, ACTIVE_MAX, RISK_MAX, np.inf], labels=STATUS_LABELS)

    seg = rfm.groupby("segment").agg(
        customers=("customer_unique_id", "count"),
        avg_recency=("recency", "mean"),
        avg_monetary=("monetary", "mean"),
        revenue=("monetary", "sum"),
    ).reset_index()
    seg["pct_customers"] = seg["customers"] / seg["customers"].sum() * 100
    seg["pct_revenue"] = seg["revenue"] / seg["revenue"].sum() * 100

    status = rfm.groupby("status", observed=True).agg(
        customers=("customer_unique_id", "count"),
        avg_monetary=("monetary", "mean"),
        revenue=("monetary", "sum"),
    ).reset_index()
    status["status"] = status["status"].astype(str)
    status["pct_customers"] = status["customers"] / status["customers"].sum() * 100
    status["pct_revenue"] = status["revenue"] / status["revenue"].sum() * 100

    # Pembeli yang kembali minimal 1 hari setelah order sebelumnya
    # (order ulang dalam hitungan jam kemungkinan belanja yang terpecah)
    oc = (df.drop_duplicates("order_id")[["customer_unique_id", "order_purchase_timestamp"]]
          .sort_values(["customer_unique_id", "order_purchase_timestamp"]))
    oc["gap"] = oc.groupby("customer_unique_id")["order_purchase_timestamp"].diff().dt.days
    returned = oc.groupby("customer_unique_id")["gap"].max().gt(0).sum()

    return {
        "n_customers": len(rfm),
        "returned_pct": returned / len(rfm) * 100,
        "avg_monetary": rfm["monetary"].mean(),
        "seg": seg,
        "status": status,
        "crosstab": pd.crosstab(rfm["segment"], rfm["status"]),
    }


# ----------------------------------------------------------------------------
# Data, judul, dan filter
# ----------------------------------------------------------------------------
items_all, orders_all = load_items(), load_orders()
min_d = items_all["order_purchase_timestamp"].min().normalize()
max_d = items_all["order_purchase_timestamp"].max().normalize()

head_l, head_r = st.columns([3, 1.4], gap="large")
with head_l:
    st.title("Dashboard E-Commerce")
    st.caption("Penjualan, pengiriman, dan perilaku pelanggan dari order yang berhasil terkirim. "
               "Nilai dalam Real Brasil (R\\$), dihitung dari harga barang tanpa ongkos kirim.")
with head_r:
    picked = st.date_input("Rentang waktu", value=(min_d.date(), max_d.date()),
                           min_value=min_d.date(), max_value=max_d.date())

if not isinstance(picked, (tuple, list)) or len(picked) != 2:
    st.info("Pilih tanggal akhir di kalender untuk menerapkan filter.")
    st.stop()

start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
items = filter_by_date(items_all, start, end)
orders = filter_by_date(orders_all, start, end)
if items.empty:
    st.warning("Tidak ada order pada rentang waktu ini. Perluas rentang tanggal.")
    st.stop()

st.markdown(
    '<div class="summary"><b>Temuan utama (seluruh periode)</b><ul>'
    "<li>18 dari 72 kategori menghasilkan 80% revenue. Kategori paling laris menurut jumlah order adalah bed_bath_table, "
    "tetapi penyumbang revenue terbesar adalah health_beauty (9,3%).</li>"
    "<li>Order yang terlambat dari estimasi (8,0%) rata-rata mendapat skor review 2,57, dibanding 4,29 pada order tepat waktu.</li>"
    "<li>97,0% pelanggan hanya membeli sekali; 53,2% pembeli bernilai tinggi yang belum kembali sudah berisiko atau tidak aktif.</li>"
    "</ul></div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Ringkasan angka
# ----------------------------------------------------------------------------
n_orders = items["order_id"].nunique()
revenue = items["price"].sum()
late_pct = orders["is_late"].mean() * 100 if len(orders) else np.nan
avg_review = orders["review_score"].mean() if len(orders) else np.nan

k1, k2, k3, k4, k5 = st.columns([1, 1.35, 1, 1, 1])
k1.metric("Total order", num(n_orders))
k2.metric("Total revenue", brl(revenue))
k3.metric("Rata-rata nilai order", brl(revenue / n_orders))
k4.metric("Order terlambat", dec(late_pct) + "%" if pd.notna(late_pct) else "-",
          help="Dihitung dari order delivered yang punya tanggal terima dan review.")
k5.metric("Rata-rata skor review", dec(avg_review, 2) if pd.notna(avg_review) else "-",
          help="Skala 1-5, dihitung dari order delivered yang punya tanggal terima dan review.")

st.write("")
tab_sales, tab_ship, tab_cust = st.tabs(["Penjualan", "Pengiriman dan review", "Pelanggan"])

# ----------------------------------------------------------------------------
# Tab 1: Penjualan
# ----------------------------------------------------------------------------
with tab_sales:
    left, right = st.columns([3, 2], gap="large")

    with left:
        section("Tren bulanan", "Setiap titik adalah satu bulan. Bulan pertama dan terakhir bisa belum lengkap.")
        metric = st.radio("Tampilkan", ["Revenue", "Jumlah order"], horizontal=True, label_visibility="collapsed")
        monthly = (
            items.assign(month=items["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp())
            .groupby("month").agg(orders=("order_id", "nunique"), revenue=("price", "sum")).reset_index()
        )
        monthly["label"] = monthly["month"].map(bulan_id)
        ycol, ylabel = ("revenue", "Revenue (R$)") if metric == "Revenue" else ("orders", "Jumlah order")
        fig = px.line(monthly, x="month", y=ycol, markers=True, custom_data=["label"])
        fig.update_traces(line_color=ACCENT, line_width=3, marker_size=7,
                          hovertemplate="%{customdata[0]}<br>" + ylabel + ": %{y:,.0f}<extra></extra>")
        step = max(1, math.ceil(len(monthly) / 10))
        ticks = list(monthly["month"].iloc[::step])
        fig.update_xaxes(tickvals=ticks, ticktext=[bulan_id(t) for t in ticks], showgrid=False)
        st.plotly_chart(style(fig))
        peak = monthly.loc[monthly[ycol].idxmax()]
        peak_val = brl(peak[ycol]) if metric == "Revenue" else num(peak[ycol]) + " order"
        takeaway(f"Puncak {metric.lower()} terjadi pada <b>{bulan_id(peak['month'])}</b> ({peak_val}).")

    with right:
        section("10 state teratas", "Persentase dari total revenue.")
        state = items.groupby("customer_state", observed=True).agg(
            revenue=("price", "sum"), orders=("order_id", "nunique")).reset_index()
        state["customer_state"] = state["customer_state"].astype(str)
        state["share"] = state["revenue"] / state["revenue"].sum() * 100
        top_state = state.nlargest(10, "revenue").sort_values("revenue")
        fig = px.bar(top_state, x="share", y="customer_state", orientation="h", custom_data=["revenue", "orders"],
                     text=top_state["share"].map(lambda v: dec(v) + "%"))
        fig.update_traces(marker_color=ACCENT, textposition="outside",
                          hovertemplate="%{y}<br>Revenue: R$ %{customdata[0]:,.0f}<br>Order: %{customdata[1]:,.0f}<extra></extra>")
        fig.update_xaxes(visible=False, range=[0, top_state["share"].max() * 1.25])
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(style(fig, height=360))
        best_state = top_state.iloc[-1]
        top3 = state.nlargest(3, "revenue")["share"].sum()
        takeaway(f"<b>{best_state['customer_state']}</b> menyumbang {dec(best_state['share'])}% revenue; "
                 f"tiga state teratas bersama-sama {dec(top3)}%.")

    st.divider()
    section("Kategori produk",
            "Label di ujung batang menunjukkan kontribusi kategori terhadap total revenue, apa pun urutan yang dipilih.")
    c1, c2 = st.columns(2, gap="large")
    sort_by = c1.radio("Peringkat berdasarkan", ["Revenue", "Jumlah order"], horizontal=True)
    top_n = c2.slider("Jumlah kategori", 5, 15, 10)

    cat = items.groupby("category", observed=True).agg(
        orders=("order_id", "nunique"), revenue=("price", "sum")).reset_index()
    cat["category"] = cat["category"].astype(str)
    cat["share"] = cat["revenue"] / cat["revenue"].sum() * 100
    key = "revenue" if sort_by == "Revenue" else "orders"
    top = cat.nlargest(top_n, key).sort_values(key)

    fig = px.bar(top, x=key, y="category", orientation="h", custom_data=["orders", "revenue", "share"],
                 text=top["share"].map(lambda v: dec(v) + "%"))
    fig.update_traces(marker_color=ACCENT, textposition="outside",
                      hovertemplate="%{y}<br>Order: %{customdata[0]:,.0f}<br>Revenue: R$ %{customdata[1]:,.0f}"
                                    "<br>Kontribusi revenue: %{customdata[2]:.1f}%<extra></extra>")
    fig = style(fig, height=max(300, 30 * top_n + 90))
    fig.update_xaxes(title="Revenue (R$)" if key == "revenue" else "Jumlah order unik",
                     range=[0, top[key].max() * 1.15], gridcolor="rgba(128,128,128,.18)")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig)
    best_cat = top.iloc[-1]
    takeaway(f"<b>{best_cat['category']}</b> ada di peringkat teratas ({dec(best_cat['share'])}% dari total revenue). "
             f"{top_n} kategori ini bersama-sama menyumbang <b>{dec(top['share'].sum())}%</b> revenue.")

    with st.expander("Temuan dari analisis penuh (seluruh periode)"):
        st.markdown(
            "- Total revenue sekitar R\\$13,2 juta dari 72 kategori; sepuluh kategori teratas menyumbang 62,4%.\n"
            "- watches_gifts di posisi ke-2 revenue meski di luar 5 besar jumlah order, karena nilai rata-rata per order "
            "sekitar R\\$212, hampir dua kali bed_bath_table (sekitar R\\$110).\n"
            "- SP menyumbang 38,3% revenue; tiga state teratas (SP, RJ, MG) 63,3%. Nilai per order di SP justru paling rendah "
            "di antara 10 state teratas, sehingga dominasinya datang dari volume."
        )

# ----------------------------------------------------------------------------
# Tab 2: Pengiriman dan review
# ----------------------------------------------------------------------------
with tab_ship:
    o = orders.dropna(subset=["delivery_days", "review_score"]).copy()
    if o.empty:
        st.info("Tidak ada order dengan data pengiriman dan review pada rentang ini.")
    else:
        o["delivery_bin"] = pd.cut(o["delivery_days"], [0, 7, 14, 21, np.inf], labels=BIN_LABELS)
        o["low_score"] = o["review_score"] <= 2

        by_bin = o.groupby("delivery_bin", observed=True).agg(
            n=("order_id", "count"), avg_score=("review_score", "mean"), pct_low=("low_score", "mean")).reset_index()
        by_bin["pct_low"] *= 100
        by_bin["delivery_bin"] = by_bin["delivery_bin"].astype(str)

        by_late = o.groupby("is_late").agg(
            n=("order_id", "count"), avg_score=("review_score", "mean"), pct_low=("low_score", "mean")).reset_index()
        by_late["pct_low"] *= 100
        by_late["status"] = by_late["is_late"].map({False: "Tepat waktu", True: "Terlambat"})

        hover = ("%{x}<br>Rata-rata skor: %{y:.2f}<br>Jumlah order: %{customdata[0]:,.0f}"
                 "<br>Review rendah (1-2): %{customdata[1]:.1f}%<extra></extra>")

        a, b = st.columns(2, gap="large")
        with a:
            section("Skor review menurut durasi pengiriman",
                    "Durasi dihitung dari tanggal order sampai barang diterima. Skor 1-5, makin tinggi makin puas.")
            fig = px.bar(by_bin, x="delivery_bin", y="avg_score", custom_data=["n", "pct_low"],
                         text=by_bin["avg_score"].map(lambda v: dec(v, 2)))
            fig.update_traces(marker_color=ACCENT, textposition="outside", hovertemplate=hover)
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(range=[1, 5])
            st.plotly_chart(style(fig))
        with b:
            section("Tepat waktu vs terlambat",
                    "Terlambat berarti barang tiba setelah tanggal estimasi yang dijanjikan.")
            fig = px.bar(by_late, x="status", y="avg_score", custom_data=["n", "pct_low"],
                         text=by_late["avg_score"].map(lambda v: dec(v, 2)))
            fig.update_traces(marker_color=ACCENT, textposition="outside", hovertemplate=hover)
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(range=[1, 5])
            st.plotly_chart(style(fig))

        scores = by_late.set_index("status")["avg_score"]
        if {"Terlambat", "Tepat waktu"} <= set(scores.index):
            takeaway(f"Order yang terlambat rata-rata mendapat skor <b>{dec(scores['Terlambat'], 2)}</b>, "
                     f"dibanding <b>{dec(scores['Tepat waktu'], 2)}</b> untuk order tepat waktu.")

        with st.expander("Lihat jumlah order dan persentase review rendah"):
            detail = pd.concat([
                by_bin.rename(columns={"delivery_bin": "kelompok"}),
                by_late.rename(columns={"status": "kelompok"}).drop(columns="is_late"),
            ]).rename(columns={"n": "jumlah order", "avg_score": "rata-rata skor", "pct_low": "% review 1-2"})
            detail["jumlah order"] = detail["jumlah order"].map(num)
            detail["rata-rata skor"] = detail["rata-rata skor"].map(lambda v: dec(v, 2))
            detail["% review 1-2"] = detail["% review 1-2"].map(dec)
            st.dataframe(detail, hide_index=True)

    with st.expander("Temuan dari analisis penuh (seluruh periode)"):
        st.markdown(
            "- Skor turun dari 4,42 (≤7 hari) menjadi 3,12 (>21 hari); review rendah naik dari 7,4% menjadi 38,2%.\n"
            "- Keterlambatan dari estimasi punya efek terbesar: skor 2,57 (terlambat) vs 4,29 (tepat waktu). "
            "Korelasi Spearman keseluruhan lemah (-0,235) karena efeknya terkonsentrasi pada pengiriman yang sangat lama atau terlambat.\n"
            "- Pengiriman antar-state (64% dari pengiriman) rata-rata 15,1 hari dan 9,2% terlambat, "
            "dibanding 7,9 hari dan 6,0% untuk satu state.\n"
            "- Ini hubungan (korelasi), bukan bukti sebab-akibat."
        )

# ----------------------------------------------------------------------------
# Tab 3: Pelanggan
# ----------------------------------------------------------------------------
with tab_cust:
    res = compute_rfm(start, end)
    if res is None:
        st.info("Rentang waktu terlalu pendek untuk analisis pelanggan. Pilih rentang yang lebih panjang.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Pelanggan unik", num(res["n_customers"]))
        m2.metric("Pembeli yang kembali", dec(res["returned_pct"], 2) + "%",
                  help="Pelanggan yang membeli lagi minimal 1 hari setelah order sebelumnya.")
        m3.metric("Rata-rata belanja per pelanggan", brl(res["avg_monetary"]))
        st.write("")

        seg = res["seg"].copy()
        status = res["status"]
        a, b = st.columns(2, gap="large")

        with a:
            section("Segmen pelanggan (RFM)",
                    "Pelanggan dikelompokkan menurut kebaruan, frekuensi, dan nilai belanja. "
                    "Bandingkan % pelanggan dengan % revenue di tiap segmen.")
            long = seg.melt(id_vars="segment", value_vars=["pct_customers", "pct_revenue"], var_name="ukuran", value_name="pct")
            long["ukuran"] = long["ukuran"].map({"pct_customers": "% pelanggan", "pct_revenue": "% revenue"})
            fig = px.bar(long, x="segment", y="pct", color="ukuran", barmode="group",
                         category_orders={"segment": SEGMENT_ORDER},
                         color_discrete_map={"% pelanggan": MUTED, "% revenue": ACCENT})
            fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>")
            fig.update_xaxes(showgrid=False)
            st.plotly_chart(style(fig, legend=True))

        with b:
            section("Status pelanggan",
                    f"Waktu sejak pembelian terakhir. Aktif ≤{ACTIVE_MAX} hari, tidak aktif >{RISK_MAX} hari.")
            if len(status) < 2:
                st.info(f"Status berisiko dan tidak aktif baru muncul jika rentang waktu lebih dari {ACTIVE_MAX} hari. "
                        "Perluas rentang tanggal.")
            else:
                fig2 = px.bar(status, x="status", y="pct_customers", custom_data=["avg_monetary", "pct_revenue"],
                              text=status["pct_customers"].map(lambda v: dec(v) + "%"))
                fig2.update_traces(marker_color=ACCENT, textposition="outside",
                                   hovertemplate="%{x}<br>% pelanggan: %{y:.1f}%<br>% revenue: %{customdata[1]:.1f}%"
                                                 "<br>Rata-rata belanja: R$ %{customdata[0]:,.0f}<extra></extra>")
                fig2.update_xaxes(showgrid=False)
                fig2.update_yaxes(range=[0, max(status["pct_customers"]) * 1.2])
                st.plotly_chart(style(fig2))

        hv = seg.set_index("segment")
        if "High-Value One-Timer" in hv.index:
            r = hv.loc["High-Value One-Timer"]
            takeaway(f"<b>{dec(r['pct_customers'])}%</b> pelanggan adalah pembeli sekali dengan nilai belanja tinggi, "
                     f"dan mereka menyumbang <b>{dec(r['pct_revenue'])}%</b> revenue.")

        with st.expander("Lihat tabel segmen dan status"):
            table = seg.sort_values("pct_revenue", ascending=False).rename(columns={
                "segment": "segmen", "customers": "pelanggan", "avg_recency": "rata-rata recency (hari)",
                "avg_monetary": "rata-rata belanja (R$)", "revenue": "revenue (R$)",
                "pct_customers": "% pelanggan", "pct_revenue": "% revenue"})
            for col in ["pelanggan", "rata-rata belanja (R$)", "revenue (R$)"]:
                table[col] = table[col].map(num)
            table["rata-rata recency (hari)"] = table["rata-rata recency (hari)"].map(lambda v: dec(v, 0))
            for col in ["% pelanggan", "% revenue"]:
                table[col] = table[col].map(dec)
            st.dataframe(table, hide_index=True)
            st.caption("Segmen dan status pelanggan (jumlah pelanggan):")
            ct = res["crosstab"].apply(lambda col: col.map(num))
            ct.columns = [str(c) for c in ct.columns]
            st.dataframe(ct)

    with st.expander("Temuan dari analisis penuh (seluruh periode)"):
        st.markdown(
            "- 97,0% dari 93.358 pelanggan hanya membeli sekali. Hanya 2,13% yang kembali minimal 1 hari setelah order sebelumnya; "
            "810 pelanggan lain hanya punya order ulang dalam hitungan jam (kemungkinan belanja yang terpecah).\n"
            "- High-Value One-Timer (37,7% pelanggan) menyumbang 71,2% revenue; 53,2% di antaranya sudah berisiko atau tidak aktif. "
            "Porsi revenue yang besar sebagian merupakan akibat definisi segmen.\n"
            f"- Batas status ({ACTIVE_MAX} dan {RISK_MAX} hari) berasal dari persentil ke-80 dan ke-90 jeda pembelian ulang, "
            "dihitung hanya dari pelanggan yang akhirnya kembali, sehingga dibaca sebagai perkiraan.\n"
            "- Kampanye win-back adalah usulan; data tidak memuat informasi promo sehingga efeknya tidak dapat diukur."
        )

st.divider()
st.caption("Sumber data: E-Commerce Public Dataset (order berstatus delivered)  ·  Dibuat oleh Abdul Azizur Rokhman  ·  Github : Aizuro")