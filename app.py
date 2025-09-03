import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from db_config import get_connection  # External DB config

def fetch_category_data(start_date, end_date):
    conn = get_connection()
    query = f"""
        SELECT Conceptual_Group, category,
               SUM(est_earnings) AS total_earnings,
               AVG(est_earnings) AS avg_earnings,
               SUM(uniq_impr) AS total_impressions,
               SUM(est_earnings)/NULLIF(SUM(uniq_impr), 0) AS EPI,
               SUM(paid_clicks)/NULLIF(SUM(uniq_impr), 0) AS CTR
        FROM team_block_stats
        WHERE eventDate BETWEEN '{start_date}' AND '{end_date}'
          AND est_earnings > 0
        GROUP BY category, Conceptual_Group
        ORDER BY total_earnings DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# --- Fetch all category-partner mapping ---
def fetch_raw_data(start_date, end_date):
    conn = get_connection()
    query = f"""
        SELECT DISTINCT category, partner
        FROM team_block_stats
        WHERE eventDate BETWEEN '{start_date}' AND '{end_date}'
          AND est_earnings > 0
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# --- Fetch category earnings for selected partner ---
def fetch_partner_category_data(start_date, end_date, partner):
    conn = get_connection()
    query = f"""
        SELECT category,
               SUM(est_earnings) AS total_earnings
        FROM team_block_stats
        WHERE eventDate BETWEEN '{start_date}' AND '{end_date}'
          AND partner = '{partner}'
          AND est_earnings > 0
          AND category IS NOT NULL
        GROUP BY category
        HAVING SUM(est_earnings) > 0
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# --- Fetch partner's Conceptual_Groups ---
def fetch_partner_conceptual_groups(start_date, end_date, partner):
    conn = get_connection()
    query = f"""
        SELECT DISTINCT Conceptual_Group
        FROM team_block_stats
        WHERE eventDate BETWEEN '{start_date}' AND '{end_date}'
          AND partner = '{partner}'
          AND est_earnings > 0
          AND Conceptual_Group IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df["Conceptual_Group"].dropna().unique().tolist()


# --- Streamlit App ---
st.set_page_config("📊 Partner Category Recommender", layout="wide")
st.title("📊 Category Recommendation Dashboard")

# --- Sidebar filters ---
st.sidebar.header("📅 Filters")
default_start = (datetime.now() - timedelta(days=7)).date()
default_end = datetime.now().date()

start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)

if start_date > end_date:
    st.sidebar.error("⚠️ Start date cannot be after end date.")
    st.stop()

# --- Load data with spinner ---
with st.spinner("Fetching data..."):
    category_df = fetch_category_data(start_date, end_date)
    raw_df = fetch_raw_data(start_date, end_date)

if category_df.empty:
    st.warning("No data available for the selected date range.")
    st.stop()

# --- Partner dropdown ---
partner_list = sorted(raw_df["partner"].dropna().unique().tolist())
selected_partner = st.sidebar.selectbox("🤝 Select Partner", partner_list)

# --- Clean category_df ---
category_df = category_df.dropna(subset=["category", "total_earnings"])
category_df = category_df[category_df["category"].str.lower() != "none"]

# --- Summary Metrics ---
# st.subheader("📌 Summary")
col1, col2, col3 = st.columns(3)
col1.metric("Total Earnings", f"${category_df['total_earnings'].sum():,.2f}")
col2.metric("Total Impressions", f"{int(category_df['total_impressions'].sum()):,}")
col3.metric("Partners", f"{raw_df['partner'].nunique():,}")

# --- Tabs for better UI ---
tab1, tab2, tab3 = st.tabs(["📂 Overall Categories", "🧠 Recommendations", f"📈 {selected_partner}'s Usage"])

with tab1:
    st.subheader("📂 Category-Level Performance")
    # Round all numeric columns to 2 decimal places
    category_df = category_df.round(2)
    st.dataframe(category_df.reset_index(drop=True), use_container_width=True, hide_index=True)
    st.download_button("📥 Download Full Category Data", category_df.to_csv(index=False), "category_performance.csv")

    # --- Toggle for chart metric ---
    metric_choice = st.radio(
        "Select metric for Top 15 Categories:",
        ["Total Earnings", "Average Earnings"],
        horizontal=True
    )

    # --- Determine column and title based on toggle ---
    y_col = "total_earnings" if metric_choice == "Total Earnings" else "avg_earnings"
    chart_title = f"Top 15 Categories by {metric_choice}"

    # --- Visualization: Top 15 Categories ---
    top15 = category_df.sort_values(y_col, ascending=False).head(20)
    fig_top = px.bar(
        top15,
        x="category",
        y=y_col,
        color=y_col,
        color_continuous_scale="blues",
        title=chart_title,
        hover_data=["Conceptual_Group", "avg_earnings", "total_earnings", "EPI", "CTR"]
    )
    st.plotly_chart(fig_top, use_container_width=True)

# --- Fetch partner category and conceptual group data ---
partner_used_df = fetch_partner_category_data(start_date, end_date, selected_partner)
partner_categories = partner_used_df["category"].tolist()
in_domain_groups = fetch_partner_conceptual_groups(start_date, end_date, selected_partner)

# --- Recommendations ---
top_categories = category_df.sort_values("total_earnings", ascending=False).head(30)["category"].tolist()
recommended = [cat for cat in top_categories if cat not in partner_categories]
recommended_df = category_df[category_df["category"].isin(recommended)]
recommended_df["Domain"] = recommended_df["Conceptual_Group"].apply(
    lambda x: "In-Domain" if x in in_domain_groups else "Out-of-Domain"
)

with tab2:
    st.subheader("🧠 Recommended Categories for Partner (Domain-Aware)")
    if not recommended_df.empty:
        st.dataframe(recommended_df[["Conceptual_Group", "category", "total_earnings", "avg_earnings", "Domain"]],
                     use_container_width=True)
        st.download_button("📥 Download Recommendations", recommended_df.to_csv(index=False), "recommendations.csv")

        # --- Toggle for recommendation charts ---
        rec_metric_choice = st.radio(
            "Select metric for Recommendation Charts:",
            ["Total Earnings", "Average Earnings"],
            horizontal=True
        )

        # --- Determine column and title based on toggle ---
        rec_y_col = "total_earnings" if rec_metric_choice == "Total Earnings" else "avg_earnings"

        # --- Visuals split by domain ---
        for domain_type in ["In-Domain", "Out-of-Domain"]:
            domain_df = recommended_df[recommended_df["Domain"] == domain_type]
            if not domain_df.empty:
                fig = px.bar(
                    domain_df.sort_values(rec_y_col, ascending=False),
                    x="category", y=rec_y_col,
                    title=f"{domain_type} Category {rec_metric_choice}",
                    labels={rec_y_col: rec_metric_choice},
                    color=rec_y_col,
                    color_continuous_scale="greens" if domain_type == "In-Domain" else "reds",
                    hover_data=["Conceptual_Group", "total_earnings", "avg_earnings"]
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"✅ Partner **{selected_partner}** already uses all top categories.")


# --- Partner Usage ---
with tab3:

    # --- In-Domain Conceptual Groups Summary Table ---
    st.markdown("### ✅ Partner's In-Domain Conceptual Groups")
    if in_domain_groups:
        in_domain_data = pd.DataFrame({
            "Partner": [selected_partner],
            "Conceptual_Groups": [", ".join(in_domain_groups)]
        })
        st.table(in_domain_data)
    else:
        st.warning(f"No Conceptual Groups found for partner {selected_partner} in the selected date range.")

    # --- Partner usage chart ---
    if not partner_used_df.empty:
        fig2 = px.bar(partner_used_df.sort_values("total_earnings", ascending=False),
                      x="category", y="total_earnings",
                      title=f"📂 Earnings from Categories Used by {selected_partner}",
                      labels={"total_earnings": "Total Earnings"},
                      color="total_earnings", color_continuous_scale="purples",
                      hover_data=["total_earnings"])
        st.plotly_chart(fig2, use_container_width=True)

        st.download_button("📥 Download Partner Data", partner_used_df.to_csv(index=False), f"{selected_partner}_usage.csv")
    else:
        st.warning(f"No categories found for partner {selected_partner} in the selected date range.")
