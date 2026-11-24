"""Stylesheet loading and the page header."""

from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_stylesheet() -> None:
    for css_path in (REPO_ROOT / "assets" / "styles.css", REPO_ROOT / "style.css"):
        if css_path.exists():
            st.markdown(
                f"<style>{css_path.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True,
            )
            return
    st.warning("CSS ফাইল পাওয়া যায়নি। assets/styles.css অথবা style.css ফাইলটি রাখুন।")


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-brand">
                <span class="hero-flower" aria-hidden="true">🌸</span>
                <span class="hero-title">মাতৃকণ্ঠ</span>
            </div>
            <div class="hero-tagline">
                আপনার কথা শুনি, ঝুঁকি বুঝি, সাহায্যের পথ দেখাই
            </div>
            <div class="hero-subtitle">
                Bangla Voice-based Maternal Risk Screener
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.warning(
        "এটি পরীক্ষামূলক স্ক্রিনিং সহায়ক—রোগ নির্ণয় "
        "বা চিকিৎসার বিকল্প নয়। জরুরি সমস্যা হলে "
        "AI-এর উত্তরের অপেক্ষা না করে হাসপাতালে যান।"
    )
