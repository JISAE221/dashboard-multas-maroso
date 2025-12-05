import pandas as pd

# 1. Carrega os dados
df_dados = pd.read_csv("dados.csv", sep=";", encoding="utf-8-sig", on_bad_lines='skip')
# Normaliza o nome da coluna para garantir
col_fornecedor = next((c for c in df_dados.columns if "Fornecedor" in c), None)
fornecedores_nos_dados = set(df_dados[col_fornecedor].str.strip().unique())

# 2. Carrega o mapa
df_mapa = pd.read_csv("mapeamento_uf.csv", sep=";")
fornecedores_no_mapa = set(df_mapa['Fornecedor'].str.strip().unique())

# 3. Descobre quem está faltando
faltantes = fornecedores_nos_dados - fornecedores_no_mapa

print(f"Total de Fornecedores nos Dados: {len(fornecedores_nos_dados)}")
print(f"Total Mapeados: {len(fornecedores_no_mapa)}")
print(f"--- FALTAM MAPEADAR ({len(faltantes)}) ---")
for f in faltantes:
    print(f)