from flask import Flask, jsonify, render_template, request
import requests
import datetime
from flask_cors import CORS
import random
from sqlalchemy import create_engine, types, Column
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import psycopg2
from sendToMail import send_letter
from ftplib import FTP
import os
from dotenv import load_dotenv
import redis

app = Flask(__name__)
CORS(app)
rd = redis.Redis()
load_dotenv()

engine = create_engine(os.getenv("DB_STRING"))
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()


class Pokemonn(Base):
    __tablename__ = 'pokemons'
    __fields__ = ['id', 'winner_id', 'loser_id', 'count_rounds', 'created_at']

    id = Column(types.Integer, autoincrement=True, primary_key=True)
    winner_id = Column(types.Integer, nullable=False)
    loser_id = Column(types.Integer, nullable=False)
    rounds_count = Column(types.Integer, nullable=False, default=False)
    created_at = Column(types.DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow)


class Pokemon:
    def __int__(self):
        self.id = 0
        self.name = ''
        self.picture = ''
        self.abils = []
        self.attack = 0
        self.hp = 0


@app.route('/poke/api/pokemon/count', methods=['GET'])
def get_pokemons_count():
    r = requests.get('https://pokeapi.co/api/v2/pokemon/')
    count = r.json()['count']
    return jsonify(count)


@app.route('/poke/api/pokemon/<int:pokemon_id>', methods=['GET'])
def get_pokemon(pokemon_id):
    pokemon = Pokemon()
    pokemon.id = pokemon_id
    if not rd.hgetall("poke" + str(pokemon_id)):
        r = requests.get('https://pokeapi.co/api/v2/pokemon/' + str(pokemon_id) + '/')
        pokemon.name = r.json()['name']
        pokemon.picture = r.json()['sprites']['front_default']
        pokemon.abils = [i['ability']['name'] for i in r.json()['abilities'][:5]]
        pokemon.attack = r.json()['stats'][0]['base_stat']
        pokemon.hp = r.json()['stats'][1]['base_stat']
        rd.hset("poke" + str(pokemon_id), mapping={
            'name': pokemon.name,
            'picture': pokemon.picture,
            'abils': '/'.join(pokemon.abils),
            'attack': pokemon.attack,
            'hp': pokemon.hp
        })
    else:
        pokemon.name = bytes(rd.hget('poke' + str(pokemon_id), 'name')).decode("utf-8")
        pokemon.picture = bytes(rd.hget('poke' + str(pokemon_id), 'picture')).decode("utf-8")
        pokemon.abils = bytes(rd.hget('poke' + str(pokemon_id), 'abils')).decode("utf-8").split('/')
        pokemon.attack = int(rd.hget('poke' + str(pokemon_id), 'attack'))
        pokemon.hp = int(rd.hget('poke' + str(pokemon_id), 'hp'))
    return jsonify(pokemon.__dict__)


@app.route('/poke/api/pokemon/list', methods=['GET'])
def get_pokemons():
    filter_name = request.args.get('name', default=None, type=str)

    pokemons_count = requests.get('https://pokeapi.co/api/v2/pokemon/').json()['count']
    pokemons = requests.get('https://pokeapi.co/api/v2/pokemon?limit=' + str(pokemons_count) + '&offset=0').json()[
        'results']

    if filter_name is not None:
        pokemons = list(filter(lambda x: x['name'] == filter_name, pokemons))

    return {"pokemons": pokemons}


@app.route('/poke/api/pokemon/random', methods=['GET'])
def get_random_pokemon():
    pokemons_count = requests.get('https://pokeapi.co/api/v2/pokemon/').json()['count']
    pokemon_id = random.randint(1, pokemons_count)
    try:
        get_pokemon(pokemon_id)
    except:
        get_pokemon(random.randint(1, 500))
    return jsonify(pokemon_id)


@app.route('/poke/api/fight/<int:user_id>/<int:comp_id>', methods=['GET'])
def get_filght(user_id, comp_id):
    user_pokemon = get_pokemon(user_id)
    comp_pokemon = get_pokemon(comp_id)
    return {"user_pokemon": user_pokemon.json, "comp_pokemon": comp_pokemon.json}


@app.route('/poke/api/fight/<int:number>', methods=['POST'])
def post_fight(number):
    data = request.get_json()
    comp_number = random.randint(1, 10000000)
    if (number % 2 == 0 and comp_number % 2 == 0) or (number % 2 != 0 and comp_number % 2 != 0):
        data['comp_pokemon']['hp'] -= data['user_pokemon']['attack']
    else:
        data['user_pokemon']['hp'] -= data['comp_pokemon']['attack']

    return jsonify(data)


@app.route('/poke/api/fight/fast', methods=['POST'])
def get_fast_fight():
    data = request.get_json()
    rounds = 0
    while True:
        rounds += 1
        comp_number = random.randint(1, 10000000)
        number = random.randint(1, 10000000)
        if (number % 2 == 0 and comp_number % 2 == 0) or (number % 2 != 0 and comp_number % 2 != 0):
            data['comp_pokemon']['hp'] -= data['user_pokemon']['attack']
            if data['comp_pokemon']['hp'] <= 0:
                pokemon = Pokemonn(winner_id=data['user_pokemon']['id'],
                                   loser_id=data['comp_pokemon']['id'],
                                   rounds_count=rounds)
                session.add(pokemon)
                session.commit()
                return {"winner": data['user_pokemon'], "loser": data['comp_pokemon'],
                        "rounds": rounds}
        else:
            data['user_pokemon']['hp'] -= data['comp_pokemon']['attack']
            if data['user_pokemon']['hp'] <= 0:
                pokemon = Pokemonn(winner_id=data['comp_pokemon']['id'],
                                   loser_id=data['user_pokemon']['id'],
                                   rounds_count=rounds)
                session.add(pokemon)
                session.commit()

                return {"winner": data['comp_pokemon'], "loser": data['user_pokemon'],
                        "rounds": rounds}


@app.route('/poke/api/fight/send', methods=['POST'])
def send():
    r = str(request.get_json()['result']).encode('utf-8').strip()
    e = request.get_json()['email']
    send_letter(r, e)
    return jsonify(True)


@app.route('/poke/api/ftp', methods=['POST'])
def to_ftp():
    data = request.get_json()
    name = data['name']
    abils = data['abils']
    current_date = datetime.datetime.now().strftime('%Y%m%d')
    current_time = datetime.datetime.now().strftime('%H_%M_%S')
    with FTP(host=os.getenv("FTP_HOST"), user=os.getenv("FTP_USER"), passwd=os.getenv("FTP_PASSWORD")) as ftp:
        ftp.encoding = "utf-8"
        if current_date not in ftp.nlst():
            ftp.mkd(current_date)
        ftp.cwd(current_date)
        with open('file.md', 'w+') as file:
            file.write('# ' + name)
            file.write('\nablis: ' + str(abils))
        new = current_time + '.md'
        with open('file.md', 'rb') as file:
            ftp.storbinary(f"STOR {new}", file)
    return jsonify(True)
