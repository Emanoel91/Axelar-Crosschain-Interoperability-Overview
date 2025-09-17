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

# --- Title & Info Messages ---------------------------------------------------------------------------------------------
st.title("📑GMP Contract Paths")

st.info("📊 Charts initially display data for a default time range. Select a custom range to view results for your desired period.")
st.info("⏳ On-chain data retrieval may take a few moments. Please wait while the results load.")

# --- Snowflake Connection ----------------------------------------------------------------------------------------
snowflake_secrets = st.secrets["snowflake"]
user = snowflake_secrets["user"]
account = snowflake_secrets["account"]
private_key_str = snowflake_secrets["private_key"]
warehouse = snowflake_secrets.get("warehouse", "")
database = snowflake_secrets.get("database", "")
schema = snowflake_secrets.get("schema", "")

private_key_pem = f"-----BEGIN PRIVATE KEY-----\n{private_key_str}\n-----END PRIVATE KEY-----".encode("utf-8")
private_key = serialization.load_pem_private_key(
    private_key_pem,
    password=None,
    backend=default_backend()
)
private_key_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

conn = snowflake.connector.connect(
    user=user,
    account=account,
    private_key=private_key_bytes,
    warehouse=warehouse,
    database=database,
    schema=schema
)

# --- Time Frame & Period Selection ----------------------------------------------------------------------------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    timeframe = st.selectbox("Select Time Frame", ["month", "week", "day"])
with col2:
    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-12-01"))
with col3:
    end_date = st.date_input("End Date", value=pd.to_datetime("2025-09-30"))

# --- Row 1 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# === Left function ==================================
@st.cache_data
def load_event_txn(start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    with tab1 as (
select event, id, data:call.transaction.from::STRING as user, CASE 
      WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
      WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
      ELSE NULL
    END AS amount_usd
from axelar.axelscan.fact_gmp
where created_at::date>='{start_str}' and created_at::date<='{end_str}')
select event as "Event", count(distinct id) as "Txns count"
from tab1
group by 1
order by 2 desc 

    """

    df = pd.read_sql(query, conn)
    return df
  
# === right function ==============================
@st.cache_data
def load_event_route_data(start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    with tab1 as (
select event, id, data:call.transaction.from::STRING as user, CASE 
      WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
      WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
      ELSE NULL
    END AS amount_usd,
    LOWER(data:call.chain::STRING) AS source_chain,
    LOWER(data:call.returnValues.destinationChain::STRING) AS destination_chain
from axelar.axelscan.fact_gmp
where created_at::date>='{start_str}' and created_at::date<='{end_str}')

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
df_event_txn = load_event_txn(start_date, end_date)
df_event_route_data = load_event_route_data(start_date, end_date)
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

# --- Row 2 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# === Left function ==================================
@st.cache_data
def load_active_contracts(timeframe, start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    select date_trunc('{timeframe}',created_at) as "Date", 
    count(distinct call:returnValues:destinationContractAddress) as "Number of Destination Contracts"
    from axelar.axelscan.fact_gmp
    where created_at::date>='{start_str}' and created_at::date<='{end_str}'
    group by 1
    order by 1

    """

    df = pd.read_sql(query, conn)
    return df
  
# === right function ==============================
@st.cache_data
def load_new_contracts(timeframe, start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    with tab1 as (
select call:returnValues:destinationContractAddress as "Destination Contract", 
min(created_at::date) as FIRST_TX
from axelar.axelscan.fact_gmp
group by 1)

select date_trunc('{timeframe}',first_tx) as "Date", count(distinct "Destination Contract") as "New Contracts", 
sum("New Contracts") over (order by "Date" asc) as "Total New Contracts"
from tab1
where first_tx>='{start_str}' and first_tx<='{end_str}'
group by 1
order by 1

    """

    df = pd.read_sql(query, conn)
    return df

# === Load Data ===================================================
df_active_contracts = load_active_contracts(timeframe, start_date, end_date)
df_new_contracts = load_new_contracts(timeframe, start_date, end_date)
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

# --- Row 3 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_cnt_stat(start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    with tab1 as (select call:returnValues:destinationContractAddress as dest_contract
from axelar.axelscan.fact_gmp
where created_at::date>='{start_str}' and created_at::date<='{end_str}')

select count(distinct dest_contract) as "Total Number of Destination Contracts"
from tab1
    """

    df = pd.read_sql(query, conn)
    return df

# --- Load Data ----------------------------------------------------------------------------------------------------
df_cnt_stat = load_cnt_stat(start_date, end_date)

# --- KPI Row ------------------------------------------------------------------------------------------------------
card_style = """
    <div style="
        background-color: #b8ffdb;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        ">
        <h4 style="margin: 0; font-size: 15px; color: #555;">{label}</h4>
        <p style="margin: 5px 0 0; font-size: 20px; font-weight: bold; color: #000;">{value}</p>
    </div>
"""

st.markdown(card_style.format(label="Total Number of Destination Contracts", value=f"📑{df_cnt_stat["Total Number of Destination Contracts"][0]:,}"), unsafe_allow_html=True)


