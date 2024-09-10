from flask import Blueprint,  redirect, request, current_app,jsonify
from utils.models import *
import jwt
from werkzeug.security import check_password_hash, generate_password_hash
import uuid
import datetime
from geopy.geocoders import Nominatim
from access import token_required_api
from geopy.geocoders import Nominatim
from geopy.adapters import URLLibAdapter
import pickle
import ssl
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
import requests

api = Blueprint("api", __name__)
ctx = ssl.create_default_context()
ctx.check_hostname=False
ctx.verify_mode=ssl.CERT_NONE
geolocator = Nominatim(user_agent="Applicazione",ssl_context=ctx,adapter_factory=URLLibAdapter)

#/api and /api/docs are the same
@api.route('/')
def initial_page():
    return redirect('/api/docs')

@api.route('/login', methods=['POST'])
def login():
    #I expect informations that are JSON-formatted
    if request.headers['Content-Type'] == 'application/json':
        #I expect 2 informations in the request: username and password
        #NOTE: for sake of simplicity the password is sent without any security (in chiaro).
        #This should be in general avoided.
        data = request.get_json()

        #I check if both the username and password are present in the message sent.
        if not data or 'username' not in data or 'password' not in data:
            return jsonify(message="Missing both 'username' and 'password' in the json sent"), 400
        
        #I extract the infos that i was looking for
        username=data['username']
        password=data['password']

        #I check if the username and the password are correct, if not i return an error.
        if User.query.filter_by(name=username.lower()).first() is None:
            return jsonify(message="Username or Password are incorrect."), 400
        if not check_password_hash(User.query.filter_by(name=username.lower()).first().password, password):
            return jsonify(message="Username or Password are incorrect."), 400
        
        #I obtain a token for the given user.
        #NOTE: the token is fundamental because in order to extract other informations, you MUST have the token
        #otherwise you get rejected. You can see if the token is necessary because in the server you see @token_required and @token_require_api
        token = jwt.encode({'name': User.query.filter_by(name=username.lower()).first().name, 'exp': datetime.datetime.utcnow(
            ) + datetime.timedelta(milliseconds=30000)}, current_app.config.get('SECRET_KEY'), algorithm='HS256')
        
        #Io te lo passo ma devi vedere te come funziona lato applicazione.
        #Siccome ti passo anche il token, dopo questo me lo devi passare ogni volta nell'header in Authorization. 
        return jsonify(message="Correct Authentication",token=token), 200
    return jsonify(message="The content of the message sent to the URL is not JSON formatted"), 401

@api.route('/register',methods=['POST'])
def register():
    #I expect informations that are JSON-formatted
    if request.headers['Content-Type'] == 'application/json':
        data = request.get_json()
        try:
            if len(data['username']) <= 0 or ' ' in data['username'] or User.query.filter_by(name=data['username'].lower()).first()\
                  is not None or len(data['password']) == 0 or len(data['password']) <= 7 or data['role'] == 'None'\
                      or (data['role'] != 'restaurant' and data['role'] != 'supplier'):
                return jsonify(message="The informations passed are incorrect. Remember that the username must present a length greater than 0, \
                               no spaces and it must not already be present in the database. The password should have a length greater than 7.\
                               Lastly, the role must either be restaurant or supplier."), 400
        except:
            return jsonify(message="The informations passed are incorrect. Remember that the username must present a length greater than 0, \
                               no spaces and it must not already be present in the database. The password should have a length greater than 7.\
                               Lastly, the role must either be restaurant or supplier."), 400

        new_user = User(id=str(uuid.uuid4()),name=data['username'].lower(), password=generate_password_hash(data['password'], \
                            method='pbkdf2:sha256'), role=data['role'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify(message="Account successfully created."),200
    else:
        return jsonify(message="The informations sent are not JSON-formatted."),401

@api.route('/account/role',methods=['GET'])
@token_required_api
def account_role(current_user):
    return jsonify(message="Account role returned.",role=current_user.role),200

@api.route('/account/deletion',methods=['DELETE'])
@token_required_api
def account_deletion(current_user):
    #Devo fare una distinzione
    #Se sono un fornitore posso togliere il ristorante ma non lo toglie dal database
    #Se sono un ristoratore invece toglie tutte le informazioni del ristorante e a catena tutto il resto
    #QUESTO SIGNIFICA CHE SU CARTA A SUA VOLTA TUTTI I SUPPLIER DOVREBBERO PERDERE LE INFORMAZIONI DEL RISTORANTE!

    if current_user.role=='supplier':
        db.session.delete(current_user)
        db.session.commit()
    if current_user.role == 'restaurant':
        #Devo eliminare tutti i box, elements, restaurants dello user
        #prima di eliminarlo
        for restaurant in current_user.restaurants:
            #print(f"Questo e\' il ristorante: {restaurant.number}")
            for element in restaurant.elements.all():
                #print(f"Questo è l\'element: {element.id}")
                for box in element.box.all():
                    #print(f"Questo è il box: {box.id}")
                    db.session.delete(box)
                db.session.delete(element)
            db.session.delete(restaurant)
        db.session.delete(current_user)
        db.session.commit()

    return jsonify(message="Account successfully deleted."),200

@api.route('/restaurants',methods=['GET'])
@token_required_api
def restaurants(current_user):
    #In this given the user, you get as a return the restaurants associated to them with all the 
    #informations needed to display them.
    restaurants=dict()
    for i,_ in enumerate(current_user.restaurants):
        restaurants[f"Restaurant_{i+1}"]={
            'id':_.id,
            'number':_.number,
            'p_iva':_.p_iva,
            'name':_.name,
            'latitude':_.latitudine,
            'longitude':_.longitudine
        }
    return jsonify(restaurants)

@api.route('/restaurants/insertion',methods=['POST'])
@token_required_api
def restaurant_insertion(current_user):
    #I expect informations that are JSON-formatted
    if request.headers['Content-Type'] == 'application/json':
        #Controllo che tutti i parametri passati siano corretti
        data = request.get_json()

        try:
            if (len(data['address']) + len(data['city']) + len(data['CAP']) + len(data['PIVA']) + len(data['name']) == 0) or \
                len(data['PIVA']) != 11 or not data['PIVA'].isnumeric() or len(data['address'] )== 0 \
                    or len(data['city']) == 0 or len(data['CAP']) == 0:
                return jsonify(message="The informations passed are incorrect."), 400
        except:
            return jsonify(message="An error has occoured."), 400

        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            indirizzo = f"{data['address']}, {data['city']}, {data['CAP']}"
            location = geolocator.geocode(indirizzo)
            if location is None:
                return jsonify(message="The location passed doesn\'t exist."), 400
        except:
            return jsonify(message="An error has occoured. Try again."), 400

        #Ora devo distinguere se il ruolo dello user è restaurant owner oppure supplier
        if current_user.role == 'restaurant':
            # Controllo che non sia presente già nel database. Se è già presente è un errore perchè non dovrebbe accadere
            if Restaurant.query.filter(Restaurant.p_iva == int(data['PIVA']), Restaurant.name == data['name'],
                    Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first() is not None:
                return jsonify(message="The restaurant already exist."),400
            
            if Restaurant.query.order_by(Restaurant.number.desc()).first() is None:
                number = 0
            else:
                number = Restaurant.query.order_by(
                    Restaurant.number.desc()).first().number
            
            restaurant=Restaurant(id=str(uuid.uuid4()), number=number+1, p_iva=int(data['PIVA']), name=data['name'],
                        latitudine=location.latitude, longitudine=location.longitude)
            db.session.add(restaurant)
            current_user.restaurants.append(restaurant)
            db.session.commit()
        else:
            # Controllo che non sia presente già nel database. Se è già presente è un errore perchè non dovrebbe accadere
            if Restaurant.query.filter(Restaurant.p_iva == int(data['PIVA']), Restaurant.name == data['name'],
                    Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first() is None:
                return jsonify(message="The restaurant is not present in the database."),400

            restaurant=Restaurant.query.filter(Restaurant.p_iva == int(data['PIVA']), Restaurant.name == data['name'],
                    Restaurant.latitudine == location.latitude, Restaurant.longitudine == location.longitude).first()
            current_user.restaurant.append(restaurant)
            db.session.commit()
            
        return jsonify(message="Restaurant successfully inserted."),200
    else:
        return jsonify(message="The informations sent are not JSON-formatted."),401

@api.route('/restaurants/<int:restaurant_number>/elements',methods=['GET'])
@token_required_api
def elements(current_user,restaurant_number):
    #In this given the user, you get as a return the restaurants associated to them
    try:
        restaurant=[_ for _ in current_user.restaurants if _.number==int(restaurant_number)][0]
    except:
        return jsonify(message="The restaurant requested doesn\'t exist."), 400
    

    elements=dict()
    if current_user.role == 'restaurant':
        for i,_ in enumerate(restaurant.elements):
            elements[f"Element_{i+1}"]={
                'id':_.id,
                'internal_code':_.internal_code,
                'quantity':pickle.loads(_.elements)[-1][0],
                'description':_.description,
                'total_capacity':sum([i.capacity for i in _.box]),
                'date_next_supply': _.forecasting['date_next_supply'] if _.forecasting is not None else None,
                'quantity_to_deliver': _.forecasting['quantity_to_deliver'] if _.forecasting is not None else None
            }
    else:
        for i,_ in enumerate(restaurant.elements):
            elements[f"Element_{i+1}"]={
                'id':_.id,
                'description':_.description,
                'date_next_supply': _.forecasting['date_next_supply'] if _.forecasting is not None else None,
                'quantity_to_deliver': _.forecasting['quantity_to_deliver'] if _.forecasting is not None else None
            }

    return jsonify(elements)

@api.route('/restaurants/<int:restaurant_number>/deletion', methods=['DELETE'])
@token_required_api
def restaurant_in(current_user, restaurant_number):
    #First of all, i check whether the user has the restaurant number associated to themselves
    try:
        restaurant=[_ for _ in current_user.restaurants if _.number==int(restaurant_number)][0]
    except:
        return jsonify(message="The restaurant requested doesn\'t exist."), 400


    if current_user.role == 'supplier':
        index = None
        for i in range(len(current_user.restaurants)):
            if current_user.restaurants[i].number == int(restaurant_number):
                index = i

        current_user.restaurants.pop(index)
        # print(current_user.restaurants)
        db.session.commit()
    else:
        #print(f"Questo è il ristorante: {current_user.restaurants[index]}")
        #Ora devo rimuovere tutto a catena cioè devo rimuovere i box, poi gli elements
        #ed infine il ristorante dal database
        #Parto andando in profondità e rimuovendo tutti
        for element in restaurant.elements.all():
            print(f"Element: {element}")
            for box in element.box.all():
                print(f"Box: {box}")
                db.session.delete(box)
            db.session.delete(element)
        db.session.delete(Restaurant.query.filter_by(number=restaurant_number).first())
        #db.session.delete(current_user.restaurants[index])
        db.session.commit()
        #print(f"Questi sono gli elementi del ristorante: {current_user.restaurants[index].elements.all()}")
        #print(f"Questi sono i box del ristorante: {current_user.restaurants[index].elements.box.all()}")

    return jsonify(message="Deletition performed."),200

@api.route('/elements/<int:element_id>/forecast',methods=['GET'])
@token_required_api
def forecast(current_user,element_id):
    #Prima di tutto controllo che al dato utente sia associato un element con il dato id
    found=False
    for restaurant in current_user.restaurants:
         if restaurant.elements.filter_by(id=element_id).first():
             found=True

    if found is False: 
        return jsonify(message="The element id requested is either not associated to your account or it doesn\'t exist."), 400
    
    #Ora che so che l'element_id è effettivamente associato al suo account, posso estrarlo
    element=Element.query.filter_by(id=element_id).first()

    #Restituisco per il dato elemento la data della successiva supply e la quantità.
    #Qualora non sia ancora stata creata entrambi i valori sono settati a None. (se si
    #è interessati ad un solo elemento)
    if element.forecasting is None:
        return jsonify({'quantity_to_deliver':None, 'date_next_supply':None})
    else:
        return jsonify({'quantity_to_deliver':element.forecasting['quantity_to_deliver'],\
                        'date_next_supply': element.forecasting['date_next_supply']}) 

@api.route('/elements/<int:element_id>/boxes', methods=['GET'])
@token_required_api
def get_boxes(current_user,element_id):
    if current_user.role != 'restaurant':
        return jsonify(message="You don\'t have the privilege to perform this operation."), 400

    #Prima di tutto controllo che al dato utente sia associato un element con il dato id
    found=False
    for restaurant in current_user.restaurants:
         if restaurant.elements.filter_by(id=element_id).first():
             found=True

    if found is False: 
        return jsonify(message="The element id requested is either not associated to your account or it doesn\'t exist."), 400
    
    #Dato un element id vengono restituiti tutti i box ad esso associato
    #con anche le varie informazioni di essi. 
    element=Element.query.filter_by(id=element_id).first()

    boxes=dict()
    for i,_ in enumerate(element.box):
        boxes[f"Box_{i+1}"]={
            'id':_.id,
            'rfid':_.rfid,
            'internal_code':_.internal_code,
            'description':_.description,
            'quantity':pickle.loads(_.elements)[-1][0],
            'capacity':_.capacity
        }

    return jsonify(boxes)

#QUESTA API SARà DA ELIMINARE, TE L'HO INTRODOTTA PER AIUTARTI A TESTARE IL TUO CODICE
@api.route('/restaurant/<int:restaurant_number>/elements/<int:element_id>/generateForecast',methods=['POST'])
def generateForecast(restaurant_number,element_id):
    #Mi passi due valori (per comodità setto che devi usare JSON)
    if request.headers['Content-Type'] == 'application/json':
        #Controllo che tutti i parametri passati siano corretti
        data = request.get_json()

        #IN DATA CI DEVONO ESSERE 2 VALORI date_next_supply e quantity_to_deliver. date_next_supply DEVE essere formattata
        #nel seguente modo: %Y-%m-%d %H:%M:%S (NOTA SONO STRINGHE! quindi dall'applicazione dovresti trasformare in datetime))
        #(ad esempio: 2024-08-03 10:06:00. Nota imporante: le date che riceverai cambieranno solo di 15 secondi
        #perchè avevamo deciso che 15s=1 giorno per noi. Quindi 2024-08-03 10:06:00 e 2024-08-03 10:06:15 sono 2 giorni diversi.)
        #Altra cosa importante, se oggi è il 2024-08-03 10:06:00 può anche capitare che la data di consegna sia proprio il giorno dopo
        #e cioè 2024-08-03 10:06:15.
        element=Element.query.filter_by(id=element_id).first()
        if element.forecasting is None:
            element.forecasting={}
        #Aggiorno anche il db così se vuoi fare dei test quando ricevi dati nel login lo puoi fare
        element.forecasting={'model':None,'forecast':None,'date_next_supply':data['date_next_supply'],'quantity_to_deliver':data['quantity_to_deliver']}
        db.session.commit()

        import json
        from main import MQTT
        
        pacchetto={'date_next_supply':element.forecasting['date_next_supply'],'quantity_to_deliver':element.forecasting['quantity_to_deliver']}
        #Eseguo la pubblicazione su MQTT
        MQTT.clientMQTT.publish(f"/restaurants/{restaurant_number}/elements/{element.id}/supply",json.dumps(pacchetto),qos=1) 

        return jsonify(message="Element successfully inserted."),200
    else:
        return jsonify(message="The informations sent are not JSON-formatted."),401

@api.route('/route/getOptimalRoute',methods=['POST'])
def optimal_route():
    #Accetta come input una lista di punti (longitudine e latitudine) che sono quelli a cui bisogna
    #calcolare la route ottimale e restituisce il risultato all'applicazione.

    #Mi passi due valori (per comodità setto che devi usare JSON)
    if request.headers['Content-Type'] == 'application/json':
        #Controllo che tutti i parametri passati siano corretti
        data = request.get_json()
        

        coordinates=f""
        #Preparo i punti per ottenere la matrice
        for i,map_point in enumerate(data['coordinates']):
            if i == 0:
                coordinates=f"{map_point[0]},{map_point[1]}"
            else:
                coordinates+=f";{map_point[0]},{map_point[1]}"

        #Sfrutto le API di OSRM per ottenere la matrice delle distanze
        url=f"http://router.project-osrm.org/table/v1/driving/{coordinates}?annotations=distance"
        response=requests.get(url)

        if response.status_code == 200:
            data_response=response.json()
            distance_matrix=data_response['distances']
            #print(f"Questa e\' la matrice: {distance_matrix}")
        else:
            return jsonify(message="OSRM is not working."),400
        
        #Lo 0 alla fine indica che la prima coordinata rappresenta quella di partenza
        #Nota: questo codice sotto è il codice proposto da Google per calcolare il TSP.
        manager=pywrapcp.RoutingIndexManager(len(distance_matrix),1,0)
        routing=pywrapcp.RoutingModel(manager)

        def distance_from_to(index_from,index_to):
            node_from=manager.IndexToNode(index_from)
            node_to=manager.IndexToNode(index_to)
            return distance_matrix[node_from][node_to]
        
        transit_index=routing.RegisterTransitCallback(distance_from_to)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

        search_parameters=pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy=(routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

        solution=routing.SolveWithParameters(search_parameters)
        
        if solution:
            #Differentemente dallo stampare la soluzione formatto la soluzione affinchè questa mi 
            #resituisca in ordine le coordinate del percorso ottimo
            list_coordinates=list()
            index=routing.Start(0)

            while not routing.IsEnd(index):
                p_index=index
                list_coordinates.append(data['coordinates'][manager.IndexToNode(p_index)])
                index=solution.Value(routing.NextVar(index))
            
            #Aggiungo ancora una volta il punto di inizio
            list_coordinates.append(data['coordinates'][manager.IndexToNode(index)])
        else:
            return jsonify(message="An error has occoured."), 400
        
        return jsonify(coordinates=list_coordinates),200
    
    return jsonify(message="The informations sent are not JSON-formatted."),401

