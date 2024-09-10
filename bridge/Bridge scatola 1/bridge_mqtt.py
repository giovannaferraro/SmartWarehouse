#BRIDGE SCATOLA 1 COM5

import serial
import serial.tools.list_ports
import binascii
import configparser
import datetime

import paho.mqtt.client as mqtt
import json


class Bridge():
    def __init__(self):
        self.config=configparser.ConfigParser()
        self.config.read('config.ini')
        self.setupSerial()
        self.setupMQTT()
        self.subscribed=False

    def setupSerial(self):
        self.ser=None
        self.inbuffer=[]

        if self.config.get("Serial","UseDescription",fallback=False):
            self.portname = self.config.get("Serial","PortName", fallback="COM1")
        else:
            print("list of available ports:")
            ports = serial.tools.list_ports.comports()

            for port in ports:
                #print (port.device)
                #print (port.description)
                if self.config.get("Serial","PortDescription", fallback="arduino").lower() \
						in port.description.lower():
                    self.portname = port.device
        
        try:
            if self.portname is not None:
                print("Connect to: "+self.portname)
                self.ser=serial.Serial(self.portname,9600,timeout=0)
        except:
            self.ser=None
            print("Fail connecting.")

    def setupMQTT(self):
        self.clientMQTT=mqtt.Client()
        self.clientMQTT.on_message=self.on_message
        self.clientMQTT.on_connect=self.on_connect

        print("I\'m connecting to the MQTT Broker.")
        self.clientMQTT.connect(
            self.config.get("MQTT","Server",fallback="localhost"),
            self.config.getint("MQTT","Port",fallback=1883),
            60
        )

        self.clientMQTT.loop_start()

    def on_connect(self,client,userdata,flags,rc):
        global once
        
        print("Connected with result code "+ str(rc))

        if rc==0:
            self.subscribed=False

    def loop(self):
        lastchar=None
        while(True):
            if not self.ser is None:
                if self.ser.in_waiting>0:
                    # data available from the serial port
                    lastchar=self.ser.read(1)
                    #print(lastchar)
                    self.inbuffer.append(lastchar)

                if lastchar==b'\n':
                    #print("Stringa")
                    #print(self.inbuffer[ser])
                    #print("\nUltimo elemento e' acapo")
                    self.useData()
                    self.inbuffer=list()
                    lastchar=None

                #QUI DEVO DIFFERENZIARE I PACCHETTI CHE POSSO RICEVERE E LO FACCIO TRAMITE L'ULTIMO CHAR
                if lastchar==b'\xfe': #EOL
                    print("\nValue received")
                    self.useData()
                    self.inbuffer=list()
                    lastchar=None

                if lastchar==b'\xae':
                    print("Eliminazione")
                    self.useData()
                    self.inbuffer=list()
                    lastchar=None
    
    def useData(self):
        if len(self.inbuffer)<3:
            return False
        
        #Controllo se il pacchetto è effettivamente composto da 0xff all'inizio
        #e prima avevo controllato finisse con 0xfe o 0xae
        if self.inbuffer[0] != b'\xff' and not self.inbuffer[0].isalpha() and self.inbuffer[0] != b'\xAA':
            return False
        
        #Il valore che è stato inviato è una stringa
        if self.inbuffer[0].isalpha():
            print(''.join([x.decode('utf-8') for x in self.inbuffer[:-1] if x != '\n']))
        
        #Paccheto per invio dati
        if self.inbuffer[0] == b'\xff':
            pacchetto=dict()
            pacchetto['rfid']=""

            self.inbuffer.pop(0)
            for i in range(1,5):
                pacchetto['rfid']+= binascii.hexlify(self.inbuffer[i]).decode('ascii')
                self.inbuffer.pop(0)
            
            eliminate=0
            pacchetto['id']=""
            for i in self.inbuffer:
                if i== b'\x00':
                    eliminate+=1
                    break
                #print(i)
                pacchetto['id']+=i.decode('ascii')
                eliminate+=1

            #print(self.inbuffer)
            for i in range(eliminate):
                self.inbuffer.pop(0)

            #print(self.inbuffer)

            eliminate=0
            pacchetto['description']=""
            for i in self.inbuffer:
                if i == b'\x00':
                    eliminate+=1
                    break
                pacchetto['description']+=i.decode('ascii')
                eliminate+=1
            for i in range(eliminate):
                self.inbuffer.pop(0)

            #print(self.inbuffer)
            pacchetto['quantity']=int.from_bytes(self.inbuffer[0],byteorder='little')
            self.inbuffer.pop(0)
            pacchetto['capacity']=int.from_bytes(self.inbuffer[0],byteorder='little')
            pacchetto['time']=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(pacchetto)

            if not self.subscribed:
                self.clientMQTT.subscribe(f"/boxes/{pacchetto['rfid']}/led",qos=1)
                self.subscribed=True

            self.clientMQTT.publish(f'/restaurants/{self.config.get("Restaurant","id")}/ingredients',json.dumps(pacchetto),qos=2)
            #response=requests.post(self.URL+"/box-insertion",json=pacchetto)
            #print(response.content)

        if(self.inbuffer[0] == b'\xaa'):
            pacchetto=dict()

            self.inbuffer.pop(0)
            pacchetto['rfid']=""
            for i in range(1,5):
                pacchetto['rfid'] += binascii.hexlify(self.inbuffer[i]).decode('ascii')
                self.inbuffer.pop(0)
            
            eliminate=0
            pacchetto['id']=""
            for i in self.inbuffer:
                if i==b'\x00':
                    eliminate+=1
                    break
                pacchetto['id']+=i.decode('ascii')
                eliminate+=1
            for i in range(eliminate):
                self.inbuffer.pop(0)
            
            print(pacchetto)

            self.clientMQTT.unsubscribe(f"/boxes/{pacchetto['rfid']}/led")
            self.subscribed=False
            self.clientMQTT.publish(f'/restaurants/{self.config.get("Restaurant","id")}/boxes/removal',json.dumps(pacchetto),qos=2)
            #response=requests.post(self.URL+"/box-removal",json=pacchetto)
            #print(response.content)

    def on_message(self,client,userdata,message):    
        print(json.loads(str(message.payload,'utf-8')))
        message=json.loads(str(message.payload,'utf-8'))
        if message['led'] == 'G':
            self.ser.write(b'G')
        elif message['led'] == 'O':
            self.ser.write(b'O')
        else:
            self.ser.write(b'R')

if __name__=='__main__':
    br=Bridge()
    br.loop()