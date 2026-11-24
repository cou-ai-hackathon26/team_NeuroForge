"""Tab 2: health-worker dashboard with counts, table, and CSV export."""

import pandas as pd
import streamlit as st

from modules.database import export_csv, list_assessments

RISK_COLUMNS = [("HIGH", "উচ্চ"), ("MODERATE", "মাঝারি"), ("LOW", "কম"), ("UNKNOWN", "অজানা")]


def render_dashboard() -> None:
    st.subheader("স্বাস্থ্যকর্মী ড্যাশবোর্ড")

    records = list_assessments()
    if not records:
        st.info(
            "এখনো কোনো মূল্যায়ন সংরক্ষণ করা হয়নি। "
            "নতুন মূল্যায়ন সম্পন্ন করে এখানে রেকর্ড দেখতে পারবেন।"
        )
        return

    df = pd.DataFrame(records)

    st.markdown("#### মূল্যায়নের সারসংক্ষেপ")
    for column, (level, label) in zip(st.columns(len(RISK_COLUMNS)), RISK_COLUMNS):
        count = int((df["risk_level"] == level).sum()) if "risk_level" in df.columns else 0
        column.metric(label, count)

    st.divider()
    st.markdown("#### সংরক্ষিত মূল্যায়ন")
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button(
        label="📥 CSV ডাউনলোড করুন",
        data=export_csv(),
        file_name="matrikontho_cases.csv",
        mime="text/csv",
        width="stretch",
    )
