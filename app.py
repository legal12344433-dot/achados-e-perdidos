import firebase_admin
import json
import os
import uuid
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
from firebase_admin import credentials, firestore


# ==========================================
# CONFIGURAÇÃO DO APLICATIVO
# ==========================================

st.set_page_config(
    page_title="Achados e Perdidos",
    page_icon="🔎",
    layout="wide"
)

# Conexão segura com o Firebase
if not firebase_admin._apps:
    dados_credenciais = json.loads(
        st.secrets["FIREBASE_CREDENTIALS"]
    )

    credencial = credentials.Certificate(dados_credenciais)

    firebase_admin.initialize_app(credencial)

db = firestore.client()

PASTA_FOTOS = "fotos"
os.makedirs(PASTA_FOTOS, exist_ok=True)

CATEGORIAS = ["mochila", "carteira", "chave", "outros"]

LOCAIS = [
    "sala de aula",
    "cantina",
    "banheiro",
    "quadra",
    "patio",
    "auditorio",
    "outros"
]

COLUNAS = [
    "tipo",
    "descricao",
    "categoria",
    "local",
    "foto",
    "usuario",
    "entregue_com",
    "comentario"
]


# ==========================================
# FUNÇÕES DO FIRESTORE
# ==========================================

def carregar_itens():
    try:
        documentos = db.collection("itens").stream()

        dados = [
            documento.to_dict()
            for documento in documentos
        ]

        if not dados:
            return pd.DataFrame(columns=COLUNAS)

        df = pd.DataFrame(dados)

        # Garante que todas as colunas necessárias existam
        for coluna in COLUNAS:
            if coluna not in df.columns:
                df[coluna] = ""

        return df[COLUNAS]

    except Exception:
        st.error(
            "Não foi possível carregar os itens do Firebase. "
            "Confira as credenciais e a configuração do Firestore."
        )
        return pd.DataFrame(columns=COLUNAS)


def salvar_item(
    tipo,
    descricao,
    categoria,
    local,
    foto,
    usuario,
    entregue_com,
    comentario
):
    nome_foto = ""

    # Salva a foto localmente, se houver uma
    if foto is not None:
        nome_foto = f"{uuid.uuid4()}.jpg"
        caminho_foto = os.path.join(PASTA_FOTOS, nome_foto)

        with open(caminho_foto, "wb") as arquivo:
            arquivo.write(foto.getbuffer())

    # Salva os dados no Firestore
    db.collection("itens").add({
        "tipo": tipo,
        "descricao": descricao,
        "categoria": categoria,
        "local": local,
        "foto": nome_foto,
        "usuario": usuario,
        "entregue_com": entregue_com,
        "comentario": comentario
    })


# ==========================================
# CORRESPONDÊNCIAS
# ==========================================

def parecenca(texto1, texto2):
    texto1 = str(texto1).lower()
    texto2 = str(texto2).lower()

    return SequenceMatcher(
        None,
        texto1,
        texto2
    ).ratio()


def encontrar_correspondencias():
    colunas_resultado = [
        "perdido",
        "foto_perdido",
        "usuario_perdido",
        "comentario_perdido",
        "achado",
        "foto_achado",
        "usuario_achado",
        "comentario_achado",
        "entregue_com",
        "match"
    ]

    df = carregar_itens()

    if df.empty:
        return pd.DataFrame(columns=colunas_resultado)

    perdidos = df[df["tipo"] == "perdido"]
    achados = df[df["tipo"] == "achado"]

    resultados = []

    for _, item_perdido in perdidos.iterrows():
        for _, item_achado in achados.iterrows():
            score = 0

            if item_perdido["categoria"] == item_achado["categoria"]:
                score += 0.4

            if item_perdido["local"] == item_achado["local"]:
                score += 0.2

            score += 0.4 * parecenca(
                item_perdido["descricao"],
                item_achado["descricao"]
            )

            resultados.append({
                "perdido": item_perdido["descricao"],
                "foto_perdido": item_perdido["foto"],
                "usuario_perdido": item_perdido["usuario"],
                "comentario_perdido": item_perdido["comentario"],
                "achado": item_achado["descricao"],
                "foto_achado": item_achado["foto"],
                "usuario_achado": item_achado["usuario"],
                "comentario_achado": item_achado["comentario"],
                "entregue_com": item_achado["entregue_com"],
                "match": round(score * 100, 1)
            })

    if not resultados:
        return pd.DataFrame(columns=colunas_resultado)

    return pd.DataFrame(resultados)


def texto_disponivel(valor):
    """Verifica se existe texto válido para exibir."""
    return (
        valor is not None
        and str(valor).strip() != ""
        and str(valor).lower() != "nan"
    )


def mostrar_foto(nome_foto, largura=150):
    """Exibe uma foto se ela estiver disponível no servidor."""
    if not texto_disponivel(nome_foto):
        st.write("Sem foto")
        return

    caminho = os.path.join(PASTA_FOTOS, str(nome_foto))

    if os.path.exists(caminho):
        st.image(caminho, width=largura)
    else:
        st.write("Foto indisponível")


def mostrar_matches(tabela):
    if tabela.empty:
        st.info("Nenhuma correspondência nessa faixa.")
        return

    for _, linha in tabela.iterrows():
        if linha["match"] >= 70:
            cor = "🟢"
        elif linha["match"] >= 40:
            cor = "🟡"
        else:
            cor = "🔴"

        with st.container(border=True):
            st.write(
                f"{cor} **{linha['match']}% de correspondência**"
            )

            col_perdido, col_achado = st.columns(2)

            with col_perdido:
                st.write(f"**Perdido:** {linha['perdido']}")
                st.caption(
                    f"Registrado por: {linha['usuario_perdido']}"
                )

                if texto_disponivel(linha["comentario_perdido"]):
                    st.caption(
                        f"💬 {linha['comentario_perdido']}"
                    )

                mostrar_foto(linha["foto_perdido"])

            with col_achado:
                st.write(f"**Achado:** {linha['achado']}")
                st.caption(
                    f"Registrado por: {linha['usuario_achado']}"
                )

                if texto_disponivel(linha["entregue_com"]):
                    st.caption(
                        "📍 Deixado onde/com quem: "
                        f"{linha['entregue_com']}"
                    )

                if texto_disponivel(linha["comentario_achado"]):
                    st.caption(
                        f"💬 {linha['comentario_achado']}"
                    )

                mostrar_foto(linha["foto_achado"])


# ==========================================
# TÍTULO E IDENTIFICAÇÃO
# ==========================================

st.title("🔎 Achados e Perdidos")

st.caption(
    "Sistema para registrar e encontrar itens perdidos e achados."
)

if "nome_usuario" not in st.session_state:
    st.session_state.nome_usuario = ""
    st.session_state.sala_usuario = ""
    st.session_state.tipo_usuario = ""

if st.session_state.nome_usuario == "":
    st.subheader("Identifique-se para continuar")

    with st.form("form_identificacao"):
        nome = st.text_input(
            "Nome completo",
            autocomplete="off"
        )

        sala = st.text_input(
            "Sala/turma (ou 'N/A' se não for aluno)",
            autocomplete="off"
        )

        tipo_pessoa = st.selectbox(
            "Você é:",
            ["Aluno", "Professor", "Funcionário", "Outro"]
        )

        entrar = st.form_submit_button("Entrar")

        if entrar:
            if not nome.strip():
                st.error("Preencha seu nome antes de continuar.")
            else:
                st.session_state.nome_usuario = nome.strip().upper()
                st.session_state.sala_usuario = sala.strip().upper()
                st.session_state.tipo_usuario = tipo_pessoa

                st.rerun()

    st.stop()


# ==========================================
# MENU
# ==========================================

st.sidebar.write(
    f"👤 **{st.session_state.nome_usuario}**"
)

st.sidebar.caption(
    f"{st.session_state.tipo_usuario} - "
    f"{st.session_state.sala_usuario}"
)

st.sidebar.divider()

pagina = st.sidebar.radio(
    "Menu",
    [
        "Cadastrar item",
        "Ver itens",
        "Correspondencias",
        "Meus itens"
    ]
)


# ==========================================
# CADASTRAR ITEM
# ==========================================

if pagina == "Cadastrar item":
    st.subheader("Registrar um item")

    with st.container(border=True):
        tipo = st.radio(
            "O item foi?",
            ["achado", "perdido"],
            horizontal=True
        )

        descricao = st.text_input("Descreva seu item")

        foto = st.camera_input(
            "Tire uma foto do item (opcional)"
        )

        col1, col2 = st.columns(2)

        with col1:
            categoria = st.selectbox(
                "Categoria",
                CATEGORIAS
            )

        with col2:
            local = st.selectbox(
                "Local",
                LOCAIS
            )

        entregue_com = ""

        if tipo == "achado":
            entregue_com = st.text_input(
                "Com quem ou onde você deixou o item? "
                "(ex.: secretaria, professor)"
            )

        comentario = st.text_input(
            "Alguma observação? (opcional)"
        )

        if st.button("Cadastrar", type="primary"):
            if not descricao.strip():
                st.error("Descreva o item antes de cadastrar.")
            else:
                usuario_completo = (
                    f"{st.session_state.nome_usuario}-"
                    f"{st.session_state.sala_usuario}"
                )

                try:
                    salvar_item(
                        tipo,
                        descricao.strip(),
                        categoria,
                        local,
                        foto,
                        usuario_completo,
                        entregue_com,
                        comentario
                    )

                    st.success("Item cadastrado com sucesso!")

                except Exception:
                    st.error(
                        "Não foi possível cadastrar o item. "
                        "Confira a conexão e as credenciais do Firebase."
                    )


# ==========================================
# VER ITENS
# ==========================================

elif pagina == "Ver itens":
    st.subheader("Itens cadastrados")

    df_itens = carregar_itens()

    total = len(df_itens)
    perdidos = len(df_itens[df_itens["tipo"] == "perdido"])
    achados = len(df_itens[df_itens["tipo"] == "achado"])

    col1, col2, col3 = st.columns(3)

    col1.metric("Total de itens", total)
    col2.metric("Perdidos", perdidos)
    col3.metric("Achados", achados)

    st.divider()

    filtro = st.selectbox(
        "Filtrar por tipo",
        ["Todos", "perdido", "achado"]
    )

    if filtro != "Todos":
        df_itens = df_itens[df_itens["tipo"] == filtro]

    st.divider()

    if df_itens.empty:
        st.info("Nenhum item cadastrado nessa categoria.")

    for _, item in df_itens.iterrows():
        with st.container(border=True):
            col_foto, col_info = st.columns([1, 3])

            with col_foto:
                mostrar_foto(item["foto"], largura=100)

            with col_info:
                st.write(
                    f"**{str(item['tipo']).capitalize()}** - "
                    f"{item['descricao']}"
                )

                st.write(
                    f"Categoria: {item['categoria']} | "
                    f"Local: {item['local']}"
                )

                st.caption(
                    f"Registrado por: {item['usuario']}"
                )


# ==========================================
# CORRESPONDÊNCIAS
# ==========================================

elif pagina == "Correspondencias":
    st.subheader("Possíveis correspondências")

    matches = encontrar_correspondencias()

    if matches.empty:
        st.info(
            "Ainda não há itens suficientes para comparar."
        )
    else:
        aba_altas, aba_todas = st.tabs(
            ["🟢 Alta chance (70–100%)", "Todas"]
        )

        with aba_altas:
            matches_altas = matches[matches["match"] >= 70]
            mostrar_matches(matches_altas)

        with aba_todas:
            mostrar_matches(matches)


# ==========================================
# MEUS ITENS
# ==========================================

elif pagina == "Meus itens":
    st.subheader("Meus itens")

    usuario_completo = (
        f"{st.session_state.nome_usuario}-"
        f"{st.session_state.sala_usuario}"
    )

    df_itens = carregar_itens()

    meus_itens = df_itens[
        df_itens["usuario"] == usuario_completo
    ]

    if meus_itens.empty:
        st.info("Você ainda não cadastrou nenhum item.")

    else:
        matches = encontrar_correspondencias()

        for _, item in meus_itens.iterrows():
            with st.container(border=True):
                col_foto, col_info = st.columns([1, 3])

                with col_foto:
                    mostrar_foto(item["foto"], largura=100)

                with col_info:
                    st.write(
                        f"**{str(item['tipo']).capitalize()}** - "
                        f"{item['descricao']}"
                    )

                    st.write(
                        f"Categoria: {item['categoria']} | "
                        f"Local: {item['local']}"
                    )

                    if item["tipo"] == "perdido":
                        match_deste_item = matches[
                            matches["perdido"] == item["descricao"]
                        ]
                    else:
                        match_deste_item = matches[
                            matches["achado"] == item["descricao"]
                        ]

                    match_deste_item = match_deste_item[
                        match_deste_item["match"] >= 70
                    ]

                    if not match_deste_item.empty:
                        st.success(
                            "🎉 Encontramos "
                            f"{len(match_deste_item)} possível(is) "
                            "correspondência(s) para este item!"
                        )

                        mostrar_matches(match_deste_item)
