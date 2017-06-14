# LIBRARIES
# --------------
# Import libraries used within program.
import sys
import binascii

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

# Constants used within program
CARD_TYPE_INVALID = -1
CARD_TYPE_USER = 0
CARD_TYPE_UNKNOWN = 1


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

# Prompt user and require a (y)es or (n)o response
def validate_prompt_yn(prompt):
    response = None
    while response == None:
        response = raw_input(prompt)
        if response is 'y' or response is 'n':
            break
        else:
            response = None
    return response

# Prompt user and require an integer of specified length to be returned
def validate_prompt_integer(prompt,numDigits, errorMessage='Please enter an integer'):
    response = None
    while response == None:
        response = raw_input(prompt)
        if response.isdigit() and len(response) == numDigits:
            break
        else:
            print(errorMessage)
            response = None
    return response


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


# PROGRAM
# ------------
# Initialize program variables.
AccessList = None

# Main script to setup card then loop to detect cards and interperet.
while True:
    # Read NFC from Rowan ID card
    print('\nWaiting for MiFare card...')
    uidhex = read_nfc_blocking()    
    print('Card scanned has UID: {0}\n'.format(uidhex))
    
    # Gain access to database and look up card to see if valid
    if AccessList is None:
        AccessList = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, WORKSHEET_ACCESS_NAME)
    status = process_card(uidhex) 
    
    # Choose action based on status of card in database
    if status == CARD_TYPE_USER:
        print('Card {0} is already in system.'.format(uidhex))
        userRow = AccessList.find(str(uidhex)).row   
    elif status == CARD_TYPE_UNKNOWN:
        addNewCard = validate_prompt_yn('Card is not in system. Do you want to add your card now (y/n): ')
        if addNewCard is 'y':
            bannerId = validate_prompt_integer('Banner ID: ', 9, 'Valid Banner ID must contain 9 digits')
            # Add card hex number and banner ID to database
            row = AccessList.row_count
            AccessList.resize(rows=row+1, cols=WORKSHEET_ACCESS_COLUMN_COUNT)
            AccessList.update_acell('A'+str(row+1), str(uidhex))
            AccessList.update_acell('B'+str(row+1), str(bannerId))
            userRow = AccessList.find(str(uidhex)).row
            print('Card {0} has been added to the system.'.format(uidhex))        
        elif addNewCard is 'n':
            continue
    else:
        print('Error: Database could not be reached.')
        continue
        
    # Report card information back to user       
    userData = AccessList.row_values(userRow)
    if '#N/A' in userData: 
        print('''ID card NFC hex code and banner ID have been affiliated, but user data
              has not been added to the master user list. Please contact Karl Dyer to 
              complete user data.''')
    else:
        print('Registered to {0} {1} ({2}) of {3}\nEmail Contact: {4}'.format(userData[3], userData[2], userData[1], userData[5], userData[4]))
    
    # Prompt for card removal and wait until no card is detected
    print('\nPlease remove your ID.\n')
    wait_for_card_removal()
