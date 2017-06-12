# monitorEquipment 0.1:
# This program allows the operator to read the NFC hex id from Rowan 
# issued student ID and lookup the hex number in the College of 
# Engineering maintained database (google sheet). The program enables 
# access to the machine by turning providing 3.3V logic level signals
# that can be used to drive a relay or some other electronic controll.
# 
# 11 June 2017
# Karl Dyer - dyerk@rowan.edu
#
# Change Log


# LIBRARIES
# --------------
# Import libraries used within program.
import sys
import binascii
from time import ctime

import ntplib
import RPi.GPIO as GPIO
import gspread
import Adafruit_PN532 as PN532

from oauth2client.service_account import ServiceAccountCredentials


# CONSTANTS
# --------------
# Constants only to be changed if new database is used.
GDOCS_OAUTH_JSON = "EquipmentAccess-c43781dcec19.json"
GDOCS_SPREADSHEET_NAME = "Equipment Access List"
WORKSHEET_ACCESS_NAME = "AY2017-18"
WORKSHEET_ACCESS_COLUMN_COUNT = 13

# Constants used within the program
CARD_TYPE_INVALID = -1
CARD_TYPE_USER = 0
CARD_TYPE_UNKNOWN = 1

# Column numbers in the access list for each certification
COL_CERT_UNIVERSITY = 8
COL_CERT_COLLEGE = 9
COL_CERT_DEPARTMENT = 10
COL_CERT_MILL = 11
COL_CERT_LATHE = 12
COL_CERT_WATERJET = 13

# Change variables to match equipment being locked out
MACHINE_NAME = 'Mill 1'
MACHINE_COL = COL_CERT_MILL

# GPIO Pin numbers of led connections
LED_GREEN = 17
LED_YELLOW = 27
LED_RED = 22
RELAY1 = 4


# FUNCTIONS
# --------------
# Read hex id from NFC card - stalls program until card is detected.
def read_nfc_blocking():
    nfchex = None
    while nfchex == None:
        nfchex = pn532.read_passive_target()
    return binascii.hexlify(nfchex)

# Stalls program until no card is present in front of card reader.
def wait_for_card_removal():
    while pn532.read_passive_target() != None:
        continue

# Check database for NFC hex id and return whether card is registered.
def process_card(nfchex): 
    if AccessList is None:
        return CARD_TYPE_INVALID

    try:
        cell = AccessList.find(str(nfchex))
        return CARD_TYPE_USER
    except:
        return CARD_TYPE_UNKNOWN

# Grant access to database worksheet using OAuth key in json file.
def login_open_sheet(oauth_key_file, spreadsheet, sheet):
    try:
        scope = 'https://spreadsheets.google.com/feeds'
        creds = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file, scope)
        gc = gspread.authorize(creds)
        AccessList = gc.open(spreadsheet).worksheet(sheet)
        return AccessList
    except Exception as ex:
        print('Unable to login and get spreadsheet. Check OAuth credentials, spreadsheet name, and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        sys.exit(1)

# Set LED status indicators and control pin driving relay		
def set_machine_state(state):
    if state == 'enabled':
        GPIO.output(LED_GREEN,GPIO.HIGH)
        GPIO.output(RELAY1,GPIO.HIGH)
        GPIO.output(LED_YELLOW,GPIO.LOW)
        GPIO.output(LED_RED,GPIO.LOW)
    elif state == 'timeout':
        GPIO.output(LED_GREEN,GPIO.LOW)
        GPIO.output(LED_YELLOW,GPIO.HIGH)
        GPIO.output(RELAY1,GPIO.HIGH)
        GPIO.output(LED_RED,GPIO.LOW)
    elif state == 'disabled':
        GPIO.output(LED_GREEN,GPIO.LOW)
        GPIO.output(LED_YELLOW,GPIO.LOW)
        GPIO.output(LED_RED,GPIO.HIGH)
        GPIO.output(RELAY1,GPIO.LOW)
    else:
        GPIO.output(LED_GREEN,GPIO.LOW)
        GPIO.output(LED_YELLOW,GPIO.LOW)
        GPIO.output(LED_RED,GPIO.LOW)
        GPIO.output(RELAY1,GPIO.LOW)
        

# BOARD CONFIGURATION
# ------------------------
# SPI pin declarations for a Raspberry Pi
CS = 18
MOSI = 23
MISO = 24
SCLK = 25

# Create instances of PN532 object and begin communications reporting back version
pn532 = PN532.PN532(cs=CS, sclk=SCLK, mosi=MOSI, miso=MISO)
pn532.begin()
ic, ver, rev, support = pn532.get_firmware_version()
print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))

# Configure PN532 to communicate with MiFare cards.
pn532.SAM_configuration()

# Setup access to NTP clock server
clock = ntplib.NTPClient()

# Configure GPIO pins on the pi.
GPIO.setup([LED_GREEN, LED_YELLOW, LED_RED, RELAY1], GPIO.OUT)
#GPIO.setmode(GPIO.BOARD)


# PROGRAM
# ------------
# Initialize program variables.
AccessList = None

# Main script to setup card then loop to detect cards and interperet.
while True:
    # Read NFC from Rowan ID card
    set_machine_state('disabled')
    print('Insert Rowan ID card to enable ' + MACHINE_NAME + '\n')
    uidhex = read_nfc_blocking()    
    
    # Gain access to database and machine log then look up card to see if valid
    if AccessList is None:
        AccessList = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, WORKSHEET_ACCESS_NAME)
        MachineLog = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, 'Mill1 - Log')
    status = process_card(uidhex)
    
    # Choose action based on status of card in database
    if status == CARD_TYPE_USER:
        userRow = AccessList.find(str(uidhex)).row
        userData = AccessList.row_values(userRow)   
        print('User: {0} {1}'.format(userData[3], userData[2]))
        
        # Log user start into machine log
        timestamp = clock.request('north-america.pool.ntp.org',version=3)
        row = MachineLog.row_count
        MachineLog.resize(rows=row+1, cols=6)
        MachineLog.update_acell('A'+str(row+1), str(userData[1]))
        MachineLog.update_acell('B'+str(row+1), str(userData[3] + ' ' + userData[2]))
        MachineLog.update_acell('C'+str(row+1), str(ctime(timestamp.tx_time)))        
        
        # Check users training and grant access if allowed
        if userData[MACHINE_COL] == '1':
            print(MACHINE_NAME + ' Enabled\nRemove card when done.')
            set_machine_state('enabled')
            
            # Wait for user to log out then complete machine log
            wait_for_card_removal()
            timestamp = clock.request('north-america.pool.ntp.org',version=3)
            MachineLog.update_acell('D'+str(row+1), str(ctime(timestamp.tx_time)))
        else:
            print('Certification not current')
        
    elif status == CARD_TYPE_UNKNOWN:
        print('Your card has not been registered - see technician.')
        set_machine_state('red')
    else:
        print('Error: Database could not be reached.')
        continue
    wait_for_card_removal()