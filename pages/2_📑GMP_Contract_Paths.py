import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# --- Page Config -------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Axelar: GMP Contract Dashboard",
    page_icon="https://axelarscan.io/logos/logo.png",
    layout="wide"
)

# --- Sidebar Footer -----------------------------------------------------------------------------------
st.sidebar.markdown(
    """
    <style>
    .sidebar-footer {
        position: fixed;
        bottom: 20px;
        width: 250px;
        font-size: 13px;
        color: gray;
        margin-left: 5px;
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
st.title("📑 GMP Contract Dashboard")
st.info("📊 Charts initially display data for all contracts. Data is fetched from Axelar API.")

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
num_contracts = df["Contract"].nunique()  # شمارش قراردادهای یکتا
avg_volume = df["Volume"].mean()
avg_txns = round(df["Number of Transactions"].mean())  # رند شده بدون اعشار

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Number of Contracts", f"{num_contracts}")
kpi2.metric("Avg Volume per Contract", f"{avg_volume:.1f}")
kpi3.metric("Avg Transaction per Contract", f"{avg_txns}")

# --- Contracts Table ----------------------------------------------------------------------------------
st.subheader("📋 Contracts Overview")
df_table_sorted = df.sort_values(by="Number of Transactions", ascending=False).copy()
# اضافه کردن اندیس از 1
df_table_sorted.index = range(1, len(df_table_sorted) + 1)
st.dataframe(df_table_sorted, use_container_width=True)

# --- Top 20 Bar Charts ---------------------------------------------------------------------------------
st.subheader("📊 Top 20 Contracts by Transactions and Volume")
col1, col2 = st.columns(2)

with col1:
    top_txns = df.nlargest(20, "Number of Transactions")
    fig_txns = px.bar(
        top_txns[::-1],
        x="Number of Transactions",
        y="Contract",
        orientation='h',
        text="Number of Transactions",
        labels={"Number of Transactions": "Number of Transactions", "Contract": "Contract"}
    )
    fig_txns.update_traces(textposition='inside')
    st.plotly_chart(fig_txns, use_container_width=True)

with col2:
    top_volume = df.nlargest(20, "Volume")
    fig_volume = px.bar(
        top_volume[::-1],
        x="Volume",
        y="Contract",
        orientation='h',
        text="Volume",
        labels={"Volume": "Volume ($)", "Contract": "Contract"}
    )
    fig_volume.update_traces(textposition='inside')
    st.plotly_chart(fig_volume, use_container_width=True)

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
