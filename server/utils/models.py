from utils.extensions import db

user_restaurant_association = db.Table('user_restaurant_association',
                                       db.Column('user_id', db.String(
                                           50), db.ForeignKey('user.id')),
                                       db.Column('restaurant_id',
                                                 db.String(50), db.ForeignKey('restaurant.id')))


class User(db.Model):
    """ 
        La classe User descrive un utente. 
        L'utente è identificato da un id univoco (tipo matricola).
        Presenta un nome ed una password che sarebbero quelle usate per iscriversi.
        Il ruolo identifica che ruolo l'utente possiede. Ne possiamo avere 3:
            1) Admin
            2) Ristoratore
            3) Fornitore
    """
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(50))
    restaurants = db.relationship(
        'Restaurant', secondary=user_restaurant_association, backref=db.backref('users', lazy='dynamic'))


class Restaurant(db.Model):
    """
        La classe Restaurant descrive il ristorante.
        Questa presenta i seguenti attributi:
            1) p_iva è la chiave primaria
            2) nome: indica il nome del locale
            3) elementi rappresenta una foreign key 
    """
    id = db.Column(db.String(50), primary_key=True)
    number=db.Column(db.Integer,unique=True,nullable=True)
    p_iva = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    latitudine = db.Column(db.Float)
    longitudine = db.Column(db.Float)
    elements = db.relationship('Element', backref='restaurant', lazy='dynamic')


class Element(db.Model):
    """
        La classe Element descrive un oggetto.
        Questo presenta i seguenti attributi:
            1) id: questo serve per identificare l'oggetto. 
                   E' il numero
            2) internal_code: descrive il nome dell'oggetto
                nell'azienda/ristorante. (si suppone che lo stesso internal_code sia usato
                per più aziende/ristoranti dello stesso user)
            3) elements: contiene una coppia (<numero elemento>,<data di inserimento>)
            4) description:contiene una descrizione dell'element
            5) forecasting: contiene una quadrupla (<model>,<forecasting>,<quantity_to_deliver>,<date_next_supply>)
            6) restaurant_id: identifica il ristorante a cui è associato
            7) box: identifica i box a cui è associato
    """
    id = db.Column(db.Integer, unique=True,primary_key=True)
    internal_code = db.Column(db.String(50))
    elements=db.Column(db.PickleType, default=[])
    description=db.Column(db.String(50))
    forecasting=db.Column(db.JSON)
    restaurant_id = db.Column(db.String(50), db.ForeignKey('restaurant.id'))
    box = db.relationship('Box', backref='element', lazy='dynamic')


class Box(db.Model):
    """
        La classe Scatola mi dice il numero di elementi che ci sono all'interno
        della scatola attualemente.
        Questa presenta i seguenti attributi:
            1) id: identifica la scatola in modo univoco
            2) rfid: contiene l'rfid associato alla scatola
            3) internal_code: contiene l'id aziendale dell'elemento
            4) name: contiene il nome dell'elemento che sta contenendo
            5) elements: contiene una coppia (<numero elementi>,<data di inserimento>)
            6) element_name: mi dice il numero dell'elemento che sta contenendo
    """
    id = db.Column(db.Integer, primary_key=True)
    rfid=db.Column(db.String(50),unique=True)
    internal_code=db.Column(db.String(50))
    description=db.Column(db.String(50))
    capacity=db.Column(db.Integer,nullable=False)
    elements = db.Column(db.PickleType, default=[])
    element_name = db.Column(db.Integer, db.ForeignKey('element.id'))
    