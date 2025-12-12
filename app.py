import streamlit as st
import pandas as pd
import plotly.express as px
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

from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
def filtrar_dataframe_dinamico(df):
    """
    Adiciona uma interface de filtragem "estilo Excel" acima do dataframe.
    """
    modify = st.checkbox("🔍 Ativar Filtros Avançados na Tabela")
    if not modify:
        return df

    df = df.copy()
    
    # Tenta converter colunas de objeto para data se possível (para o filtro funcionar melhor)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col], dayfirst=True)
            except Exception:
                pass
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()

    with modification_container:
        # O usuário escolhe quais colunas quer filtrar
        to_filter_columns = st.multiselect("Escolha as colunas para filtrar:", df.columns)
        
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("↳")
            
            # Lógica para escolher o tipo de filtro
            if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                # Se tiver poucos valores únicos, usa Checkbox/Multiselect
                user_cat_input = right.multiselect(
                    f"Valores para {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
                
            elif is_numeric_dtype(df[column]):
                # Se for número, usa Slider
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Faixa de valores para {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
                
            elif is_datetime64_any_dtype(df[column]):
                # Se for data, usa Calendário
                user_date_input = right.date_input(
                    f"Período para {column}",
                    value=(df[column].min(), df[column].max()),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
                    
            else:
                # Se for texto livre, usa Caixa de Busca
                user_text_input = right.text_input(
                    f"Buscar texto em {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input, case=False)]

    return df
# --- 1. FUNÇÕES AUXILIARES (Definidas antes do carregamento) ---

def limpar_observacao(texto):
    """
    Função de sanitização de texto. Remove datas, valores, placas e padroniza motivos.
    """
    if not isinstance(texto, str):
        return "SEM OBSERVAÇÃO"
    
    texto = str(texto).upper()
    
    # 1. REMOVE DATAS (ex: 10/11, 12-12-2023)
    texto = re.sub(r'\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?', '', texto)
    
    # 2. REMOVE VALORES (ex: R$ 150,00, 150.00)
    texto = re.sub(r'R\$\s?[\d\.,]+', '', texto)
    
    # 3. REMOVE CÓDIGOS/NÚMEROS SOLTOS (ex: 745-5, 12345)
    texto = re.sub(r'\b\d{3,}\b', '', texto)
    
    # 4. REMOVE PLACAS (Padrão antigo e Mercosul)
    texto = re.sub(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}', '', texto)
    texto = re.sub(r'[A-Z]{3}-?\d{4}', '', texto)

    # 5. LIMPEZA FINAL (Remove pontuação e espaços duplos)
    texto = re.sub(r'[.\-,;:]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    # --- CATEGORIZAÇÃO INTELIGENTE ---
    if "VELOCIDADE" in texto or "RADAR" in texto or "VEL" in texto or "VELOC" in texto or "VELOCID" in texto or "VELOCIDAD" in texto:
        return "EXCESSO DE VELOCIDADE"
    elif "FAROL" in texto:
        return "FAROL DESLIGADO"
    elif "CINTO" in texto:
        return "FALTA DE CINTO"
    elif "CELULAR" in texto:
        return "USO DE CELULAR"
    elif "ESTACION" in texto:
        return "ESTACIONAMENTO IRREGULAR"
    elif "ULTRAPASSA" in texto:
        return "ULTRAPASSAGEM INDEVIDA"
    elif "IDENTIFICACAO" in texto or "IDENTIFICAÇÃO" in texto or "IDENTIF":
        return "MULTA POR NÃO IDENTIFICAÇÃO DO CONDUTOR INFRATOR, IMPOSTA A PJ"
    
    return texto

def get_coluna_motivo(df):
    # Procura a melhor coluna para usar como motivo
    prioridades = ["OBSERVAÇÃO", "OBSERVACAO", "MOTIVO", "INFRAÇÃO", "INFRACAO", "DESCRIÇÃO"]
    
    # 1. Busca Exata
    for p in prioridades:
        for c in df.columns:
            if c.upper().strip() == p:
                return c
                
    # 2. Busca Parcial (contém o nome)
    for c in df.columns:
        upper_c = c.upper()
        if ("OBSERVAÇÃO" in upper_c or "MOTIVO" in upper_c):
            if "BRUTO" not in upper_c and "ORIGINAL" not in upper_c:
                return c
    return None

def busca_binaria(lista, termo):
    idx = bisect.bisect_left(lista, termo.upper())
    res = []
    while idx < len(lista) and lista[idx].startswith(termo.upper()):
        res.append(lista[idx])
        idx += 1
    return res

# --- 2. CARREGAMENTO E LIMPEZA (CACHEADO) ---
@st.cache_data(ttl=0)
def carregar_dados():
    # 1. Carrega Mapeamento
    path_mapa = "mapeamento_uf.csv"
    if os.path.exists(path_mapa):
        try:
            df_mapa = pd.read_csv(path_mapa, sep=";")
            df_mapa.columns = [c.lower().strip() for c in df_mapa.columns]
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")
            return None
    else:
        st.error("⚠️ Faltando arquivo 'mapeamento_uf.csv'.")
        return None

    # 2. Carrega Dados Principais
    arquivos_csv = [f for f in os.listdir('.') if f.lower().endswith('.csv') and "mapeamento" not in f]
    if not arquivos_csv: 
        return None
    
    arquivo_alvo = arquivos_csv[0]
    
    try:
        df = pd.read_csv(arquivo_alvo, sep=";", encoding="utf-8-sig", on_bad_lines='skip')
    except:
        df = pd.read_csv(arquivo_alvo, sep=";", encoding="latin1", on_bad_lines='skip')
    
    # Padroniza colunas
    df.columns = df.columns.str.strip()

    # --- APLICAÇÃO DA LIMPEZA (REGEX) ---
    col_motivo = get_coluna_motivo(df)
    
    if col_motivo:
        # Cria a coluna nova tratada
        df['MOTIVO_TRATADO'] = df[col_motivo].apply(limpar_observacao)
    else:
        # Se não achar, cria uma coluna vazia pra não quebrar o código
        df['MOTIVO_TRATADO'] = "SEM INFORMAÇÃO"

    # --- TRATAMENTO DE VALORES ---
    col_valor = next((c for c in df.columns if "Vlr" in c or "Valor" in c), None)
    if col_valor:
        df['Vlr. Total'] = df[col_valor].astype(str).apply(lambda x: re.sub(r'[^\d,]', '', x).replace(',', '.'))
        df['Vlr. Total'] = pd.to_numeric(df['Vlr. Total'], errors='coerce').fillna(0)

    # --- TRATAMENTO DE DATAS ---
    col_data = next((c for c in df.columns if "DATA DEFINITIVA" in c.upper()), None)
    if not col_data:
        col_data = next((c for c in df.columns if "VENCIMENTO" in c.upper()), None)

    if col_data:
        df['DATA_REF'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
        # Fallback se falhar
        if df['DATA_REF'].isna().mean() > 0.9:
             col_venc = next((c for c in df.columns if "VENCIMENTO" in c.upper()), None)
             if col_venc:
                 df['DATA_REF'] = pd.to_datetime(df[col_venc], dayfirst=True, errors='coerce')
    else:
        df['DATA_REF'] = pd.NaT

    # --- CRUZAMENTO (JOIN) ---
    col_fornecedor = next((c for c in df.columns if "Fornecedor" in c or "Orgao" in c), None)
    
    if col_fornecedor:
        df['chave_join'] = df[col_fornecedor].astype(str).str.strip()
        if 'fornecedor' in df_mapa.columns:
            df_mapa['fornecedor'] = df_mapa['fornecedor'].astype(str).str.strip()
            df = pd.merge(df, df_mapa, left_on='chave_join', right_on='fornecedor', how='left')
        
        cols_check = ['uf_correta', 'lat', 'lon']
        for col in cols_check:
            if col not in df.columns: df[col] = None 
            
        df['uf_correta'] = df['uf_correta'].fillna('OUTROS')
        df['lat'] = df['lat'].fillna(-15.78)
        df['lon'] = df['lon'].fillna(-47.92)
    
    return df

# --- INÍCIO DO APP ---
df = carregar_dados()

if df is None:
    st.error("⚠️ Adicione os arquivos CSV na pasta.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", width=200)
    st.header("Filtros")
    
    if not df.empty and 'DATA_REF' in df.columns and df['DATA_REF'].notna().any():
        d_min = df['DATA_REF'].min().date()
        d_max = df['DATA_REF'].max().date()
        inicio = st.date_input("Início", d_min)
        fim = st.date_input("Fim", d_max)
        df = df[(df['DATA_REF'].dt.date >= inicio) & (df['DATA_REF'].dt.date <= fim)]
    else:
        st.warning("⚠️ Nenhuma data válida encontrada nos dados.")

    # Filtro: Placa
    col_placa = next((c for c in df.columns if "PLACA" in c.upper()), None)
    if col_placa:
        st.markdown("---")
        metodo = st.radio("Busca Placa:", ["Lista", "Digitar"], key="radio_placa")
        if metodo == "Lista":
            sel = st.checkbox("Todas", True, key="check_placa_todas")
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

    # Filtro: Estado
    if 'uf_correta' in df.columns:
        lst_uf = sorted([x for x in df['uf_correta'].unique() if isinstance(x, str)])
        ufs = st.multiselect("Estado:", lst_uf)
        if ufs: df = df[df['uf_correta'].isin(ufs)]

    # Filtro: Operação
    col_operacao = next((c for c in df.columns if "OPERAÇÃO" in c.upper() or "OPERACAO" in c.upper()), None)
    if col_operacao:
        st.markdown("---")
        lst_operacao = sorted([str(x) for x in df[col_operacao].unique() if pd.notna(x)])
        
        metodo_op = st.radio("Busca Operação:", ["Lista", "Digitar"], key="radio_op")
        
        if metodo_op == "Lista":
            operacoes = st.multiselect("Selecione a Operação:", lst_operacao)
            if operacoes:
                df = df[df[col_operacao].isin(operacoes)]
        else:
            termo_op = st.text_input("Digite a Operação:", key="txt_op")
            if termo_op:
                achou_op = busca_binaria(lst_operacao, termo_op)
                if achou_op:
                    st.success(f"{len(achou_op)} encontradas.")
                    df = df[df[col_operacao].isin(achou_op)]
                else:
                    st.warning("Nenhuma operação encontrada.")
                    df = df[df[col_operacao] == 'X_NADA']

    # Filtro: Motivos (USANDO A COLUNA TRATADA AGORA!)
    if 'MOTIVO_TRATADO' in df.columns:
        st.markdown("---")
        lst_motivos = sorted([str(x) for x in df['MOTIVO_TRATADO'].unique() if pd.notna(x)])
        
        metodo_mot = st.radio("Busca Motivo:", ["Lista", "Digitar"], key="radio_mot")
        
        if metodo_mot == "Lista":
            motivos_sel = st.multiselect("Selecione o Motivo:", lst_motivos)
            if motivos_sel:
                df = df[df['MOTIVO_TRATADO'].isin(motivos_sel)]
        else:
            termo_mot = st.text_input("Digite o Motivo:", key="txt_mot")
            if termo_mot:
                achou_mot = busca_binaria(lst_motivos, termo_mot)
                if achou_mot:
                    st.success(f"{len(achou_mot)} encontrados.")
                    df = df[df['MOTIVO_TRATADO'].isin(achou_mot)]
                else:
                    st.warning("Nenhum motivo encontrado.")
                    df = df[df['MOTIVO_TRATADO'] == 'X_NADA']

# --- KPI ---
total = df['Vlr. Total'].sum()
qtd = df.shape[0]

top_ofensor = "N/A"
if col_operacao and not df.empty:
    df_val = df[df[col_operacao].astype(str).str.contains("NÃO LOCALIZADA", case=False) == False]
    if not df_val.empty:
        top_ofensor = df_val[col_operacao].value_counts().idxmax()

# Total Motivos (Baseado na coluna tratada)
total_motivos = 0
if 'MOTIVO_TRATADO' in df.columns:
    total_motivos = df['MOTIVO_TRATADO'].nunique()

# --- VISUALIZAÇÃO ---
st.title("📊 Gestão de Multas - Maroso")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Custo Total", f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
c2.metric("Qtd. Infrações", qtd)
c3.metric("Maior Ofensor", top_ofensor)
c4.metric("Total Tipos de Motivos", total_motivos)

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
                hover_name="Fornecedor" if 'Fornecedor' in df.columns else None, 
                hover_data=["Vlr. Total", "MOTIVO_TRATADO"]
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor="#0E1117", height=400)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sem dados geográficos.")
    else: st.info("Dados insuficientes.")

with col2:
    st.subheader("🚫 Principais Motivos")
    # AQUI ESTÁ A MUDANÇA PRINCIPAL: Usando MOTIVO_TRATADO
    if 'MOTIVO_TRATADO' in df.columns:
        df_m = df['MOTIVO_TRATADO'].value_counts().head(10).sort_values(ascending=True)
        fig = px.bar(df_m, orientation='h', text_auto='true', color_discrete_sequence=["#D90429"])
        
        fig.update_traces(
            textfont_size=14, 
            textangle=0, 
            textposition="outside",
            cliponaxis=False
        )
        
        fig.update_layout(
            showlegend=False, 
            plot_bgcolor="#0E1117", 
            paper_bgcolor="#0E1117", 
            font_color="white",
            margin=dict(l=0, r=50, t=0, b=0),
            xaxis=dict(showgrid=True, gridcolor='#333333'),
            yaxis=dict(showgrid=False, title="")
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("Coluna de Motivos não encontrada.")

st.subheader("📅 Evolução Financeira")

df_evo = df.dropna(subset=['DATA_REF']).copy()

if not df_evo.empty:
    df_evo['Mes_Ref'] = df_evo['DATA_REF'].dt.to_period('M').dt.to_timestamp()
    df_t = df_evo.groupby('Mes_Ref')['Vlr. Total'].sum().reset_index().sort_values('Mes_Ref')

    fig_line = px.area(df_t, x='Mes_Ref', y='Vlr. Total', markers=True, text='Vlr. Total')

    fig_line.update_traces(
        line_color="#D90429", 
        fillcolor="rgba(217, 4, 41, 0.2)", 
        texttemplate='R$ %{y:.2s}',
        textposition='top center',
        textfont_size=12
    )

    fig_line.update_layout(
        plot_bgcolor="#0E1117", 
        paper_bgcolor="#0E1117", 
        font_color="white",
        yaxis=dict(showgrid=True, gridcolor='#333333', title=""),
        xaxis=dict(showgrid=False, title="", tickformat="%b/%Y", dtick="M1"), 
        margin=dict(t=30, l=10, r=10, b=10)
    )
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("⚠️ Não há dados com datas válidas para gerar o gráfico de evolução.")

st.divider()
st.subheader("📋 Dados Brutos (Tratados)")

# 1. Prepara as colunas na ordem bonita
cols_ordenadas = ['DATA_REF', 'MOTIVO_TRATADO', 'Vlr. Total'] + \
                 [c for c in df.columns if c not in ['DATA_REF', 'MOTIVO_TRATADO', 'Vlr. Total']]

df_visualizacao = df[cols_ordenadas].sort_values('DATA_REF', ascending=False)

# 2. CHAMA A FUNÇÃO MÁGICA AQUI
df_filtrado = filtrar_dataframe_dinamico(df_visualizacao)

# 3. Exibe o Dataframe filtrado e contagem
st.caption(f"Mostrando {len(df_filtrado)} de {len(df)} registros")
st.dataframe(
    df_filtrado, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "Vlr. Total": st.column_config.NumberColumn(
            "Valor (R$)",
            format="R$ %.2f"
        ),
        "DATA_REF": st.column_config.DateColumn(
            "Data",
            format="DD/MM/YYYY"
        )
    }
)