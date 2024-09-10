from flask import jsonify
import paho.mqtt.client as mqtt
import configparser
from utils.models import *
import pickle
import datetime
import json
import pandas as pd
import holidays
import numpy as np
from prophet import Prophet, serialize
import datetime
import json
import math
import pickle
import threading
from sqlalchemy import inspect

last_publish_led=None
lock=threading.Lock()

def timeserie(element_id):
    element=Element.query.filter_by(id=element_id).first()
    capacity=0
    for box in element.box.all():
        capacity += box.capacity

    #print(f"Questa e\' la capacity: {capacity}")
    PREDICTION=45

    it_holidays=holidays.IT(years=datetime.datetime.now().year)
    italian_holidays=pd.DataFrame({'ds':it_holidays.keys(),'holiday':it_holidays.values()})
    #Devo trasformarli in giorni altrimenti non funziona correttamente..
    #DEVO MODIFICARE QUI PERCHè DEVE PRENDERE I DATI DA ELEMENTS E NON GENERARLI NUOVI
    
    df=pd.DataFrame(pickle.loads(element.elements),columns=['y','ds'])
    df['ds']=pd.to_datetime(df['ds'])

    today=datetime.datetime.now().replace(microsecond=0)

    df['ds']=today-pd.to_timedelta(len(df)-df.index-1,unit='D')

    #print(df)
    
    #DOVRESTI SPECIFICARE COME SONO I DATI DI DATA
    model=Prophet(holidays=italian_holidays)
    model.fit(df.tail(365))

    fbfuture=model.make_future_dataframe(periods=PREDICTION,freq="D",include_history=False)
    forecast=model.predict(fbfuture)

    
    #NOTA IMPORTANTE: la parte sotto è stata introdotta allo scopo di mostrare il tutto sotto-forma di 15 s = 1 giorno
    date_seconds=pd.date_range(pd.Timestamp(datetime.datetime.strptime(pickle.loads(element.elements)[len(pickle.loads(element.elements))-1][1],'%Y-%m-%d %H:%M:%S'))\
                               -pd.Timedelta(f'{364*15}s'),datetime.datetime.strptime(pickle.loads(element.elements)[len(pickle.loads(element.elements))-1][1],'%Y-%m-%d %H:%M:%S')\
                                ,freq="15s")
    df_2=pd.DataFrame({'ds':date_seconds,'y':df['y'].tail(365)})
    #print(df_2)
    model_2=Prophet()
    model_2.fit(df=df_2)
    

    datetime_prediction=list()
    for i in range(1,PREDICTION+1):
        datetime_prediction.append(f"{datetime.datetime.strptime(pickle.loads(element.elements)[len(pickle.loads(element.elements))-1][1],'%Y-%m-%d %H:%M:%S')+ i*datetime.timedelta(seconds=15)}")
    
    forecast['ds']=datetime_prediction
    forecast.loc[forecast['yhat_lower']<0,'yhat_lower']=0
    forecast.loc[forecast['yhat_upper']>capacity,'yhat_upper']=capacity

    #print(forecast)
    #Di base si ha che la date_next_supply avviene quando si arriva al 15% delle scorte.
    #Tuttavia, siccome potrebbe accadere che la predizione non intersechi il 15%, in questo caso
    #viene considerato il primo minimo relativo.
    try:
        threshold=round(capacity*0.25)
        date_next_supply=forecast[forecast['yhat']<threshold]['ds'].head(1)
        date_next_supply=date_next_supply.values[0]
    except:
        forecast['diff']=forecast['yhat'].diff()
        forecast['diff_next']=forecast['yhat'].diff(-1)
        forecast['minimo_relativo']=(forecast['diff']<0)&(forecast['diff_next'] < 0)
        #Calcolo il minimo, tuttavia il minimo potrebbe avere un valore con virgola
        #siccome io voglio un valore intero, prendo l'intero SUPERIORE (questo perchè
        #se l'intero inferiore fosse 0, avrei problemi. Questo è un approccio cautelativo.)
        threshold=math.ceil(forecast[forecast['minimo_relativo']].iloc[0]['yhat'])
        date_next_supply=forecast[forecast['yhat']<threshold].iloc[0]['ds']
        #print(date_next_supply)

    return {'model':serialize.model_to_dict(model_2),'forecast':forecast.to_dict(orient='records'),'date_next_supply':date_next_supply,'quantity_to_deliver':capacity-threshold}

def led_timeserie(elements,capacity):
    PREDICTION=1

    #print(elements)

    df=pd.DataFrame(elements,columns=['ds','y'])
    df['ds']=pd.to_datetime(df['ds'])

    today=datetime.datetime.now().replace(microsecond=0)

    df['ds']=today-pd.to_timedelta(len(df)-df.index-1,unit='D')

    model=Prophet()
    model.fit(df.tail(365))

    fbfuture=model.make_future_dataframe(periods=PREDICTION,freq="D",include_history=False)
    forecast=model.predict(fbfuture)

    forecast.loc[forecast['yhat_lower']<0,'yhat_lower']=0
    forecast.loc[forecast['yhat_upper']>capacity,'yhat_upper']=capacity
    
    forecast.loc[forecast['yhat']>capacity,'yhat']=capacity
    forecast.loc[forecast['yhat']<0,'yhat']=0
    
    return forecast


def generate_predictions_long(today, MAX_CAPACITY, target_value=None):
    dates = pd.date_range(pd.Timestamp(today) - pd.Timedelta('365D'), datetime.datetime.now(), freq="D")

    VARIANZA_WEEK = 0.3
    VARIANZA_MONTH = 0.2
    MEDIA = 1

    days = pd.Series({'monday': round(MAX_CAPACITY - MAX_CAPACITY * 0.8), 
                      'tuesday': round(MAX_CAPACITY - MAX_CAPACITY * 0.8), 
                      'wednesday': round(MAX_CAPACITY),
                      'thursday': round(MAX_CAPACITY - MAX_CAPACITY * 0.10), 
                      'friday': round(MAX_CAPACITY - MAX_CAPACITY * 0.3), 
                      'saturday': round(MAX_CAPACITY - MAX_CAPACITY * 0.5), 
                      'sunday': round(MAX_CAPACITY - MAX_CAPACITY * 0.7)})

    weeks = pd.Series({week: np.random.normal(MEDIA, VARIANZA_WEEK) for week in range(0, 5)})   
    months = pd.Series({month: np.random.normal(MEDIA, VARIANZA_MONTH) for month in range(0, 12)})

    data = list()
    for month in months:
        for week in weeks:
            for day in days:
                data.append(round(day * week * month))
    data = data[:365]

    results = pd.DataFrame({'ds': dates[:365], 'y': data})
    results.loc[results['y'] < 0, 'y'] = 0
    results.loc[results['y'] > MAX_CAPACITY, 'y'] = MAX_CAPACITY

    if target_value is not None:
        current_value = results['y'].iloc[-1]

        while current_value != target_value:   
            last_date = results['ds'].iloc[-1] + pd.Timedelta('1D')
            #print(f"Questa e\' last_date: {last_date}")
            week = np.random.normal(MEDIA, VARIANZA_WEEK)
            month = np.random.normal(MEDIA, VARIANZA_MONTH)
            day_of_week = last_date.day_name().lower()
            new_value = round(days[day_of_week] * week * month)
            
            if new_value < 0:
                new_value = 0
            elif new_value > MAX_CAPACITY:
                new_value = MAX_CAPACITY

            current_value = new_value

            #print(f"Prima: {results[['ds','y']].iloc[-1]}")
            # Aggiungi nuovo valore alla serie principale, rimuovendo il primo valore per mantenere la lunghezza di 365
            results = pd.concat([results,pd.DataFrame([{'ds': last_date, 'y': new_value}])], axis=0,ignore_index=True)
            #print(f"Dopo: {results[['ds','y']].iloc[-1]}")
            if len(results) > 365:
                results = results.iloc[-365:]

        #print(len(results))
    return results

def get_interval(date):
    seconds=date.second
    if seconds < 15:
        return 0
    elif seconds < 30:
        return 15
    elif seconds < 45:
        return 30
    else:
        return 45    
    
def round_sec(date):
    date_datetime=datetime.datetime.strptime(date,'%Y-%m-%d %H:%M:%S')
    sec_modified=get_interval(date_datetime)
    return date_datetime.replace(second=sec_modified).strftime('%Y-%m-%d %H:%M:%S')

def led(self,restaurante_number,internal_code,next_date):
    #L'utente che possiede il dato ristorante in modo da poter accedere ai tutti i ristoranti
    restaurant=Restaurant.query.filter_by(number=restaurante_number).first()
    user=restaurant.users.first() 
    user_restaurant=Restaurant.query.join(User.restaurants).filter(User.id == user.id).all()

    #Ora voglio estrarre tutti gli element di tutti i ristoranti dello user che contengono lo stesso internal code
    elements=list()
    for u_restaurant in user_restaurant:
        for u_element in u_restaurant.elements.all():
            if u_element.internal_code == internal_code:
                elements.append(u_element)

    #print(user_restaurant)

    extracted_elements=[pickle.loads(_.elements) for _ in elements]

    #La capacity considerata è quella dell'ultimo elemento introdotto
    capacity=0
    for element in elements:
        for box in element.box.all():
            capacity += box.capacity

    #Una volta estratti gli elementi vado a sommare tutti i valori di elements assieme così da poter fare successivamente
    #una serie temporale. Siccome i valori allo step attuale devono ancora arrivare, si escludono quelli attuali e si considerano
    #quelli precedenti, e a partire da questi si calcola il valore tra 2 giorni.
    final=list()
    ris=dict()
    for element in extracted_elements:
        for num, date in element:
            date=datetime.datetime.strptime(date,"%Y-%m-%d %H:%M:%S")
            if datetime.datetime.strftime(date,"%Y-%m-%d %H:%M:%S") in ris:
                ris[datetime.datetime.strftime(date,"%Y-%m-%d %H:%M:%S")] += num
            else:
                ris[datetime.datetime.strftime(date,"%Y-%m-%d %H:%M:%S")] = num

    final=[(date,total) for date,total in ris.items()]
    
    final.sort(key=lambda x: datetime.datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"))

    #Questa condizione la devo mettere perchè voglio che mi aggiorni il led solo la prima volta dopo che l'arco dei 15 secondi
    #sia terminato.
    if datetime.datetime.strptime(next_date,"%Y-%m-%d %H:%M:%S") != datetime.datetime.strptime(final[-1][0],"%Y-%m-%d %H:%M:%S"):
        #print(f"{final[-1]}, {next_date}, {final[-1][0]}")
        forecast=led_timeserie(final,capacity)
        #print(f"Capacità: {capacity}. Valore predetto: {forecast['yhat']}. Valore precedente: {final[-1][1]}.")
        
        colour=None
        #Ora in base ai vari valori predetti si analizza se accendere il led quale colore
        #1) Verde: valore atteso >= 50% capacità
        #2) Arancione: valore atteso >= 20% capacità
        #3) Rosso: valore atteso < 20% capacità (l'aumento non giustifica il poter essere sicuri)
        #NOTE: questo approccio in realtà potrebbe generare problemi (di tipo psicologico - caso in cui faccio
        #una predizione ma la predizione influenza il mio modo di decidere e compio una azione che rende la forecasting
        #falsa))).
        if round(forecast['yhat'].iloc[0]) >= capacity/2:
            colour='G'
        elif round(forecast['yhat'].iloc[0]) >= (capacity*0.2):
            colour='O'
        else:
            colour='R'

        for element in elements:
            for box in element.box.all():
                self.clientMQTT.publish(f"/boxes/{box.rfid}/led",json.dumps({'led':colour}),qos=1) 

    return

def restaurant_box_insertion(self,restaurant_number,data):
    global last_publish_led

    #print(restaurant_number)
    box = Box.query.filter_by(rfid=data['rfid']).first()
    number=0
    #print(box)

    # Prendo il ristorante nel database associato all'utente avente come numero quello nell'URL
    # Nota bene: facendo così nel bridge devo mettere anche il nome dello user. Se non voglio fare questo potrei solo
    # mettere il restaurant number e andare a filtrare restaurant con quello. Questo potrei farlo perchè il numero in Restaurant è unique
    # Tuttavia, facendo così è molto facile per chiunque introdurre valori.
    restaurant = Restaurant.query.filter_by(number=restaurant_number).first()

    if restaurant is None:
        return jsonify({"message": "Restaurant number incorrect."})

    # Controllo se il box associato al dato rfid abbia lo stesso internal_code
    if box is not None and box.internal_code != data['id']:
        #Nota: eliminare box lo elimina anche in element.box
        db.session.delete(box)
        db.session.commit()
        box = None
    
    # print(box.elements)
    #Modifico i secondi in in data
    #print(f"Prima della modifica: {data['time']}")
    data['time']=round_sec(data['time'])
    print(f"Dopo la modifica: {data['time']}")

    if box is None:
        # Il box non è presente nel database
        # Vado a vedere qual'è l'ultimo numero assegnato
        if Box.query.order_by(Box.id.desc()).first() is None:
            number = 1
        else:
            number = (Box.query.order_by(Box.id.desc()).first().id)+1
        #print(f"Questo è il numero che viene introdotto in box: {number}")
        box = Box(id=number, rfid=data['rfid'], internal_code=data['id'],
                  description=data['description'], capacity=data['capacity'])

        box.elements = [(data['quantity'], data['time'])]
        box.elements = pickle.dumps(box.elements)
        db.session.add(box)
        db.session.commit()
    else:
        #print(box)
        # Una volta ottenuto devo andare ad aggiungere l'elemento della quantità
        elementi = pickle.loads(box.elements)
        elementi.append((data['quantity'], data['time']))
        box.elements = pickle.dumps(elementi)
        db.session.commit()
        
    
    # restaurant.elements.append(Element(id=2,number=2,name=data['id']))
    # Controllo se l'id aziendale è già in elements, cioè l'elemento era già stato introdotto precedentemente
    element = [i for _, i in enumerate(
        restaurant.elements.all()) if i.internal_code == data['id']]
    #print(element)
    
    if len(element) > 1:
        return jsonify({"message": "Something went wrong."})
    
    # Questo significa che esiste già element in restaurant e quindi devo solo associargli un'altro box e aggiungere i parametri
    if len(element) == 1:
        element = element[0]
        #print(element)
        element_objects = pickle.loads(element.elements)
        """
        print(f"Ti sto stampando: {pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1]}")
        print(datetime.datetime.strptime(pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1], "%Y-%m-%d %H:%M:%S"))
        print(f"Ti sto stampando l'altra parte: {datetime.datetime.strptime(element_objects[len(element_objects)-1][1], '%Y-%m-%d %H:%M:%S')}")
        """
        #print(f"Primo: {datetime.datetime.strptime(element_objects[len(element_objects)-1][1], '%Y-%m-%d %H:%M:%S') + datetime.timedelta(seconds=15)}, secondo:{datetime.datetime.strptime(pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1], '%Y-%m-%d %H:%M:%S')}")
        
        
        # Prendo l'ultimo elemento e guardo se il nuovo box arrivato è stato inviato nella finestra dei 15 secondi
        if (datetime.datetime.strptime(element_objects[len(element_objects)-1][1], '%Y-%m-%d %H:%M:%S') + datetime.timedelta(seconds=14) > datetime.datetime.strptime(pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1], "%Y-%m-%d %H:%M:%S") and not (datetime.datetime.strptime(pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1], "%Y-%m-%d %H:%M:%S") < datetime.datetime.strptime(element_objects[len(element_objects)-1][1], '%Y-%m-%d %H:%M:%S'))):
            """
            #Se l'ultima data di datetime è inferiore di quella che si vuole inserire significa che si è passati al valore successivo, inoltre controllo se la distanza
            #in secondi è di 15.
            if  (datetime.datetime.strptime(data['time'],'%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(element_objects[len(element_objects)-1][1],'%Y-%m-%d %H:%M:%S')) == datetime.timedelta(seconds=15):
                led(restaurant_number,data['id'])
            """
            #print(box.id)
            #print(element.box.all())
            #print([boxes.id for boxes in element.box])
            if not any(box.id == boxes.id for boxes in element.box):
                #Calcolo la capacità totale fino ad ora
                capacity=0
                for box in element.box.all():
                    capacity += box.capacity

                #print(f"This is the capacity: {capacity}")
                #La capacità può essere 0 se ad esempio in un ristorante ho tolto l'unico box.
                #Nel momento in cui lo ri-introduco la capacità di element è nulla perchè il box lo introduco dopo!
                if capacity == 0:
                    val=generate_predictions_long(data['time'],data['capacity'],data['quantity'])
                else:
                    print(f"Questa e\' capacity: {capacity} e data['capacity']: {data['capacity']}")
                    print(f"Questa e\' element_object: {element_objects[len(element_objects)-1][0]} e data['quantitty']: {data['quantity']}")
                    val=generate_predictions_long(data['time'],capacity+data['capacity'],element_objects[len(element_objects)-1][0]+data['quantity'])
                date_seconds=pd.date_range(pd.Timestamp(data['time'])-pd.Timedelta(f'{364*15}s'),data['time'],freq="15s")
                val['ds']=date_seconds

                #Devo aggiungere tutti i valori (anache quelli generati ad elements)
                element_objects=[(row['y'],row['ds'].strftime('%Y-%m-%d %H:%M:%S')) for index,row in val.iterrows()]
                #print(element_objects)

                pippo = Box.query.filter_by(rfid=data['rfid']).first()
                pippo.element_name = element.id
                element.elements=pickle.dumps(element_objects)
                element.box.append(pippo)
            else:
                element_objects[len(element_objects)-1] = (data['quantity']+element_objects[len(element_objects)-1][0],element_objects[len(element_objects)-1][1])
                element.elements = pickle.dumps(element_objects)
            db.session.commit()
            print(f'Sono element.box DOPO_1: {element.box.all()}')

            # print(element_objects[len(element_objects)-1][0])
        elif datetime.datetime.strptime(element_objects[len(element_objects)-1][1], '%Y-%m-%d %H:%M:%S') + datetime.timedelta(seconds=14) <= datetime.datetime.strptime(pickle.loads(box.elements)[len(pickle.loads(box.elements))-1][1], "%Y-%m-%d %H:%M:%S"):
            with lock:
                if datetime.datetime.now().second // 15 != last_publish_led:
                    last_publish_led = datetime.datetime.now().second // 15
                    #Se l'ultima data di datetime è inferiore di quella che si vuole inserire significa che si è passati al valore successivo, inoltre controllo se la distanza
                    #in secondi è di 15.
                    if  (datetime.datetime.strptime(data['time'],'%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(element_objects[len(element_objects)-1][1],'%Y-%m-%d %H:%M:%S')) > datetime.timedelta(seconds=0) and (datetime.datetime.strptime(data['time'],'%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(element_objects[len(element_objects)-1][1],'%Y-%m-%d %H:%M:%S')) <= datetime.timedelta(seconds=15):
                        #print(f"QUesto e\' il valore di data['time] prima della chiamata: {data['time']}")
                        led(self,restaurant_number,data['id'],data['time'])
        
            #print(box.id)
            #print([boxes.id for boxes in element.box])
            if not any(box.id == boxes.id for boxes in element.box):
                #Calcolo la capacità totale fino ad ora
                capacity=0
                for box in element.box.all():
                    capacity += box.capacity

                #print(f"This is the capacity: {capacity}")
                #La capacità può essere 0 se ad esempio in un ristorante ho tolto l'unico box.
                #Nel momento in cui lo ri-introduco la capacità di element è nulla perchè il box lo introduco dopo!
                if capacity == 0:
                    val=generate_predictions_long(data['time'],data['capacity'],data['quantity'])
                else:
                    val=generate_predictions_long(data['time'],capacity+data['capacity'],element_objects[len(element_objects)-1][0]+data['quantity'])

                date_seconds=pd.date_range(pd.Timestamp(data['time'])-pd.Timedelta(f'{364*15}s'),data['time'],freq="15s")
                val['ds']=date_seconds

                #Devo aggiungere tutti i valori (anache quelli generati ad elements)
                element_objects=[(row['y'],row['ds'].strftime('%Y-%m-%d %H:%M:%S')) for index,row in val.iterrows()]
                #print(element_objects)

                pippo = Box.query.filter_by(rfid=data['rfid']).first()
                print(pippo)
                pippo.element_name = element.id
                element.elements=pickle.dumps(element_objects)
                element.box.append(pippo)
            else:
                element_objects.append([data['quantity'], data['time']])
                element.elements = pickle.dumps(element_objects)
            db.session.commit()
            print(f'Sono element.box DOPO_2: {element.box.all()}')

        capacity=0
        for box in element.box.all():
            capacity += box.capacity
        
        #print(f"Questo e\' il valore di float: {float(pickle.loads(element.elements)[-1][0])}")
        #print(f"Questo e\' il valore di capacity: {capacity}")
              
        #print(f"Questo e\' il valore: {float(pickle.loads(element.elements)[-1][0]/capacity)}")
        #Genero la serie temporale solo se si sono introdotti elementi e l'incremento ha portato il rapporto tra il valore attuale e la capacità
        #totale al di sopra dell'80%.
        if pickle.loads(element.elements)[-1][0] - pickle.loads(element.elements)[-2][0] > 0 and float(pickle.loads(element.elements)[-1][0]/capacity) >= 0.8:
            #Qui vado a generare la serie temporale. Per semplificare il tutto, uso un generatore di elementi e
            #non considero quelli presenti nel database.
            element.forecasting=timeserie(element.id)
            db.session.commit()
            
            #Pubblico la data in cui il supplier deve fare 
            pacchetto={'date_next_supply':element.forecasting['date_next_supply'],'quantity_to_deliver':element.forecasting['quantity_to_deliver']}
            self.clientMQTT.publish(f"/restaurants/{restaurant_number}/elements/{element.id}/supply",json.dumps(pacchetto),qos=1) 
            
            #print(element_objects)
        #print(element_objects)
    else:
        # Vado a vedere qual'è l'ultimo numero assegnato
        if Element.query.order_by(Element.id.desc()).first() is None:
            number = 1
        else:
            number = Element.query.order_by(Element.id.desc()).first().id+1
        # l'element non esiste e quindi devo crearlo
        new_element = Element(
            id=number, internal_code=data['id'], restaurant_id=restaurant.id, description=data['description'])
        
        # Aggiungo la quantità e data in elements
        #print("sono qui")

        val=generate_predictions_long(data['time'],data['capacity'],data['quantity'])
        date_seconds=pd.date_range(pd.Timestamp(datetime.datetime.strptime(data['time'],'%Y-%m-%d %H:%M:%S'))-pd.Timedelta(f'{364*15}s'),\
                                   datetime.datetime.strptime(data['time'],'%Y-%m-%d %H:%M:%S'),freq="15s")
        val['ds']=date_seconds

        #Devo aggiungere tutti i valori (anache quelli generati ad elements)
        new_element.elements=[(row['y'],row['ds'].strftime('%Y-%m-%d %H:%M:%S')) for index,row in val.iterrows()]

        #new_element.elements = [[data['quantity'], data['time']]]
        new_element.elements = pickle.dumps(new_element.elements)
        new_element.box.append(box)
        box.element_name = new_element.id

        restaurant.elements.append(new_element)
        db.session.add(new_element)
        db.session.commit()
    
    return "Box successfully added.", 200

def restaurant_box_removal(data):
    box = Box.query.filter_by(rfid=data['rfid']).first()
    #print(box)
    if box is not None and box.internal_code == data['id']:
        element = Element.query.filter_by(id=box.element_name).first()
        if element is not None:
            #print(f"Questi sono i box in element{element.box.all()}")
            element.box.remove(box)
            db.session.commit()
            #print(f"Questi sono i box in element{element.box.all()}")
            #print(f"Questi sono i box {box}")
            return jsonify({"message": "The box has been correctly removed"})

class BridgeMQTT():
    def __init__(self,app):
        self.config=configparser.ConfigParser()
        self.config.read('config.ini')
        self.setupMQTT()
        self.app=app

    def setupMQTT(self):
        self.clientMQTT=mqtt.Client()
        self.clientMQTT.on_message=self.on_message
        self.clientMQTT.on_connect=self.on_connect
        print("Connecting to the MQTT Broker")
        self.clientMQTT.connect(
            self.config.get("MQTT","Server",fallback="localhost"),
            self.config.getint("MQTT","Port",fallback=1883),
            60
        )
        self.clientMQTT.loop_start()

    def on_connect(self,client,userdata,flags,rc):
        print("Connected with result code "+ str(rc))

        self.clientMQTT.subscribe("/restaurants/+/ingredients",qos=2)
        self.clientMQTT.subscribe("/restaurants/+/boxes/removal",qos=2)

    def on_message(self,client,userdata,message):
        #print(message.topic)
        
        print(json.loads(str(message.payload,'utf-8')))
        if message.topic.split('/')[1] == 'restaurants' and message.topic.split('/')[3] == 'ingredients':
            with self.app.app_context():
                restaurant_box_insertion(self,message.topic.split('/')[2],json.loads(str(message.payload,'utf-8')))
        if message.topic.split('/')[1] == 'restaurants' and message.topic.split('/')[3] == 'boxes' and message.topic.split('/')[4] == 'removal':
            with self.app.app_context():
                restaurant_box_removal(json.loads(str(message.payload,'utf-8')))

