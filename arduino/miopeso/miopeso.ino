#include "HX711.h"
#include <math.h>
#include <MFRC522.h>

/************************************************************
  WIRING ed INIZIALIZZAZIONE DELLE VARIABILI PER LA FSM - HX711
  Qui vengono inizializzate le variabili per il sensore di peso
  e la realizzazione della sua FSM
************************************************************/
const int LOADCELL_DOUT_PIN = 2;
const int LOADCELL_SCK_PIN = 3;
HX711 scale;
//0: idle; 1: lettura; 2: serial write; 3: peso<=0.1, in attesa
int cstate = 0;
int i = 0;
float getunit;
bool update = 0;
int qta;
float tara = 2.2; //2.4 0 2,5 in base alla scatola che usi, leggi sotto, Me lo pesa come 2.3 per la scatola con 2.4 (per arduino), mentre l'altra dovrebbe essere 2.2.
float media = 0;

/************************************************************
  WIRING ED INIZIALIZZAZIONE DELLE VARIABILI PER LA FSM - MFRC522
  Qui vengono inizializzare le variabili per il sensore RFID
  e la realizzazione della sua FSM
*************************************************************/
MFRC522 rfid(10, 9);
//0: lettura disabilitata; 1: lettura abilitata;
int cstaterfid = 0;
bool flagrfid = false;
const int serialPrintInterval = 0;

/***************************************************
  INIZIALIZZAZIONE DELLE VARIABILI PER LA READ DA RFID
****************************************************/
MFRC522::MIFARE_Key key;          //create a MIFARE_Key struct named 'key' to hold the card information
byte readtypeblock[255];

byte readbackblock[25];
String uid = "";
byte sector = 1;
byte val[25];
String peso = "";       //metto la lettura della seriale
String finalpeso = "";  //stringa dove metto il peso converitito in int
int pesoint[25];        //vettore che contiene le singole cifre del numero intero
float p = 0;         //su questa variabile metto il peso totale che ho calcolato
long int j = 0;
int z = 0;
float t = 0;
long int vettoreid[4]; //vettore che conserva i numeri che compongono l'id del rfid
char identificator[100];

/********************************************************
  WIRING ED INIZIALIZZAZIONE DELLE VARIABILI PER FSM - TEMP
  Qui vengono inizializzate le variabili per il sensore di
  temperatura e la realizzazione della sua FSM
********************************************************/
int pinRed = 5; //Led RGB Rosso - forecasting
int pinGreen = 6; //Led RGB Verde - forecasting 
int pinBlue  = 7; //Led RGB Blu - forecasting
int fstate = 0;
unsigned long timestamp;

/**************************************************
  Qui ci sono variabili inizializzate per controllare
  what the heck succede nell'arduino
**************************************************/
float now = 0.0;
float then = 0.0;
int c = 0;
int c_pred = 0;
float t_count;


/************
  VARIABILI USATE
************/
int i_media = 1; /*Serve per tenere conto del numero reale di elementi che servono per calcolare la media*/
float change = 0;   /*Change serve perchè se nei 15 secondi vengono introdotti altri elementi, è in grado di modificare il numero di oggetti sulla bilancia correttamente.
                      Inoltre, viene anche usato per filtrare possibili rumori restituiti dalla bilancia. (valori più elevati rispetto alla media)
*/
int index = -2;  /*Indice che mantiene quando è avvenuto il primo cambiamento*/

String tipo = ""; /*In tipo viene introdotto il nome dell'elemento che è presente nella scatola e viene estrapolato dalla scheda dell'RFID*/
String internal_id="";  /*Il valore di internal_id indica il nome interno utilizzato dall'impresa per identificare in maniera univoca il prodotto*/
int capacita; /*Il valore di capacita indica la capacita che la scatola puo contenere*/

/************
  VARIABILI GESTIONE TEMPO
************/
static const unsigned long REFRESH_INTERVAL = 1000; //ms (1 s)
static unsigned long lastRefreshTime=0;

/************
  INIZIO CODICE
************/

void setup() {
  Serial.begin(9600);
  //inizializzo i sensori di peso
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  Serial.println("Initializing the scale");
  scale.set_scale(2280.f);
  scale.tare();
  Serial.println("Readings:");
  //ora attende che venga letto un rfid
  SPI.begin();
  rfid.PCD_Init();
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }

  //Pin-Forecasting
  pinMode(pinRed, OUTPUT); 
  pinMode(pinGreen, OUTPUT);
  pinMode(pinBlue, OUTPUT); 
}

void loop() {
  rfid.PCD_Reset();
  rfid.PCD_Init();


  if (millis() - lastRefreshTime >= REFRESH_INTERVAL){
    lastRefreshTime += REFRESH_INTERVAL;

    /***************************************************************
      Questo pezzo di codice si occupa di realizzare la FSM per l'RFID
    ***************************************************************/
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      //ho letto, incremento il contatore
      c++;
      readBlock(5, readbackblock);
      p=HEXtoDEC();
      Serial.println(p);
      readBlock(4, readtypeblock);
      tipo = TypeHEXtoDEC();
      Serial.println(tipo);
      readBlock(6, readtypeblock);
      internal_id=TypeHEXtoDEC();
      Serial.println(internal_id);
      readBlock(8,readbackblock);
      capacita=(int)HEXtoDEC();
      Serial.println(capacita);
      uid = getUID();
    }
  
    if ((c - c_pred) == 1 && (c % 2 != 0)) {
      //Serial.println("Ho letto RFID in ingresso");
      flagrfid = true;
    }
    else if ((c - c_pred) == 1 && (c % 2 == 0)) {
      //Serial.println("Ho letto RFID in uscita");
      flagrfid = false;

      digitalWrite(pinRed,LOW);
      digitalWrite(pinBlue,LOW);
      digitalWrite(pinGreen,LOW);
    }
  
    c_pred = c;
    rfid.PICC_HaltA();
  
    /****************************************************************
      Questo pezzo di codice si occupa di realizzare la FSM per i pesi
    ****************************************************************/
  
    if (flagrfid == true && cstate == 0) fstate = 1;
    if (i == 14 && cstate == 1) fstate = 2;
    if (update && cstate == 2) fstate = 1;
    if (flagrfid == false && cstate == 1) {
      fstate = 3;
      Serial.write(0xAA);
      /*************************************************
        indicazione di quale scatola si tratta
        da modificare quando lo flashi sull'altro arduino,
        da modificare con 0x02
      *************************************************/
      //rfid
      for (int q = 0; q < 4; q++) {
        Serial.write(map(vettoreid[q], 0, 255, 0, 253));
      }
  
      String IID; //Questa contiene la stringa effettiva id internal_id
                    //Affinchè il bridge sappia che questa stringa è terminata 
                    //appongo alla fine un terminatore di string
        for(unsigned int foo=0;foo < internal_id.length();foo++)
          if(internal_id[foo]!= '\0')
            IID += internal_id[foo];
        IID+='\0';
        //Internal code
        Serial.print(IID);
        Serial.write(0xAE);
    }
    if (flagrfid == true && cstate == 3) fstate = 1;
    
    cstate = fstate;
    FSM();
    
  }

   int dato;
   dato = Serial.read();
   if (dato=='G') setColour(0,255,0); //Verde
   if (dato=='O') setColour(255,69,0); //Arancione
   if (dato=='R') setColour(255,0,0); //Rosso
}

/************
  FINITE STATE MACHINE
*************/
void FSM(){
  if (cstate == 1) {
    /******************************************************
      i indica quante volte di seguito ho lo stesso risultato
    *******************************************************/
    Serial.println("entering state one...");
    //Serial.print("one reading:\t");
    getunit = scale.get_units() - tara;

    /*
      Se la media è nulla significa che è la prima misurazione
      All'interno del valore media vado a porre la somma di valori che non variano per di più di 0.4
      Se però il valore cambia di più di tale valore, viene introdotto in una variabile e servirà
      Per sapere se sono stati introdotti più oggetti
    */
    Serial.print("Il valore di I e': ");
    Serial.println(i);
    if (getunit >= 0) { /* cioe se sto misurando qualcosa*/
      if (media == 0)   /*se sto misurando qualcosa per la prima volta*/
        media = getunit;
      else if (abs((media / i_media) - getunit) <= 0.2) { /*il peso si sta mantenendo stabile 
                                                          -> è lo stesso prodotto quindi la media deve essere uguale a quanto sto misurando*/
        media += getunit;
        Serial.println("Stampo la media che sto creando: ");
        Serial.print(media / (i_media + 1));
        i_media++;
      }
      else {
        /*Se il val assoluto tra change ed il valore attuale sono <= 0.2 significa che per la seconda volta ho incontrato un valore simile
          al precedente e significa che quello visto prima non era rumore ma il numero di elementi nella bilancia è cambiato.
        */
        if (index + 1 == i && abs(change - getunit) <= 0.2) {
          media = change + getunit;
          Serial.println("Stampo il cambiamento: ");
          Serial.print(media);
          i_media = 2;
          change = 0;
          index = -2;
        }
        else {
          Serial.println("Stampo la prima volta che vedo il cambiamento: ");
          Serial.print(getunit);
          change = getunit;
          index = i;
        }
      }

      i++;
    }
    else
      /*INTRODOTTO SOLO SE LA SCATOLA VIENE ESTRATTA SENZA FAR PASSARE L'RFID.*/
      i=0;
  }

  if (cstate == 2) {
    //Serial.println("entering state two...");
    Serial.print("Manda messaggio al broker. Il numero di oggetti calcolata e: ");
    //stampa di controllo della quantità, può essere cancellata

    if (i == 0) {
      qta = round(media * 100 / p);
    }
    else {
      qta = round((media / i_media) * 100 / p);
      Serial.println(qta);
    }

    if (qta >= 0) {
      //pacchetto
      //inizio messaggio
      Serial.write(0xFF);
      for (int q = 0; q < 4; q++) {
        Serial.write(map(vettoreid[q], 0, 255, 0, 253));
      }

      String IID; //Questa contiene la stringa effettiva id internal_id
                  //Affinchè il bridge sappia che questa stringa è terminata 
                  //appongo alla fine un terminatore di string
      for(unsigned int foo=0;foo < internal_id.length();foo++)
        if(internal_id[foo]!= '\0')
          IID += internal_id[foo];
      IID+='\0';
      //Internal code
      Serial.print(IID);

      String TP;  //Questa contiene la stringa effettiva di Tipo
                  //Affinchè il bridge sappia che questa stringa è terminata 
                  //appongo alla fine un terminatore di string
      for(unsigned int foo=0;foo < tipo.length();foo++)
        if(tipo[foo]!= '\0')
          TP += tipo[foo];
      TP+='\0';
      //Descrizione
      Serial.print(TP);
      //quantità calcolata
      Serial.write(map(qta, 0, 253, 0, 253));
      //capacita calcolata
      Serial.write(map(capacita,0,253,0,253));
      //fine messaggio
      Serial.write(0xFE);
    }

    /* RIPORTANO VARIABILI PER LO STATO 1 SUCCESSIVO */
    update = true;
    i = 0;
    i_media = 1;
    media = -(tara);
  }

  if (cstate == 3) {
    //Serial.println("entering state three...");
    Serial.println("Stato di idle, sfilata la cassetta e ho peso zero");
    i = 0;
  }
  
}

/***********************************************************
  Funzione per leggere da rfid i primi due byte per blocco.
  non modificare.
***********************************************************/
int readBlock(int blockNumber, byte arrayAddress[]) {
  int largestModulo4Number = blockNumber / 4 * 4;
  int trailerBlock = largestModulo4Number + 3;  //determine trailer block for the sector
  //authentication of the desired block for access
  byte status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, trailerBlock, &key, &(rfid.uid));
  if (status != MFRC522::STATUS_OK) {
    //Serial.print("Authentication failed : ");
    //Serial.println(rfid.GetStatusCodeName(status));
    return 3;  //return "3" as error message
  }
  //reading data from the block
  byte buffersize = 18;
  status = rfid.MIFARE_Read(blockNumber, arrayAddress, &buffersize);  //&buffersize is a pointer to the buffersize variable; MIFARE_Read requires a pointer instead of just a number
  if (status != MFRC522::STATUS_OK) {
    //Serial.print("Data read failed: ");
    //Serial.println(rfid.GetStatusCodeName(status));
    return 4;  //return "4" as error message
  }
  //Serial.println("Data read successfully");
}

/*Funzione usata per trasformare un dato da HEX in ASCII*/

String hexToAscii( String hex )
{
  uint16_t len = hex.length();
  String ascii = "";
  for ( uint16_t i = 0; i < len; i += 2 )
    ascii += (char)strtol( hex.substring( i, i + 2 ).c_str(), NULL, 16 );
  return ascii;
}

/*****************************************
  Procedura per convertire da hex a decimale.
  In p ottengo il peso del singolo oggetto.
  c'è la print del peso calcolato.
*****************************************/
float HEXtoDEC() {
  String tmp="";
  //leggo quello che ho letto da seriale
  for (j = 0; j < 10; j++) {
    tmp += readbackblock[j] < 0x10 ? "0" : "";
    tmp += String(readbackblock[j], HEX);
  }
  return (float)hexToAscii(tmp).toInt();
}

/******************************************
  Procedura per estrapolare dalla card
  l'informazione del tipo di oggetto
  alla quale è associata
*******************************************/
String TypeHEXtoDEC() {
  String tmp = "";
  for (j = 0; j < 10; j++) {
    tmp += readtypeblock[j] < 0x10 ? "0" : "";
    tmp += String(readtypeblock[j], HEX);
  }
  return hexToAscii(tmp);
}
/*******************************************
  Funzione per recuperare l'UID dell'RFID
  valido come nome identificativo dell'oggetto.
  non modificare.
********************************************/
String getUID() {
  String uid = "";
  for (int i = 0; i < rfid.uid.size; i++) {
    uid += "0x";
    uid += rfid.uid.uidByte[i] < 0x10 ? "0" : "";
    uid += String(rfid.uid.uidByte[i], HEX);
    uid.toCharArray(identificator, 8);
    vettoreid[i] = strtol(identificator, NULL, 0);
    uid = "";
  }
  return uid;
}

void setColour(int redValue, int greenValue, int blueValue){
  analogWrite(pinRed,redValue);
  analogWrite(pinGreen,greenValue);
  analogWrite(pinBlue,blueValue);  
}
