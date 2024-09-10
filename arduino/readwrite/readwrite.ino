#include <SPI.h>      //include the SPI library
#include <MFRC522.h>  //include the MFRC522 RFID reader library
#define RST_PIN 9  //reset pin, which can be changed to another digital pin if needed.
#define SS_PIN 10  //SS or the slave select pin, which can be changed to another digital pin if needed.
MFRC522 mfrc522(SS_PIN, RST_PIN);  // create a MFRC522 instant.
MFRC522::MIFARE_Key key;          //create a MIFARE_Key struct named 'key' to hold the card information
byte data1[14] = {"Patate"};  //Il primo dato che viene scritto nel tag rappresenta la descrizione dell'elemento nella scatola.
byte data2[14] = {"104"};  //Il secondo dato che viene scritto nel tag rappresenta il peso del singolo elemento nella scatola.
byte data3[14] = {"AX8L0"};;  //Il terzo dato che viene scritto nel tag rappresenta il codice interno aziendale dell'elemento nella scatola
byte data4[14] = {"3"};;  //Il quarto dato che viene scritto nel tag rappresenta la capacità della scatola

byte readbackblock[18];  //Array for reading out a block.
String oggetto="";
String peso="";
String internal_id="";
String capacita="";

void setup()
{
  Serial.begin(9600);        // Initialize serial communications with the PC
  SPI.begin();               // Init SPI bus
  mfrc522.PCD_Init();        // Init MFRC522 card (in case you wonder what PCD means: proximity coupling device)
  Serial.println("Scan a MIFARE Classic card");
  for (byte i = 0; i < 6; i++)
  {
    key.keyByte[i] = 0xFF;  // Prepare the security key for the read and write operations.
  }
}
void loop()
{
  // Look for new cards if not found rerun the loop function
  if ( ! mfrc522.PICC_IsNewCardPresent()) {
    return;
  }
  // read from the card if not found rerun the loop function
  if ( ! mfrc522.PICC_ReadCardSerial())
  {
    return;
  }
  Serial.println("card detected. Writing data");
  writeBlock(4, data1); //write data1 to the block 1 of the tag
  writeBlock(5, data2); //write data2 to the block 2 of the tag
  writeBlock(6, data3); //write data3 to the block 3 of the tag
  writeBlock(8, data4); //write data3 to the block 4 of the tag
  Serial.println("reading data from the tag");
  readBlock(4, readbackblock);   //read block 1
  //print data

  Serial.print("read block 4: ");
  for (int j = 0 ; j < 14 ; j++)
  {
    oggetto += readbackblock[j] <0x10 ? "0" : "";
    oggetto += String(readbackblock[j], HEX);
  }

  short int val=50;
  Serial.println(oggetto);
  Serial.write(0x1);
  Serial.println(map(1, 1,1, 1, 1));
   
  readBlock(5, readbackblock);  //read block 2
  //print data
  Serial.print("read block 5: ");
  for (int j = 0 ; j < 5 ; j++)
  {
    peso += readbackblock[j] < 0x10 ? "0" : "";
    peso += String(readbackblock[j], HEX);
  }
  Serial.println(peso);
  //mfrc522.PICC_DumpToSerial(&(mfrc522.uid));//uncomment below line if want to see the entire memory dump.

  readBlock(6, readbackblock);  //read block 3
  Serial.print("read block 6: ");
  for (int j = 0 ; j < 14 ; j++)
  {
    internal_id += readbackblock[j] <0x10 ? "0" : "";
    internal_id += String(readbackblock[j], HEX);
  }
  Serial.println(internal_id);

  readBlock(8, readbackblock);  //read block 2
  //print data
  Serial.print("read block 8: ");
  for (int j = 0 ; j < 5 ; j++)
  {
    capacita += readbackblock[j] < 0x10 ? "0" : "";
    capacita += String(readbackblock[j], HEX);
  }
  Serial.println(capacita);
}
//Write specific block
int writeBlock(int blockNumber, byte arrayAddress[])
{
  //check if the block number corresponds to data block or triler block, rtuen with error if it's trailer block.
  int largestModulo4Number = blockNumber / 4 * 4;
  int trailerBlock = largestModulo4Number + 3; //determine trailer block for the sector
  if (blockNumber > 2 && (blockNumber + 1) % 4 == 0) {
    Serial.print(blockNumber);
    Serial.println(" is a trailer block: Error");
    return 2;
  }
  //authentication
  byte status = mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, trailerBlock, &key, &(mfrc522.uid));
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Authentication failed: ");
    Serial.println(mfrc522.GetStatusCodeName(status));
    return 3;//return "3" as error message
  }
  //writing data to the block
  status = mfrc522.MIFARE_Write(blockNumber, arrayAddress, 16);
  //status = mfrc522.MIFARE_Write(9, value1Block, 16);
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Data write failed: ");
    Serial.println(mfrc522.GetStatusCodeName(status));
    return 4;//return "4" as error message
  }
  Serial.print("Data written to block ");
  Serial.println(blockNumber);
}
//Read specific block
int readBlock(int blockNumber, byte arrayAddress[])
{
  int largestModulo4Number = blockNumber / 4 * 4;
  int trailerBlock = largestModulo4Number + 3; //determine trailer block for the sector
  //authentication of the desired block for access
  byte status = mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, trailerBlock, &key, &(mfrc522.uid));
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Authentication failed : ");
    Serial.println(mfrc522.GetStatusCodeName(status));
    return 3;//return "3" as error message
  }
  //reading data from the block
  byte buffersize = 18;
  status = mfrc522.MIFARE_Read(blockNumber, arrayAddress, &buffersize);//&buffersize is a pointer to the buffersize variable; MIFARE_Read requires a pointer instead of just a number
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Data read failed: ");
    Serial.println(mfrc522.GetStatusCodeName(status));
    return 4;//return "4" as error message
  }
  Serial.println("Data read successfully");
}
