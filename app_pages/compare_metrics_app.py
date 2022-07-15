from typing import Iterable
import streamlit as st
import pandas as pd
import datetime
import plotly.express as px

from pandas_profiling import ProfileReport
from streamlit_pandas_profiling import st_profile_report

from core.util import (
    get_subgraphs_df, retrieve_deployment_df, NoDataRetrievedError,
    get_metrics_fields
)

# TODO make this more modular!
#   Maybe use a class per app?

def app() -> None:
    st.title('Subgraph Metric Comparison')

    subgraphs_df: pd.DataFrame = get_subgraphs_df()

    col1, col2, col3 = st.columns(3)
    selected_subgraph_type: str = col1.selectbox(
        'Subgraph Type',
        subgraphs_df['subgraph_type'].unique()
    )
    query = f"subgraph_type == '{selected_subgraph_type}'"

    selected_network: str = col2.selectbox(
        'Network',
        sorted(subgraphs_df.query(query)['network'].unique())
    )
    query += f" & network == '{selected_network}'"

    selected_deployment: str = col3.selectbox(
        'Deployment',
        sorted(subgraphs_df.query(query)['deployment'].unique())
    )
    query += f" & network == '{selected_network}'"

    # Need to add list of options to session state to maintain choices across different dropdowns
    if 'selected' not in st.session_state:
        st.session_state['selected'] = set()

    if st.button('Add Deployment'):
        st.session_state['selected'].add(selected_deployment)

    # Display selected deployments added via button
    selected_deployments = st.multiselect(
        'Selected',st.session_state['selected'],default=list(st.session_state['selected'])
    )
    st.session_state['selected'] = set(selected_deployments)

    deployments_to_grab: set[str] = st.session_state['selected']
    selected_deployments_df: pd.DataFrame = subgraphs_df[subgraphs_df['deployment'].isin(deployments_to_grab)]

    # Consolidatesnapshot types, to shared set across subgraph types
    snapshot_types = list()
    deployment_snapshot_types: list[str] = list()
    for row in selected_deployments_df.itertuples():
        deployment_snapshot_types.append(get_metrics_fields(row.url))

    if deployment_snapshot_types:
        snapshot_types: set[str] = set.intersection(*map(set, deployment_snapshot_types))

    # Organize with columns
    col1, col2, col3 = st.columns(3)
    now = datetime.datetime.now()
    end_val, start_val = now, now-datetime.timedelta(days=7)
    selected_end_date = col2.date_input(
        "End Date", end_val, max_value=now)
    selected_start_date = col1.date_input(
        "Start Date",start_val, max_value=now)

    if selected_end_date < selected_start_date or selected_start_date > selected_end_date:
        st.error("Date range invalid")
    start_epoch, end_epoch = selected_start_date.strftime('%s'), selected_end_date.strftime('%s')

    # Snapshot type and metric selection
    selected_snapshot = col3.selectbox(
        'Snapshot', list(snapshot_types)
    )
    if selected_snapshot not in st.session_state:
        st.session_state[selected_snapshot] = list()

    # Initialize empty selector
    # Selector doesnt populate immediately
    selected_metric = st.selectbox(
        'Metric', st.session_state[selected_snapshot],
        key='metric_selector'
    )

    dfs: list[pd.DataFrame] = list()
    for row in selected_deployments_df.itertuples():
        # TODO: Maybe can make this operation async?
        name, url = row.deployment, row.url
        try:
            retrieved_df: pd.DataFrame = retrieve_deployment_df(url, start_epoch=int(start_epoch), end_epoch=int(end_epoch), snapshot=selected_snapshot)
            if not len(st.session_state[selected_snapshot]):   
                st.session_state[selected_snapshot] = retrieved_df.columns

            # Reshape data and change column names
            if selected_metric is not None:
                selected_metric_df: pd.DataFrame = retrieved_df[[selected_metric]]
                selected_metric_df.rename(columns={selected_metric: name}, inplace=True)
                dfs.append(selected_metric_df)
        except NoDataRetrievedError:
            st.error(f'No data for {name} in between {selected_start_date} - {selected_end_date}')
            continue  
    
    # Plot dfs together
    if dfs:
        st.subheader('Results')
        result_df = pd.concat(dfs, axis=1)

        fig = px.line(result_df, markers='o')
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns([1,5])
        pagination_date = col1.date_input(
            "Timestamp", selected_start_date, max_value=selected_end_date)
        num = col1.selectbox(
        'Results',
        (10, 20, 50, 100))
        col2.table(result_df[result_df.index >= pagination_date].head(num).sort_index(ascending=True))
        
        with st.expander("Data Profiling Results"):
            pr = ProfileReport(result_df, dark_mode=True, explorative=True)
            st_profile_report(pr)