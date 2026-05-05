import streamlit as st
import gspread as gsp
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import json

senha = st.text_input("Senha de Acesso", type="password")
    if senha != st.secrets["PASSWORD"]:
        st.error("Acesso negado.")
        st.stop() 
    st.success("Bem-vindo!")

ESCOPO = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

CHAVE = 'orcamento-familiar-493121-14f276170fbc.json'

TRADUCAO = {
    'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
    'April': 'Abril', 'May': 'Maio', 'June': 'Junho', 'July': 'Julho',
    'August': 'Agosto', 'September': 'Setembro', 'October': 'Outubro',
    'November': 'Novembro', 'December': 'Dezembro'
}

@st.cache_resource
def conectar_sheets():
    try:
        info = json.loads(st.secrets["gcp_service_account"]["json"])
        credenciais = Credentials.from_service_account_info(info, scopes=ESCOPO)
        cliente = gsp.authorize(credenciais)
        sheet = cliente.open("base_dados_app_orçamento_familiar").sheet1
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

@st.cache_data(ttl=120)
def carregar_dados(_sheet):
    dados = _sheet.get_all_records()
    df = pd.DataFrame(dados)
    if df.empty or 'DATA' not in df.columns:
        return df
    df = df[df['DATA'] != '']
    df['VALOR'] = df['VALOR'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.').str.strip()
    df['VALOR'] = pd.to_numeric(df['VALOR'], errors='coerce')
    df['DATA'] = pd.to_datetime(df['DATA'], dayfirst=True)
    df['MES_ANO'] = df['DATA'].dt.to_period('M')
    df['DATA'] = df['DATA'].dt.strftime('%d/%m/%Y')
    return df

def adicionar_transacao(sheet):
    st.subheader("Nova Transação")
    
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0

    key = st.session_state.form_key
    
    data = st.date_input("Data")
    tipo = st.selectbox("Tipo", ["Saída", "Entrada"]).upper()
    lista_entradas = ['Salário', 'Freelance']
    lista_saidas = ["Mercado", "Gasolina", "Aluguel", "Comida", "Contas", "Transportes", "Saúde", "Lazer", "Roupa", "Poupança", "Pagamentos", "Verdinho"]
    if tipo == 'ENTRADA':
        categoria = st.selectbox('Categoria', lista_entradas).upper()
    else:
        categoria = st.selectbox('Categoria', lista_saidas).upper()
    valor = st.number_input("Valor (€)", min_value=0.0, format="%.2f", key=f'valor_{key}')
    comentario = st.text_input("Comentário", key=f'comentario_{key}')
    usuario = st.selectbox("Usuário", ["Mariano", "Jacque"]).upper()
    if st.button("Guardar"):
        sheet.append_row([str(data), tipo, categoria, valor, comentario, usuario])
        st.session_state.form_key += 1
        st.cache_data.clear()
        st.success("Transação guardada!")
        st.rerun()

def main():
    st.title('Orçamento Familiar')
    sheet = conectar_sheets()
    if sheet:
        df = carregar_dados(sheet)
        aba1, aba2, aba3 = st.tabs(['Principal', 'Visualização', 'Gráficos'])
        
        with aba1:
            adicionar_transacao(sheet)
            st.dataframe(df.drop(columns=['MES_ANO'], errors='ignore').iloc[::-1][:3], hide_index=True)
        
        with aba2:
            if not df.empty:
                meses_pt = [TRADUCAO[m.strftime('%B')] + ' ' + str(m.year) for m in df['MES_ANO'].unique()]
                mapa_meses = dict(zip(meses_pt, df['MES_ANO'].unique()))
                mes_selec = st.selectbox('Seleciona o mês', meses_pt, key='mes_aba2')
                df_filtrado = df[df['MES_ANO'] == mapa_meses[mes_selec]]
                total_entradas = df_filtrado[df_filtrado['TIPO'] == 'ENTRADA']['VALOR'].sum()
                total_saidas = df_filtrado[df_filtrado['TIPO'] == 'SAÍDA']['VALOR'].sum()
                col1, col2 = st.columns(2)
                col1.metric('Entradas', f'€ {total_entradas:.2f}')
                col2.metric('Saídas', f'€ {total_saidas:.2f}')
                st.dataframe(df_filtrado.drop(columns=['MES_ANO']).reset_index(drop=True), hide_index=True)
            else:
                st.info('Ainda não há transações registradas.')
        
        with aba3:
            if not df.empty:
                df_evolucao = df.groupby(['MES_ANO', 'TIPO'])['VALOR'].sum().reset_index()
                df_evolucao['MES_ANO'] = df_evolucao['MES_ANO'].apply(
                    lambda x: TRADUCAO[pd.Period(x, 'M').strftime('%B')] + ' ' + str(pd.Period(x, 'M').year)
                )
                fig = px.line(df_evolucao, x='MES_ANO', y='VALOR', color='TIPO',
                              color_discrete_map={'ENTRADA': 'green', 'SAÍDA': 'red'},
                              markers=True,
                              title='Evolução de Entradas e Saídas',
                              category_orders={'MES_ANO': sorted(df_evolucao['MES_ANO'].unique())})
                fig.update_xaxes(type='category')
                st.plotly_chart(fig)
                meses_pt3 = [TRADUCAO[m.strftime('%B')] + ' ' + str(m.year) for m in df['MES_ANO'].unique()]
                mapa_meses3 = dict(zip(meses_pt3, df['MES_ANO'].unique()))
                mes_selec3 = st.selectbox('Seleciona o mês', meses_pt3, key='mes_aba3')
                df_mes = df[df['MES_ANO'] == mapa_meses3[mes_selec3]]
                df_entradas = df_mes[df_mes['TIPO'] == 'ENTRADA']
                df_saidas = df_mes[df_mes['TIPO'] == 'SAÍDA']

                col1, col2 = st.columns(2)

                with col1:
                    if not df_entradas.empty:
                        fig_ent = px.pie(df_entradas, values='VALOR', names='CATEGORIA', title='Entradas por Categoria', color_discrete_sequence=px.colors.qualitative.Dark24)
                        st.plotly_chart(fig_ent)
                    else:
                        st.info('Sem entradas neste mês.')

                with col2:
                    if not df_saidas.empty:
                        fig_sai = px.pie(df_saidas, values='VALOR', names='CATEGORIA', title='Saídas por Categoria', color_discrete_sequence=px.colors.qualitative.Dark24)
                        st.plotly_chart(fig_sai)
                    else:
                        st.info('Sem saídas neste mês.')
            else:
                st.info('Ainda não há transações registradas.')

if __name__ == "__main__":
    main()