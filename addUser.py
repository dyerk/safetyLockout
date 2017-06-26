# LIBRARIES
# --------------
# Import libraries used within program.
import sys
import binascii

import gspread
import Adafruit_PN532 as PN532
import Adafruit_CharLCD as LCD

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

# GPIO pin connections using DEVICE_CONNECTION naming convention.
PN532_SSEL = 13
PN532_MOSI = 5
PN532_MISO = 12
PN532_SCLK = 6
LCD_RS = 27
LCD_EN = 22
LCD_D4 = 25
LCD_D5 = 24
LCD_D6 = 23
LCD_D7 = 18
LCD_RED = 4
LCD_GREEN = 17
LCD_BLUE = 7

# LCD constants
LCD_COLS = 20
LCD_ROWS = 4


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
def process_card(database, nfchex): 
    if database is None:
        return CARD_TYPE_INVALID

    try:
        cell = database.find(str(nfchex))
        return CARD_TYPE_USER
    except:
        return CARD_TYPE_UNKNOWN

# Grant access to database worksheet using OAuth key in json file.
def login_open_sheet(oauth_key_file, spreadsheet, sheet):
    try:
        scope = 'https://spreadsheets.google.com/feeds'
        creds = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file, scope)
        gc = gspread.authorize(creds)
        openedSheet = gc.open(spreadsheet).worksheet(sheet)
        return openedSheet
    except Exception as ex:
        print('Unable to login and get spreadsheet. Check OAuth credentials, spreadsheet name, and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        sys.exit(1)

# Prompt user and require a (y)es or (n)o response
def validate_prompt_yn(prompt):
    response = None
    while response is None:
        response = raw_input(prompt)
        if response is 'y' or response is 'n':
            break
        else:
            response = None
    return response

# Prompt user and require an integer of specified length to be returned
def validate_prompt_integer(prompt, numDigits, errorMessage='Please enter an integer'):
    response = None
    while response is None:
        response = raw_input(prompt)
        if response.isdigit() and len(response) is numDigits:
            break
        else:
            print(errorMessage)
            response = None
    return response

def lcd_message(screen, background, messageText):
    if background is 'Blue':
        screen.set_color(0, 0, 1)
    elif background is 'Red':
        screen.set_color(1, 0, 0)
    elif background is 'Yellow':
        screen.set_color(1, 1, 0)
    elif background is 'Green':
        screen.set_color(0, 1, 0)
    else:
        screen.set_color(1, 1, 1) #White
    screen.clear()
    screen.message(messageText)
    
    
# HARDWARE SETUP
# -----------------
# Create instances of LCD object and begin communications
lcd = LCD.Adafruit_CharLCD(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, 
                           LCD_D7, LCD_COLS, LCD_ROWS, LCD_RED, LCD_GREEN, LCD_BLUE)

# Create instances of PN532 object and begin communications reporting back version
pn532 = PN532.PN532(cs=PN532_SSEL, sclk=PN532_SCLK, mosi=PN532_MOSI, miso=PN532_MISO)
pn532.begin()
ic, ver, rev, support = pn532.get_firmware_version()
tempMessage = ('Found PN532\nFirmware version: {0}.{1}'.format(ver, rev))
print(tempMessage)
lcd_message(lcd,'Blue',tempMessage)

# Configure PN532 to communicate with MiFare cards.
pn532.SAM_configuration()


# PROGRAM
# ------------
# Initialize program variables.
accessList = None       # spreadsheet with list of users and access rights

# Main script to setup card then loop to detect cards and interperet.
while True:
    # Read NFC from Rowan ID card
    print('\nWaiting for MiFare card...')
    lcd_message(lcd,'Green','Waiting for ID Card')
    uidhex = read_nfc_blocking()    
    print('Card scanned has UID: {0}\n'.format(uidhex))
    
    # Gain access to database and look up card to see if valid
    if accessList is None:
        accessList = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, WORKSHEET_ACCESS_NAME)
    status = process_card(accessList, uidhex) 
    
    # Choose action based on status of card in database
    if status == CARD_TYPE_USER:
        print('Card {0} is already in system.'.format(uidhex))
        userRow = accessList.find(str(uidhex)).row   
    elif status == CARD_TYPE_UNKNOWN:
        addNewCard = validate_prompt_yn('Card is not in system. Do you want to add your card now (y/n): ')
        if addNewCard is 'y':
            bannerId = validate_prompt_integer('Banner ID: ', 9, 'Valid Banner ID must contain 9 digits')
            # Add card hex number and banner ID to database
            row = accessList.row_count
            accessList.resize(rows=row+1, cols=WORKSHEET_ACCESS_COLUMN_COUNT)
            accessList.update_acell('A'+str(row+1), str(uidhex))
            accessList.update_acell('B'+str(row+1), str(bannerId))
            userRow = accessList.find(str(uidhex)).row
            print('Card {0} has been added to the system.'.format(uidhex))        
        elif addNewCard is 'n':
            # Prompt for card removal and wait until no card is detected
            print('\nPlease remove your ID.\n')
            wait_for_card_removal()
            continue
    else:
        print('Error: Database could not be reached.')
        continue
        
    # Report card information back to user       
    userData = accessList.row_values(userRow)
    if '#N/A' in userData: 
        print('''ID card NFC hex code and banner ID have been affiliated, but user data 
has not been added to the master user list. Please contact Karl Dyer to 
complete user data.''')
    else:
        print('Registered to {0} {1} ({2}) of {3}\nEmail Contact: {4}'.format(userData[3], userData[2], userData[1], userData[5], userData[4]))
    
    # Prompt for card removal and wait until no card is detected
    print('\nPlease remove your ID.\n')
    wait_for_card_removal()
