import streamlit as st

from app_pages.compare_metrics_app import app as compare_metrics_app

st.set_page_config(layout="wide")

with st.sidebar:
    add_radio = st.radio(
        "View",
        ['Compare Metrics', 'Distribution Plots']
    )

if add_radio == 'Compare Metrics':
    compare_metrics_app()