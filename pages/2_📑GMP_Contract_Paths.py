import streamlit as st
import pandas as pd
import requests
import snowflake.connector
import plotly.graph_objects as go
import plotly.express as px
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import time

# --- Page Config: Tab Title & Icon -------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Axelar: Crosschain Interoperability Overview",
    page_icon="https://axelarscan.io/logos/logo.png",
    layout="wide"
)

# --- Sidebar Footer Slightly Left-Aligned ---
st.sidebar.markdown(
    """
    <style>
    .sidebar-footer {
        position: fixed;
        bottom: 20px;
        width: 250px;
        font-size: 13px;
        color: gray;
        margin-left: 5px; # -- MOVE LEFT
        text-align: left;  
    }
    .sidebar-footer img {
        width: 16px;
        height: 16px;
        vertical-align: middle;
        border-radius: 50%;
        margin-right: 5px;
    }
    .sidebar-footer a {
        color: gray;
        text-decoration: none;
    }
    </style>

    <div class="sidebar-footer">
        <div>
            <a href="https://x.com/axelar" target="_blank">
                <img src="https://img.cryptorank.io/coins/axelar1663924228506.png" alt="Axelar Logo">
                Powered by Axelar
            </a>
        </div>
        <div style="margin-top: 5px;">
            <a href="https://x.com/0xeman_raz" target="_blank">
                <img src="https://pbs.twimg.com/profile_images/1841479747332608000/bindDGZQ_400x400.jpg" alt="Eman Raz">
                Built by Eman Raz
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
# --- Title --------------------------------------------------------------------------------------------
st.title("📑 GMP Contracts")

# --- Fetch Data --------------------------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_gmp_data():
    url = "https://api.axelarscan.io/gmp/GMPStatsByContracts"
    response = requests.get(url)
    data = response.json()
    contracts_list = []
    for chain in data.get("chains", []):
        for contract in chain.get("contracts", []):
            contracts_list.append({
                "Chain": chain["key"],
                "Contract": contract["key"],
                "Number of Transactions": contract["num_txs"],
                "Volume": contract["volume"]
            })
    df = pd.DataFrame(contracts_list)
    return df

df = fetch_gmp_data()

# --- KPI Row ------------------------------------------------------------------------------------------
num_contracts = df["Contract"].nunique()  
avg_volume = df["Volume"].mean()
avg_txns = round(df["Number of Transactions"].mean())  

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Number of Contracts", f"{num_contracts}")
kpi2.metric("Avg Volume per Contract", f"{avg_volume:.1f}")
kpi3.metric("Avg Transaction per Contract", f"{avg_txns}")

# --- Contracts Table ----------------------------------------------------------------------------------
st.subheader("📋 Contracts Overview")
df_table_sorted = df.sort_values(by="Number of Transactions", ascending=False).copy()

df_table_sorted.index = range(1, len(df_table_sorted) + 1)
st.dataframe(df_table_sorted, use_container_width=True)

# --- Distribution Pie Charts ---------------------------------------------------------------------------
st.subheader("📊 Distribution of Contracts")

# Distribution by Number of Transactions
bins_txns = [0,1,10,50,100,1000,10000,float('inf')]
labels_txns = ["1 Txn", "2-10 Txns", "11-50 Txns", "51-100 Txns", "101-1000 Txns", "1001-10000 Txns", ">10000 Txns"]
df["Txn Category"] = pd.cut(df["Number of Transactions"], bins=bins_txns, labels=labels_txns, right=True, include_lowest=True)
txn_distribution = df["Txn Category"].value_counts().reindex(labels_txns)

# Distribution by Volume
bins_volume = [0,1,10,100,1000,10000,100000,1000000,float('inf')]
labels_volume = ["V<=1$", "1<V<=10$", "10<V<=100$", "100<V<=1k$", "1k<V<=10k$", "10k<V<=100k$", "100k<V<=1M$", ">1M$"]
df["Volume Category"] = pd.cut(df["Volume"], bins=bins_volume, labels=labels_volume, right=True, include_lowest=True)
volume_distribution = df["Volume Category"].value_counts().reindex(labels_volume)

col1, col2 = st.columns(2)

with col1:
    fig_pie_txn = px.pie(
        names=txn_distribution.index,
        values=txn_distribution.values,
        title="Distribution of Contracts by Number of Transactions"
    )
    st.plotly_chart(fig_pie_txn, use_container_width=True)

with col2:
    fig_pie_volume = px.pie(
        names=volume_distribution.index,
        values=volume_distribution.values,
        title="Distribution of Contracts by Volume"
    )
    st.plotly_chart(fig_pie_volume, use_container_width=True)

# --- Row 4 --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# === Left function ==================================
@st.cache_data
def load_event_txn():

    query = f"""
    with tab1 as (
select event, id, data:call.transaction.from::STRING as user, CASE 
      WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
      WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
      ELSE NULL
    END AS amount_usd
from axelar.axelscan.fact_gmp)
select event as "Event", count(distinct id) as "Txns count"
from tab1
group by 1
order by 2 desc 

    """

    df = pd.read_sql(query, conn)
    return df
  
# === right function ==============================
@st.cache_data
def load_event_route_data():

    query = f"""
    with tab1 as (
select event, id, data:call.transaction.from::STRING as user, CASE 
      WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
      WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
      ELSE NULL
    END AS amount_usd,
    LOWER(data:call.chain::STRING) AS source_chain,
    LOWER(data:call.returnValues.destinationChain::STRING) AS destination_chain
from axelar.axelscan.fact_gmp)

select source_chain || '➡' || destination_chain as "Route", 
count(distinct id) as "🔗Txns count", 
count(distinct user) as "👥Users Count", 
round(sum(amount_usd),1) as "💸Txns Value (USD)"
from tab1
where event in ('ContractCall','ContractCallWithToken')
group by 1
order by 2 desc 

    """

    df = pd.read_sql(query, conn)
    return df

# === Load Data ===================================================
df_event_txn = load_event_txn()
df_event_route_data = load_event_route_data()
# === Tables =====================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown("<h5 style='text-align:center; font-size:16px;'>Number of GMP Transactions By Events</h5>", unsafe_allow_html=True)
    df_display = df_event_txn.copy()
    df_display.index = df_display.index + 1
    df_display = df_display.applymap(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
    styled_df = df_display.style.set_properties(**{"background-color": "#c9fed8"})
    st.dataframe(styled_df, use_container_width=True, height=320)   

with col2:
    st.markdown("<h5 style='text-align:center; font-size:16px;'>Contract Calls Across Chains (Sorted by Txns Count)</h5>", unsafe_allow_html=True)
    df_display = df_event_route_data.copy()
    df_display.index = df_display.index + 1
    df_display = df_display.applymap(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
    styled_df = df_display.style.set_properties(**{"background-color": "#c9fed8"})
    st.dataframe(styled_df, use_container_width=True, height=320)

# --- Row 5 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# === Left function ==================================
@st.cache_data
def load_active_contracts():

    query = f"""
    select date_trunc('month',created_at) as "Date", 
    count(distinct call:returnValues:destinationContractAddress) as "Number of Destination Contracts"
    from axelar.axelscan.fact_gmp
    group by 1
    order by 1

    """

    df = pd.read_sql(query, conn)
    return df
  
# === right function ==============================
@st.cache_data
def load_new_contracts():

    query = f"""
    with tab1 as (
select call:returnValues:destinationContractAddress as "Destination Contract", 
min(created_at::date) as FIRST_TX
from axelar.axelscan.fact_gmp
group by 1)

select date_trunc('month',first_tx) as "Date", count(distinct "Destination Contract") as "New Contracts", 
sum("New Contracts") over (order by "Date" asc) as "Total New Contracts"
from tab1
group by 1
order by 1

    """

    df = pd.read_sql(query, conn)
    return df

# === Load Data ===================================================
df_active_contracts = load_active_contracts()
df_new_contracts = load_new_contracts()
# === Tables =====================================================
col1, col2 = st.columns(2)

with col1:
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=df_new_contracts["Date"], y=df_new_contracts["New Contracts"], name="New Contracts", yaxis="y1", marker_color="#ff7f27"))
    fig1.add_trace(go.Scatter(x=df_new_contracts["Date"], y=df_new_contracts["Total New Contracts"], name="Total New Contracts", mode="lines", yaxis="y2", 
                              line=dict(color="#0ed145", width=2, dash="solid")))
    fig1.update_layout(title="Number of New Destination Contracts Over Time", yaxis=dict(title="contract count"), yaxis2=dict(title="contract count", 
                            overlaying="y", side="right"), barmode="group", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig_contract = px.scatter(df_active_contracts, x="Date", y="Number of Destination Contracts", size="Number of Destination Contracts", color="Number of Destination Contracts", 
                              color_continuous_scale="Viridis", title="Number of Active Destination Contracts Over Time", 
                              labels={"Number of Destination Contracts": "number of contracts", "Date":""})
    st.plotly_chart(fig_contract)
