import pandas as pd
import random

def buscar_jogos(tags, caminho='dados/jogos_dataset.csv', quantidade=8, nota_minima=0):
    try:
        df = pd.read_csv(caminho)
        df = df.dropna(subset=['nome'])

        recomendacoes = []
        tags_base = set([tag.strip().lower() for tag in tags])

        for index, linha in df.iterrows():
            nota_jogo = pd.to_numeric(linha.get('metacritic', 0), errors='coerce') 

            if pd.notna(nota_jogo) and nota_jogo < nota_minima:
                continue

            str_tags = str(linha.get('tags', ''))
            str_generos = str(linha.get('generos', ''))

            combinado = str_tags + "," + str_generos

            tags_jogos_csv = set([t.strip().lower() for t in combinado.split(',') if t.strip()])

            pontos = len(tags_base.intersection(tags_jogos_csv))

            if pontos > 0:
                _genero = str(linha.get('generos', 'Indie')).split(',')[0].strip()

                recomendacoes.append({
                    'titulo': linha['nome'],
                    'pontos': pontos,
                    'imagem': linha.get('imagem_url', 'https://placehold.co/150x200/2b2d31/ffffff?text=Capa'),
                    'genero': _genero
                })

        recomendacoes.sort(key=lambda x: x['pontos'], reverse=True)
        opcoes = recomendacoes[:40]
        qtd_final = min(quantidade, len(opcoes))
        sorteados = random.sample(opcoes, qtd_final)
        sorteados.sort(key=lambda x: x['pontos'], reverse=True)

        return sorteados
        
    except Exception as e:
        print(f"Erro ao recomendar: {e}")
        return []


def buscar_imagem(titulo, caminho='dados/jogos_dataset.csv'):
    try:
        df = pd.read_csv(caminho)
        match = df[df['nome'].str.lower() == titulo.lower()]

        if not match.empty:
            return match.iloc[0]['imagem_url']
    except Exception as e:
        print(f"Erro ao buscar imagem {e}")

    return None