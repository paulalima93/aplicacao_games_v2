import io
import base64
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask import Blueprint, render_template, request, redirect, url_for, session
from deep_translator import GoogleTranslator

from app import db
from app.models import Jogo

from app.services.scrapper import buscar_horas
from app.services.recomendador import buscar_jogos, buscar_imagem

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def home():
    if 'usuario' not in session:
        return render_template("home.html", zerados=0, backlog=0, wishlist=0)
    
    meu_id = session['usuario']['id']
    qtd_zerados = Jogo.query.filter_by(status='Zerado', usuario_id = meu_id).count()
    qtd_backlog = Jogo.query.filter_by(status='Backlog', usuario_id = meu_id).count()
    qtd_wishlist = Jogo.query.filter_by(status='Wishlist', usuario_id = meu_id).count()

    jogos_zerados = Jogo.query.filter_by(status='Zerado', usuario_id=meu_id).all()
    tags_perfil = []

    tradutor_pt_en = {
        'Indie': 'Indie',
        'Ação': 'Action',
        'Casual': 'Casual',
        'Aventura': 'Adventure',
        'Simulação': 'Simulation',
        'Estratégia': 'Strategy',
        'RPG': 'RPG',
        'Plataforma': 'Platformer',
        'Ação-Aventura': 'Action-Adventure',
        'Esportes': 'Sports',
        'Corrida': 'Racing',
        'Software': 'Software',
        'Luta': 'Fighting',
        'Acesso Antecipado': 'Early Access',
        'Complementos de jogo': 'Steam'
    }

    for j in jogos_zerados:
        if j.steam_appid:
            url_loja = f"https://store.steampowered.com/api/appdetails?appids={j.steam_appid}&l=english"
            try:
                resposta = requests.get(url_loja)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    str_appid = str(j.steam_appid)

                    if dados.get(str_appid, {}).get('success'):
                        dados_loja = dados[str_appid]['data']
                        if 'genres' in dados_loja:
                            for g in dados_loja['genres']:
                                tags_perfil.append(g['description'])
                                print(tags_perfil)
            except Exception as e:
                print(f"erro: {e}")
        else:
            if j.genero:
                genero_ingles = tradutor_pt_en.get(j.genero)
                if genero_ingles:
                    tags_perfil.append(genero_ingles)

    tags_perfil = list(set(tags_perfil))

    recomendacoes_home = buscar_jogos(tags_perfil, quantidade=10, nota_minima=8) 

    return render_template("home.html", zerados=qtd_zerados, backlog=qtd_backlog, wishlist=qtd_wishlist, 
                           recomendacoes=recomendacoes_home)

# Rota para a página de Jogos Zerados
@main_bp.route("/biblioteca")
def biblioteca():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_zerados = Jogo.query.filter_by(status='Zerado', usuario_id=meu_id).all()
    return render_template("biblioteca.html", lista_jogos=jogos_zerados)

# Rota para a página de Backlog
@main_bp.route("/backlog")
def backlog():
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_backlog = Jogo.query.filter_by(status='Backlog', usuario_id=meu_id).all()
    return render_template("backlog.html", lista_jogos=jogos_backlog)

# Rota para a página de Wishlist
@main_bp.route("/wishlist")
def wishlist():
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_wishlist = Jogo.query.filter_by(status='Wishlist', usuario_id=meu_id).all()
    return render_template("wishlist.html", lista_jogos=jogos_wishlist)

@main_bp.route("/adicionar", methods=["POST"])
def adicionar_jogo():
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    #pegar dados do formulário
    titulo_digitado = request.form.get("titulo")
    genero_digitado = request.form.get("genero")
    status_escolhido = request.form.get("status")

    novo_jogo = Jogo(
        titulo=titulo_digitado, 
        genero=genero_digitado, 
        status=status_escolhido,
        usuario_id = session['usuario']['id']
    )
    db.session.add(novo_jogo)
    db.session.commit()

    return redirect(url_for('main.home'))

@main_bp.route("/jogo/<int:id>")
def mostrar_jogo(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id=meu_id).first_or_404()

    # jogo = Jogo.query.get_or_404(id)

    imagem = "https://placehold.co/460x215/2b2d31/ffffff?text=Capa+Indisponivel"
    descricao = "Nenhuma descrição disponível para este jogo."
    metacritic = None

    if not jogo.steam_appid:
        url_busca = f"https://store.steampowered.com/api/storesearch/?term={jogo.titulo}&l=brazilian&cc=BR"
        try:
            res_busca = requests.get(url_busca).json()
            if res_busca.get('total', 0) > 0:
                jogo.steam_appid = res_busca['items'][0]['id']
                db.session.commit()
        except Exception as e:
            print(f"Erro ao buscar pelo nome: {e}")

    if jogo.steam_appid:
        url_loja = f"https://store.steampowered.com/api/appdetails?appids={jogo.steam_appid}&l=brazilian"

        try:
            resposta = requests.get(url_loja)
            if resposta.status_code == 200:
                dados = resposta.json()
                str_appid = str(jogo.steam_appid)
            

                if dados.get(str_appid, {}).get('success'):
                    dados_loja = dados[str_appid]['data']

                    if 'short_description' in dados_loja:
                        sinopse_original = dados_loja['short_description']
                        try:
                            sinopse_traduzida = GoogleTranslator(source='auto', target='pt').translate(sinopse_original)
                        except Exception as e:
                            print(f"Erro ao traduzir: {e}")    

                    imagem = dados_loja.get("header_image")
                    #descricao = dados_loja.get("short_description")
                    descricao = sinopse_traduzida
                    metacritic = dados_loja.get("metacritic", {}).get("score")

                    #if 'genres' in dados_loja:
                    # jogo.genero = dados_loja['genres'][0]['description']

                    

                    # db.session.commit()

        except Exception as e:
            print("Deu ruim", e)

    if imagem == "https://placehold.co/460x215/2b2d31/ffffff?text=Capa+Indisponivel":
        _imagem = buscar_imagem(jogo.titulo)

        if _imagem:
            imagem = _imagem

    if jogo.tempo_historia is None and jogo.tempo_solo is None:

        print(f"Buscando jogo {jogo.titulo}")
        resultado = buscar_horas(jogo.titulo)

        if resultado and resultado.get("sucesso"):
            jogo.tempo_historia = resultado["historia"]
            jogo.tempo_extra = resultado["extra"]
            jogo.tempo_completo = resultado["completo"]
            jogo.tempo_solo = resultado["solo"]
            jogo.tempo_coop = resultado["coop"]
            jogo.tempo_vs = resultado["vs"]

            print("Foi")
        else:
            jogo.tempo_historia = ""
            jogo.tempo_extra = ""
            jogo.tempo_completo = ""
            jogo.tempo_solo = ""
            jogo.tempo_coop = ""
            jogo.tempo_vs = ""
            print("O jogo já tá lá")
        db.session.commit()

    tradutor_pt_en = {
        'Indie': 'Indie',
        'Ação': 'Action',
        'Casual': 'Casual',
        'Aventura': 'Adventure',
        'Simulação': 'Simulation',
        'Estratégia': 'Strategy',
        'RPG': 'RPG',
        'Plataforma': 'Platformer',
        'Ação-Aventura': 'Action-Adventure',
        'Esportes': 'Sports',
        'Corrida': 'Racing',
        'Software': 'Software',
        'Luta': 'Fighting',
        'Acesso Antecipado': 'Early Access',
        'Complementos de jogo': 'Steam'
    }

    tags_busca = []
    if jogo.genero:
        genero_ingles = tradutor_pt_en.get(jogo.genero)
        if genero_ingles:
            tags_busca.append(genero_ingles)

    similares = buscar_jogos(tags_busca, quantidade=10, nota_minima=70) if tags_busca else []

    similares = [s for s in similares if s['titulo'].lower() != jogo.titulo.lower()]

    return render_template("jogo.html", 
                           jogo=jogo, 
                           imagem=imagem, 
                           descricao=descricao, 
                           metacritic=metacritic,
                           similares=similares)

@main_bp.route("/deletar/<int:id>")
def deletar_jogo(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id = meu_id).first_or_404()

    #jogo = Jogo.query.get_or_404(id)
    db.session.delete(jogo)
    db.session.commit()
    return redirect(url_for('main.home'))

@main_bp.route("/mudar_status/<int:id>/<novo_status>")
def mudar_status(id, novo_status):
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id = meu_id).first_or_404()

    #jogo = Jogo.query.get_or_404(id)
    jogo.status = novo_status
    db.session.commit()
    return redirect(request.referrer)

@main_bp.route('/estatisticas')
def estatiticas():
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))
    
    meu_id = session['usuario']['id']
    #meu_id = 76561198868735365

    consulta = Jogo.query.filter_by(usuario_id=meu_id).statement
    df_jogos = pd.read_sql(consulta, db.engine)

    if df_jogos.empty:
        return render_template(
            "estatisticas.html", 
            grafico_barras=None,
            grafico_pizza=None,
            grafico_matriz=None
            )
    
    dict_games = {
    'Indie' : 'Indie',
    'Action': 'Ação',
    'Casual': 'Casual',
    'Adventure' : 'Aventura',
    'Simulation' : 'Simulação',
    'Strategy' : 'Estratégia',
    'RPG': 'RPG',
    'Action-Adventure': 'Ação-Aventura',
    'Sports' : 'Esportes',
    'Racing': 'Corrida',
    'Software' : 'Software',
    'Fighting': 'Luta',
    'Early Access': 'Acesso Antecipado',
    'Steam': 'Complementos de jogo'
    }

    df_jogos['genero'] = df_jogos['genero'].replace(dict_games)

    #grafico de barras
    contagem_generos = df_jogos['genero'].value_counts()
    plt.figure(figsize=(10,6))
    plt.bar(contagem_generos.index, contagem_generos.values, color="gray")
    #plt.title ("Quantidade de jogos por gênero", fontsize=12)
    plt.xlabel("Gêneros", fontsize=12)
    plt.ylabel("Número de jogos", fontsize=12)
    plt.xticks(fontsize=8, rotation = 45)


    plt.tight_layout()
    img1 = io.BytesIO()
    plt.savefig(img1, format='png')
    img1.seek(0)
    graf_bar = base64.b64encode(img1.getvalue()).decode('utf-8')
    plt.close()

    #grafico de pizza
    contagem_status = df_jogos['status'].value_counts()
    plt.figure(figsize=(6,6))

    cores = ['tomato', 'lightskyblue', 'lightgreen']

    plt.pie(
        contagem_status.values,
        labels=contagem_status.index,
        autopct="%1.1f%%",
        startangle=90,
        colors=cores
    )

    #plt.title("Proporção da biblioteca")

    img2 = io.BytesIO()
    plt.savefig(img2, format='png')
    img2.seek(0)
    graf_pizza = base64.b64encode(img2.getvalue()).decode('utf-8')
    plt.close()


    #grafico matriz 
    matriz_comportamento = pd.crosstab(df_jogos['genero'], df_jogos['status'])
    matriz_comportamento.plot(kind='bar', stacked=True, figsize=(10,6), colormap='viridis')
    #plt.title('Situação dos jogos: Status X Gênero')
    plt.xlabel('Gêneros', fontsize=12)
    plt.ylabel('Quantidade de Jogos', fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    img3 = io.BytesIO()
    plt.savefig(img3, format='png')
    img3.seek(0)
    graf_matriz = base64.b64encode(img3.getvalue()).decode('utf-8')
    plt.close()

    return render_template(
        "estatisticas.html",
        grafico_barras=graf_bar,
        grafico_pizza=graf_pizza,
        graf_matriz=graf_matriz
        )

@main_bp.route('/little_update_dashora/<int:id>')
def little_update_dashora(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))

    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id=meu_id).first_or_404()

    resultado = buscar_horas(jogo.titulo)

    if resultado and resultado.get("sucesso"):
        jogo.tempo_historia = resultado["historia"]
        jogo.tempo_extra = resultado["extra"]
        jogo.tempo_completo = resultado["completo"]
        jogo.tempo_solo = resultado["solo"]
        jogo.tempo_coop = resultado["coop"]
        jogo.tempo_vs = resultado["vs"]
    
        print("Foi")
    else:
        jogo.tempo_historia = ""
        jogo.tempo_extra = ""
        jogo.tempo_completo = ""
        jogo.tempo_solo = ""
        jogo.tempo_coop = ""
        jogo.tempo_vs = ""
        print("O jogo já tá lá")
    db.session.commit()
    return redirect(url_for('main.mostrar_jogo', id=jogo.id))


