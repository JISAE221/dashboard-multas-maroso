import streamlit as st
import pandas as pd
import plotly as px
import os
import re
import bisect

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Dashboard de Multas - Maroso", page_icon="🚗", layout="wide")

# --- ESTILO (Dark/Red Refinado) ---
st.markdown("""
    <style>
    /* Ajuste dos Cards KPI */
    div[data-testid="stMetric"] {
        background-color: #1E1E1E; 
        padding: 15px; 
        border-radius: 8px; 
        border-left: 5px solid #D90429; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.5);
    }
    /* Ajuste do Título */
    h1 { color: #ffffff; }
    /* Ajuste de espaçamento global */
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    </style>
    """, unsafe_allow_html=True)

# --- CARREGAMENTO ---
@st.cache_data(ttl=0)
def carregar_dados():
    # 1. Carrega Mapeamento
    if not os.path.exists("mapeamento_uf.csv"):
        st.error("⚠️ Faltando arquivo 'mapeamento_uf.csv'.")
        return None
        
    try:
        df_mapa = pd.read_csv("mapeamento_uf.csv", sep=";")
        # Normaliza colunas para evitar erro de maiúscula/minúscula
        df_mapa.columns = [c.lower().strip() for c in df_mapa.columns]
    except Exception as e:
        st.error(f"Erro no mapeamento: {e}")
        return None

    # 2. Carrega Dados
    arquivos_csv = [f for f in os.listdir('.') if f.lower().endswith('.csv') and "mapeamento" not in f]
    if not arquivos_csv: return None
    
    try:
        df = pd.read_csv(arquivos_csv[0], sep=";", encoding="utf-8-sig", on_bad_lines='skip')
    except:
        df = pd.read_csv(arquivos_csv[0], sep=";", encoding="latin1", on_bad_lines='skip')

    df.columns = df.columns.str.strip()

    # --- LIMPEZA ---
    
    # Valor
    col_valor = next((c for c in df.columns if "Vlr" in c or "Valor" in c), None)
    if col_valor:
        df['Vlr. Total'] = df[col_valor].astype(str).apply(lambda x: re.sub(r'[^\d,]', '', x).replace(',', '.'))
        df['Vlr. Total'] = pd.to_numeric(df['Vlr. Total'], errors='coerce').fillna(0)

    # Data
    col_data = next((c for c in df.columns if "DATA DEFINITIVA" in c), None)
    if col_data:
        df['DATA_REF'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
        df['DATA_REF'] = df['DATA_REF'].fillna(pd.to_datetime('today'))
    else:
        df['DATA_REF'] = pd.to_datetime('today')

    # --- CRUZAMENTO ---
    col_fornecedor = next((c for c in df.columns if "Fornecedor" in c or "Orgao" in c), None)
    
    if col_fornecedor:
        df['chave_join'] = df[col_fornecedor].astype(str).str.strip()
        # Garante que a coluna de join do mapa também é string
        if 'fornecedor' in df_mapa.columns:
            df_mapa['fornecedor'] = df_mapa['fornecedor'].astype(str).str.strip()
            df = pd.merge(df, df_mapa, left_on='chave_join', right_on='fornecedor', how='left')
        
        # Tratamento de Nulos pós-join
        cols_check = ['uf_correta', 'lat', 'lon']
        for col in cols_check:
            if col not in df.columns: df[col] = None # Cria se não existir
            
        df['uf_correta'] = df['uf_correta'].fillna('OUTROS')
        df['lat'] = df['lat'].fillna(-15.78)
        df['lon'] = df['lon'].fillna(-47.92)
    
    return df

df = carregar_dados()

if df is None:
    st.error("⚠️ Adicione os arquivos CSV.")
    st.stop()

# --- BUSCA BINÁRIA ---
def busca_binaria(lista, termo):
    idx = bisect.bisect_left(lista, termo.upper())
    res = []
    while idx < len(lista) and lista[idx].startswith(termo.upper()):
        res.append(lista[idx])
        idx += 1
    return res

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", width=200)
    st.header("Filtros")
    
    d_min = df['DATA_REF'].min().date()
    d_max = df['DATA_REF'].max().date()
    inicio = st.date_input("Início", d_min)
    fim = st.date_input("Fim", d_max)
    
    col_placa = next((c for c in df.columns if "PLACA" in c.upper()), None)
    if col_placa:
        st.markdown("---")
        metodo = st.radio("Busca Placa:", ["Lista", "Digitar"])
        if metodo == "Lista":
            sel = st.checkbox("Todas", True)
            if not sel:
                placas = st.multiselect("Placa:", df[col_placa].unique())
                if placas: df = df[df[col_placa].isin(placas)]
        else:
            placas_ord = sorted(df[col_placa].dropna().astype(str).unique())
            termo = st.text_input("Digite a placa:")
            if termo:
                achou = busca_binaria(placas_ord, termo)
                if achou: 
                    df = df[df[col_placa].isin(achou)]
                    st.success(f"{len(achou)} encontradas.")
                else: 
                    st.warning("Nada encontrado.")
                    df = df[df[col_placa] == 'X']

    if 'uf_correta' in df.columns:
        lst_uf = sorted([x for x in df['uf_correta'].unique() if isinstance(x, str)])
        ufs = st.multiselect("Estado:", lst_uf)
        if ufs: df = df[df['uf_correta'].isin(ufs)]

    df = df[(df['DATA_REF'].dt.date >= inicio) & (df['DATA_REF'].dt.date <= fim)]

# --- KPI ---
total = df['Vlr. Total'].sum()
qtd = df.shape[0]

top_ofensor = "N/A"
if 'OPERAÇÃO' in df.columns:
    df_val = df[df['OPERAÇÃO'].astype(str).str.contains("NÃO LOCALIZADA", case=False) == False]
    if not df_val.empty:
        top_ofensor = df_val['OPERAÇÃO'].value_counts().idxmax()

# --- VISUALIZAÇÃO ---
st.title("📊 Gestão de Multas - Maroso")

c1, c2, c3 = st.columns(3)
c1.metric("Custo Total", f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
c2.metric("Qtd. Infrações", qtd)
c3.metric("Maior Ofensor", top_ofensor)

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📍 Mapa de Calor")
    if 'lat' in df.columns and not df.empty:
        df_map = df[df['uf_correta'] != 'OUTROS']
        if not df_map.empty:
            fig = px.scatter_mapbox(
                df_map, lat="lat", lon="lon", color="uf_correta", size="Vlr. Total",
                zoom=3, mapbox_style="carto-darkmatter",
                color_discrete_sequence=px.colors.qualitative.Bold,
                hover_name="Fornecedor", hover_data=["Vlr. Total"]
            )
            # Remove margens para o mapa ocupar tudo
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor="#0E1117", height=400)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sem dados geográficos.")
    else: st.info("Dados insuficientes.")

with col2:
    st.subheader("🚫 Motivos")
    col_obs = next((c for c in df.columns if "OBSERVAÇÃO" in c or "MOTIVO" in c), None)
    if col_obs:
        df_m = df[col_obs].value_counts().head(10).sort_values(ascending=True)
        # text_auto='.2s' formata para 10k, 1M, etc.
        fig = px.bar(df_m, orientation='h', text_auto='.2s', color_discrete_sequence=["#D90429"])
        
        fig.update_traces(
            textfont_size=14, 
            textangle=0, 
            textposition="outside", # Texto fora da barra
            cliponaxis=False # Permite que o texto saia da área do gráfico sem cortar
        )
        
        fig.update_layout(
            showlegend=False, 
            plot_bgcolor="#0E1117", 
            paper_bgcolor="#0E1117", 
            font_color="white",
            margin=dict(l=0, r=50, t=0, b=0), # Margem direita extra para o texto caber
            xaxis=dict(showgrid=True, gridcolor='#333333'), # Grid suave
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)

st.subheader("📅 Evolução Financeira")
df['Mes'] = df['DATA_REF'].dt.to_period('M').astype(str)
df_t = df.groupby('Mes')['Vlr. Total'].sum().reset_index()

fig_line = px.area(df_t, x='Mes', y='Vlr. Total', markers=True, text='Vlr. Total')

# Formatação R$ compacta no gráfico de linha
fig_line.update_traces(
    line_color="#D90429", 
    fillcolor="rgba(217, 4, 41, 0.2)", 
    texttemplate='R$ %{y:.2s}', # Formata o label do ponto (Ex: R$ 10k)
    textposition='top center',
    textfont_size=12
)

fig_line.update_layout(
    plot_bgcolor="#0E1117", 
    paper_bgcolor="#0E1117", 
    font_color="white",
    yaxis=dict(showgrid=True, gridcolor='#333333', title=""), # Tira titulo do eixo Y para limpar
    xaxis=dict(showgrid=False, title=""),
    margin=dict(t=20, l=10, r=10, b=10)
)
st.plotly_chart(fig_line, use_container_width=True)

st.divider()
st.subheader("📋 Dados Brutos")
st.dataframe(df.sort_values('DATA_REF', ascending=False), use_container_width=True, hide_index=True)