from supabase import create_client
from difflib import SequenceMatcher
import pandas as pd
import streamlit as st
import os
import uuid

st.set_page_config(
    page_title="Achados e Perdidos",
    page_icon="🔎",
    layout="wide"
)

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

ARQUIVO_DADOS = "itens.csv"
PASTA_FOTOS = "fotos"
os.makedirs(PASTA_FOTOS, exist_ok=True)

CATEGORIAS = ["mochila", "carteira", "chave", "outros"]
LOCAIS = ["sala de aula", "cantina", "banheiro", "quadra", "patio", "auditorio", "outros"]


def carregar_itens():
    colunas = ["tipo", "descricao", "categoria", "local", "foto", "usuario", "entregue_com", "comentario"]

    resposta = supabase.table("itens").select("*").execute()

    if not resposta.data:
        return pd.DataFrame(columns=colunas)

    return pd.DataFrame(resposta.data)


def salvar_item(tipo, descricao, categoria, local, foto, usuario, entregue_com, comentario):
    nome_foto = ""

    if foto is not None:
        nome_foto = f"{uuid.uuid4()}.jpg"
        caminho_foto = os.path.join(PASTA_FOTOS, nome_foto)
        with open(caminho_foto, "wb") as arquivo:
            arquivo.write(foto.getbuffer())

    supabase.table("itens").insert({
        "tipo": tipo,
        "descricao": descricao,
        "categoria": categoria,
        "local": local,
        "foto": nome_foto,
        "usuario": usuario,
        "entregue_com": entregue_com,
        "comentario": comentario
    }).execute()

def parecenca(texto1, texto2):
    texto1 = str(texto1).lower()
    texto2 = str(texto2).lower()
    return SequenceMatcher(None, texto1, texto2).ratio()


def encontrar_correspondencias():
    colunas_resultado = ["perdido", "foto_perdido", "usuario_perdido", "comentario_perdido",
                          "achado", "foto_achado", "usuario_achado", "comentario_achado",
                          "entregue_com", "match"]

    df = carregar_itens()
    perdidos = df[df["tipo"] == "perdido"]
    achados = df[df["tipo"] == "achado"]

    resultados = []

    for indice_p, item_perdido in perdidos.iterrows():
        for indice_a, item_achado in achados.iterrows():
            score = 0

            if item_perdido["categoria"] == item_achado["categoria"]:
                score += 0.4

            if item_perdido["local"] == item_achado["local"]:
                score += 0.2

            score += 0.4 * parecenca(item_perdido["descricao"], item_achado["descricao"])

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


def mostrar_matches(tabela):
    if tabela.empty:
        st.info("nenhum item nessa faixa")
        return

    for indice, linha in tabela.iterrows():
        if linha["match"] >= 70:
            cor = "🟢"
        elif linha["match"] >= 40:
            cor = "🟡"
        else:
            cor = "🔴"

        with st.container(border=True):
            st.write(f"{cor} **{linha['match']}% de match**")

            col_perdido, col_achado = st.columns(2)

            with col_perdido:
                st.write(f"**Perdido:** {linha['perdido']}")
                st.caption(f"Registrado por: {linha['usuario_perdido']}")
                if linha["comentario_perdido"] and str(linha["comentario_perdido"]) != "nan":
                    st.caption(f"💬 \"{linha['comentario_perdido']}\"")
                if linha["foto_perdido"] and str(linha["foto_perdido"]) != "nan" and os.path.exists(os.path.join(PASTA_FOTOS, linha["foto_perdido"])):
                    caminho = os.path.join(PASTA_FOTOS, linha["foto_perdido"])
                    st.image(caminho, width=150)
                else:
                    st.write("sem foto")

            with col_achado:
                st.write(f"**Achado:** {linha['achado']}")
                st.caption(f"Registrado por: {linha['usuario_achado']}")
                if linha["entregue_com"] and str(linha["entregue_com"]) != "nan":
                    st.caption(f"📍 Deixado onde e com: {linha['entregue_com']}")
                if linha["comentario_achado"] and str(linha["comentario_achado"]) != "nan":
                    st.caption(f"💬 \"{linha['comentario_achado']}\"")
                if linha["foto_achado"] and str(linha["foto_achado"]) != "nan" and os.path.exists(os.path.join(PASTA_FOTOS, linha["foto_achado"])):
                    caminho = os.path.join(PASTA_FOTOS, linha["foto_achado"])
                    st.image(caminho, width=150)
                else:
                    st.write("sem foto")

st.title("🔎 Achados e Perdidos")
st.caption("Sistema para registrar e encontrar itens perdidos e achados")

if "nome_usuario" not in st.session_state:
    st.session_state.nome_usuario = ""
    st.session_state.sala_usuario = ""
    st.session_state.tipo_usuario = ""

if st.session_state.nome_usuario == "":
    st.subheader("Identifique-se para continuar")

    with st.form("form_identificacao"):
        nome = st.text_input("Nome completo", autocomplete="off")
        sala = st.text_input("Sala/turma (ou 'N/A' se não for aluno)", autocomplete="off")
        tipo_pessoa = st.selectbox("Você é:", ["Aluno", "Professor", "Funcionário", "Outro"])

        if st.form_submit_button("Entrar"):
            if nome.strip() == "":
                st.error("Preencha seu nome antes de continuar")
            else:
                st.session_state.nome_usuario = nome.strip().upper()
                st.session_state.sala_usuario = sala.strip().upper()
                st.session_state.tipo_usuario = tipo_pessoa
                st.rerun()

    st.stop()

st.sidebar.write(f"👤 **{st.session_state.nome_usuario}**")
st.sidebar.caption(f"{st.session_state.tipo_usuario} - {st.session_state.sala_usuario}")
st.sidebar.divider()

pagina = st.sidebar.radio("Menu", ["Cadastrar item", "Ver itens", "Correspondencias", "Meus itens"])

if pagina == "Cadastrar item":
    st.subheader("registrar um item")

    with st.container(border=True):
        tipo = st.radio("o item foi?", ["achado", "perdido"], horizontal=True)
        descricao = st.text_input("descreva seu item")
        foto = st.camera_input("Tire uma foto do item (opcional)")

        col1, col2 = st.columns(2)
        with col1:
            categoria = st.selectbox("categoria", CATEGORIAS)
        with col2:
            local = st.selectbox("local", LOCAIS)

        entregue_com = ""
        if tipo == "achado":
            entregue_com = st.text_input("Com quem ou onde você deixou o item? (ex: secretaria, prof. Ana)")

        comentario = st.text_input("Alguma observação? (opcional, ex: 'me chama no intervalo')")

        if st.button("Cadastrar", type="primary"):
            usuario_completo = f"{st.session_state.nome_usuario}-{st.session_state.sala_usuario}"
            salvar_item(tipo, descricao, categoria, local, foto, usuario_completo, entregue_com, comentario)
            st.success("item cadastrado com sucesso") 

if pagina == "Ver itens":
    st.subheader("itens cadastrados")

    df_itens = carregar_itens()
    total = len(df_itens)
    perdidos = len(df_itens[df_itens["tipo"] == "perdido"])
    achados = len(df_itens[df_itens["tipo"] == "achado"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de itens", total)
    with col2:
        st.metric("Perdidos", perdidos)
    with col3:
        st.metric("Achados", achados)

    st.divider()

    filtro = st.selectbox("Filtrar por tipo", ["Todos", "perdido", "achado"])
    if filtro != "Todos":
        df_itens = df_itens[df_itens["tipo"] == filtro]

    st.divider()

    for indice, item in df_itens.iterrows():
        with st.container(border=True):
            col_foto, col_info = st.columns([1, 3])

            with col_foto:
                if item["foto"] and str(item["foto"]) != "nan" and os.path.exists(os.path.join(PASTA_FOTOS, item["foto"])):
                    caminho = os.path.join(PASTA_FOTOS, item["foto"])
                    st.image(caminho, width=100)
                else:
                    st.write("sem foto")

            with col_info:
                st.write(f"**{item['tipo'].capitalize()}** - {item['descricao']}")
                st.write(f"Categoria: {item['categoria']} | Local: {item['local']}")

if pagina == "Correspondencias":
    st.subheader("possiveis correspondencias")

    matches = encontrar_correspondencias()

    if matches.empty:
        st.info("ainda nao ha itens suficientes para comparar")
    else:
        aba_altas, aba_todas = st.tabs(["🟢 Alta chance (70-100%)", "Todas"])

        with aba_altas:
            matches_altas = matches[matches["match"] >= 70]
            mostrar_matches(matches_altas)

        with aba_todas:
            mostrar_matches(matches)

if pagina ==  "Meus itens":
    st.subheader("Meus itens")

    usuario_completo = f"{st.session_state.nome_usuario}-{st.session_state.sala_usuario}"

    df_itens = carregar_itens()
    meus_itens = df_itens[df_itens["usuario"] == usuario_completo]

    if meus_itens.empty:
        st.info("você ainda não cadastrou nenhum item")
    else:
        matches = encontrar_correspondencias()

        for indice, item in meus_itens.iterrows():
            with st.container(border=True):
                col_foto, col_info = st.columns([1, 3])

                with col_foto:
                    if item["foto"] and str(item["foto"]) != "nan" and os.path.exists(os.path.join(PASTA_FOTOS, item["foto"])):
                        caminho = os.path.join(PASTA_FOTOS, item["foto"])
                        st.image(caminho, width=100)
                    else:
                        st.write("sem foto")

                with col_info:
                    st.write(f"**{item['tipo'].capitalize()}** - {item['descricao']}")
                    st.write(f"Categoria: {item['categoria']} | Local: {item['local']}")

                    if item["tipo"] == "perdido":
                        match_deste_item = matches[matches["perdido"] == item["descricao"]]
                    else:
                        match_deste_item = matches[matches["achado"] == item["descricao"]]

                    match_deste_item = match_deste_item[match_deste_item["match"] >= 70]

                    if not match_deste_item.empty:
                        st.success(f"🎉 encontramos {len(match_deste_item)} possível(is) match(es) para este item!")