from flask import Blueprint, render_template, redirect, session, url_for, flash, request, current_app
from utils.models import *
import jwt
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from geopy.geocoders import Nominatim
from geopy.adapters import URLLibAdapter
import ssl

auth = Blueprint("auth", __name__)
ctx = ssl.create_default_context()
ctx.check_hostname=False
ctx.verify_mode=ssl.CERT_NONE
geolocator = Nominatim(user_agent="Applicazione",ssl_context=ctx,adapter_factory=URLLibAdapter)


@auth.route('/')
def initial_page():
    return render_template("main.html")


@auth.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        #print(request.form)

        if len(request.form.get('username')) <= 0:
            flash("No Username has been introduced", category="error")
        # CODICE AGGIUNTO E DA TESTARE
        elif ' ' in request.form.get('username'):
            flash(
                f"The username introduced contains spaces. Please remove all the spaces.", category="error")
        elif User.query.filter_by(name=request.form.get('username').lower()).first() is not None:
            flash(
                f"{request.form.get('username')} is already existing. Please choose a different username.", category="error")
        elif len(request.form.get('password')) == 0:
            flash("No password submitted",
                  category="error")
        elif len(request.form.get('password')) <= 7:
            flash("The password introduced has less than 8 characters",
                  category="error")
        elif request.form.get('role') == 'None':
            # FAR CONTROLLARE
            flash("It's mandatory to choose if the account is for a restaurant owner or as a supplier.",
                  category="error")
        # Eseguo ora i controlli
        # Attenzione: il ristoratore può aggiungere nuovi ristoranti nel database, mentre il supplier
        # può solo associare a sè ristoranti che già sono stati introdotti nel database
        else:
            blank = 0
            new_restaurants = list()
            if Restaurant.query.order_by(Restaurant.number.desc()).first() is None:
                number = 0
            else:
                number = Restaurant.query.order_by(
                    Restaurant.number.desc()).first().number
            # Utilizzo il flag correct per arricurarmi se tutto è andato a buon fine
            correct = False
            for _ in range(5):
                indirizzo = ""
                indirizzo = f"{request.form.get(f'address {_}')}, {request.form.get(f'city {_}')}, {request.form.get(f'CAP {_}')}"
                # Se tutti i campi forniti sono nulli passo all'iterazione successiva
                if len(request.form.get(f'address {_}')) + len(request.form.get(f'city {_}')) + len(request.form.get(f'CAP {_}')) + len(request.form.get(f'PIVA {_}')) + len(request.form.get(f'name {_}')) == 0:
                    blank += 1
                    continue
                # Faccio dei controlli sulla partita iva
                elif len(request.form.get(f'PIVA {_}')) != 11 or not request.form.get(f'PIVA {_}').isnumeric():
                    flash(
                        f"The informations about Partita IVA written in Restaurant {_+1} are incorrect. Please remember that it must be composed of 11 numbers.", category="error")
                    correct = False
                    break
                # Se tutti i campi dell'indirizzo non sono stati compilati genero un messaggio di errore.
                elif len(request.form.get(f'address {_}')) == 0 or len(request.form.get(f'city {_}')) == 0 or len(request.form.get(f'CAP {_}')) == 0:
                    flash(
                        f"In Restaurant {_+1} not all the forms have been added. Please, add all the informations.", category="error")
                    correct = False
                    break
                # Se i campi dell'indirizzo sono tutti stati compilati, controllo se l'indizzo fornito è effettivamente corretto
                else:
                    ssl._create_default_https_context = ssl._create_unverified_context
                    location = geolocator.geocode(indirizzo)
                    if location is None:
                        flash(
                            f"In Restaurant {_+1}, the location introduced does not exist.", category="error")
                        correct = False
                        break
                
                # Variabile che mi serve per poter uscire dal ciclo se il ristorante è già presente
                is_inside = False

                # Controllo che il ristorante non sia già presente all'interno di new_restaurants, altrimenti aggiungerei 2 volte lo stesso ristorante
                for foo in new_restaurants:
                    if foo.p_iva == int(request.form.get(f'PIVA {_}')) and foo.name == request.form.get(f'name {_}') and foo.latitudine == location.latitude and foo.longitudine == location.longitude:
                        flash(
                            f"Restaurant {_+1} has been repeated. Please, be sure you have inserted the correct datas.", category="error")
                        correct = False
                        is_inside = True
                if is_inside:
                    break

                if request.form.get('role') == 'restaurant':
                    # Controllo che non sia presente già nel database. Se è già presente è un errore perchè non dovrebbe accadere
                    if Restaurant.query.filter(Restaurant.p_iva == int(request.form.get(f'PIVA {_}')), Restaurant.name == request.form.get(f'name {_}'),
                                               Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first() is not None:
                        flash(
                            f"Restaurant {_+1} has alredy been introduced by another restaurant owner. Please, be sure you have inserted the correct datas.", category="error")
                        correct = False
                        break
                    #print(f"{location.latitude},{location.longitude}")

                    # Se sono arrivato qui tutte le informazioni inviate dell'i-esimo ristorante sono corrette,
                    # pertanto posso procedere a creare l'istanza di un ristorante.
                    # Attenzione: i ristoranti verranno introdotti nel database SOLO quando tutti gli input sono stati controllati
                    new_restaurants.append(Restaurant(id=str(uuid.uuid4()), number=number+_+1-blank, p_iva=int(request.form.get(f'PIVA {_}')), name=request.form.get(f'name {_}'),
                                                      latitudine=location.latitude, longitudine=location.longitude))
                    correct = True
                else:
                    # Se sono un supplier, il ristorante deve essere GIA' presente all'interno del database
                    if Restaurant.query.filter(Restaurant.p_iva == int(request.form.get(f'PIVA {_}')), Restaurant.name == request.form.get(f'name {_}'),
                                               Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first() is None:
                        flash(
                            f"Restaurant {_+1} doesn\'t exist in the database. Please, be sure you have inserted the correct datas.", category="error")
                        correct = False
                        break
                    else:
                        print(
                            f"Sono all\'iterazione {_} e new_restaurants è composto da: {new_restaurants}")

                        new_restaurants.append(Restaurant.query.filter(Restaurant.p_iva == int(request.form.get(f'PIVA {_}')), Restaurant.name == request.form.get(f'name {_}'),
                                                                       Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first())
                        correct = True

            # Se non è stato introdotto neanche un ristorante, segnalo che almeno 1 deve essere passato
            if blank == 5:
                flash(
                    f"In order to create an account, at least 1 restaurant needs to be introduced", category="error")

            # Se correct è posto a True significa che non ho mai avuto nessun problema con gli input ricevuti
            # pertanto posso procedere ad introdurre nel database le informazioni.
            # Nota bene: almeno un ristorante deve essere stato introdotto
            if correct:
                #print("sono arrivato qui!!!")
                new_user = User(id=str(uuid.uuid4()),
                                name=request.form.get('username').lower(), password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'), role=request.form.get('role'))
                #print(f"Sono arrivato alla fine. Restaurants: {new_restaurants} e la sua dimensione e\': {len(new_restaurants)}")
                for _ in new_restaurants:
                    if request.form.get('role') == 'restaurant':
                        db.session.add(_)
                    new_user.restaurants.append(_)

                #print(new_user.restaurants)
                db.session.add(new_user)
                db.session.commit()

                #print(User.query.filter_by(name=request.form.get('username').lower()).first().restaurants)

                # La registrazione è andata a buon fine, segnala all'utente che bisogna ora loggare e ridirigi a login
                flash(
                    "The account has been successfully created. Please Login in with your credentials", category="success")
                return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        """
        print(request.form)
        print(
            f"La dimensione dello username e\' {len(request.form.get('username'))}")
        print(
            f"La dimensione della password e\' {len(request.form.get('password'))}")
        """
        # Controllo generico per assicurarmi che le informazioni passate soddisfino i requisiti base
        if len(request.form.get('username')) <= 0:
            flash("No Username has been introduced", category="error")
        elif len(request.form.get('password')) == 0:
            flash("No password submitted",
                  category="error")
        elif len(request.form.get('password')) <= 7:
            flash("The password introduced has less than 8 characters",
                  category="error")
        # Controllo che l'utente e la password passate esistano nel database
        elif User.query.filter_by(name=request.form.get('username').lower()).first() is None:
            flash("Username not existing", category="error")
        elif not check_password_hash(User.query.filter_by(name=request.form.get('username').lower()).first().password, request.form.get('password')):
            flash("Password incorrect", category="error")
        else:
            # PER ORA IL TOKEN DURA 30 SECONDI
            token = jwt.encode({'name': User.query.filter_by(name=request.form.get('username').lower()).first().name, 'exp': datetime.datetime.utcnow(
            ) + datetime.timedelta(milliseconds=60000)}, current_app.config.get('SECRET_KEY'), algorithm='HS256')
            session['token'] = token
            # Accedo alla specifica pagina dell'account (siccome lo username è univoco uso questo)
            return redirect(url_for('restaurants.logged_in', name_id=User.query.filter_by(name=request.form.get('username').lower()).first().name))

    return render_template("login.html")
