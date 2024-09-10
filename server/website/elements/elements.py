from flask import Blueprint, render_template
from access import token_required
from utils.models import *
from geopy.geocoders import Nominatim
from geopy.adapters import URLLibAdapter
import plotly.graph_objs as pg
import pandas as pd
import pickle
import numpy as np
from prophet import plot, serialize
import ssl

elements = Blueprint("elements", __name__)
ctx = ssl.create_default_context()
ctx.check_hostname=False
ctx.verify_mode=ssl.CERT_NONE
geolocator = Nominatim(user_agent="Applicazione",ssl_context=ctx,adapter_factory=URLLibAdapter)

@elements.route('/')
@token_required
def elements_in(current_user, name_id, restaurant_number):
    restaurant=[x for x in current_user.restaurants if x.number == int(
        restaurant_number)][0]
    return render_template("elements.html", user=current_user, restaurant=restaurant,elements=restaurant.elements)


@elements.route('/<element_id>')
@token_required
def element(current_user, name_id, restaurant_number, element_id):
    element=Element.query.filter_by(id=element_id).first()
    #Estraggo gli elementi da element
    elements_in_element=pickle.loads(element.elements)
    if len(elements_in_element) < 50:
        elements_in_element=elements_in_element[-len(elements_in_element):]
    else:
        elements_in_element=elements_in_element[-50:]
    x=list()
    y=list()
    for j in elements_in_element:
        x.append(j[1])
        y.append(j[0])
    chart=pg.Figure(data=pg.Scatter(x=x,y=y))
    chart.update_layout(title="Quantity over time", xaxis_title="Time", yaxis_title="Quantity")
    plot_div=chart.to_html(full_html=False)
    return render_template("element.html", user=current_user, restaurant_number=restaurant_number, element_id=element_id,element=element,chart=plot_div)
    
def draw_threshold_line(ax,threshold_date):
    ymin,ymax=ax.get_ylim()
    ax.vlines(threshold_date,ymin,ymax,linestyles="dashed",colors="r")
    ax.text(threshold_date,ymax,"Soglia={}".format(3),ha="center",va="bottom",color="r")

@elements.route('/<element_id>/timeserie')
@token_required
def timeseries(current_user, name_id, restaurant_number, element_id):
    element=Element.query.filter_by(id=element_id).first()

    capacity=0
    for box in element.box.all():
        capacity += box.capacity

    fig=plot.plot_plotly(serialize.model_from_dict(element.forecasting['model']),pd.DataFrame.from_dict(element.forecasting['forecast']))

    fig.update_layout(title="Timeserie prediction",xaxis_title="Time",yaxis_title="Quantity")
    fig.add_hline(y=-(element.forecasting['quantity_to_deliver']-capacity),line_color="red",line_dash="dash",annotation_text="Supply Threshold",annotation_position="top left")
    timeserie=fig.to_html()
    
    return render_template("timeseries.html",user=current_user.name,timeserie=timeserie)
