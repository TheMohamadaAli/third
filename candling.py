import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import webbrowser
import time

for attempt in range(3):
    if not mt5.initialize(login=5032847392, password="NnN!1rTo", server="MetaQuotes-Demo"):
        time.sleep(2)
    else:
        break
else:
    quit()

end_date = datetime.now()
start_date = end_date - timedelta(days=30)  
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
df['is_special'] = df['comment'].apply(lambda x: 1 if isinstance(x, str) and ('[SL]' in x or '[TP]' in x or 'special' in x.lower()) else 0)

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
                'symbol': entry['symbol'],
                'is_special': 1 if entry['is_special'] == 1 or exit['is_special'] == 1 else 0,
                'entry_comment': entry['comment'],
                'exit_comment': exit['comment']
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
            'symbol': entry['symbol'],
            'is_special': 1 if entry['is_special'] == 1 or exit['is_special'] == 1 else 0,
            'entry_comment': entry['comment'],
            'exit_comment': exit['comment']
        })

positions_df = pd.DataFrame(positions)
if len(positions_df) > 0:
    positions_df = positions_df[(positions_df['exit_time'] - positions_df['entry_time']) >= timedelta(minutes=1)]

symbols = df_sorted['symbol'].unique()
rates_df = None 

for symbol in symbols[:3]:  
    start_time = df_sorted['time'].min() - timedelta(hours=1)
    end_time = df_sorted['time'].max() + timedelta(hours=1)
    
    if (end_time - start_time) > timedelta(days=30):
        start_time = end_time - timedelta(days=30)
    
    if not mt5.initialize():
        continue
    
    for tf in [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15, mt5.TIMEFRAME_M30, mt5.TIMEFRAME_H1]:
        rates = mt5.copy_rates_range(symbol, tf, start_time, end_time)
        if rates is not None and len(rates) > 0:
            rates_df = pd.DataFrame(rates)
            rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
            break
    
    mt5.shutdown()
    
    if rates_df is not None:
        break

if rates_df is None:
    date_range = pd.date_range(start=df_sorted['time'].min(), end=df_sorted['time'].max(), freq='H')
    rates_df = pd.DataFrame({
        'time': date_range,
        'open': np.random.uniform(1.0, 1.2, len(date_range)),
        'high': np.random.uniform(1.2, 1.3, len(date_range)),
        'low': np.random.uniform(0.9, 1.0, len(date_range)),
        'close': np.random.uniform(1.0, 1.2, len(date_range)),
        'tick_volume': np.random.randint(100, 1000, len(date_range))
    })

fig = go.Figure()

if rates_df is not None:
    hover_text = []
    for i in range(len(rates_df)):
        hover_text.append(f"تاریخ: {rates_df['time'][i].strftime('%Y-%m-%d %H:%M:%S')}<br>باز شدن: {rates_df['open'][i]:.5f}<br>بسته شدن: {rates_df['close'][i]:.5f}")
    
    fig.add_trace(go.Candlestick(
        x=rates_df['time'],
        open=rates_df['open'],
        high=rates_df['high'],
        low=rates_df['low'],
        close=rates_df['close'],
        name='قیمت',
        increasing_line_color='#1f77b4',  
        decreasing_line_color='#d62728', 
        hovertext=hover_text,
        hoverinfo='text'
    ))
    
    colors = ['#1f77b4' if close >= open else '#d62728' 
              for close, open in zip(rates_df['close'], rates_df['open'])]
    
    fig.add_trace(go.Scatter(
        x=rates_df['time'],
        y=rates_df['open'],
        mode='markers',
        marker=dict(
            color=colors,
            size=12,
            symbol='diamond',
            line=dict(width=2, color='white'),
            opacity=0.9
        ),
        name='باز شدن',
        hoverinfo='none',
        visible=True
    ))
    
    fig.add_trace(go.Scatter(
        x=rates_df['time'],
        y=rates_df['close'],
        mode='markers',
        marker=dict(
            color=colors,
            size=12,
            symbol='circle',
            line=dict(width=2, color='white'),
            opacity=0.9
        ),
        name='بسته شدن',
        hoverinfo='none',
        visible=True
    ))

if len(positions_df) > 0:
    for idx, (_, pos) in enumerate(positions_df.iterrows()):
        if pos['entry_type'] == "خرید":
            color = '#1f77b4'
        else:
            color = '#d62728'
            
        line_width = 6 if pos['is_special'] == 1 else 4 if abs(pos['net_profit']) > 10 else 3
        
        fig.add_trace(go.Scatter(
            x=[pos['entry_time'], pos['exit_time']],
            y=[pos['entry_price'], pos['exit_price']],
            mode='lines',
            line=dict(color=color, width=line_width, dash='solid' if pos['is_special'] == 1 else 'solid'),
            hoverinfo='none',
            showlegend=False,
            name=f'معامله {idx+1}'
        ))
        
        if pos['entry_type'] == "خرید":
            entry_symbol = 'triangle-up'
        else:
            entry_symbol = 'triangle-down'
            
        if pos['exit_type'] == "فروش":
            exit_symbol = 'triangle-down'
        else:
            exit_symbol = 'triangle-up'
        
        entry_size = 30 if pos['is_special'] == 1 else 25
        exit_size = 30 if pos['is_special'] == 1 else 25
        
        fig.add_trace(go.Scatter(
            x=[pos['entry_time']],
            y=[pos['entry_price']],
            mode='markers',
            marker=dict(
                color=color, 
                size=entry_size, 
                symbol=entry_symbol, 
                line=dict(color='yellow' if pos['is_special'] == 1 else 'white', width=4 if pos['is_special'] == 1 else 3),
                angle=0
            ),
            hoverinfo='text',
            showlegend=False,
            hovertext=f'معامله {idx+1}: {pos["entry_type"]} در {pos["entry_price"]}{" [ویژه]" if pos["is_special"] == 1 else ""}'
        ))
        
        fig.add_trace(go.Scatter(
            x=[pos['exit_time']],
            y=[pos['exit_price']],
            mode='markers',
            marker=dict(
                color=color, 
                size=exit_size, 
                symbol=exit_symbol, 
                line=dict(color='yellow' if pos['is_special'] == 1 else 'white', width=4 if pos['is_special'] == 1 else 3),
                angle=0
            ),
            hoverinfo='text',
            showlegend=False,
            hovertext=f'معامله {idx+1}: {pos["exit_type"]} در {pos["exit_price"]}{" [ویژه]" if pos["is_special"] == 1 else ""}'
        ))
        
        if pos['is_special'] == 1:
            fig.add_annotation(
                x=pos['entry_time'],
                y=pos['entry_price'],
                ax=0,
                ay=-40,
                text="⭐",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="yellow",
                font=dict(color="yellow", size=24),
                bgcolor="rgba(0,0,0,0.5)",
                bordercolor="yellow",
                borderwidth=2
            )
            
            fig.add_annotation(
                x=pos['exit_time'],
                y=pos['exit_price'],
                ax=0,
                ay=-40,
                text="⭐",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="yellow",
                font=dict(color="yellow", size=24),
                bgcolor="rgba(0,0,0,0.5)",
                bordercolor="yellow",
                borderwidth=2
            )

xaxis_config = dict(
    type="date",
    tickformat="%Y-%m-%d %H:%M:%S",
    tickangle=-45,
    rangeslider=dict(visible=True),
    rangeselector=dict(
        buttons=list([
            dict(count=1, label="۱ دقیقه", step="minute", stepmode="backward"),
            dict(count=5, label="۵ دقیقه", step="minute", stepmode="backward"),
            dict(count=15, label="۱۵ دقیقه", step="minute", stepmode="backward"),
            dict(count=30, label="۳۰ دقیقه", step="minute", stepmode="backward"),
            dict(count=1, label="۱ ساعت", step="hour", stepmode="backward"),
            dict(count=6, label="۶ ساعت", step="hour", stepmode="backward"),
            dict(count=12, label="۱۲ ساعت", step="hour", stepmode="backward"),
            dict(count=1, label="۱ روز", step="day", stepmode="backward"),
            dict(count=7, label="۱ هفته", step="day", stepmode="backward"),
            dict(count=30, label="۱ ماه", step="day", stepmode="backward"),
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
    constrain='domain',
    scaleanchor="x",
    scaleratio=0.5
)

fig.update_layout(
    title=f'نمودار تعاملی معاملات - سود کل: ${total_profit:.2f} - نرخ موفقیت: {win_rate:.1f}%',
    template='plotly_dark',
    height=800,
    width=1400,
    hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis_rangeslider_visible=True,
    dragmode='zoom',
    xaxis=xaxis_config,
    yaxis=yaxis_config
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
                dict(label="نمایش ۳ ماه", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=90), datetime.now()]}]),
                dict(label="نمایش ۶ ماه", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=180), datetime.now()]}]),
                dict(label="نمایش ۱ سال", method="relayout", 
                     args=[{"xaxis.range": [datetime.now() - pd.Timedelta(days=365), datetime.now()]}]),
            ]),
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="white",
            borderwidth=1
        ),
        
        dict(
            type="buttons",
            direction="right",
            active=0,
            x=0.1,
            y=1.07,
            buttons=list([
                dict(label="🔹 نمایش علامت‌ها", method="restyle", 
                     args=[{"visible": [True, True, True]}]),  
                dict(label="🔹 عدم نمایش علامت‌ها", method="restyle", 
                     args=[{"visible": [True, False, False]}]),  
            ]),
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="white",
            borderwidth=1
        ),
        
        dict(
            type="buttons",
            direction="right",
            active=0,
            x=0.1,
            y=1.12,
            buttons=list([
                dict(label="🔍+ بزرگنمایی عمودی", method="relayout", 
                     args=[{"yaxis.range": [rates_df['low'].min() * 0.99, rates_df['high'].max() * 1.01]}]),
                dict(label="🔍- کوچک‌نمایی عمودی", method="relayout", 
                     args=[{"yaxis.range": [rates_df['low'].min() * 0.95, rates_df['high'].max() * 1.05]}]),
                dict(label="↕️ بازنشانی محور عمودی", method="relayout", 
                     args=[{"yaxis.autorange": True}]),
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
        'height': 800,
        'width': 1400,
        'scale': 2
    }
}

special_trades_count = len(positions_df[positions_df['is_special'] == 1]) if len(positions_df) > 0 else 0

stats_text = f"""
<b>آمار کلی معاملات</b><br>
تعداد کل معاملات: {len(df)}<br>
تعداد موقعیت‌ها: {len(positions_df)}<br>
معاملات ویژه: {special_trades_count}<br>
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

output_file = "tradingview_fixed_chart.html"
fig.write_html(output_file, config=config)
webbrowser.open(output_file)
print("successful")