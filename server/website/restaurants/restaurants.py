from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash
from access import token_required
from geopy.geocoders import Nominatim
from geopy.adapters import URLLibAdapter
from utils.models import *
import folium as fl
import uuid
import pickle
import datetime
import ssl

restaurants = Blueprint("restaurants", __name__)
ctx = ssl.create_default_context()
ctx.check_hostname=False
ctx.verify_mode=ssl.CERT_NONE
geolocator = Nominatim(user_agent="Applicazione",ssl_context=ctx,adapter_factory=URLLibAdapter)

def from_coordinates_to_address(current_user):
    # Ricostruisco gli indirizzi del ristoranti. Li introduco all'interno di un dizionario e li passo al template per mostrarli.
    location = dict()
    for _ in current_user.restaurants:
        foo = geolocator.reverse(f"{_.latitudine},{_.longitudine}").address
        location[(_.p_iva, _.name)] = foo

    return location


@restaurants.route('/insertion', methods=['GET', 'POST'])
@token_required
def restaurant_insertion(current_user, name_id):
    # Calcolo quanti ristoranti può andare ad introdurre.
    number_restaurants = len(current_user.restaurants)

    if request.method == 'POST':
        blank = 0
        new_restaurants = list()
        #print(Restaurant.query.order_by(Restaurant.number.desc()).first())
        if Restaurant.query.order_by(
                Restaurant.number.desc()).first() is None:
            number = 0
        else:
            number = Restaurant.query.order_by(
                Restaurant.number.desc()).first().number

        # Utilizzo il flag correct per arricurarmi se tutto è andato a buon fine
        correct = False
        for _ in range(5-number_restaurants):
            indirizzo = ""
            indirizzo = f"{request.form.get(f'address {_}')}, {request.form.get(f'city {_}')}, {request.form.get(f'CAP {_}')}"
            #print(request.form.get(f'address {_}'))
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
            try:
                location = geolocator.geocode(indirizzo)
            except:
                #Qualora si verifichi un errore, mostra la pagina ancora di registrazione
                flash(f"Sadly, the Geolocator API used has not worked properly. Please, insert the informations again.", category="error")
                return redirect(url_for("restaurants.restaurant_insertion", name_id=name_id))
            
            # Se i campi dell'indirizzo sono tutti stati compilati, controllo se l'indizzo fornito è effettivamente corretto
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

            if current_user.role == 'restaurant':
                # Controllo che non sia presente già nel database. Se è già presente è un errore perchè non dovrebbe accadere (se sono un ristoratore)
                if Restaurant.query.filter(Restaurant.p_iva == int(request.form.get(f'PIVA {_}')), Restaurant.name == request.form.get(f'name {_}'),
                                           Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first() is not None:
                    flash(
                        f"Restaurant {_+1} has alredy been introduced by another restaurant owner. Please, be sure you have inserted the correct datas.", category="error")
                    correct = False
                    break
            # print(f"{location.latitude},{location.longitude}")
            # Se sono arrivato qui tutte le informazioni inviate dell'i-esimo ristorante sono corrette,
            # pertanto posso procedere a creare l'istanza di un ristorante.
            # Attenzione: i ristoranti verranno introdotti nel database SOLO quando tutti gli input sono stati controllati
            if current_user.role=='restaurant':
                new_restaurants.append(Restaurant(id=str(uuid.uuid4()), number=number+_+1-blank, p_iva=int(request.form.get(f'PIVA {_}')), name=request.form.get(f'name {_}'),
                                              latitudine=location.latitude, longitudine=location.longitude))
            else:
                #Qui introduco gli elementi per il supplier se p_iva e la location sono corretti. Chiaramente non è il massimo
                #in quanto non identificano in maniera univoca il ristoratore.
                new_restaurants.append(Restaurant.query.filter_by(p_iva=int(request.form.get(f'PIVA {_}')),
                                              latitudine=location.latitude, longitudine=location.longitude).first())
            correct = True
        # Se correct è posto a True significa che non ho mai avuto nessun problema con gli input ricevuti
        # pertanto posso procedere ad introdurre nel database le informazioni.
        # Nota bene: almeno un ristorante deve essere stato introdotto
        if correct:
            for _ in new_restaurants:
                db.session.add(_)
                current_user.restaurants.append(_)
            #print(current_user.restaurants)
            db.session.commit()
            #print(User.query.filter_by(name=name_id.lower()).first().restaurants)
            # La registrazione è andata a buon fine, segnala all'utente che bisogna ora loggare e ridirigi a login
            flash(
                "The restaurants have been successfully added.", category="success")
            return redirect(url_for("restaurants.logged_in", name_id=name_id))

    return render_template("insertion.html", name=name_id, number=5-number_restaurants, username=current_user.name)


@restaurants.route('/<restaurant_number>', methods=['GET','DELETE'])
@token_required
def restaurant_in(current_user, name_id, restaurant_number):
    if request.method == 'DELETE':
        if current_user.role == 'supplier':
            #print(f"Questi sono i ristoranti: {current_user.restaurants}")
            index = None
            for i in range(len(current_user.restaurants)):
                #print(f"Questo è l'ID:{i.id}")
                #print(f"Questo è numero: {i.number}")
                if current_user.restaurants[i].number == int(restaurant_number):
                    index = i
            current_user.restaurants.pop(index)
            # print(current_user.restaurants)
            db.session.commit()
        if current_user.role == 'restaurant':
            #print(f"Questi sono i ristoranti: {current_user.restaurants}")
            index = None
            for i in range(len(current_user.restaurants)):
                #print(f"Questo è l'ID:{i.id}")
                #print(f"Questo è numero: {i.number}")
                if current_user.restaurants[i].number == int(restaurant_number):
                    index = i
            #print(f"Questo è il ristorante: {current_user.restaurants[index]}")
            # Ora devo rimuovere tutto a catena cioè devo rimuovere i box, poi gli elements
            # ed infine il ristorante dal database

            # Parto andando in profondità e rimuovendo tutti
            for element in current_user.restaurants[index].elements.all():
                #print(f"Element: {element}")
                for box in element.box.all():
                    #print(f"Box: {box}")
                    db.session.delete(box)
                db.session.delete(element)
            db.session.delete(current_user.restaurants[index])
            db.session.commit()
            #print(f"Questi sono gli elementi del ristorante: {current_user.restaurants[index].elements.all()}")
            #print(f"Questi sono i box del ristorante: {current_user.restaurants[index].elements.box.all()}")

        return jsonify({'redirect': f'/users/{name_id}/restaurants'})

    restaurant = [x for x in current_user.restaurants if x.number == int(
        restaurant_number)][0]
    # Uso folium per mostrare la mappa in maniera dinamica
    map = fl.Map(location=[restaurant.latitudine,
                           restaurant.longitudine], zoom_start=20)
    fl.Marker(location=[restaurant.latitudine,
                        restaurant.longitudine], popup=restaurant.name).add_to(map)
    map_html = map._repr_html_()
    # Ricreo l'address del ristorante
    address = geolocator.reverse(
        f"{restaurant.latitudine},{restaurant.longitudine}").address

    return render_template('restaurant.html', user=current_user, restaurant=restaurant, map=map_html, address=address)


@restaurants.route("/")
@token_required
def logged_in(current_user, name_id):
    # print(current_user.restaurants)
    # print(len(current_user.restaurants))
    location = from_coordinates_to_address(current_user)

    # print(location)
    return render_template('restaurants.html', username=current_user.name, restaurants=current_user.restaurants, locations=location)
