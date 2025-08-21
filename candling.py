import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone
import numpy as np
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import webbrowser
import os
import pytz
import logging
from functools import lru_cache
import time
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server
local_tz = pytz.timezone('Asia/Tehran')
mt5_initialized = False
mt5_lock = threading.Lock()


TIME_ADJUSTMENT = timedelta(hours=-2, minutes=-12) 

def initialize_mt5():
    global mt5_initialized
    if not mt5_initialized:
        with mt5_lock:
            if not mt5_initialized:
                for attempt in range(3):
                    try:
                        if mt5.initialize(login=5032847392, password="NnN!1rTo", server="MetaQuotes-Demo"):
                            mt5_initialized = True
                            logger.info("اتصال به MT5 با موفقیت انجام شد")
                            return True
                    except Exception as e:
                        logger.error(f"خطا در تلاش اتصال {attempt+1}: {str(e)}")
                    
                    logger.error(f"اتصال ناموفق، تلاش {attempt+1}/3")
                    time.sleep(1)
                
                logger.error("اتصال به MT5 پس از 3 تلاش ناموفق بود")
                return False
    return True

def get_server_time():
    """دریافت زمان فعلی از سرور MT5 (UTC)"""
    if not initialize_mt5():
        return datetime.now(timezone.utc)
    
    try:
        with mt5_lock:
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.warning("نتوانستیم اطلاعات ترمینال را دریافت کنیم")
                return datetime.now(timezone.utc)
            
            
            server_time_utc = datetime.fromtimestamp(terminal_info.trade_server_time, tz=timezone.utc)
            
            logger.info(f"زمان سرور (UTC): {server_time_utc}")
            
            return server_time_utc
    except Exception as e:
        logger.error(f"خطا در دریافت زمان سرور: {str(e)}")
        return datetime.now(timezone.utc)

def convert_utc_to_tehran(utc_time):
    """تبدیل زمان UTC به زمان تهران با اصلاح برای نمایش 10:48"""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    
    
    tehran_time = utc_time + timedelta(hours=1, minutes=12)
    
    
    tehran_time = tehran_time + TIME_ADJUSTMENT
    
    
    tehran_time = tehran_time.replace(tzinfo=local_tz)
    
    return tehran_time

def get_symbol_digits(symbol):
    if not initialize_mt5():
        return 5
    
    try:
        with mt5_lock:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is not None:
                return symbol_info.digits
        return 5
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات نماد {symbol}: {str(e)}")
        return 5

@lru_cache(maxsize=32)
def get_rates_data(symbol, start_time, end_time, timeframe, force_refresh=False):
    if not initialize_mt5():
        return pd.DataFrame(), False
    
    try:
        with mt5_lock:
            mt5.symbol_select(symbol, True)
            rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"داده‌ای برای {symbol} دریافت نشد")
            return pd.DataFrame(), True
            
        rates_df = pd.DataFrame(rates)
        
        rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s', utc=True)
        rates_df['time'] = rates_df['time'].apply(convert_utc_to_tehran)
        
        rates_df = rates_df.sort_values('time').reset_index(drop=True)
        
        original_count = len(rates_df)
        rates_df = rates_df[rates_df['open'] > 0]
        rates_df = rates_df[rates_df['high'] > 0]
        rates_df = rates_df[rates_df['low'] > 0]
        rates_df = rates_df[rates_df['close'] > 0]
        rates_df = rates_df.dropna(subset=['open', 'high', 'low', 'close'])
        rates_df = rates_df[rates_df['high'] >= rates_df['low']]
        
        if len(rates_df) < original_count:
            logger.warning(f"پاک‌سازی داده‌های نامعتبر: {original_count - len(rates_df)} ردیف حذف شد")
        
        logger.info(f"داده‌های قیمت برای {symbol} با موفقیت دریافت شد")
        return rates_df, True
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های قیمت {symbol}: {str(e)}")
        return pd.DataFrame(), False

@lru_cache(maxsize=16)
def get_deals_data(symbol, start_time, end_time):
    if not initialize_mt5():
        return pd.DataFrame(), False
    
    try:
        with mt5_lock:
            deals = mt5.history_deals_get(start_time, end_time)
        
        if deals is None or len(deals) == 0:
            logger.info(f"معامله‌ای برای {symbol} یافت نشد")
            return pd.DataFrame(), True
            
        deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
         
        deals_df['time'] = pd.to_datetime(deals_df['time'], unit='s', utc=True)
        deals_df['time'] = deals_df['time'].apply(convert_utc_to_tehran)
        
        if 'symbol' in deals_df.columns:
            deals_df = deals_df[deals_df['symbol'] == symbol]
            
        deals_df = deals_df[deals_df['type'].isin([0, 1])]
        deals_df['type'] = deals_df['type'].map({0: 'buy', 1: 'sell'})
        deals_df = deals_df.sort_values('time').reset_index(drop=True)
        
        if 'ticket' in deals_df.columns:
            deals_df = deals_df.dropna(subset=['ticket'])
            deals_df = deals_df.drop_duplicates(subset=['ticket'])  
            deals_df['ticket'] = deals_df['ticket'].astype('int64')  
        
        original_count = len(deals_df)
        deals_df = deals_df[deals_df['price'] > 0]
        if 'volume' in deals_df.columns:
            deals_df = deals_df[deals_df['volume'] > 0]
            
        if len(deals_df) < original_count:
            logger.warning(f"پاک‌سازی معاملات نامعتبر: {original_count - len(deals_df)} ردیف حذف شد")
            
        logger.info(f"داده‌های معاملات برای {symbol} با موفقیت دریافت شد")
        return deals_df, True
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های معاملات {symbol}: {str(e)}")
        return pd.DataFrame(), False

def create_empty_chart():
    fig = go.Figure()
    fig.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0D1117',
        paper_bgcolor='#0D1117',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="Loading chart data...",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                font=dict(color="#C9D1D9", size=16),
                bgcolor="rgba(22,27,34,0.8)",
                bordercolor="#30363D",
                borderwidth=1,
                borderpad=10
            )
        ]
    )
    return fig

def create_chart_with_data(rates_df, deals_df, symbol, timeframe_minutes, chart_type, visible_range_minutes=None):
    fig = go.Figure()
    
    fig.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0D1117',
        paper_bgcolor='#0D1117',
        font=dict(color='#C9D1D9', family='Arial'),
        height=700,
        margin=dict(l=50, r=50, t=50, b=50),
        title=dict(
            text=f'<b>Trading Chart - {symbol}</b>', 
            font=dict(size=20, color='#FFFFFF', family='Arial'),
            x=0.05, y=0.95, xanchor='left', yanchor='top'
        ),
        xaxis=dict(
            type='date',
            gridcolor='#21262D',
            zerolinecolor='#21262D',
            tickcolor='#484F58',
            linecolor='#30363D',
            showgrid=True,
            showticklabels=True,
            tickfont=dict(size=10),
            fixedrange=False,
            autorange=True,
            rangeslider=dict(visible=True, thickness=0.03, bgcolor='#161B22'),
            rangeselector=None
        ),
        yaxis=dict(
            title=dict(text='Price', font=dict(size=12)),
            gridcolor='#21262D',
            zerolinecolor='#21262D',
            tickcolor='#484F58',
            linecolor='#30363D',
            showgrid=True,
            tickfont=dict(size=10),
            autorange=True,
            fixedrange=False
        ),
        legend=dict(
            orientation='h', 
            yanchor='bottom', 
            y=0.02, 
            xanchor='left', 
            x=0.02,
            font=dict(size=10), 
            bgcolor='rgba(13, 17, 23, 0.8)', 
            bordercolor='#30363D', 
            borderwidth=1
        ),
        hovermode='x unified',
        dragmode='pan',
        hoverlabel=dict(
            bgcolor='#161B22', 
            font_size=11, 
            font_color='#C9D1D9', 
            bordercolor='#30363D'
        ),
        xaxis_rangeslider_visible=True,
        modebar_add=[
            "zoom2d", "pan2d", "select2d", "lasso2d", 
            "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"
        ],
        showlegend=True,
        spikedistance=1000,
        hoverdistance=100,
        uirevision='constant'  
    )
    
    visible_range = visible_range_minutes if visible_range_minutes is not None else timeframe_minutes * 100
    dtick_val, tickformat_val = calculate_axis_settings(visible_range)
    fig.update_xaxes(tickformat=tickformat_val, dtick=dtick_val)
    
    digits = get_symbol_digits(symbol)
    price_format = f".{digits}f"
    
    if rates_df is not None and not rates_df.empty:
        df = rates_df.copy()
        
        if chart_type in ['candlestick', 'both']:
            fig.add_trace(go.Candlestick(
                x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Candlestick',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
                hoverinfo='text',
                increasing_fillcolor='#26a69a',
                decreasing_fillcolor='#ef5350',
                line=dict(width=0.8),
                whiskerwidth=0.3,
                
                hovertext=[
                    f"<b>Date:</b> {d}<br>"
                    f"<b>Open:</b> {o:{price_format}}<br>"
                    f"<b>High:</b> {h:{price_format}}<br>"
                    f"<b>Low:</b> {l:{price_format}}<br>"
                    f"<b>Close:</b> {c:{price_format}}"
                    for d, o, h, l, c in zip(
                       
                        (df['time'] + timedelta(hours=1, minutes=48)).dt.strftime('%Y-%m-%d %H:%M:%S'),
                        df['open'],
                        df['high'],
                        df['low'],
                        df['close']
                    )
                ],
                visible=True
            ))
        
        if chart_type in ['line', 'both']:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['close'],
                mode='lines',
                name='Line',
                line=dict(color='#1f77b4', width=1),
                hoverinfo='text',
                
                hovertext=[
                    f"<b>Date:</b> {d}<br>"
                    f"<b>Price:</b> {c:{price_format}}"
                    for d, c in zip(
                        
                        (df['time'] + timedelta(hours=1, minutes=48)).dt.strftime('%Y-%m-%d %H:%M:%S'),
                        df['close']
                    )
                ],
                visible=True
            ))
    
    if deals_df is not None and not deals_df.empty:
        dd = deals_df.copy()
        
        
        dd['rounded_time'] = dd['time'].dt.floor(f'{timeframe_minutes}T')
        
        def s_list(dframe, col, default=None):
            return dframe[col].tolist() if col in dframe.columns else [default]*len(dframe)
        
        for ttype, color, marker_symbol in [
            ('buy', '#4CAF50', 'triangle-up'),
            ('sell', '#F44336', 'triangle-down')
        ]:
            sub = dd[dd['type'] == ttype]
            if not sub.empty:
                if 'ticket' in sub.columns:
                    tickets = sub['ticket'].astype(str).tolist()
                else:
                    tickets = ['N/A'] * len(sub)
                    
                prices  = s_list(sub, 'price', None)
                vols    = s_list(sub, 'volume', None)
                profits = s_list(sub, 'profit', None)
                times   = sub['rounded_time'].tolist()
                symbols = s_list(sub, 'symbol', symbol)
                
               
                adjusted_times = [t + timedelta(hours=1, minutes=48) for t in times]
                
                hover_text = [
                    f"<b>{ttype.upper()}</b><br>"
                    f"<b>Ticket:</b> {tk}<br>"
                    f"<b>Symbol:</b> {sym}<br>"
                    f"<b>Time:</b> {tm.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                    f"<b>Price:</b> {pr:{price_format}}<br>"
                    f"<b>Volume:</b> {vl:,.0f}<br>" if vl is not None else ""
                    f"<b>Profit:</b> {pf:,.2f}" if pf is not None else ""
                    for tk, tm, pr, vl, pf, sym in zip(tickets, adjusted_times, prices, vols, profits, symbols)
                ]
                
                fig.add_trace(go.Scatter(
                    x=times,
                    y=prices,
                    mode='markers',
                    marker=dict(
                        symbol=marker_symbol, 
                        size=10, 
                        color=color, 
                        line=dict(width=1, color='white'),
                        opacity=0.9
                    ),
                    name=f'{ttype.capitalize()} Deals',
                    hoverinfo='text',
                    hovertext=hover_text,
                    showlegend=True,
                    marker_line_width=1,
                    marker_size=10
                ))
    
    return fig

def calculate_axis_settings(visible_range_minutes):
    """محاسبه تنظیمات محور زمانی بر اساس بازه visible"""
    if visible_range_minutes <= 60:
        dtick = 5 * 60 * 1000  
        tickformat = "%H:%M"
    elif visible_range_minutes <= 240:
        dtick = 15 * 60 * 1000  
        tickformat = "%H:%M"
    elif visible_range_minutes <= 1440:
        dtick = 60 * 60 * 1000  
        tickformat = "%m-%d %H:%M"
    elif visible_range_minutes <= 10080:
        dtick = 24 * 60 * 60 * 1000  
        tickformat = "%Y-%m-%d"
    elif visible_range_minutes <= 43200:
        dtick = 7 * 24 * 60 * 60 * 1000   
        tickformat = "%Y-%m-%d"
    elif visible_range_minutes <= 525600:  
        dtick = "M1"  
        tickformat = "%b %Y"
    elif visible_range_minutes <= 1051200:  
        dtick = "M3"  
        tickformat = "%b %Y"
    elif visible_range_minutes <= 2628000:  
        dtick = "M6"  
        tickformat = "%b %Y"
    else:
        dtick = "M12" 
        tickformat = "%Y"
    
    return dtick, tickformat

def create_error_chart(message, color="#F44336"):
    fig = go.Figure()
    fig.update_layout(
        template='plotly_dark',
        plot_bgcolor='#0D1117',
        paper_bgcolor='#0D1117',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                font=dict(color=color, size=16),
                bgcolor="rgba(22,27,34,0.9)",
                bordercolor=color,
                borderwidth=2,
                borderpad=10
            )
        ]
    )
    return fig

TIMEFRAME_MAPPING = {
    '1m': {'mt5': mt5.TIMEFRAME_M1, 'minutes': 1},
    '5m': {'mt5': mt5.TIMEFRAME_M5, 'minutes': 5},
    '15m': {'mt5': mt5.TIMEFRAME_M15, 'minutes': 15},
    '30m': {'mt5': mt5.TIMEFRAME_M30, 'minutes': 30},
    '1h': {'mt5': mt5.TIMEFRAME_H1, 'minutes': 60},
    '4h': {'mt5': mt5.TIMEFRAME_H4, 'minutes': 240},
    '1d': {'mt5': mt5.TIMEFRAME_D1, 'minutes': 1440},
    '1w': {'mt5': mt5.TIMEFRAME_W1, 'minutes': 10080},
    '1M': {'mt5': mt5.TIMEFRAME_MN1, 'minutes': 43200}
}

app.layout = dbc.Container([
    html.Div([
        html.H1("Trading Chart", className="text-center mb-4",
                style={'color': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '24px'}),
        html.P("Real-time price chart with your trading history",
               className="text-center mb-4", style={'color': '#C9D1D9'}),
        html.Div(id='server-time-display', className="text-center mb-2", 
                 style={'color': '#C9D1D9', 'fontSize': '12px'})
    ], style={'backgroundColor': '#161B22', 'padding': '20px 0'}),
    
    html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Select Symbol", className="form-label text-light"),
                dcc.Dropdown(
                    id='symbol-dropdown',
                    options=[
                        {'label': 'EUR/USD', 'value': 'EURUSD'},
                        {'label': 'GBP/USD', 'value': 'GBPUSD'},
                        {'label': 'USD/JPY', 'value': 'USDJPY'},
                        {'label': 'USD/CHF', 'value': 'USDCHF'},
                        {'label': 'AUD/USD', 'value': 'AUDUSD'},
                        {'label': 'USD/CAD', 'value': 'USDCAD'},
                        {'label': 'NZD/USD', 'value': 'NZDUSD'},
                        {'label': 'Gold (XAU/USD)', 'value': 'XAUUSD'},
                        {'label': 'Silver (XAG/USD)', 'value': 'XAGUSD'},
                        {'label': 'Oil (XTI/USD)', 'value': 'XTIUSD'}
                    ],
                    value='EURUSD',
                    clearable=False,
                    className="bg-dark text-light border-secondary"
                )
            ], width=3),
            
            dbc.Col([
                html.Label("Select Timeframe", className="form-label text-light"),
                dcc.Dropdown(
                    id='timeframe-dropdown',
                    options=[
                        {'label': '1 Minute', 'value': '1m'},
                        {'label': '5 Minutes', 'value': '5m'},
                        {'label': '15 Minutes', 'value': '15m'},
                        {'label': '30 Minutes', 'value': '30m'},
                        {'label': '1 Hour', 'value': '1h'},
                        {'label': '4 Hours', 'value': '4h'},
                        {'label': '1 Day', 'value': '1d'},
                        {'label': '1 Week', 'value': '1w'},
                        {'label': '1 Month', 'value': '1M'}
                    ],
                    value='1h',
                    clearable=False,
                    className="bg-dark text-light border-secondary"
                )
            ], width=3),
            
            dbc.Col([
                html.Label("Chart Type", className="form-label text-light"),
                dcc.Dropdown(
                    id='chart-type-dropdown',
                    options=[
                        {'label': 'Candlestick', 'value': 'candlestick'},
                        {'label': 'Line', 'value': 'line'},
                        {'label': 'Both', 'value': 'both'}
                    ],
                    value='candlestick',
                    clearable=False,
                    className="bg-dark text-light border-secondary"
                )
            ], width=3),
            
            dbc.Col([
                html.Label("Quick Actions", className="form-label text-light"),
                html.Div([
                    dbc.Button("Reset Zoom", id="reset-zoom-btn", color="primary", size="sm", className="me-2"),
                    dbc.Button("Refresh Data", id="refresh-btn", color="secondary", size="sm")
                ])
            ], width=3)
        ])
    ], className="bg-dark p-3 mb-4", style={'borderRadius': '8px'}),
    
    dcc.Loading(
        id="loading-icon",
        children=[
            dcc.Graph(
                id='price-chart',
                figure=create_empty_chart(),
                config={
                    'displayModeBar': True,
                    'scrollZoom': True,
                    'displaylogo': False,
                    'modeBarButtonsToAdd': [
                        "zoom2d", "pan2d", "select2d", "lasso2d", 
                        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"
                    ],
                    'doubleClick': 'reset+autosize'
                },
                style={
                    'height': '600px', 
                    'backgroundColor': '#0D1117',
                    'border': '1px solid #30363D',
                    'borderRadius': '8px'
                }
            )
        ],
        type="circle",
        color='#2196F3'
    ),
    
    dcc.Interval(id='interval-component', interval=30*1000, n_intervals=0),
    html.Div(id='reset-zoom-trigger', style={'display': 'none'}),
    dcc.Store(id='last-timeframe', storage_type='memory'),
    dcc.Store(id='last-symbol', storage_type='memory')
], fluid=True, style={'backgroundColor': '#0D1117', 'padding': '20px', 'minHeight': '100vh'})

@app.callback(
    Output('price-chart', 'figure'),
    [Input('symbol-dropdown', 'value'),
     Input('timeframe-dropdown', 'value'),
     Input('chart-type-dropdown', 'value'),
     Input('price-chart', 'relayoutData'),
     Input('interval-component', 'n_intervals'),
     Input('reset-zoom-trigger', 'children')],
    [State('price-chart', 'figure'),
     State('last-timeframe', 'data'),
     State('last-symbol', 'data')]
)
def update_chart(selected_symbol, timeframe_key, chart_type, relayout_data, n_intervals, 
                reset_trigger, current_figure, last_timeframe, last_symbol):
    logger.info(f"آپدیت نمودار برای {selected_symbol} با تایم‌فریم {timeframe_key}")
    
    timeframe_changed = last_timeframe != timeframe_key
    symbol_changed = last_symbol != selected_symbol
    
    end_date_utc = get_server_time()
    logger.info(f"زمان پایان (UTC): {end_date_utc}")
    
    end_date_tehran = convert_utc_to_tehran(end_date_utc)
    logger.info(f"زمان پایان (تهران): {end_date_tehran}")
    
    timeframe_info = TIMEFRAME_MAPPING.get(timeframe_key, TIMEFRAME_MAPPING['1h'])
    mt5_timeframe = timeframe_info['mt5']
    timeframe_minutes = timeframe_info['minutes']
    
    total_minutes = 100 * timeframe_minutes
    start_date_tehran = end_date_tehran - timedelta(minutes=total_minutes)
    logger.info(f"بازه زمانی (تهران): {start_date_tehran} تا {end_date_tehran}")
    
    start_date_utc = end_date_utc - timedelta(minutes=total_minutes)
    logger.info(f"بازه زمانی (UTC): {start_date_utc} تا {end_date_utc}")
    
    manual_zoom = False
    visible_range_minutes = None
    
    if relayout_data and not timeframe_changed and not symbol_changed:
        try:
            if 'xaxis.range' in relayout_data:
                start_local = pd.to_datetime(relayout_data['xaxis.range'][0])
                end_local = pd.to_datetime(relayout_data['xaxis.range'][1])
            elif 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                start_local = pd.to_datetime(relayout_data['xaxis.range[0]'])
                end_local = pd.to_datetime(relayout_data['xaxis.range[1]'])
            else:
                raise ValueError("فرمت relayoutData نامعتبر است")
                
            if start_local.tzinfo is None:
                start_local = local_tz.localize(start_local)
            if end_local.tzinfo is None:
                end_local = local_tz.localize(end_local)
                
            start_date_tehran = start_local
            end_date_tehran = end_local
            
            
            start_date_utc = start_date_tehran - timedelta(hours=3, minutes=30) - TIME_ADJUSTMENT
            end_date_utc = end_date_tehran - timedelta(hours=3, minutes=30) - TIME_ADJUSTMENT
            
            manual_zoom = True
            
            visible_range_minutes = (end_date_tehran - start_date_tehran).total_seconds() / 60
            logger.info(f"زوم دستی: بازه {visible_range_minutes} دقیقه")
        except Exception as e:
            logger.error(f"خطا در پردازش زوم دستی: {str(e)}")
            pass
    
    if timeframe_changed or symbol_changed:
        manual_zoom = False
        end_date_utc = get_server_time()
        end_date_tehran = convert_utc_to_tehran(end_date_utc)
        start_date_tehran = end_date_tehran - timedelta(minutes=total_minutes)
        start_date_utc = end_date_utc - timedelta(minutes=total_minutes)
        visible_range_minutes = None
        logger.info(f"تغییر تایم‌فریم یا نماد: بازه جدید محاسبه شد")
    
    rates_df, rates_status = get_rates_data(
        selected_symbol, start_date_utc, end_date_utc, 
        timeframe=mt5_timeframe, force_refresh=manual_zoom or timeframe_changed or symbol_changed
    )
    
    deals_df, deals_status = get_deals_data(
        selected_symbol, start_date_utc, end_date_utc
    )
    
    if not rates_status and not deals_status:
        fig = create_error_chart("Cannot connect to MT5")
    elif rates_df is None or rates_df.empty:
        fig = create_error_chart("No data from MT5 for the selected range/symbol", "#FF9800")
    else:
        fig = create_chart_with_data(
            rates_df, deals_df, selected_symbol, timeframe_minutes, 
            chart_type, visible_range_minutes
        )
        
        if manual_zoom and relayout_data:
            try:
                if 'xaxis.range' in relayout_data:
                    fig.update_layout(xaxis_range=relayout_data['xaxis.range'])
                elif 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                    fig.update_layout(xaxis_range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
            except Exception:
                pass
    
    return fig

@app.callback(
    Output('reset-zoom-trigger', 'children'),
    [Input('reset-zoom-btn', 'n_clicks'),
     Input('timeframe-dropdown', 'value'),
     Input('symbol-dropdown', 'value')],
    prevent_initial_call=True
)
def reset_zoom(n_clicks, timeframe, symbol):
    return str(get_server_time())

@app.callback(
    Output('refresh-btn', 'children'),
    Input('refresh-btn', 'n_clicks'),
    State('refresh-btn', 'children'),
    prevent_initial_call=True
)
def refresh_data(n_clicks, children):
    if n_clicks:
        get_rates_data.cache_clear()
        get_deals_data.cache_clear()
        return "Data Refreshed!"
    return children

@app.callback(
    Output('server-time-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_server_time_display(n):
    server_time_utc = get_server_time()
    tehran_time = convert_utc_to_tehran(server_time_utc)
    return f"Tehran Time: {tehran_time.strftime('%Y-%m-%d %H:%M:%S')}"

@app.callback(
    [Output('last-timeframe', 'data'),
     Output('last-symbol', 'data')],
    [Input('timeframe-dropdown', 'value'),
     Input('symbol-dropdown', 'value')]
)
def update_last_values(timeframe, symbol):
    return timeframe, symbol

def open_browser():
    try:
        time.sleep(0.4)
        webbrowser.open('http://127.0.0.1:8050/')
    except Exception as e:
        logger.error(f"خطا در باز کردن مرورگر: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, use_reloader=False, host='127.0.0.1', port=8050)