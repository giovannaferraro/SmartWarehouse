from flask import Blueprint, redirect, render_template,jsonify, request, session, url_for
from access import token_required
from geopy.geocoders import Nominatim
from geopy.adapters import URLLibAdapter
from utils.models import *
import ssl

users=Blueprint("users",__name__)
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

@users.route("/<name_id>")
@token_required
def user_page(current_user,name_id):
    return render_template("name.html",user=current_user)

@users.route("/<name_id>/profile",methods=['GET','POST','DELETE'])
@token_required
def profile(current_user,name_id):
    if request.method=='POST':
        #Questo è qualora venga eseguito il Sign Out
        session['token']=None
        return redirect(url_for('auth.login'))
    if request.method=='DELETE':
        #Questo viene eseguito qualora venga eseguito l'eliminazione dell'account
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
        session['token']=None
        return jsonify({'redirect':'/login'})
    # Devo fare una distinzione
    # Se sono un fornitore posso togliere il ristorante ma non lo toglie dal database
    # Se sono un ristoratore invece toglie tutte le informazioni del ristorante e a catena tutto il resto
    # QUESTO SIGNIFICA CHE SU CARTA A SUA VOLTA TUTTI I SUPPLIER DOVREBBERO PERDERE LE INFORMAZIONI DEL RISTORANTE!
    location=from_coordinates_to_address(current_user)
    return render_template("profile.html",user=current_user,locations=location)