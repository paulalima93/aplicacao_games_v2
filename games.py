import os
from dotenv import load_dotenv
load_dotenv()

import urllib.parse
import requests
import re
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import MetaData

#imports da analise
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import time

from teste_bot import buscar_horas

from deep_translator import GoogleTranslator

app = Flask(__name__)

app.secret_key = os.environ.get('CHAVE_SECRETA_FLASK')

STEAM_API_KEY = os.environ.get('CHAVE_API_STEAM')
#print(STEAM_API_KEY)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meus_jogos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db)

#molde tabela jogos 
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    steam_id = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    foto = db.Column(db.String(255))
    #referencia ao jogo
    jogos = db.relationship('Jogo', backref='dono', lazy=True)


class Jogo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable = False)
    genero = db.Column(db.String(50), nullable = False)
    status = db.Column(db.String(20), default = 'Wishlist')
    #ISSO FOI ADICIONADO USANDO MIGRATE
    steam_appid = db.Column(db.Integer, nullable = True)
    #chave estrangeira - fk
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    tempo_historia = db.Column(db.String(20), nullable=True)
    tempo_extra = db.Column(db.String(20), nullable=True)
    tempo_completo = db.Column(db.String(20), nullable=True)
    tempo_solo = db.Column(db.String(20), nullable=True)
    tempo_coop = db.Column(db.String(20), nullable=True)
    tempo_vs = db.Column(db.String(20), nullable=True)


# with app.app_context():
#     db.create_all()

# Rota para a página inicial
@app.route("/")
def home():
    if 'usuario' not in session:
        return render_template("home.html", zerados=0, backlog=0, wishlist=0)
    
    meu_id = session['usuario']['id']
    qtd_zerados = Jogo.query.filter_by(status='Zerado', usuario_id = meu_id).count()
    qtd_backlog = Jogo.query.filter_by(status='Backlog', usuario_id = meu_id).count()
    qtd_wishlist = Jogo.query.filter_by(status='Wishlist', usuario_id = meu_id).count()

    return render_template("home.html", zerados=qtd_zerados, backlog=qtd_backlog, wishlist=qtd_wishlist)

# Rota para a página de Jogos Zerados
@app.route("/biblioteca")
def biblioteca():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_zerados = Jogo.query.filter_by(status='Zerado', usuario_id=meu_id).all()
    return render_template("biblioteca.html", lista_jogos=jogos_zerados)

# Rota para a página de Backlog
@app.route("/backlog")
def backlog():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_backlog = Jogo.query.filter_by(status='Backlog', usuario_id=meu_id).all()
    return render_template("backlog.html", lista_jogos=jogos_backlog)

# Rota para a página de Wishlist
@app.route("/wishlist")
def wishlist():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']
    jogos_wishlist = Jogo.query.filter_by(status='Wishlist', usuario_id=meu_id).all()
    return render_template("wishlist.html", lista_jogos=jogos_wishlist)

@app.route("/adicionar", methods=["POST"])
def adicionar_jogo():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
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

    return redirect(url_for('home'))

@app.route("/jogo/<int:id>")
def mostrar_jogo(id):
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
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

    return render_template("jogo.html", jogo=jogo, imagem=imagem, descricao=descricao, metacritic=metacritic)

@app.route("/deletar/<int:id>")
def deletar_jogo(id):
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id = meu_id).first_or_404()

    #jogo = Jogo.query.get_or_404(id)
    db.session.delete(jogo)
    db.session.commit()
    return redirect(url_for('home'))

@app.route("/mudar_status/<int:id>/<novo_status>")
def mudar_status(id, novo_status):
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
    meu_id = session['usuario']['id']

    jogo = Jogo.query.filter_by(id=id, usuario_id = meu_id).first_or_404()

    #jogo = Jogo.query.get_or_404(id)
    jogo.status = novo_status
    db.session.commit()
    return redirect(request.referrer)


@app.route('/login/steam')
def login_steam():
    steam_openid_url = 'https://steamcommunity.com/openid/login'
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.mode': 'checkid_setup',
        'openid.return_to': url_for('steam_authorize', _external=True),
        'openid.realm': request.host_url
    }
    query_string = urllib.parse.urlencode(params)
    
    return redirect(f"{steam_openid_url}?{query_string}")

@app.route('/authorize/steam')
def steam_authorize():
    claimed_id = request.args.get('openid.claimed_id')
    if not claimed_id:
        return "Falha no login com a Steam", 400

    steam_id = re.search(r'\d+', claimed_id).group()
    api_url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}" 
    
    resposta = requests.get(api_url).json()

    # res = requests.get(api_url)
    # print("URL:", api_url)
    # print("Status:", res.status_code)
    # print("Headers:", res.headers.get("Content-Type"))
    # print("Texto:")
    # print(res.text)
    #resposta = res.json()

    jogador = resposta['response']['players'][0]

    usuario = Usuario.query.filter_by(steam_id=steam_id).first()

    if not usuario:
        usuario = Usuario(
            steam_id=steam_id,
            nome=jogador['personaname'],
            foto=jogador['avatarfull']
        )
        db.session.add(usuario)
        db.session.commit()

    session['usuario'] = {
        'id': usuario.id,
        'nome': jogador['personaname'],
        'foto': jogador['avatarfull'],
        'steam_id': steam_id
    }

    return redirect(url_for('sincronizar_steam'))


@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('home'))

@app.route('/estatisticas')
def estatiticas():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))
    
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

@app.route('/sincronizar_steam')
def sincronizar_steam():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))

    steam_id = session['usuario']['steam_id']
    meu_id = session['usuario']['id'] #NOVO

    # --- puxa dados da biblioteca ---
    url_owned = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={STEAM_API_KEY}&steamid={steam_id}&include_appinfo=1&format=json"

    try:
        resposta = requests.get(url_owned).json()
        jogos_steam = resposta.get('response', {}).get('games', [])

        for jogo_api in jogos_steam:
            titulo_steam = jogo_api.get('name')
            appid_steam = jogo_api.get('appid')
            
            #MUDEI AQUI
            jogo_existente = Jogo.query.filter_by(titulo=titulo_steam, usuario_id=meu_id).first()

            if not jogo_existente:
                novo_jogo = Jogo(
                    titulo = titulo_steam,
                    genero = "Steam",
                    status="Backlog",
                    steam_appid = appid_steam,
                    usuario_id = meu_id
                )

                db.session.add(novo_jogo)

        db.session.commit()

        # enriquecimento de dados (genero)
        jogos_pedentes = Jogo.query.filter_by(usuario_id = meu_id, genero = "Steam").all();
    
        for jogo in jogos_pedentes:
            if not jogo.steam_appid:
                continue

            url_store = f"http://store.steampowered.com/api/appdetails?appids={jogo.steam_appid}&l=brazilian"  

            try:
                res_store = requests.get(url_store)
                if res_store.status_code == 200:
                    dados = res_store.json()
                    str_appid = str(jogo.steam_appid)

                    if dados.get(str_appid, {}).get('success'):
                        info_jogo = dados[str_appid]['data']
                        generos = info_jogo.get('genres', [])

                        if generos:
                            jogo.genero = generos[0]['description']
            except Exception as e:
                print("Erro")

            time.sleep(1.5)

        db.session.commit()

    except Exception as e:
        print(f"Erro ao sincronzar: {e}")    

    return redirect(url_for('home'))


@app.route('/little_update_dashora/<int:id>')
def little_update_dashora(id):
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))

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
    return redirect(url_for('mostrar_jogo', id=jogo.id))



if __name__ == "__main__":
    app.run(debug=True)