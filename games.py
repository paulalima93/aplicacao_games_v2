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

app = Flask(__name__)

app.secret_key = os.environ.get('CHAVE_SECRETA_FLASK')

STEAM_API_KEY = os.environ.get('CHAVE_API_STEAM')

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

    #jogo = Jogo.query.get_or_404(id)

    if jogo.genero == "Steam" and jogo.steam_appid:
        url_loja = f"https://store.steampowered.com/api/appdetails?appids={jogo.steam_appid}&l=brazilian"

        try:
            resposta = requests.get(url_loja).json()
            str_appid = str(jogo.steam_appid)

            if resposta.get(str_appid, {}).get('success'):
                dados_loja = resposta[str_appid]['data']

                if 'genres' in dados_loja:
                    jogo.genero = dados_loja['genres'][0]['description']

                    db.session.commit()
        except Exception as e:
            print("Deu ruim", e)

    return render_template("jogo.html", jogo=jogo)

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

@app.route('/sincronizar_steam')
def sincronizar_steam():
    if 'usuario' not in session:
        return redirect(url_for('login_steam'))

    steam_id = session['usuario']['steam_id']
    meu_id = session['usuario']['id'] #NOVO

    # --- aqui vem da biblioteca ---
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

    except Exception as e:
        print(f"Erro ao sincronzar: {e}")    

    # # --- aqui vem da wishlist ---
    # # --- 2. AQUI VEM DA WISHLIST ---
    
    # # Colocamos o ?p=0 no final para forçar a Steam a não redirecionar e trazer os dados
    # url_wishlist = f"https://store.steampowered.com/wishlist/profiles/{steam_id}/wishlistdata/?p=0"
    
    # # Criamos um "Disfarce" (User-Agent). Isso engana a segurança da Steam, 
    # # fazendo ela achar que é um usuário real usando o Google Chrome no Windows.
    # cabecalhos = {
    #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    # }

    # try:
    #     # Enviamos a requisição usando o nosso disfarce
    #     req_wishlist = requests.get(url_wishlist, headers=cabecalhos)
        
    #     if req_wishlist.text.strip(): 
    #         try:
    #             resposta_wishlist = req_wishlist.json()

    #             if isinstance(resposta_wishlist, dict):
    #                 if not resposta_wishlist:
    #                     print("A Wishlist está vazia na página 0.")
    #                 else:
    #                     for appid_str, dados_jogo in resposta_wishlist.items():
    #                         titulo_wishlist = dados_jogo.get('name')
    #                         appid_wishlist = int(appid_str)

    #                         jogo_existente = Jogo.query.filter_by(titulo=titulo_wishlist, usuario_id=session['usuario']['id']).first()

    #                         if not jogo_existente:
    #                             novo_jogo = Jogo(
    #                                 titulo=titulo_wishlist,
    #                                 genero="Steam",
    #                                 status="Wishlist",
    #                                 steam_appid=appid_wishlist,
    #                                 usuario_id=session['usuario']['id']
    #                             )
    #                             db.session.add(novo_jogo)

    #                     db.session.commit()
                        
    #         except Exception as e_json:
    #             print("A Steam bloqueou a leitura da Wishlist.")
    #             flash("A Steam bloqueou o acesso à Wishlist. Tente novamente mais tarde.", "erro")
    #     else:
    #         flash("Sua Wishlist é privada ou está vazia. Verifique a Steam.", "erro")
        
    # except Exception as e:
    #     print(f"Erro de conexão com a WISHLIST: {e}")

    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)