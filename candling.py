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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server
local_tz = pytz.timezone('Asia/Tehran')
mt5_initialized = False


def initialize_mt5():
    global mt5_initialized
    if not mt5_initialized:
        for attempt in range(3):
            if mt5.initialize(login=5032847392, password="NnN!1rTo", server="MetaQuotes-Demo"):
                mt5_initialized = True
                logger.info("اتصال به MT5 با موفقیت انجام شد")
                return True
            logger.error(f"اتصال ناموفق، تلاش {attempt+1}/3")
            time.sleep(0.5)
        logger.error("اتصال به MT5 پس از 3 تلاش ناموفق بود")
        return False
    return True


def axis_dtick_and_format(days_float: float):
    minutes = days_float * 1440.0
    if minutes <= 30:
        return 60 * 1000, "%H:%M"
    if minutes <= 60:
        return 5 * 60 * 1000, "%H:%M"
    if minutes <= 4*60:
        return 15 * 60 * 1000, "%H:%M"
    if minutes <= 24*60:
        return 60 * 60 * 1000, "%d %b %H:%M"
    if days_float <= 7:
        return 24 * 60 * 60 * 1000, "%Y-%m-%d"
    if days_float <= 30:
        return "M1", "%b %Y"
    if days_float <= 90:
        return "M1", "%b %Y"
    if days_float <= 180:
        return "M1", "%b %Y"
    if days_float <= 365:
        return "M3", "%b %Y"
    if days_float <= 730:
        return "M6", "%b %Y"
    return "M12", "%Y"

def pick_mt5_timeframe(start_utc: datetime, end_utc: datetime):
    total_minutes = (end_utc - start_utc).total_seconds() / 60.0
    if total_minutes <= 120:
        return mt5.TIMEFRAME_M1
    if total_minutes <= 24*60:
        return mt5.TIMEFRAME_M5
    if total_minutes <= 3*24*60:
        return mt5.TIMEFRAME_M15
    if total_minutes <= 7*24*60:
        return mt5.TIMEFRAME_M30
    if total_minutes <= 30*24*60:
        return mt5.TIMEFRAME_H1
    if total_minutes <= 90*24*60:
        return mt5.TIMEFRAME_H4
    if total_minutes <= 365*24*60:
        return mt5.TIMEFRAME_D1
    return mt5.TIMEFRAME_W1

def get_smaller_timeframe(tf):
    """برگرداندن تایم‌فریم کوچکتر برای اعتبارسنجی"""
    timeframe_map = {
        mt5.TIMEFRAME_M5: mt5.TIMEFRAME_M1,
        mt5.TIMEFRAME_M15: mt5.TIMEFRAME_M5,
        mt5.TIMEFRAME_M30: mt5.TIMEFRAME_M15,
        mt5.TIMEFRAME_H1: mt5.TIMEFRAME_M30,
        mt5.TIMEFRAME_H4: mt5.TIMEFRAME_H1,
        mt5.TIMEFRAME_D1: mt5.TIMEFRAME_H4,
        mt5.TIMEFRAME_W1: mt5.TIMEFRAME_D1
    }
    return timeframe_map.get(tf, None)

def get_symbol_digits(symbol):
    """دریافت تعداد ارقام اعشار نماد"""
    if not initialize_mt5():
        return 5
    
    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is not None:
            return symbol_info.digits
        return 5
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات نماد {symbol}: {str(e)}")
        return 5


@lru_cache(maxsize=32)
def get_rates_data(symbol, start_time, end_time, timeframe=None, force_refresh=False):
    if not initialize_mt5():
        return pd.DataFrame(), False
    
    try:
        mt5.symbol_select(symbol, True)
        tf = timeframe if timeframe is not None else pick_mt5_timeframe(start_time, end_time)
        rates = mt5.copy_rates_range(symbol, tf, start_time, end_time)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"داده‌ای برای {symbol} دریافت نشد")
            return pd.DataFrame(), True
            
        rates_df = pd.DataFrame(rates)
        rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s', utc=True)
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
        deals = mt5.history_deals_get(start_time, end_time)
        if deals is None or len(deals) == 0:
            logger.info(f"معامله‌ای برای {symbol} یافت نشد")
            return pd.DataFrame(), True
            
        deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        deals_df['time'] = pd.to_datetime(deals_df['time'], unit='s', utc=True)
        
        
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

def create_chart_with_data(rates_df, deals_df, symbol, timeframe_days, chart_type, visible_range_days=None):
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
            rangeslider=dict(visible=True, thickness=0.05),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            )
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
    
    
    range_for_ticks = visible_range_days if visible_range_days is not None else timeframe_days
    dtick_val, tickformat_val = axis_dtick_and_format(range_for_ticks)
    fig.update_xaxes(tickformat=tickformat_val, dtick=dtick_val)
    
    digits = get_symbol_digits(symbol)
    price_format = f".{digits}f"
    
    
    if rates_df is not None and not rates_df.empty:
        df = rates_df.copy()
        df['time'] = df['time'].dt.tz_convert(local_tz)
        
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
                hovertext=[
                    f"<b>Date:</b> {d}<br>"
                    f"<b>Open:</b> {o:{price_format}}<br>"
                    f"<b>High:</b> {h:{price_format}}<br>"
                    f"<b>Low:</b> {l:{price_format}}<br>"
                    f"<b>Close:</b> {c:{price_format}}"
                    for d, o, h, l, c in zip(
                        df['time'].dt.strftime('%Y-%m-%d %H:%M:%S'),
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
                        df['time'].dt.strftime('%Y-%m-%d %H:%M:%S'),
                        df['close']
                    )
                ],
                visible=True
            ))
    
    
    if deals_df is not None and not deals_df.empty:
        dd = deals_df.copy()
        dd['time'] = dd['time'].dt.tz_convert(local_tz)
        
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
                times   = sub['time'].tolist()
                symbols = s_list(sub, 'symbol', symbol)
                
                
                hover_text = [
                    f"<b>{ttype.upper()}</b><br>"
                    f"<b>Ticket:</b> {tk}<br>"
                    f"<b>Symbol:</b> {sym}<br>"
                    f"<b>Time:</b> {tm.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                    f"<b>Price:</b> {pr:{price_format}}<br>"
                    f"<b>Volume:</b> {vl:,.0f}<br>" if vl is not None else ""
                    f"<b>Profit:</b> {pf:,.2f}" if pf is not None else ""
                    for tk, tm, pr, vl, pf, sym in zip(tickets, times, prices, vols, profits, symbols)
                ]
                
                fig.add_trace(go.Scatter(
                    x=times,
                    y=prices,
                    mode='markers',
                    marker=dict(
                        symbol=marker_symbol, 
                        size=12, 
                        color=color, 
                        line=dict(width=2, color='white'),
                        opacity=0.9
                    ),
                    name=f'{ttype.capitalize()} Deals',
                    hoverinfo='text',
                    hovertext=hover_text,
                    showlegend=True,
                    marker_line_width=2,
                    marker_size=12
                ))
    
    return fig

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


app.layout = dbc.Container([
    html.Div([
        html.H1("Trading Chart", className="text-center mb-4",
                style={'color': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '24px'}),
        html.P("Real-time price chart with your trading history",
               className="text-center mb-4", style={'color': '#C9D1D9'})
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
                        {'label': '1 Minute', 'value': 1/1440},
                        {'label': '5 Minutes', 'value': 5/1440},
                        {'label': '15 Minutes', 'value': 15/1440},
                        {'label': '30 Minutes', 'value': 30/1440},
                        {'label': '1 Hour', 'value': 1/24},
                        {'label': '4 Hours', 'value': 4/24},
                        {'label': '1 Day', 'value': 1},
                        {'label': '1 Week', 'value': 7},
                        {'label': '1 Month', 'value': 30},
                        {'label': '3 Months', 'value': 90},
                        {'label': '6 Months', 'value': 180},
                        {'label': '1 Year', 'value': 365},
                        {'label': '2 Years', 'value': 730},
                        {'label': '5 Years', 'value': 1825}
                    ],
                    value=7,
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
                        'zoom2d', 'pan2d', 'select2d', 'lasso2d',
                        'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
                    ]
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
def update_chart(selected_symbol, timeframe_days, chart_type, relayout_data, n_intervals, 
                reset_trigger, current_figure, last_timeframe, last_symbol):
    timeframe_changed = last_timeframe != timeframe_days
    symbol_changed = last_symbol != selected_symbol
    end_date_utc = datetime.now(timezone.utc)
    
    
    start_date_utc = end_date_utc - timedelta(days=timeframe_days)
    manual_zoom = False
    visible_range_days = None
    
   
    if relayout_data and ('xaxis.range' in relayout_data or 'xaxis.range[0]' in relayout_data) and not timeframe_changed and not symbol_changed:
        try:
            if 'xaxis.range' in relayout_data:
                start_local = pd.to_datetime(relayout_data['xaxis.range'][0])
                end_local   = pd.to_datetime(relayout_data['xaxis.range'][1])
            else:
                start_local = pd.to_datetime(relayout_data['xaxis.range[0]'])
                end_local   = pd.to_datetime(relayout_data['xaxis.range[1]'])
                
            if start_local.tzinfo is None:
                start_local = local_tz.localize(start_local)
            if end_local.tzinfo is None:
                end_local = local_tz.localize(end_local)
                
            start_date_utc = start_local.astimezone(timezone.utc)
            end_date_utc   = end_local.astimezone(timezone.utc)
            manual_zoom = True
            
            
            visible_range_days = (end_local - start_local).days + (end_local - start_local).seconds / (24*3600)
        except Exception:
            pass
    
    
    if timeframe_changed or symbol_changed:
        manual_zoom = False
        start_date_utc = end_date_utc - timedelta(days=timeframe_days)
        visible_range_days = None
    
    
    mt5_tf = pick_mt5_timeframe(start_date_utc, end_date_utc)
    
    
    rates_df, rates_status = get_rates_data(
        selected_symbol, start_date_utc, end_date_utc, 
        timeframe=mt5_tf, force_refresh=manual_zoom or timeframe_changed or symbol_changed
    )
    
    deals_df, deals_status = get_deals_data(
        selected_symbol, start_date_utc, end_date_utc
    )
    
   
    if not rates_status and not deals_status:
        fig = create_error_chart("Cannot connect to MT5")
    elif rates_df is None or rates_df.empty:
        fig = create_error_chart("No data from MT5 for the selected range/symbol", "#FF9800")
    else:
        fig = create_chart_with_data(rates_df, deals_df, selected_symbol, timeframe_days, chart_type, visible_range_days)
        
        
        if manual_zoom and relayout_data:
            try:
                if 'xaxis.range' in relayout_data:
                    fig.update_layout(xaxis_range=relayout_data['xaxis.range'])
                else:
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
    return str(datetime.now(timezone.utc))

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
    [Output('last-timeframe', 'data'),
     Output('last-symbol', 'data')],
    [Input('timeframe-dropdown', 'value'),
     Input('symbol-dropdown', 'value')]
)
def update_last_values(timeframe, symbol):
    return timeframe, symbol


def open_in_chrome(url):
    try:
        chrome_path = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        if os.path.exists(chrome_path):
            webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
            webbrowser.get('chrome').open(url)
            return
        chrome_path = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
        if os.path.exists(chrome_path):
            webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
            webbrowser.get('chrome').open(url)
            return
        webbrowser.open(url)
    except:
        webbrowser.open(url)


if __name__ == '__main__':
    open_in_chrome('http://127.0.0.1:8050/')
    app.run(debug=False, use_reloader=False, host='127.0.0.1', port=8050)