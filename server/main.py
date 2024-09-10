from flask import Flask,render_template
from flask_swagger_ui import get_swaggerui_blueprint
from config.config import Config
from utils.extensions import db
from website.auth.auth import auth
from website.users.users import users
from website.restaurants.restaurants import restaurants
from website.elements.elements import elements
from website.boxes.boxes import boxes
from api.api.api import api
from mqtt import BridgeMQTT

SWAGGER_URL='/api/docs'
API_URL= '/static/swagger.json'

appname = "Magazzino pesi"
app = Flask(appname)
configurazione = Config()
app.config.from_object(configurazione)

MQTT=BridgeMQTT(app)

db.init_app(app)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL,API_URL,config={'app_name': "Magazzino pesi"})
app.register_blueprint(swaggerui_blueprint,url_prefix=SWAGGER_URL)

app.register_blueprint(auth,url_prefix="")
app.register_blueprint(api,url_prefix="/api")
app.register_blueprint(users,url_prefix="/users")
app.register_blueprint(restaurants,url_prefix="/users/<name_id>/restaurants")
app.register_blueprint(elements,url_prefix="/users/<name_id>/restaurants/<restaurant_number>/elements")
app.register_blueprint(boxes,url_prefix="/users/<name_id>/restaurants/<restaurant_number>/elements/<element_id>/boxes")

@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html"), 404

if __name__ == "__main__":
    """
    with app.app_context():
        db.drop_all()

    if True:
        with app.app_context():
            db.create_all()
    """
    port = 80
    interface = '0.0.0.0'

    app.run(host=interface, port=port)