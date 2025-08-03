import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import webbrowser

login = 5032847392
password = "NnN!1rTo"
server = "MetaQuotes-Demo"

if not mt5.initialize(login=login, password=password, server=server):
    quit()

end_date = datetime.now()
start_date = datetime(2010, 1, 1)

deals = mt5.history_deals_get(start_date, end_date)
mt5.shutdown()

if deals is None or len(deals) == 0:
    quit()

df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())

df['time'] = pd.to_datetime(df['time'], unit='s')
df['time_msc'] = pd.to_datetime(df['time_msc'], unit='ms')

important_columns = [
    'ticket', 'order', 'time', 'symbol', 'type', 'volume', 
    'price', 'commission', 'swap', 'profit', 'entry', 'comment' 
]
available_columns = [col for col in important_columns if col in df.columns]
df = df[available_columns]

df['type'] = df['type'].apply(lambda x: "خرید" if x == 0 else "فروش")
df['entry'] = df['entry'].apply(lambda x: 
    "ورود" if x == 0 else 
    "خروج" if x == 1 else 
    "معکوس")

df['net_profit'] = df['profit'] + df['commission'] + df['swap']
total_profit = df['net_profit'].sum()
winning_trades = df[df['net_profit'] > 0]
losing_trades = df[df['net_profit'] < 0]
win_rate = len(winning_trades) / len(df) * 100 if len(df) > 0 else 0
avg_win = winning_trades['net_profit'].mean() if len(winning_trades) > 0 else 0
avg_loss = losing_trades['net_profit'].mean() if len(losing_trades) > 0 else 0

df_sorted = df.sort_values('time')
df_sorted['cumulative_profit'] = df_sorted['net_profit'].cumsum()
window_size = min(5, len(df_sorted))  
df_sorted['moving_avg'] = df_sorted['cumulative_profit'].rolling(window=window_size).mean()

positions = []
entry_deals = df_sorted[df_sorted['entry'] == 'ورود'].copy()
exit_deals = df_sorted[df_sorted['entry'] == 'خروج'].copy()

if 'order' in df_sorted.columns:
    for _, entry in entry_deals.iterrows():
        matching_exits = exit_deals[exit_deals['order'] == entry['order']]
        if len(matching_exits) > 0:
            exit = matching_exits.iloc[0]
            positions.append({
                'entry_time': entry['time'],
                'exit_time': exit['time'],
                'entry_price': entry['price'],
                'exit_price': exit['price'],
                'entry_type': entry['type'],
                'exit_type': exit['type'],
                'volume': entry['volume'],
                'net_profit': entry['net_profit'] + exit['net_profit'],
                'entry_ticket': entry['ticket'],
                'exit_ticket': exit['ticket'],
                'symbol': entry['symbol']
            })
            exit_deals = exit_deals[exit_deals['ticket'] != exit['ticket']]
else:
    for i in range(min(len(entry_deals), len(exit_deals))):
        entry = entry_deals.iloc[i]
        exit = exit_deals.iloc[i]
        positions.append({
            'entry_time': entry['time'],
            'exit_time': exit['time'],
            'entry_price': entry['price'],
            'exit_price': exit['price'],
            'entry_type': entry['type'],
            'exit_type': exit['type'],
            'volume': entry['volume'],
            'net_profit': entry['net_profit'] + exit['net_profit'],
            'entry_ticket': entry['ticket'],
            'exit_ticket': exit['ticket'],
            'symbol': entry['symbol']
        })

positions_df = pd.DataFrame(positions)

symbols = df_sorted['symbol'].unique()
rates_df = None 

if len(symbols) > 0:
    symbol = symbols[0]  
    
    start_time = df_sorted['time'].min() - timedelta(hours=1)
    end_time = df_sorted['time'].max() + timedelta(hours=1)
    
    mt5.initialize()
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, start_time, end_time)
    mt5.shutdown()
    
    if rates is not None and len(rates) > 0:
        rates_df = pd.DataFrame(rates)
        rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')

fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.6, 0.2, 0.2],
    subplot_titles=('نمودار قیمت و معاملات', 'حجم معاملات', 'سود/زیان تجمعی')
)

if rates_df is not None:
    fig.add_trace(go.Candlestick(
        x=rates_df['time'],
        open=rates_df['open'],
        high=rates_df['high'],
        low=rates_df['low'],
        close=rates_df['close'],
        name='قیمت',
        increasing_line_color='green',
        decreasing_line_color='red'
    ), row=1, col=1)

for _, pos in positions_df.iterrows():
    color = 'green' if pos['net_profit'] > 0 else 'red'
    line_width = 3 if abs(pos['net_profit']) > 10 else 2
    
    hover_text = f"""
    <b>موقعیت معاملاتی</b><br>
    نماد: {pos['symbol']}<br>
    نوع ورود: {pos['entry_type']}<br>
    نوع خروج: {pos['exit_type']}<br>
    حجم: {pos['volume']}<br>
    قیمت ورود: {pos['entry_price']:.5f}<br>
    قیمت خروج: {pos['exit_price']:.5f}<br>
    سود/زیان: {pos['net_profit']:.2f}<br>
    زمان ورود: {pos['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}<br>
    زمان خروج: {pos['exit_time'].strftime('%Y-%m-%d %H:%M:%S')}
    """
    fig.add_trace(go.Scatter(
        x=[pos['entry_time'], pos['exit_time']],
        y=[pos['entry_price'], pos['exit_price']],
        mode='lines',
        line=dict(color=color, width=line_width),
        text=hover_text,
        hoverinfo='text',
        name=f"موقعیت {pos['entry_ticket']}-{pos['exit_ticket']}",
        showlegend=False,
        hoverlabel=dict(bgcolor='white', font_size=12)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=[pos['entry_time']],
        y=[pos['entry_price']],
        mode='markers',
        marker=dict(color='blue', size=12, symbol='triangle-up', line=dict(color='white', width=2)),
        text=f"ورود: {pos['entry_type']}<br>قیمت: {pos['entry_price']:.5f}<br>حجم: {pos['volume']}",
        hoverinfo='text',
        showlegend=False,
        hoverlabel=dict(bgcolor='white', font_size=12)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=[pos['exit_time']],
        y=[pos['exit_price']],
        mode='markers',
        marker=dict(color='orange', size=12, symbol='triangle-down', line=dict(color='white', width=2)),
        text=f"خروج: {pos['exit_type']}<br>قیمت: {pos['exit_price']:.5f}<br>سود/زیان: {pos['net_profit']:.2f}",
        hoverinfo='text',
        showlegend=False,
        hoverlabel=dict(bgcolor='white', font_size=12)
    ), row=1, col=1)

if rates_df is not None:
    fig.add_trace(go.Bar(
        x=rates_df['time'],
        y=rates_df['tick_volume'],
        name='حجم',
        marker_color='blue',
        opacity=0.7
    ), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df_sorted['time'],
    y=df_sorted['cumulative_profit'],
    mode='lines',
    name='سود تجمعی',
    line=dict(color='green', width=2.5),
    hovertemplate='%{y:.2f}<extra></extra>'
), row=3, col=1)

fig.add_trace(go.Scatter(
    x=df_sorted['time'],
    y=df_sorted['moving_avg'],
    mode='lines',
    name=f'میانگین متحرک ({window_size})',
    line=dict(color='blue', width=2, dash='dash'),
    hovertemplate='%{y:.2f}<extra></extra>'
), row=3, col=1)

fig.add_hline(y=0, line_dash="solid", line_color="black", opacity=0.3, row=3, col=1)
fig.add_hline(y=total_profit, line_dash="dot", line_color="purple", opacity=0.5, 
              annotation_text=f'سود کل: ${total_profit:.2f}', row=3, col=1)

xaxis_config = dict(
    rangeslider=dict(visible=True),
    rangeselector=dict(
        buttons=list([
            dict(count=1, label="1H", step="hour", stepmode="backward"),
            dict(count=6, label="6H", step="hour", stepmode="backward"),
            dict(count=12, label="12H", step="hour", stepmode="backward"),
            dict(count=1, label="1D", step="day", stepmode="backward"),
            dict(count=7, label="1W", step="day", stepmode="backward"),
            dict(count=30, label="1M", step="day", stepmode="backward"),
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
    zerolinewidth=1
)

fig.update_layout(
    title=f'نمودار تعاملی معاملات - سود کل: ${total_profit:.2f} - نرخ موفقیت: {win_rate:.1f}%',
    template='plotly_dark',
    height=1200,
    width=1400,
    hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis_rangeslider_visible=False,
    dragmode='zoom',
    xaxis=xaxis_config,
    yaxis=yaxis_config,
    yaxis2=yaxis_config,
    yaxis3=yaxis_config
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
                dict(label="نمایش همه", method="relayout", 
                     args=[{"xaxis.range": [df_sorted['time'].min(), df_sorted['time'].max()]}]),
                dict(label="نمایش امروز", method="relayout", 
                     args=[{"xaxis.range": [datetime.now().replace(hour=0, minute=0, second=0), datetime.now()]}]),
                dict(label="نمایش این هفته", method="relayout", 
                     args=[{"xaxis.range": [datetime.now().replace(hour=0, minute=0, second=0) - pd.Timedelta(days=7), datetime.now()]}]),
                dict(label="نمایش این ماه", method="relayout", 
                     args=[{"xaxis.range": [datetime.now().replace(day=1, hour=0, minute=0, second=0), datetime.now()]}]),
                dict(label="نمایش 3 ماه", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=90), datetime.now()]}]),
                dict(label="نمایش 6 ماه", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=180), datetime.now()]}]),
                dict(label="نمایش 1 سال", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=365), datetime.now()]}]),
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
        'filename': 'trading_chart',
        'height': 1200,
        'width': 1400,
        'scale': 2
    }
}

stats_text = f"""
<b>آمار کلی معاملات</b><br>
تعداد کل معاملات: {len(df)}<br>
تعداد موقعیت‌ها: {len(positions_df)}<br>
معاملات سودده: {len(winning_trades)} ({len(winning_trades)/len(df)*100:.1f}%)<br>
معاملات زیانده: {len(losing_trades)} ({len(losing_trades)/len(df)*100:.1f}%)<br>
میانگین سود: ${avg_win:.2f}<br>
میانگین زیان: ${avg_loss:.2f}<br>
سود/زیان کل: ${total_profit:.2f}
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

fig.write_html("tradingview_fixed_chart.html", config=config)
webbrowser.open("tradingview_fixed_chart.html")