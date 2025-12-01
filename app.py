import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard de Multas - Maroso",
    page_icon="🚗",
    layout="wide"
)

# --- 🎨 ANIMAÇÕES CSS (O SEGREDO DO VISUAL) ---
def injetar_css():
    st.markdown("""
        <style>
        /* Define a animação de aparecer subindo */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translate3d(0, 20px, 0);
            }
            to {
                opacity: 1;
                transform: translate3d(0, 0, 0);
            }
        }

        /* Aplica nos Cartões de KPI (Métricas) */
        div[data-testid="stMetric"], div[data-testid="metric-container"] {
            animation: fadeInUp 0.5s ease-out forwards;
            background-color: #262730; /* Fundo cinza suave no cartão */
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); /* Sombra leve */
            border: 1px solid #333;
        }

        /* Aplica nos Gráficos */
        div[data-testid="stPlotlyChart"] {
            animation: fadeInUp 0.7s ease-out forwards;
        }

        /* Aplica na Tabela */
        div[data-testid="stDataFrame"] {
            animation: fadeInUp 0.9s ease-out forwards;
        }
        
        /* Ajuste fino para remover espaços brancos extras no topo */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)

# Chama a função para aplicar o estilo
injetar_css()

# --- CARREGAMENTO E LIMPEZA DE DADOS (ETL) ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        df = pd.read_csv("dados.csv", sep=";", encoding="utf-8-sig")
    except:
        df = pd.read_csv("dados.csv", sep=";", encoding="latin1")

    df.columns = df.columns.str.strip()

    # 1. Tratamento do Valor Total
    col_valor = None
    for col in df.columns:
        if "Vlr" in col or "Valor" in col:
            col_valor = col
            break
            
    if col_valor:
        df['Vlr. Total'] = df[col_valor].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df['Vlr. Total'] = pd.to_numeric(df['Vlr. Total'], errors='coerce').fillna(0)
    else:
        df['Vlr. Total'] = 0

    # 2. Tratamento da Data
    col_data = None
    for col in df.columns:
        if "DATA DEFINITIVA" in col:
            col_data = col
            break
            
    if col_data:
        df['DATA DEFINITIVA MULTA'] = pd.to_datetime(df[col_data], format='%d/%m/%Y', errors='coerce')
    else:
        df['DATA DEFINITIVA MULTA'] = pd.to_datetime('today')

    # 3. Extrair Estado
    estados_coords = {
        'PARANA': {'lat': -24.89, 'lon': -51.55, 'uf': 'PR'}, 'PR': {'lat': -24.89, 'lon': -51.55, 'uf': 'PR'},
        'MINAS': {'lat': -18.10, 'lon': -44.38, 'uf': 'MG'}, 'MG': {'lat': -18.10, 'lon': -44.38, 'uf': 'MG'},
        'PAULO': {'lat': -22.19, 'lon': -48.79, 'uf': 'SP'}, 'SP': {'lat': -22.19, 'lon': -48.79, 'uf': 'SP'},
        'CATARINA': {'lat': -27.45, 'lon': -50.95, 'uf': 'SC'}, 'SC': {'lat': -27.45, 'lon': -50.95, 'uf': 'SC'},
        'MATO GROSSO DO SUL': {'lat': -20.51, 'lon': -54.54, 'uf': 'MS'}, 'MS': {'lat': -20.51, 'lon': -54.54, 'uf': 'MS'},
        'GOIAS': {'lat': -15.98, 'lon': -49.86, 'uf': 'GO'}, 'GO': {'lat': -15.98, 'lon': -49.86, 'uf': 'GO'},
    }

    def identificar_estado(texto):
        texto = str(texto).upper()
        for estado, coords in estados_coords.items():
            if estado in texto:
                return coords['lat'], coords['lon'], coords['uf']
        return None, None, 'Outros'

    col_fornecedor = [c for c in df.columns if "Fornecedor" in c or "Orgao" in c]
    if col_fornecedor:
        coords = df[col_fornecedor[0]].apply(identificar_estado)
        df['lat'] = [x[0] for x in coords]
        df['lon'] = [x[1] for x in coords]
        df['UF'] = [x[2] for x in coords]
    
    return df

try:
    df = carregar_dados()
except Exception as e:
    st.error(f"Erro ao ler CSV: {e}")
    st.stop()

# --- SIDEBAR (FILTROS) ---
with st.sidebar:
    st.image("logo.png", width=200) 
    st.header("Filtros")
    
    # Filtros
    min_date = df['DATA DEFINITIVA MULTA'].min()
    max_date = df['DATA DEFINITIVA MULTA'].max()
    data_inicio = st.date_input("Data Início", min_date)
    data_fim = st.date_input("Data Fim", max_date)

    if 'PLACA TRATATIVA' in df.columns:
        todas_placas = st.checkbox("Todas as Placas", value=True)
        if not todas_placas:
            placas = st.multiselect("Pesquisar Placa:", df['PLACA TRATATIVA'].unique())
            if placas:
                df = df[df['PLACA TRATATIVA'].isin(placas)]
    
    if 'UF' in df.columns:
        ufs = st.multiselect("Região (UF)", df['UF'].unique(), default=df['UF'].unique())
        if ufs:
            df = df[df['UF'].isin(ufs)]

    df = df[(df['DATA DEFINITIVA MULTA'] >= pd.to_datetime(data_inicio)) & 
            (df['DATA DEFINITIVA MULTA'] <= pd.to_datetime(data_fim))]

# --- ÁREA PRINCIPAL ---

st.title("📊 Gestão de Multas - Maroso")

total_multas = df['Vlr. Total'].sum()
qtd_multas = df.shape[0]

top_infrator = "N/A"
if 'OPERAÇÃO' in df.columns:
    top_infrator = df['OPERAÇÃO'].value_counts().idxmax() if not df.empty else "N/A"

col1, col2, col3 = st.columns(3)
col1.metric("Custo Total", f"R$ {total_multas:,.2f}")
col2.metric("Qtd. Infrações", qtd_multas)
col3.metric("Maior Ofensor", top_infrator)

st.divider()

# --- GRÁFICOS ---
row1_col1, row1_col2 = st.columns([2, 1])

with row1_col1:
    st.subheader("📍 Mapa de Calor")
    if 'lat' in df.columns and not df['lat'].isnull().all():
        df_map = df.dropna(subset=['lat', 'lon'])
        fig_map = px.scatter_mapbox(
            df_map, 
            lat="lat", lon="lon", 
            color="UF",
            size="Vlr. Total",
            zoom=3, height=400,
            mapbox_style="carto-darkmatter",
            color_discrete_sequence=["#D90429", "#EF233C", "#FF5400", "#FF6D00", "#FF9E00"]
        )
        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor="#0E1117")
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Mapa indisponível.")

with row1_col2:
    st.subheader("🚫 Motivos")
    if 'OBSERVAÇÃO DEFINITIVA' in df.columns:
        fig_motivos = px.bar(
            df['OBSERVAÇÃO DEFINITIVA'].value_counts().head(10).sort_values(),
            orientation='h',
            color_discrete_sequence=["#D90429"]
        )
        fig_motivos.update_layout(showlegend=False, xaxis_title="", yaxis_title="", plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="white")
        st.plotly_chart(fig_motivos, use_container_width=True)

st.subheader("📅 Evolução")
df['Mes'] = df['DATA DEFINITIVA MULTA'].dt.to_period('M').astype(str)
df_temporal = df.groupby('Mes')['Vlr. Total'].sum().reset_index()
fig_line = px.line(df_temporal, x='Mes', y='Vlr. Total', markers=True)
fig_line.update_traces(line_color="#D90429")
fig_line.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="white")
st.plotly_chart(fig_line, use_container_width=True)

# --- TABELA ---
st.divider()
st.subheader("📋 Detalhamento das Multas")
colunas_para_tabela = ['DATA DEFINITIVA MULTA', 'PLACA TRATATIVA', 'OBSERVAÇÃO DEFINITIVA', 'Vlr. Total', 'OPERAÇÃO', 'Fornecedor']
cols_existentes = [c for c in colunas_para_tabela if c in df.columns]

st.dataframe(
    df[cols_existentes].sort_values('DATA DEFINITIVA MULTA', ascending=False),
    use_container_width=True,
    hide_index=True
)