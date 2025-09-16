import streamlit as st
import pandas as pd
import requests
import snowflake.connector
import plotly.graph_objects as go
import plotly.express as px
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

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
st.title("💸Interchain Token Service (ITS)")

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

# --- Time Frame & Period Selection --------------------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    timeframe = st.selectbox("Select Time Frame", ["month", "week", "day"])
with col2:
    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-12-01"))
with col3:
    end_date = st.date_input("End Date", value=pd.to_datetime("2025-09-30"))

# --- Row 1: KPIs ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# --- Fetch Data from APIs -------------------------------------------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_interchain_stats(start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
  
  SELECT  created_at, LOWER(data:call.chain::STRING) AS source_chain, LOWER(data:call.returnValues.destinationChain::STRING) AS destination_chain,
    data:call.transaction.from::STRING AS user, CASE 
      WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
      WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
      ELSE NULL
    END AS amount, CASE 
      WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
      WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
      ELSE NULL
    END AS amount_usd, COALESCE(CASE 
        WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
          OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
        THEN NULL
        WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
          AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
        THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
        ELSE NULL END, CASE 
        WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
        WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
        ELSE NULL END) AS fee, id, data:symbol::STRING AS Symbol
  FROM axelar.axelscan.fact_gmp 
  WHERE status = 'executed' AND simplified_status = 'received' AND (
        data:approved:returnValues:contractAddress ilike '%0xB5FB4BE02232B1bBA4dC8f81dc24C26980dE9e3C%' -- Interchain Token Service
        or data:approved:returnValues:contractAddress ilike '%axelar1aqcj54lzz0rk22gvqgcn8fr5tx4rzwdv5wv5j9dmnacgefvd7wzsy2j2mr%' -- Axelar ITS Hub
        ))

SELECT count(distinct user) as "Unique Users", count(distinct (source_chain || '➡' || destination_chain)) as "Paths", 
count(distinct symbol) as "Tokens", round(sum(fee)) as "Total Transfer Fees"
FROM axelar_service
where created_at::date>='{start_str}' and created_at::date<='{end_str}'
    """

    df = pd.read_sql(query, conn)
    return df

# --- Load Data --------------------------------------------------------------------------------------------------------------------
df_interchain_stats = load_interchain_stats(start_date, end_date)
# ---Axelarscan api ----------------------------------------------------------------------------------------------------------------
api_urls = [
    "https://api.axelarscan.io/gmp/GMPChart?contractAddress=0xB5FB4BE02232B1bBA4dC8f81dc24C26980dE9e3C",
    "https://api.axelarscan.io/gmp/GMPChart?contractAddress=axelar1aqcj54lzz0rk22gvqgcn8fr5tx4rzwdv5wv5j9dmnacgefvd7wzsy2j2mr"
]

dfs = []
for url in api_urls:
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()["data"]
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        dfs.append(df)
    else:
        st.error(f"Failed to fetch data from {url}")

# --- Combine and Filter ------------------------------------------------------------------------------------------------
df_all = pd.concat(dfs)
df_all = df_all[(df_all["timestamp"].dt.date >= start_date) & (df_all["timestamp"].dt.date <= end_date)]

# --- Aggregate by Timeframe ----------------------------------------------------------------------------------------
if timeframe == "week":
    df_all["period"] = df_all["timestamp"].dt.to_period("W").apply(lambda r: r.start_time)
elif timeframe == "month":
    df_all["period"] = df_all["timestamp"].dt.to_period("M").apply(lambda r: r.start_time)
else:
    df_all["period"] = df_all["timestamp"]

agg_df = df_all.groupby("period").agg({
    "num_txs": "sum",
    "volume": "sum"
}).reset_index()

agg_df = agg_df.sort_values("period")
agg_df["cum_num_txs"] = agg_df["num_txs"].cumsum()
agg_df["cum_volume"] = agg_df["volume"].cumsum()

# --- KPIs -----------------------------------------------------------------------------------------------------------
card_style = """
    <div style="
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        ">
        <h4 style="margin: 0; font-size: 20px; color: #555;">{label}</h4>
        <p style="margin: 5px 0 0; font-size: 20px; font-weight: bold; color: #000;">{value}</p>
    </div>
"""

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(card_style.format(label="Total Number of Transfers", value=f"{agg_df['num_txs'].sum():,} Txns"), unsafe_allow_html=True)

with col2:
    st.markdown(card_style.format(label="Total Volume of Transfers", value=f"${round(agg_df['volume'].sum()):,}"), unsafe_allow_html=True)

with col3:
    st.markdown(card_style.format(label="Unique Users", value=f"{df_interchain_stats['Unique Users'][0]:,} Wallets"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Row 2: KPIs ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_deploy_stats(start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    with table1 as (
SELECT data:interchain_token_deployment_started:tokenId as token, 
data:call:transaction:from as deployer, COALESCE(CASE 
        WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
          OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
        THEN NULL
        WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
          AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
        THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
        ELSE NULL
      END, CASE 
        WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
        WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
        ELSE NULL
      END) AS fee
FROM axelar.axelscan.fact_gmp 
WHERE status = 'executed' AND simplified_status = 'received' AND (
data:approved:returnValues:contractAddress ilike '%0xB5FB4BE02232B1bBA4dC8f81dc24C26980dE9e3C%' -- Interchain Token Service
or data:approved:returnValues:contractAddress ilike '%axelar1aqcj54lzz0rk22gvqgcn8fr5tx4rzwdv5wv5j9dmnacgefvd7wzsy2j2mr%' -- Axelar ITS Hub
) AND data:interchain_token_deployment_started:event='InterchainTokenDeploymentStarted'
and created_at::date>='{start_str}' and created_at::date<='{end_str}')

select count(distinct token) as "Total Number of Deployed Tokens",
count(distinct deployer) as "Total Number of Token Deployers",
round(sum(fee)) as "Total Gas Fees"
from table1

    """

    df = pd.read_sql(query, conn)
    return df

# === Load Data: Row 1 =================================================
df_deploy_stats = load_deploy_stats(start_date, end_date)
# === KPIs: Row 1 ======================================================
card_style = """
    <div style="
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        ">
        <h4 style="margin: 0; font-size: 20px; color: #555;">{label}</h4>
        <p style="margin: 5px 0 0; font-size: 20px; font-weight: bold; color: #000;">{value}</p>
    </div>
"""

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(card_style.format(label="Number of Deployed Tokens", value=f"✨{df_deploy_stats["Total Number of Deployed Tokens"][0]:,}"), unsafe_allow_html=True)
with col2:
    st.markdown(card_style.format(label="Number of Token Deployers", value=f"👨‍💻{df_deploy_stats["Total Number of Token Deployers"][0]:,}"), unsafe_allow_html=True)
with col3:
    st.markdown(card_style.format(label="Total Gas Fees", value=f"⛽${df_deploy_stats["Total Gas Fees"][0]:,}"), unsafe_allow_html=True)

# --- Row 3 ---------------------------------------------------------------------------------------------------------------------------------------------------------
# === Number of Tokens Deployed =====================================
@st.cache_data
def load_deployed_tokens(timeframe, start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    SELECT date_trunc('{timeframe}',created_at) as "Date", count(distinct data:interchain_token_deployment_started:tokenId) as "Number of Tokens", case 
when (call:receipt:logs[0]:address ilike '%0xB5FB4BE02232B1bBA4dC8f81dc24C26980dE9e3C%' or 
call:receipt:logs[0]:address ilike '%axelar1aqcj54lzz0rk22gvqgcn8fr5tx4rzwdv5wv5j9dmnacgefvd7wzsy2j2mr%') then 'Existing Tokens'
else 'Newly Minted Token' end as "Token Type"
FROM axelar.axelscan.fact_gmp 
WHERE status = 'executed' AND simplified_status = 'received' AND (
data:approved:returnValues:contractAddress ilike '%0xB5FB4BE02232B1bBA4dC8f81dc24C26980dE9e3C%' -- Interchain Token Service
or data:approved:returnValues:contractAddress ilike '%axelar1aqcj54lzz0rk22gvqgcn8fr5tx4rzwdv5wv5j9dmnacgefvd7wzsy2j2mr%' -- Axelar ITS Hub
) AND data:interchain_token_deployment_started:event='InterchainTokenDeploymentStarted'
AND created_at::date>='{start_str}' and created_at::date<='{end_str}'
group by 1, 3 
order by 1

    """

    df = pd.read_sql(query, conn)
    return df
# === Load Data ==========================================================
df_deployed_tokens = load_deployed_tokens(timeframe, start_date, end_date)
# === Charts: Row 3 ======================================================
color_map = {
    "Existing Tokens": "#858dff",
    "Newly Minted Token": "#fc9047"
}
col1, col2 = st.columns(2)

with col1:

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=agg_df["period"], y=agg_df["num_txs"], name="Number of Transfers", yaxis="y1", marker_color="#ff7f27"))
    fig1.add_trace(go.Scatter(x=agg_df["period"], y=agg_df["volume"], name="Volume of Transfers", yaxis="y2", mode="lines", line=dict(color="#7f8efe")))
    fig1.update_layout(title="Interchain Transfers Over Time", yaxis=dict(title="Txns count"), yaxis2=dict(title="$USD", overlaying="y", side="right"),
        xaxis_title="", legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5))
    col1.plotly_chart(fig1, use_container_width=True)

with col2:
    fig_stacked_tokens = px.bar(df_deployed_tokens, x="Date", y="Number of Tokens", color="Token Type", title="Number of Tokens Deployed Over Time", color_discrete_map=color_map)
    fig_stacked_tokens.update_layout(barmode="stack", yaxis_title="Number of Tokens", xaxis_title="", 
                                     legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, title=""))
    st.plotly_chart(fig_stacked_tokens, use_container_width=True)

# --- Row 4 -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --- Convert date to unix (sec) ----------------------------------------------------------------------------------
def to_unix_timestamp(dt):
    return int(time.mktime(dt.timetuple()))

# --- Getting APIs -----------------------------------------------------------------------------------------
@st.cache_data
def load_data(start_date, end_date):
    from_time = to_unix_timestamp(pd.to_datetime(start_date))
    to_time = to_unix_timestamp(pd.to_datetime(end_date))

    url_tx = f"https://api.axelarscan.io/gmp/GMPTopITSAssets?fromTime={from_time}&toTime={to_time}"
    tx_data = requests.get(url_tx).json().get("data", [])

    url_assets = "https://api.axelarscan.io/api/getITSAssets"
    assets_data = requests.get(url_assets).json()

    address_to_symbol = {}
    symbol_to_image = {}
    for asset in assets_data:
        symbol = asset.get("symbol", "")
        image = asset.get("image", "")
        symbol_to_image[symbol] = image
        addresses = asset.get("addresses", [])
        if isinstance(addresses, str):
            try:
                addresses = eval(addresses)
            except:
                addresses = []
        for addr in addresses:
            address_to_symbol[addr.lower()] = symbol

    df = pd.DataFrame(tx_data)
    if df.empty:
        return pd.DataFrame(columns=["Token Address", "Symbol", "Logo", "Number of Transfers", "Volume of Transfers"]), {}

    df["Token Address"] = df["key"]
    df["Symbol"] = df["key"].str.lower().map(address_to_symbol).fillna("Unknown")
    df["Logo"] = df["Symbol"].map(symbol_to_image).fillna("")
    df["Number of Transfers"] = df["num_txs"].astype(int)
    df["Volume of Transfers"] = df["volume"].astype(float)

    df = df[["Token Address", "Symbol", "Logo", "Number of Transfers", "Volume of Transfers"]]

    return df, symbol_to_image

# --- Main Run ------------------------------------------------------------------------------------------------------

df, symbol_to_image = load_data(start_date, end_date)

if df.empty:
    st.warning("⛔ No data available for the selected time range.")
else:

    df_display = df.copy()
    df_display["Number of Transfers"] = df_display["Number of Transfers"].map("{:,}".format)
    df_display["Volume of Transfers"] = df_display["Volume of Transfers"].map("{:,.0f}".format)

    def logo_html(url):
        if url:
            return f'<img src="{url}" style="width:20px;height:20px;border-radius:50%;">'
        return ""

    df_display["Logo"] = df_display["Logo"].apply(logo_html)

    st.subheader("📑 Interchain Token Transfers Table")

    scrollable_table = f"""
    <div style="max-height:700px; overflow-y:auto;">
        {df_display.to_html(escape=False, index=False)}
    </div>
    """

    st.write(scrollable_table, unsafe_allow_html=True)

    # --- chart 1: Top 10 by Volume (without Unknown) -------------------------------------------------------------------
    df_grouped = (
        df[df["Symbol"] != "Unknown"]
        .groupby("Symbol", as_index=False)
        .agg({
            "Number of Transfers": "sum",
            "Volume of Transfers": "sum"
        })
    )

    top_volume = df_grouped.sort_values("Volume of Transfers", ascending=False).head(10)
    fig1 = px.bar(
        top_volume,
        x="Symbol",
        y="Volume of Transfers",
        text="Volume of Transfers",
        color="Symbol"
    )
    fig1.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig1.update_layout(
        title="Top 10 Tokens by Interchain Transfers Volume",
        xaxis_title=" ",
        yaxis_title="$USD",
        showlegend=False
    )

    # --- chart2: Top 10 by Transfers Count (without Unknown + volume > 0) ------------------------------------------------
    df_nonzero = df_grouped[df_grouped["Volume of Transfers"] > 0]
    top_transfers = df_nonzero.sort_values("Number of Transfers", ascending=False).head(10)

    fig2 = px.bar(
        top_transfers,
        x="Symbol",
        y="Number of Transfers",
        text="Number of Transfers",
        color="Symbol"
    )
    fig2.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig2.update_layout(
        title="Top 10 Tokens by Interchain Transfers Count",
        xaxis_title=" ",
        yaxis_title="Transfers count",
        showlegend=False
    )

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)
