import MetaTrader5 as mt5
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
import os
from datetime import datetime, timedelta

login = 5032847392
password = "NnN!1rTo"
server = "MetaQuotes-Demo"

if not mt5.initialize(login=login, password=password, server=server):
    quit()

account_info = mt5.account_info()
if account_info is None:
    mt5.shutdown()
    quit()

current_balance = account_info.balance

end_date = datetime.now()
start_date = end_date - timedelta(days=30)
deals = mt5.history_deals_get(start_date, end_date)

if deals is None or len(deals) == 0:
    mt5.shutdown()
    quit()

df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
mt5.shutdown()

df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.sort_values('time')

total_profit = df['profit'].sum()
initial_balance = current_balance - total_profit
df['balance'] = initial_balance + df['profit'].cumsum()

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.7, 0.3],
    subplot_titles=('نمودار سرمایه', 'سود/زیان معاملات')
)

fig.add_trace(go.Scatter(
    x=df['time'],
    y=df['balance'],
    mode='lines',
    name='سرمایه',
    line=dict(color='white', width=4),
    hovertemplate='سرمایه: %{y:,.2f}<extra></extra>'
), row=1, col=1)

colors = ['green' if p >= 0 else 'red' for p in df['profit']]
fig.add_trace(go.Bar(
    x=df['time'],
    y=df['profit'],
    name='سود/زیان',
    marker_color=colors,
    opacity=0.7,
    hovertemplate='سود/زیان: %{y:,.2f}<extra></extra>'
), row=2, col=1)

xaxis_config = dict(
    rangeslider=dict(visible=True),
    rangeselector=dict(
        buttons=list([
            dict(count=1, label="1D", step="day", stepmode="backward"),
            dict(count=7, label="1W", step="day", stepmode="backward"),
            dict(count=30, label="1M", step="day", stepmode="backward"),
            dict(count=90, label="3M", step="day", stepmode="backward"),
            dict(count=180, label="6M", step="day", stepmode="backward"),
            dict(count=365, label="1Y", step="day", stepmode="backward"),
            dict(step="all", label="همه")
        ]),
        bgcolor="rgba(0,0,0,0.5)",
        activecolor="rgba(255,255,255,0.3)"
    )
)

yaxis_config = dict(
    autorange=True,
    fixedrange=False,
    showgrid=True,
    gridcolor='rgba(255,255,255,0.1)',
    gridwidth=1,
    zerolinecolor='rgba(255,255,255,0.3)',
    zerolinewidth=1,
    tickformat=",.2f"
)

fig.update_layout(
    title=f'نمودار سرمایه معاملات - سرمایه فعلی: ${current_balance:,.2f}',
    template='plotly_dark',
    height=900,
    width=1400,
    hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=xaxis_config,
    yaxis=yaxis_config,
    yaxis2=yaxis_config,
    xaxis2=dict(rangeslider=dict(visible=False))
)

fig.update_layout(
    updatemenus=[
        dict(
            type="buttons",
            direction="right",
            active=0,
            x=0.1,
            y=1.02,
            buttons=list([
                dict(label="ساعتی", method="restyle", 
                     args=[{"x": [df['time']], 
                            "y": [df['balance']]}, 
                           {"x": [df['time']], 
                            "y": [df['profit']]}]),
                dict(label="روزانه", method="restyle", 
                     args=[{"x": [df['time']], 
                            "y": [df['balance']]}, 
                           {"x": [df['time']], 
                            "y": [df['profit']]}]),
                dict(label="هفتگی", method="restyle", 
                     args=[{"x": [df['time']], 
                            "y": [df['balance']]}, 
                           {"x": [df['time']], 
                            "y": [df['profit']]}]),
                dict(label="ماهانه", method="restyle", 
                     args=[{"x": [df['time']], 
                            "y": [df['balance']]}, 
                           {"x": [df['time']], 
                            "y": [df['profit']]}])
            ]),
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="white",
            borderwidth=1
        )
    ]
)

config = {
    'displayModeBar': True,
    'scrollZoom': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': ['pan2', 'lasso2', 'select2'],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'capital_chart',
        'height': 900,
        'width': 1400,
        'scale': 2
    }
}

winning_trades = df[df['profit'] > 0]
losing_trades = df[df['profit'] < 0]
win_rate = len(winning_trades) / len(df) * 100 if len(df) > 0 else 0
avg_win = winning_trades['profit'].mean() if len(winning_trades) > 0 else 0
avg_loss = losing_trades['profit'].mean() if len(losing_trades) > 0 else 0

stats_text = f"""
<b>آمار کلی معاملات</b><br>
سرمایه فعلی: ${current_balance:,.2f}<br>
سود/زیان کل: ${total_profit:,.2f}<br>
تعداد کل معاملات: {len(df)}<br>
معاملات سودده: {len(winning_trades)} ({win_rate:.1f}%)<br>
معاملات زیانده: {len(losing_trades)} ({100-win_rate:.1f}%)<br>
میانگین سود: ${avg_win:,.2f}<br>
میانگین زیان: ${avg_loss:,.2f}
"""

fig.add_annotation(
    text=stats_text,
    align='right',
    showarrow=False,
    xref='paper',
    yref='paper',
    x=0.98,
    y=0.98,
    bordercolor='yellow',
    borderwidth=1,
    bgcolor='rgba(0,0,0,0.7)',
    opacity=0.9,
    font=dict(size=12, color='white')
)

fig.update_xaxes(showticklabels=False, row=1, col=1)
fig.update_xaxes(showticklabels=True, row=2, col=1)

html_file = os.path.expanduser("~/Documents/capital_chart.html")
fig.write_html(html_file, config=config)
webbrowser.open(html_file)