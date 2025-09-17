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
st.title("🚀Satellite")

st.info("📊 Charts initially display data for a default time range. Select a custom range to view results for your desired period.")
st.info("⏳ On-chain data retrieval may take a few moments. Please wait while the results load.")
st.info("⭕The standalone Satellite interface is no longer available. The old satellite.money interface, which allowed users to transfer tokens across chains, has been deprecated. Now, satellite.money redirects you to the Squid Router interface.")

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
    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-01-01"))
with col3:
    end_date = st.date_input("End Date", value=pd.to_datetime("2025-09-30"))

# --- Row 1 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

@st.cache_data
def get_kpi_data(_conn, start_date, end_date):
    query = f"""
    WITH overview AS (
      WITH tab1 AS (
        SELECT block_timestamp::date AS date, tx_hash, source_chain, destination_chain, sender, token_symbol
        FROM AXELAR.DEFI.EZ_BRIDGE_SATELLITE
        WHERE block_timestamp::date >= '{start_date}'
      ),
      tab2 AS (
        SELECT 
            created_at::date AS date, 
            LOWER(data:send:original_source_chain) AS source_chain, 
            LOWER(data:send:original_destination_chain) AS destination_chain,
            sender_address AS user,
            CASE WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING) END AS amount,
            CASE 
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
              THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING) END AS amount_usd,
            SPLIT_PART(id, '_', 1) as tx_hash
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed' 
          AND simplified_status = 'received'
          AND created_at::date >= '{start_date}'
      )
      SELECT tab1.date, tab1.tx_hash, tab1.source_chain, tab1.destination_chain, sender, token_symbol, amount, amount_usd
      FROM tab1 
      LEFT JOIN tab2 ON tab1.tx_hash=tab2.tx_hash
    )
    SELECT 
      COUNT(DISTINCT tx_hash) AS "Number of Transfers", 
      COUNT(DISTINCT sender) AS "Number of Users",
      ROUND(SUM(amount_usd)) AS "Volume of Transfers"
    FROM overview
    WHERE date >= '{start_date}' AND date <= '{end_date}';
    """
    df = pd.read_sql(query, _conn)
    return df.iloc[0]

# --- Load KPI Data from Snowflake ---------------------------
kpi_df = get_kpi_data(conn, start_date, end_date)

# --- Display KPI (Row 1) --------------------------------
card_style = """
    <div style="
        background-color: #f9f9f9;
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

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(card_style.format(label="Bridge Volume", value=f"${kpi_df["Volume of Transfers"][0]:,}"), unsafe_allow_html=True)
with col2:
    st.markdown(card_style.format(label="Bridge Transactions", value=f"{kpi_df["Number of Transfers"][0]:,} Txns"), unsafe_allow_html=True)
with col3:
    st.markdown(card_style.format(label="Unique Users", value=f"{kpi_df["Numebr of Users"][0]:,} Wallets"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

