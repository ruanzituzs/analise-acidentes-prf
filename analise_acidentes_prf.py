import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


# ---------- LIMPEZA DOS DADOS ----------

def carregar_e_limpar_dados(caminho_arquivo):
    df = pd.read_csv(caminho_arquivo, sep=";", encoding="latin-1")

    # Remove registros sem classificação e IDs duplicados
    df = df.dropna(subset=["classificacao_acidente"]).copy()

    if "id" in df.columns:
        df = df.drop_duplicates(subset="id").copy()

    # Converte a data
    df["data_inversa"] = pd.to_datetime(
        df["data_inversa"], errors="coerce"
    )

    # Converte coordenadas e quilometragem para números
    for coluna in ["latitude", "longitude", "km"]:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(
                df[coluna].astype("string").str.replace(
                    ",", ".", regex=False
                ),
                errors="coerce"
            )

    # Extrai a hora, aceitando horários como HH:MM ou HH:MM:SS
    horas = df["horario"].astype("string").str.extract(
        r"^\s*(\d{1,2}):\d{2}", expand=False
    )

    df["hora"] = pd.to_numeric(horas, errors="coerce")
    df["hora"] = df["hora"].where(df["hora"].between(0, 23))

    # Garante que mortos e feridos graves sejam numéricos
    for coluna in ["mortos", "feridos_graves"]:
        df[coluna] = pd.to_numeric(
            df[coluna], errors="coerce"
        ).fillna(0)

    # Acidente grave: pelo menos um morto ou ferido grave
    df["grave"] = (
        (df["mortos"] > 0) | (df["feridos_graves"] > 0)
    ).astype(int)

    return df


# ---------- HIPÓTESE 1: GRAVIDADE POR FASE DO DIA ----------

def analisar_h1(df):
    taxas = (
        df.groupby("fase_dia")["grave"]
        .mean()
        .mul(100)
        .sort_values(ascending=False)
    )

    print("\nProporção de acidentes graves por fase do dia (%):")
    print(taxas.round(2))

    plt.figure(figsize=(9, 5))
    ax = sns.barplot(
        x=taxas.index,
        y=taxas.values,
        color="steelblue"
    )

    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:.0f}%")
    )

    plt.title("H1: Acidentes graves por fase do dia em 2025")
    plt.xlabel("Fase do dia")
    plt.ylabel("Proporção de acidentes graves (%)")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig("figuras/hipotese1_fase_dia.png", dpi=300)
    plt.show()


# ---------- HIPÓTESE 2: CAUSAS E TIPOS DE ACIDENTE ----------

def analisar_h2(df):
    media_geral = df["grave"].mean() * 100

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    analises = [
        (axes[0], "tipo_acidente", "Por tipo de acidente"),
        (axes[1], "causa_acidente", "Por causa do acidente")
    ]

    for ax, coluna, titulo in analises:
        grupos = df.groupby(coluna)["grave"].agg(["mean", "count"])

        # Considera somente categorias com pelo menos 100 acidentes
        grupos = grupos[grupos["count"] >= 100]

        # Seleciona as 10 categorias com maior proporção
        taxas = (
            grupos["mean"]
            .mul(100)
            .nlargest(10)
            .sort_values()
        )

        if taxas.empty:
            ax.text(
                0.5, 0.5,
                "Nenhuma categoria atende ao mínimo de 100 acidentes",
                ha="center", va="center",
                transform=ax.transAxes
            )
            ax.set_title(titulo)
            continue

        sns.barplot(
            x=taxas.values,
            y=taxas.index,
            color="firebrick",
            ax=ax
        )

        ax.axvline(
            media_geral,
            color="black",
            linestyle="--",
            label=f"Média geral ({media_geral:.1f}%)"
        )

        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{x:.0f}%")
        )

        ax.set_title(titulo)
        ax.set_xlabel("Acidentes graves (%)")
        ax.set_ylabel("")
        ax.legend()

    fig.suptitle(
        "H2: Categorias com maior proporção de acidentes graves em 2025"
    )
    plt.tight_layout()
    plt.savefig("figuras/hipotese2_tipo_causa.png", dpi=300)
    plt.show()


# ---------- HIPÓTESE 3: TIPO DE PISTA ----------

def analisar_h3(df):
    # Normaliza os nomes para evitar problemas com espaços ou maiúsculas
    tipo = df["tipo_pista"].astype("string").str.strip().str.casefold()

    dados = df[tipo.isin(["simples", "dupla"])].copy()
    dados["tipo_pista"] = (
        dados["tipo_pista"].astype("string").str.strip().str.capitalize()
    )

    resultado = (
        dados.groupby("tipo_pista")
        .agg(
            quantidade_acidentes=("grave", "size"),
            acidentes_graves=("grave", "sum"),
            proporcao_graves=("grave", "mean")
        )
        .reset_index()
    )

    resultado["proporcao_graves"] *= 100

    print("\nResultados por tipo de pista:")
    print(
        resultado[
            [
                "tipo_pista",
                "quantidade_acidentes",
                "acidentes_graves",
                "proporcao_graves"
            ]
        ].round(2).to_string(index=False)
    )

    plt.figure(figsize=(8, 5))

    ax = sns.barplot(
        data=dados,
        x="tipo_pista",
        y="grave",
        order=["Simples", "Dupla"],
        errorbar=None,
        color="steelblue"
    )

    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:.0%}")
    )

    plt.title("H3: Acidentes graves por tipo de pista em 2025")
    plt.xlabel("Tipo de pista")
    plt.ylabel("Proporção de acidentes graves")
    plt.tight_layout()
    plt.savefig("figuras/hipotese3_tipo_pista.png", dpi=300)
    plt.show()


# ---------- HIPÓTESE 4: HORÁRIOS E GRAVIDADE POR ESTADO ----------

def analisar_h4(df):
    dias = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
    ]

    dados = df.copy()

    dados["dia"] = dados["data_inversa"].dt.dayofweek.map(
        dict(enumerate(dias))
    )

    # H4.1: Quantidade de acidentes por dia da semana e hora
    pivo = dados.pivot_table(
        index="dia",
        columns="hora",
        aggfunc="size",
        fill_value=0
    ).reindex(index=dias, columns=range(24), fill_value=0)

    plt.figure(figsize=(12, 5))

    sns.heatmap(
        pivo,
        cmap="YlOrRd",
        cbar_kws={"label": "Número de acidentes"}
    )

    plt.title("H4.1: Acidentes por dia da semana e hora em 2025")
    plt.xlabel("Hora do dia")
    plt.ylabel("Dia da semana")
    plt.tight_layout()
    plt.savefig("figuras/hipotese4_tempo_heatmap.png", dpi=300)
    plt.show()

    # H4.2: Proporção de acidentes graves por estado
    taxas = (
        dados.groupby("uf")["grave"]
        .mean()
        .mul(100)
        .sort_values(ascending=False)
    )

    media_nacional = dados["grave"].mean() * 100

    plt.figure(figsize=(12, 5))

    ax = sns.barplot(
        x=taxas.index,
        y=taxas.values,
        color="firebrick"
    )

    ax.axhline(
        media_nacional,
        color="black",
        linestyle="--",
        label=f"Média nacional ({media_nacional:.1f}%)"
    )

    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:.0f}%")
    )

    plt.title("H4.2: Proporção de acidentes graves por estado em 2025")
    plt.xlabel("Estado (UF)")
    plt.ylabel("Acidentes graves (%)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig("figuras/hipotese4_estado_gravidade.png", dpi=300)
    plt.show()


# ---------- EXECUÇÃO DO PROGRAMA ----------

sns.set_theme(style="whitegrid")

os.makedirs("figuras", exist_ok=True)

# Baixe o arquivo datatran2025.csv no portal de Dados Abertos da PRF e coloque na pasta data/
caminho = "data/datatran2025.csv"

df_pronto = carregar_e_limpar_dados(caminho)

print("Primeiras linhas dos dados:")
print(df_pronto.head())

print("\nQuantidade de acidentes por classificação de gravidade:")
print(df_pronto["grave"].value_counts())

analisar_h1(df_pronto)
analisar_h2(df_pronto)
analisar_h3(df_pronto)
analisar_h4(df_pronto)