from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import ollama
import inquirer
# from transformers import pipeline
# import torch

###################################################################################
# Função para fazer perguntas para o usuário
###################################################################################

def obter_parametros_busca():
    questions = [
        inquirer.Text("query",
                      message="Query de busca",
                      ),
        inquirer.Text("n_artigos",
                      message="Número de artigos que deseja extrair",
                      ),
        inquirer.List("ordenamento",
                      message="Escolha o critério de ordenação",
                      choices=["Mais novos", "Mais antigos", "Mais relevantes", "Mais citados", "Mais acessados"],
                      ),
        inquirer.List("tipo_resumo",
                      message="Escolha o tipo de resumo",
                      choices=["Resumir com o texto todo (rápido, mas mais superficial)", "Resumir por seção (lento, mas mais detalhado)", "Ambos"],
                      ),
        inquirer.Confirm("quer_recorte_temporal",
                         message="Deseja escolher um recorte temporal?",
                         default=True,
                         ),
    ]

    answers = inquirer.prompt(questions)
    query = answers["query"]
    n_artigos = int(answers["n_artigos"])
    ordenamento = answers["ordenamento"]
    tipo_resumo = answers["tipo_resumo"]
    quer_recorte_temporal = answers["quer_recorte_temporal"]

    if quer_recorte_temporal:
        
        questions_anos = [
            inquirer.Text("ano_inicial",
                          message="Ano inicial",
                          ),
            inquirer.Text("ano_final",
                          message="Ano final",
                          ),
        ]
    
        answers_anos = inquirer.prompt(questions_anos)
        ano_inicial = answers_anos.get("ano_inicial")
        ano_final = answers_anos.get("ano_final")
        anos = (ano_inicial, ano_final)
    
    else:
        anos = None
    
    return query, n_artigos, ordenamento, tipo_resumo, quer_recorte_temporal, anos

###################################################################################
# Função para buscar artigos no site da SciELO
###################################################################################
def buscar_artigos(consulta, n_artigos_pg = 15, pg = 1, sorting=None, anos = None):
    """
    Função para buscar artigos no site da SciELO.
    Parâmetros:
    - consulta: string          # termo ou termos de pesquisa
    - n_artigos_pg: int         # número de artigos por página
    - pg: int                   # número da página
    - sorting: string           # critério de ordenação
    - anos: int ou list of int  # anos de publicação dos artigos
    """

    url = 'https://search.scielo.org/'

    # Tratamento do parâmetro sorting
    if sorting == 'Mais novos':
        sorting = 'YEAR_DESC'
    elif sorting == 'Mais antigos':
        sorting = 'YEAR_ASC'
    elif sorting == 'Mais relevantes':
        sorting = 'RELEVANCE'
    elif sorting == 'Mais citados':
        sorting = 'CITED_DESC'
    elif sorting == 'Mais acessados':
        sorting = 'ACCESS_DESC'
    elif sorting == None:
        sorting = ''

    params = {
        "q": consulta,
        "lang": "pt",
        "count": n_artigos_pg,
        "output": "site",
        "sort": sorting,
        "format": "summary",
        "page": pg
    }
    if anos:
        if isinstance(anos, list):
            params.update({f"filter[year_cluster][]": ano} for ano in anos)
        else:
            params[f"filter[year_cluster][]"] = anos

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Erro ao acessar a página: {response.status_code}")
        return None


###################################################################################
# Função para buscar artigos no site da SciELO
###################################################################################
def extrair_artigos(html):
    """
    Função para extrair os dados dos artigos da página de busca.
    Parâmetros:
    - html: string
    """
    # Parse do HTML
    soup = BeautifulSoup(html, 'html.parser')

    # Encontrar os elementos (divs) que contêm os dados dos artigos
    artigos = soup.find_all('div', class_='item')

    resultados = []
    for artigo in artigos:
        try:
            # Encontrar e extrair o título
            titulo_elem = artigo.find('strong', class_='title')
            titulo = titulo_elem.text.strip() if titulo_elem else 'Título não encontrado'

            # Encontrar e extrair o link
            link_elem = artigo.find('a')
            link = link_elem['href'] if link_elem else 'Link não encontrado'

            # Encontrar e extrair o DOI
            doi_elem = artigo.find('div', class_='line metadata')
            if doi_elem:
                doi_link_elem = doi_elem.find('a')
                doi = doi_link_elem['href'] if doi_link_elem else 'DOI não encontrado'
            else:
                doi = 'DOI não encontrado'

            # Encontrar e extrair o resumo
            abstract_elem = artigo.find('div', id=lambda x: x and x.endswith('_pt'))
            abstract = abstract_elem.text.strip() if abstract_elem else 'Resumo em português não encontrado'


            # Encontrar e extrair os nomes dos autores
            autores_elementos = artigo.find_all('a', class_='author')
            autores = [autor.text for autor in autores_elementos]
            if not autores:
                autores.append('Autores não encontrados')

            # Adicionar os dados ao DataFrame
            resultados.append({
                'titulo': titulo,
                'autores': autores,
                'doi': doi,
                'link': link,
                'resumo': abstract
            })
            df = pd.DataFrame(resultados)

            # Remover duplicatas com base no título, mantendo apenas a primeira ocorrência
            df = df.drop_duplicates(subset='titulo', keep='first')
            df = df.reset_index(drop=True)

        except AttributeError as e:
            print(f"Erro ao extrair artigo: {e}")

    return df


###################################################################################
# Função para extrair o texto da seção de artigo de uma página da SciELO
###################################################################################
def extrair_secoes(link):
    """
    Extrai o texto da seção de artigo de uma página da SciELO.
    Parâmetros:
    - link: string
    """

    try:
        # Requisição
        response = requests.get(link)

        # Aguardar 5 segundos antes de fazer a requisição
        time.sleep(5)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            secao_artigo = soup.find('div', class_='articleSection', attrs={'data-anchor': 'Text'})
            if secao_artigo:
                elementos = secao_artigo.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'])

                # List to store the results
                resultado = []
                header = None
                content = ''

                for elemento in elementos:
                    # Handle <p><b></b></p> as headers
                    if elemento.name == 'p' and elemento.find('b'):
                        if header:
                            resultado.append({'header': header, 'content': content.strip()})
                        header = elemento.text.strip()
                        content = ''
                    # Handle headers
                    elif elemento.name.startswith('h'):
                        if header:
                            resultado.append({'header': header, 'content': content.strip()})
                        header = elemento.text.strip()
                        content = ''
                    else:
                        # Normal paragraph
                        # Remover os spans com class "ref"
                        for span in elemento.find_all('span', class_='ref'):
                            span.decompose()
                        content += elemento.text.strip() + ' '

                # Append the last header-content pair
                if header:
                    resultado.append({'header': header, 'content': content.strip()})

                return resultado if resultado else 'Títulos e parágrafos não encontrados na seção de artigo'
            else:
                return 'Seção de artigo não encontrada'
        else:
            return 'Erro ao acessar a página'
    except requests.exceptions.RequestException as e:
        return f'Erro de requisição: {str(e)}'
    except Exception as e:
        return f'Erro: {str(e)}'
    

###################################################################################
# Função para extrair texto completo
###################################################################################
def extrair_texto_completo(secoes):
    """
    Extrai o texto completo dos artigos.
    Parâmetros:
    - df: DataFrame
    """

    # Adicionar uma coluna ao DataFrame para armazenar o texto completo
    texto_completo = ''
    for secao in secoes:
        texto_completo += f"{secao['header']}\n{secao['content']}\n\n"

    return texto_completo


###################################################################################
# Funções para resumir artigo (texto completo ou por seções)
###################################################################################
def resumir_artigo_texto_completo(texto_completo):
    """
    Resumir o texto completo do artigo. Usa o modelo llama3 a partir do ollama.
    Parâmetros:
    - texto_completo: string
    """

    prompt = 'Resuma o seguinte texto: ' + texto_completo
    response = ollama.chat(
        model = 'llama3',
        messages = [{'role': 'user', 'content': prompt}]
    )
    return response['message']['content']

def resumir_artigo_secoes(secoes):
    """
    Resumir o texto completo do artigo. Usa o modelo llama3 a partir do ollama.
    Parâmetros:
    - secoes: list
    """
    resumo = ''
    for secao in secoes:
        prompt = 'Resuma o seguinte texto: ' + secao['content']
        response = ollama.chat(
            model = 'llama3',
            messages = [{'role': 'user', 'content': prompt}]
        )
        resumo_mais_heading = f"{secao['heading']}\n{response['message']['content']}\n\n"
        resumo += resumo_mais_heading
    return resumo

# def resumir_artigo(secoes, summarization_model):
#     for secao in secoes:
#         content = secao['content']
        
#         if len(content) > 2000:
#             chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
#             summaries = [summarization_model(chunk, max_length=30, min_length = 10)[0]['summary_text'] for chunk in chunks]
#             secao['resumo'] = " ".join(summaries)
#         else:
#             secao['resumo'] = summarization_model(content, max_length=30, min_length = 10)[0]['summary_text']
    
#     resumo_completo = " ".join(secao['resumo'] for secao in secoes)

#     return resumo_completo

# def resumir_artigo(secoes, summarization_model):
#     for secao in secoes:
#         content = secao['content']
        
#         if len(content) > 2000:
#             chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
#             summaries = [summarization_model(chunk, max_length=int(len(chunk)//3), min_length = 10)[0]['summary_text'] for chunk in chunks]
#             secao['resumo'] = " ".join(summaries)
#         else:
#             secao['resumo'] = summarization_model(content, max_length=int(len(content)//3), min_length = 10)[0]['summary_text']
    
#     #resumo_completo = " ".join(secao['resumo'] for secao in secoes)

#     return secoes

