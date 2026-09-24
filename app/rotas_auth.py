import os
import urllib.parse
import requests
import re
import time
from flask import Blueprint, redirect, url_for, request, session

from app import db
from app.models import Usuario, Jogo

auth_bp = Blueprint('auth', __name__);
STEAM_API_KEY = os.environ.get('CHAVE_API_STEAM')


@auth_bp.route('/login/steam')
def login_steam():
    steam_openid_url = 'https://steamcommunity.com/openid/login'
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.mode': 'checkid_setup',
        'openid.return_to': url_for('auth.steam_authorize', _external=True),
        'openid.realm': request.host_url
    }
    query_string = urllib.parse.urlencode(params)
    
    return redirect(f"{steam_openid_url}?{query_string}")

@auth_bp.route('/authorize/steam')
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

    return redirect(url_for('auth.sincronizar_steam'))

@auth_bp.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('main.home'))

@auth_bp.route('/sincronizar_steam')
def sincronizar_steam():
    if 'usuario' not in session:
        return redirect(url_for('auth.login_steam'))

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

    return redirect(url_for('main.home'))

