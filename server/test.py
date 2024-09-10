import requests
import datetime


"""
URL="http://127.0.0.1:80/users/mattia/restaurants/1/box-insertion"

data={"rfid" : "lalspd", "id" : "AX8L0", "description": "Patate", "quantity":4,"capacity":5,"time":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

response=requests.post(URL,json=data)

print(response.content)

"""

URL="http://127.0.0.1:80/users/mattia/restaurants/2/box-removal"

data={"rfid" : "a787584c", "id" : "AX8L0"}

response=requests.post(URL,json=data)

print(response.content)


