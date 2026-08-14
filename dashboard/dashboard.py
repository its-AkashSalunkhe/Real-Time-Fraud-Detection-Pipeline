import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Fraud Shield", page_icon="🛡️", layout="wide")

conn = sqlite3.connect('fraud_detection.db')
query = '''
SELECT t.TransactionID, t.TransactionDT, t.TransactionAmt, t.ProductCD,
       t.card4, t.card6, t.DeviceType, t.received_at,
       p.fraud_probability, p.predicted_label, p.scored_at
FROM transactions t
JOIN predictions p ON t.TransactionID = p.TransactionID
'''
df = pd.read_sql(query, conn)
conn.close()

st.sidebar.title("🛡️ Fraud Shield")
st.sidebar.caption("Real-time transaction monitoring")
st.sidebar.markdown("---")

threshold = st.sidebar.slider("Flagging Threshold", 0.0, 1.0, 0.4, 0.01)
product_filter = st.sidebar.multiselect("Product Type", options=df['ProductCD'].unique(), default=list(df['ProductCD'].unique()))
device_filter = st.sidebar.multiselect("Device Type", options=df['DeviceType'].dropna().unique(), default=list(df['DeviceType'].dropna().unique()))

st.sidebar.markdown("---")
st.sidebar.caption("Model: LightGBM")
st.sidebar.caption("ROC-AUC: 0.885")
st.sidebar.caption("Optimized via business cost function")

df['predicted_label'] = (df['fraud_probability'] >= threshold).astype(int)
filtered = df[df['ProductCD'].isin(product_filter)]
if device_filter:
    filtered = filtered[filtered['DeviceType'].isin(device_filter) | filtered['DeviceType'].isna()]

total_txns = len(filtered)
flagged_txns = int(filtered['predicted_label'].sum())
fraud_rate = round((flagged_txns / total_txns) * 100, 2) if total_txns > 0 else 0
avg_prob = round(filtered['fraud_probability'].mean(), 4) if total_txns > 0 else 0
amt_flagged = filtered.loc[filtered['predicted_label']==1, 'TransactionAmt'].sum()
amt_saved_estimate = amt_flagged

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📡 Live Feed", "📈 Analytics", "🚩 Flagged Transactions"])

with tab1:
    st.header("System Overview")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Transactions", total_txns)
    k2.metric("Flagged as Fraud", flagged_txns, delta=f"{fraud_rate}% of total")
    k3.metric("Avg Fraud Score", avg_prob)
    k4.metric("Amount at Risk", f"${amt_flagged:,.0f}")
    k5.metric("Current Threshold", threshold)

    st.markdown("---")

    left, right = st.columns([1.3, 1])

    with left:
        st.subheader("Fraud Probability Gauge")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=avg_prob*100,
            title={'text': "Average Risk Score (%)"},
            gauge={'axis': {'range': [0,100]},
                   'bar': {'color': "#e63946"},
                   'steps': [
                       {'range':[0,40], 'color':"#1c1f26"},
                       {'range':[40,70], 'color':"#3a2f2f"},
                       {'range':[70,100], 'color':"#4a1f1f"}]}
        ))
        fig_gauge.update_layout(height=300, margin=dict(t=40,b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with right:
        st.subheader("Flagged vs Legit")
        pie_data = filtered['predicted_label'].value_counts().rename({0:'Legit', 1:'Flagged'})
        fig_pie = px.pie(values=pie_data.values, names=pie_data.index, hole=0.5,
                          color=pie_data.index,
                          color_discrete_map={'Legit':'#4C72B0','Flagged':'#e63946'})
        fig_pie.update_layout(height=300, margin=dict(t=10,b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    st.header("Live Transaction Feed")
    st.caption("Most recently scored transactions")

    feed = filtered.sort_values('scored_at', ascending=False).head(15)

    for _, row in feed.iterrows():
        risk = row['fraud_probability']
        color = "#e63946" if row['predicted_label']==1 else "#4C72B0"
        icon = "🚨" if row['predicted_label']==1 else "✅"

        c1, c2, c3, c4, c5 = st.columns([1,1.5,1,1,1])
        c1.write(f"{icon} `{row['TransactionID']}`")
        c2.write(f"${row['TransactionAmt']:.2f} — {row['ProductCD']}")
        c3.write(row['DeviceType'] if pd.notnull(row['DeviceType']) else "Unknown")
        c4.progress(min(risk,1.0))
        c5.markdown(f"<span style='color:{color}; font-weight:bold'>{risk:.1%}</span>", unsafe_allow_html=True)

with tab3:
    st.header("Risk Analytics")

    st.subheader("Probability Distribution")
    fig_hist = px.histogram(filtered, x='fraud_probability', nbins=30,
                             color_discrete_sequence=['#4C72B0'])
    fig_hist.add_vline(x=threshold, line_dash="dash", line_color="#e63946",
                        annotation_text="threshold")
    fig_hist.update_layout(height=350)
    st.plotly_chart(fig_hist, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Fraud Rate by Product")
        prod_rate = filtered.groupby('ProductCD')['predicted_label'].mean().sort_values(ascending=False)
        fig_bar1 = px.bar(x=prod_rate.index, y=prod_rate.values,
                           color=prod_rate.values, color_continuous_scale='Reds',
                           labels={'x':'Product','y':'Fraud Rate'})
        fig_bar1.update_layout(height=320)
        st.plotly_chart(fig_bar1, use_container_width=True)

    with c2:
        st.subheader("Fraud Rate by Device")
        dev_rate = filtered.groupby('DeviceType')['predicted_label'].mean().sort_values(ascending=False)
        fig_bar2 = px.bar(x=dev_rate.index, y=dev_rate.values,
                           color=dev_rate.values, color_continuous_scale='Reds',
                           labels={'x':'Device','y':'Fraud Rate'})
        fig_bar2.update_layout(height=320)
        st.plotly_chart(fig_bar2, use_container_width=True)

    st.subheader("Transaction Amount vs Fraud Score")
    fig_scatter = px.scatter(filtered, x='TransactionAmt', y='fraud_probability',
                              color='predicted_label',
                              color_continuous_scale=['#4C72B0','#e63946'],
                              opacity=0.6)
    fig_scatter.update_layout(height=350)
    st.plotly_chart(fig_scatter, use_container_width=True)

with tab4:
    st.header("Flagged Transactions")

    flagged_table = filtered[filtered['predicted_label']==1].sort_values('fraud_probability', ascending=False)
    flagged_table = flagged_table[['TransactionID','TransactionAmt','ProductCD','card4','card6','DeviceType','fraud_probability','scored_at']]

    st.dataframe(
        flagged_table.style.background_gradient(subset=['fraud_probability'], cmap='Reds'),
        use_container_width=True,
        height=450
    )

    st.download_button("⬇️ Download Flagged Transactions CSV",
                        flagged_table.to_csv(index=False),
                        "flagged_transactions.csv")