import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard de Multas - Maroso",
    page_icon="🚗",
    layout="wide"
)

# --- CARREGAMENTO E LIMPEZA DE DADOS (ETL) ---
@st.cache_data(ttl=0) # ttl=0 força recarregar sempre, ótimo para testes
def carregar_dados():
    # Tenta carregar com 'utf-8-sig' que lida melhor com caracteres especiais do Excel
    try:
        df = pd.read_csv("dados.csv", sep=";", encoding="utf-8-sig")
    except:
        # Se falhar, tenta latin1
        df = pd.read_csv("dados.csv", sep=";", encoding="latin1")

    # --- O PULO DO GATO PARA O ERRO 'ID' ---
    # Remove espaços em branco antes e depois dos nomes das colunas
    df.columns = df.columns.str.strip()
    
    # Se a primeira coluna não se chamar 'ID' exatamente, forçamos a renomeação
    # (Isso resolve problemas de caracteres invisíveis no início do arquivo)
    coluna_id_real = df.columns[0]
    df.rename(columns={coluna_id_real: 'ID'}, inplace=True)
    # ---------------------------------------

    # 1. Tratamento do Valor Total
    if 'Vlr. Total' in df.columns:
        df['Vlr. Total'] = df['Vlr. Total'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df['Vlr. Total'] = pd.to_numeric(df['Vlr. Total'], errors='coerce').fillna(0)

    # 2. Tratamento da Data
    if 'DATA DEFINITIVA MULTA' in df.columns:
        df['DATA DEFINITIVA MULTA'] = pd.to_datetime(df['DATA DEFINITIVA MULTA'], format='%d/%m/%Y', errors='coerce')

    # 3. Extrair Estado
    estados_coords = {
        'PARANA': {'lat': -24.89, 'lon': -51.55, 'uf': 'PR'},
        'PR': {'lat': -24.89, 'lon': -51.55, 'uf': 'PR'},
        'MINAS GERAIS': {'lat': -18.10, 'lon': -44.38, 'uf': 'MG'},
        'MG': {'lat': -18.10, 'lon': -44.38, 'uf': 'MG'},
        'SAO PAULO': {'lat': -22.19, 'lon': -48.79, 'uf': 'SP'},
        'SP': {'lat': -22.19, 'lon': -48.79, 'uf': 'SP'},
        'SANTA CATARINA': {'lat': -27.45, 'lon': -50.95, 'uf': 'SC'},
        'SC': {'lat': -27.45, 'lon': -50.95, 'uf': 'SC'},
        'MATO GROSSO DO SUL': {'lat': -20.51, 'lon': -54.54, 'uf': 'MS'},
        'MS': {'lat': -20.51, 'lon': -54.54, 'uf': 'MS'},
        'GOIAS': {'lat': -15.98, 'lon': -49.86, 'uf': 'GO'},
        'GO': {'lat': -15.98, 'lon': -49.86, 'uf': 'GO'},
    }

    def identificar_estado(texto):
        texto = str(texto).upper()
        # Mapeia estados
        for estado, coords in estados_coords.items():
            if estado in texto:
                return coords['lat'], coords['lon'], coords['uf']
        return None, None, 'Outros'

    if 'Fornecedor' in df.columns:
        coords = df['Fornecedor'].apply(identificar_estado)
        df['lat'] = [x[0] for x in coords]
        df['lon'] = [x[1] for x in coords]
        df['UF'] = [x[2] for x in coords]
    
    return df

try:
    df = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar o arquivo: {e}")
    st.stop()

# --- SIDEBAR (FILTROS) ---
with st.sidebar:
    # Tente colocar a logo aqui. Se não tiver, comente a linha abaixo.
    st.image("logo.png", width=200) 
    st.header("Filtros de Análise")
    
    # Filtro de Data
    min_date = df['DATA DEFINITIVA MULTA'].min()
    max_date = df['DATA DEFINITIVA MULTA'].max()
    
    data_inicio = st.date_input("Data Início", min_date)
    data_fim = st.date_input("Data Fim", max_date)

    # Filtro de Placa
    todas_placas = st.checkbox("Todas as Placas", value=True)
    if not todas_placas:
        placas_selecionadas = st.multiselect("Selecione a Placa", df['PLACA TRATATIVA'].unique())
        df = df[df['PLACA TRATATIVA'].isin(placas_selecionadas)]

    # Filtro de UF
    ufs = st.multiselect("Região (UF)", df['UF'].unique(), default=df['UF'].unique())
    df = df[df['UF'].isin(ufs)]

    # Aplicando filtro de data no dataframe
    df = df[(df['DATA DEFINITIVA MULTA'] >= pd.to_datetime(data_inicio)) & 
            (df['DATA DEFINITIVA MULTA'] <= pd.to_datetime(data_fim))]

# --- ÁREA PRINCIPAL ---

st.title("📊 Gestão de Multas - Maroso")
st.markdown(f"**Análise Financeira e Operacional de Infrações**")

# 1. KPIs (Indicadores Principais)
if 'Vlr. Total' in df.columns:
    total_multas = df['Vlr. Total'].sum()
else:
    total_multas = 0

# Conta as linhas da tabela (funciona mesmo sem a coluna ID)
qtd_multas = df.shape[0]
top_infrator = df['OPERAÇÃO'].value_counts().idxmax() if not df.empty else "N/A"

col1, col2, col3 = st.columns(3)
col1.metric("Custo Total (Perda)", f"R$ {total_multas:,.2f}")
col2.metric("Qtd. Infrações", qtd_multas)
col3.metric("Maior Ofensor (Freq.)", top_infrator)

st.divider()

# 2. GRÁFICOS E ANÁLISES

row1_col1, row1_col2 = st.columns([2, 1])

with row1_col1:
    st.subheader("📍 Mapa de Calor (Volume por Região)")
    # Agrupando por UF para o mapa
    if not df['lat'].isnull().all():
        df_map = df.dropna(subset=['lat', 'lon'])
        with row1_col1:
    st.subheader("📍 Mapa de Calor (Volume por Região)")
    # Agrupando por UF para o mapa
    if 'lat' in df.columns and not df['lat'].isnull().all():
        df_map = df.dropna(subset=['lat', 'lon'])
        
        fig_map = px.scatter_mapbox(
            df_map, 
            lat="lat", 
            lon="lon", 
            hover_name="Fornecedor",
            hover_data=["Vlr. Total", "PLACA TRATATIVA"],
            color="UF",   # As cores mudam conforme o Estado
            size="Vlr. Total",
            zoom=3, 
            height=400,
            # 1. AQUI VIRA DARK (Sem precisar de API Key)
            mapbox_style="carto-darkmatter",
            # 2. AQUI DEFINIMOS AS CORES (Vermelho Sangue -> Laranja)
            color_discrete_sequence=["#D90429", "#EF233C", "#FF5400", "#FF6D00", "#FF9E00"]
        )
        
        # Ajustes finos para remover margens brancas
        fig_map.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            paper_bgcolor="#0E1117", # Fundo preto igual ao do site
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("Não foi possível extrair localização dos fornecedores para gerar o mapa.")
        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("Não foi possível extrair localização dos fornecedores para gerar o mapa.")

with row1_col2:
    st.subheader("🚫 Top Motivos")
    # Gráfico de barras horizontais para facilitar leitura no celular
    fig_motivos = px.bar(
        df['OBSERVAÇÃO DEFINITIVA'].value_counts().head(10).sort_values(),
        orientation='h',
        title="Maiores Causas de Multas"
    )
    fig_motivos.update_layout(showlegend=False, xaxis_title="Qtd", yaxis_title="")
    st.plotly_chart(fig_motivos, use_container_width=True)

# 3. ANÁLISE TEMPORAL E FINANCEIRA
st.subheader("📅 Evolução dos Custos")
# Agrupando por mês
df['Mes'] = df['DATA DEFINITIVA MULTA'].dt.to_period('M').astype(str)
df_temporal = df.groupby('Mes')['Vlr. Total'].sum().reset_index()
fig_line = px.line(df_temporal, x='Mes', y='Vlr. Total', markers=True)
st.plotly_chart(fig_line, use_container_width=True)

# 4. TABELA DETALHADA
st.subheader("📋 Detalhamento das Multas")
st.dataframe(
    df[['DATA DEFINITIVA MULTA', 'PLACA TRATATIVA', 'OBSERVAÇÃO DEFINITIVA', 'Vlr. Total', 'OPERAÇÃO', 'Fornecedor']].sort_values('DATA DEFINITIVA MULTA', ascending=False),
    use_container_width=True,
    hide_index=True
)