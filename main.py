import src.utils as utils
from tqdm import tqdm
import os
tqdm.pandas()

def main():

    print("📄 Bem-vindo ao SciELO Summarizer!")
    print("📚 Vamos buscar artigos do SciELO para você usando webscraping e resumi-los com o Llama3 🦙!")

    print("--------------------")

    print("🔍 Primeiro, vamos definir o que você quer buscar...")
    query, n_artigos, ordenamento, quer_recorte_temporal, anos = utils.obter_parametros_busca()

    print("--------------------")

    print("📝 Agora, vamos definir como você quer resumir os artigos...")
    print("\n")
    tipo_resumo, prompt_resumo, server = utils.obter_parametros_resumo()
    
    print("--------------------")

    print("🔍 Buscando os artigos no SciELO...")
    if quer_recorte_temporal:
        html = utils.buscar_artigos(query, n_artigos, sorting=ordenamento, anos=anos)
    else:
        html = utils.buscar_artigos(query, n_artigos, sorting=ordenamento)
    
    print("✅ Artigos encontrados!")

    print("--------------------")

    print("📄 Extraindo metadados dos artigos...")
    articles = utils.extrair_artigos(html)
    print("✅ Informações extraídas!")

    print("--------------------")

    print("📝 Extraindo seções dos artigos...")
    articles["secoes_dict"] = articles["link"].progress_apply(utils.extrair_secoes)
    print("✅ Seções extraídas!")

    print("--------------------")

    print("📝 Compondo texto completo dos artigos...")
    articles["texto_completo"] = articles["secoes_dict"].progress_apply(utils.extrair_texto_completo)
    print("✅ Texto completo extraído!")

    print("--------------------")

    print("📝 Sumarizando os artigos usando o modelo Llama3 🦙...")
    print("⏳ Isso pode levar um tempo... sugerimos pegar um café! ☕")
    
    if tipo_resumo == "Resumir com o texto todo (rápido, mas mais superficial)":
        articles["resumo_llm_texto_completo"] = articles["texto_completo"].progress_apply(utils.resumir_artigo_texto_completo, prompt_resumo=prompt_resumo, server=server)
    
    elif tipo_resumo == "Resumir por seção (lento, mas mais detalhado)":
        articles["resumo_llm_secoes"] = articles["secoes_dict"].progress_apply(utils.resumir_artigo_secoes)
    
    elif tipo_resumo == "Ambos":
        articles["resumo_llm_texto_completo"] = articles["texto_completo"].progress_apply(utils.resumir_artigo_texto_completo, prompt_resumo=prompt_resumo, server=server)
        articles["resumo_llm_secoes"] = articles["secoes_dict"].progress_apply(utils.resumir_artigo_secoes)
    
    print("✅ Artigos sumarizados!")

    print("--------------------")

    print("🎲 Exportando os dados para um arquivo .xlsx...")
    os.makedirs("resumos", exist_ok=True)
    FILENAME = f"resumos/artigos_{query.replace(' ', '_')}_{n_artigos}_{ordenamento.replace(' ', '_')}.xlsx"
    articles.to_excel(FILENAME, index=False)
    print("✅ Dados exportados!")

    return articles

if __name__ == "__main__":
    main()