
class Config:
    #Introduco le caratteristiche generali di flask
    SECRET_KEY= b'smartwarehouse'

    SQLALCHEMY_DATABASE_URI = "sqlite:///application.sqlite"
    SQLALCHEMY_TRACK_MODIFICATIONS=False