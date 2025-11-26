import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Pro Trading Dashboard", layout="wide")
try:
    API_KEY = st.secrets["FMP_API_KEY"]
except:
    # Esto es por si lo corres en tu PC local sin configurar secretos
    API_KEY = "TU_API_KEY_AQUI_SOLO_PARA_LOCAL"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- FUNCIONES DE CARGA DE DATOS ---
@st.cache_data(ttl=300) # Cache de 5 minutos para no saturar la API
def get_json(endpoint, params=None):
    if params is None:
        params = {}
    params['apikey'] = API_KEY
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        st.error(f"Error conectando a la API: {e}")
        return []

# --- 1. STOCK SCREENER (CORREGIDO CON NUEVO ENDPOINT) ---
def show_screener():
    st.header("🔍 Stock Screener")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        limit = st.number_input("Cantidad de resultados", min_value=10, max_value=1000, value=50)
    with col2:
        # El input es en Millones, lo multiplicamos para la API
        min_cap_input = st.number_input("Min Market Cap (Millions)", value=1000)
        min_market_cap = min_cap_input * 1000000
    with col3:
        sector = st.selectbox("Sector", ["Technology", "Healthcare", "Financial Services", "Energy", "Consumer Cyclical", "All"], index=5)

    if st.button("Ejecutar Screener"):
        # Usamos los parámetros exactos de la documentación que enviaste
        params = {
            'marketCapMoreThan': min_market_cap,
            'limit': limit,
            'isEtf': 'false',
            'isActivelyTrading': 'true'
        }
        if sector != "All":
            params['sector'] = sector
            
        # CAMBIO CLAVE: Usamos "company-screener" en lugar de "stock-screener"
        # Nota: La base URL es api/v3, al concatenar queda api/v3/company-screener
        # Si falla, intentaremos forzar la url 'stable'
        
        # Intentamos primero con la estructura estándar
        data = get_json("company-screener", params)

        # Verificación de datos
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            
            # Definimos las columnas basados en el JSON que me mostraste
            cols_to_show = ['symbol', 'companyName', 'price', 'beta', 'marketCap', 'sector', 'industry', 'lastAnnualDividend', 'volume']
            
            # Filtramos solo las que existan para evitar errores
            available_cols = [c for c in cols_to_show if c in df.columns]
            
            # Formateo visual
            st.dataframe(
                df[available_cols].style.format({
                    'price': '${:.2f}', 
                    'beta': '{:.2f}', 
                    'marketCap': '${:,.0f}',
                    'volume': '{:,.0f}'
                }),
                use_container_width=True
            )
        
        elif isinstance(data, dict) and 'Error Message' in data:
            st.error(f"Error FMP: {data['Error Message']}")
        else:
            st.warning("No se encontraron resultados con esos filtros.")

# --- 2. ECONOMIC CALENDAR ---
def show_calendar():
    st.header("📅 Economic Calendar")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Desde", datetime.now())
    with col2:
        end_date = st.date_input("Hasta", datetime.now() + timedelta(days=7))
        
    if st.button("Cargar Calendario"):
        params = {'from': start_date, 'to': end_date}
        data = get_json("economic_calendar", params)
        
        if data:
            df = pd.DataFrame(data)
            # Limpieza y orden
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values(by='date')
                
                # Mapeo de impacto para colores (si existiera) o formato simple
                st.dataframe(
                    df[['date', 'country', 'event', 'actual', 'estimate', 'impact']],
                    use_container_width=True
                )
            else:
                st.info("No hay eventos económicos para este rango.")

# --- 3. INFORMACIÓN DE SÍMBOLOS ---
def show_symbol_info():
    st.header("ℹ️ Información de Símbolo")
    symbol = st.text_input("Ingresa el Ticker (ej. AAPL, TSLA)", "AAPL").upper()
    
    if symbol:
        data = get_json(f"profile/{symbol}")
        if data:
            profile = data[0]
            
            c1, c2 = st.columns([1, 3])
            with c1:
                st.image(profile.get('image'), width=100)
                st.metric("Precio Actual", f"${profile.get('price')}")
                st.metric("Beta", f"{profile.get('beta')}")
            
            with c2:
                st.subheader(profile.get('companyName'))
                st.write(f"**Sector:** {profile.get('sector')}")
                st.write(f"**Industria:** {profile.get('industry')}")
                st.write(f"**CEO:** {profile.get('ceo')}")
                st.write(f"**Descripción:** {profile.get('description')}")
                st.write(f"[Web Oficial]({profile.get('website')})")

# --- 4. TREND ANALYSIS (Técnico) ---
def show_trend_analysis():
    st.header("📈 Trend Analysis & Charts")
    symbol = st.text_input("Ticker para análisis", "NVDA").upper()
    
    if symbol:
        # Obtener histórico diario
        data = get_json(f"historical-price-full/{symbol}")
        
        if data and 'historical' in data:
            hist_data = data['historical'][:200] # Últimos 200 días
            df = pd.DataFrame(hist_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Crear gráfico de velas con Plotly
            fig = go.Figure(data=[go.Candlestick(x=df['date'],
                            open=df['open'],
                            high=df['high'],
                            low=df['low'],
                            close=df['close'],
                            name='Precio')])
            
            # Agregar medias móviles simples (cálculo manual rápido)
            df['SMA_50'] = df['close'].rolling(window=50).mean()
            df['SMA_20'] = df['close'].rolling(window=20).mean()
            
            fig.add_trace(go.Scatter(x=df['date'], y=df['SMA_50'], line=dict(color='orange', width=1), name='SMA 50'))
            fig.add_trace(go.Scatter(x=df['date'], y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
            
            fig.update_layout(title=f"Análisis de Tendencia: {symbol}", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Datos técnicos rápidos
            latest = df.iloc[0]
            st.write(f"**Cambio Diario:** {latest['changePercent']}%")
            st.write(f"**Volumen:** {latest['volume']:,}")

# --- 5. CURRENCY STRENGTH METER ---
def show_currency_meter():
    st.header("💪 Currency Strength Meter (CSM)")
    st.info("Calculado basado en el cambio porcentual de las últimas 24h frente al USD.")
    
    # Lógica: Obtenemos los pares mayores y calculamos la fuerza relativa
    # FMP Endpoint para forex
    majors = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD']
    data = get_json(f"quotes/forex")
    
    if data:
        df = pd.DataFrame(data)
        # Filtrar solo los majors
        df = df[df['symbol'].isin(majors)]
        
        strength_scores = {}
        
        # Calcular fuerza relativa base USD
        # Si el par es XXXUSD y sube -> XXX es fuerte.
        # Si el par es USDXXX y sube -> XXX es debil.
        
        for index, row in df.iterrows():
            sym = row['symbol']
            change = row['changesPercentage']
            
            if sym in ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD']:
                base = sym[:3] # EUR, GBP...
                strength_scores[base] = change
            elif sym in ['USDJPY', 'USDCHF', 'USDCAD']:
                quote = sym[3:] # JPY, CHF...
                strength_scores[quote] = -change # Inverso porque USD es base
        
        # El USD es el promedio inverso de los demás o 0 relativo (simplificado aquí como punto de pivote)
        strength_scores['USD'] = 0.0
        
        # Crear DataFrame para visualizar
        df_strength = pd.DataFrame(list(strength_scores.items()), columns=['Moneda', 'Fuerza'])
        df_strength = df_strength.sort_values(by='Fuerza', ascending=False)
        
        # Visualización de barras
        fig = go.Figure(go.Bar(
            x=df_strength['Fuerza'],
            y=df_strength['Moneda'],
            orientation='h',
            marker=dict(
                color=df_strength['Fuerza'],
                colorscale='RdYlGn' # Rojo para negativo, Verde para positivo
            )
        ))
        fig.update_layout(title="Fuerza Relativa de Divisas (Intradía)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df_strength, use_container_width=True)

# --- NAVEGACIÓN PRINCIPAL ---
def main():
    st.sidebar.title("🛠️ Trading Tools")
    st.sidebar.write("Powered by FMP API")
    
    option = st.sidebar.radio("Ir a:", 
                              ["Stock Screener", "Economic Calendar", "Info Símbolos", "Trend Analysis", "Currency Strength"])
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Datos provistos por Financial Modeling Prep")

    if option == "Stock Screener":
        show_screener()
    elif option == "Economic Calendar":
        show_calendar()
    elif option == "Info Símbolos":
        show_symbol_info()
    elif option == "Trend Analysis":
        show_trend_analysis()
    elif option == "Currency Strength":
        show_currency_meter()

if __name__ == "__main__":
    main()