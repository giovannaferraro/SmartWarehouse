from flask import Blueprint, jsonify, render_template
from access import token_required
from utils.models import Box, Element

import plotly.graph_objs as pg
import pickle

boxes=Blueprint("boxes",__name__)

@boxes.route('/')
@token_required
def boxes_in(current_user,name_id,restaurant_number,element_id):
    elements=Element.query.filter_by(id=element_id).first()
    return render_template("boxes.html",user=current_user.name, boxes=elements.box.all())

@boxes.route('/<box_id>')
@token_required
def box(current_user,name_id,restaurant_number,element_id,box_id):
    box=Box.query.filter_by(id=box_id).first()
    #Estraggo gli elementi da element
    elements_in_box=pickle.loads(box.elements)
    if len(elements_in_box) < 50:
        elements_in_box=elements_in_box[-len(elements_in_box):]
    else:
        elements_in_box=elements_in_box[-50:]
    x=list()
    y=list()
    for j in elements_in_box:
        x.append(j[1])
        y.append(j[0])
    
    chart=pg.Figure(data=pg.Scatter(x=x,y=y))
    chart.update_layout(title="Quantity over time", xaxis_title="Time", yaxis_title="Quantity")
    plot_div=chart.to_html(full_html=False)
    return render_template("box.html", user=current_user, restaurant_number=restaurant_number, element_id=element_id,box=box,chart=plot_div)