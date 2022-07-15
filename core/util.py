import streamlit as st
import pandas as pd
import requests

from subgrounds import Subgrounds
from subgrounds.subgraph.subgraph import Subgraph
from subgrounds.subgraph.object import Object as QueryObject
from flatdict import FlatDict

# TODO break this out into multiple files for error/ util methods
class NoDataRetrievedError(Exception):
    """Raised when no data is retrieved from Subgraph"""

    pass


def get_metrics_fields(url: str) -> list[str]:
    sg = Subgrounds()
    subgraph: Subgraph = sg.load_subgraph(url)
    subqueries: list[str] = subgraph.Query.__dict__.keys()
    return [x for x in subqueries if x.endswith("DailySnapshots")]


# Reference Subgraphs
def get_reference_subgraphs() -> dict[str, QueryObject]:
    sg = Subgrounds()
    return {
        "exchanges": sg.load_subgraph(),
        "lending_protocols": sg.load_subgraph(
            "https://thegraph.com/hosted-service/subgraph/messari/compound-ethereum"
        ),
        "vaults": sg.load_subgraph(),
    }


@st.cache
def get_subgraphs_df() -> pd.DataFrame:
    subgraphs = requests.get("https://subgraphs.messari.io/deployments.json")
    subgraphs_data = subgraphs.json()
    flat = dict(FlatDict(subgraphs_data, delimiter="."))
    rows = []
    for f, v in flat.items():
        subgraph_type, protocol, network = f.split(".")
        rows.append(
            {
                "subgraph_type": subgraph_type,
                "network": network,
                "protocol": protocol,
                "deployment": f"{protocol}-{network}",
                "url": v,
            }
        )
    return pd.DataFrame(rows)


@st.cache
def retrieve_deployment_df(
    url: str, start_epoch: int, end_epoch: int, snapshot: str, limit: int = 10000
) -> pd.DataFrame:
    sg = Subgrounds()
    subgraph = sg.load_subgraph(url)
    subquery = getattr(subgraph.Query, snapshot)
    query = subquery(
        orderBy=subquery.timestamp,
        orderDirection="desc",
        first=limit,
        where={"timestamp_lte": int(end_epoch), "timestamp_gte": int(start_epoch)},
    )

    fields: list[str] = list(query.__dict__.keys())
    fields_to_ignore: list[str] = ["id", "protocol", "blockNumber", "timestamp"]
    metrics = [x for x in fields if x not in fields_to_ignore and not x.startswith("_")]

    # Pre-fetch all metrics for given snapshot, leverage caching
    df = sg.query_df([query.timestamp, *(getattr(query, metric) for metric in metrics)])

    # Raise error if no data
    if df.empty:
        raise NoDataRetrievedError("Data does not exist")

    # Format redundant column naming
    df.rename(columns=lambda c: c.split("_")[1], inplace=True)

    # Parse timestamp and re-index
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df["timestamp"] = df["timestamp"].apply(lambda x: x.date())
    return df.set_index("timestamp")
