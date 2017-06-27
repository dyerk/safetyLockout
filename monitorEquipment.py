# LIBRARIES
# --------------
# Import libraries used within program.
import os
import sys
import time
import binascii
import picamera

import RPi.GPIO as GPIO
import gspread
import Adafruit_PN532 as PN532
import Adafruit_CharLCD as LCD

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials


# CONSTANTS
# --------------
# Constants only to be changed if new database is used.
GDOCS_OAUTH_JSON = "EquipmentAccess-c43781dcec19.json"
GDOCS_SPREADSHEET_NAME = "Equipment Access List"
WORKSHEET_ACCESS_NAME = "AY2017-18"
WORKSHEET_ACCESS_COLUMN_COUNT = 13

# Column numbers in the database for each certification
COL_CERT_UNIVERSITY = 8
COL_CERT_COLLEGE = 9
COL_CERT_DEPARTMENT = 10
COL_CERT_MILL = 11
COL_CERT_LATHE = 12
COL_CERT_WATERJET = 13

# Constants only to be changed if images are to be stored in different Google Drive.
DRIVE_OAUTH_JSON = "DriveAccess.json"
DRIVE_CREDENTIALS = "driveCredentials.txt"
DRIVE_SAVE_FOLDER_ID = "0BzZSztlM2pZYaWUwVmZ1LUo5dFE"

# Constants used within the program
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
RELAY1 = 9

# LCD constants
LCD_COLS = 20
LCD_ROWS = 4


# EQUIPMENT SPECIFIC
# ******************* MUST CHANGE ****************************
# Change these constants to reflect equpiment being monitored.
WORKSHEET_MACHINE_LOG = 'Mill1 - Log'
MACHINE_NAME = 'Mill 1'
MACHINE_COL = COL_CERT_MILL
# ******************* MUST CHANGE ****************************


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

# Grant access to google drive using OAuth key in json file.        
def login_drive(credentials_file):
    try:
        gauth = GoogleAuth()
        # Try to load saved client credentials
        gauth.LoadCredentialsFile(credentials_file)
        if gauth.credentials is None:
            # Authenticate if they're not there
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # Refresh them if expired
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()
        # Save the current credentials to a file
        gauth.SaveCredentialsFile(credentials_file)
        openedDrive = GoogleDrive(gauth)
        return openedDrive
    except Exception as ex:
        print('Unable to login and get spreadsheet. Check OAuth credentials, spreadsheet name, and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        sys.exit(1)
        
# Set control pin driving relay		
def set_machine_state(state):
    if state == 'enabled':
        GPIO.output(RELAY1,GPIO.HIGH)
    elif state == 'timeout':
        GPIO.output(RELAY1,GPIO.HIGH)
    elif state == 'disabled':
        GPIO.output(RELAY1,GPIO.LOW)
    else:
        GPIO.output(RELAY1,GPIO.LOW)
        
# Upload a file from the local machine to a Google Drive and return the new Google file id.
def upload_file(local_filename, save_as_filename, drive, drive_folder_id):
    fileToUpload = drive.CreateFile({"title":[save_as_filename], "parents":[{"kind":"drive#fileLink", "id":drive_folder_id}]})
    fileToUpload.SetContentFile(local_filename)
    fileToUpload.Upload()
    return fileToUpload['id']

def lcd_message(screen, background, messageText):
    if background is 'Blue':
        screen.set_color(0, 0, 1)
    elif background is 'Red':
        screen.set_color(1, 0, 0)
    elif background is 'Yellow':
        screen.set_color(1, 1, 0)
    elif background is 'Green':
        screen.set_color(0, 1, 0)
    elif background is 'White':
        screen.set_color(1, 1, 1)
    else:
        screen.set_color(1, 1, 1)
    screen.clear()
    screen.message(messageText)
    os.system('clear')
    print(messageText)
    
    
# HARDWARE SETUP
# -----------------
# Create instances of LCD object and begin communications
lcd = LCD.Adafruit_RGBCharLCD(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, 
                           LCD_D7, LCD_COLS, LCD_ROWS, LCD_RED, LCD_GREEN, LCD_BLUE)

# Create instances of PN532 object and begin communications reporting back version
pn532 = PN532.PN532(cs=PN532_SSEL, sclk=PN532_SCLK, mosi=PN532_MOSI, miso=PN532_MISO)
pn532.begin()
ic, ver, rev, support = pn532.get_firmware_version()
tempMessage = ('Found PN532\nFirmware version {0}.{1}'.format(ver, rev))
lcd_message(lcd,'Yellow',tempMessage)
time.sleep(3)

# Configure PN532 to communicate with MiFare cards.
pn532.SAM_configuration()

# Configure GPIO pins on the pi.
GPIO.setup([RELAY1], GPIO.OUT)

# Setup clock
# os.environ['TZ'] = 'EST5EDT'
# time.tzset()

# Camera Setup    
try:
    camera = picamera.PiCamera()
except Exception as ex:
    camear = None
    lcd_message(lcd,'Yellow','Camera not enabled.\n-Check connections\n-Check RasPi Config')
    time.sleep(3)
    print('Error Details: ', ex)
        
imageFilename = 'testimage.jpg'

# PROGRAM
# ------------
# Initialize program variables.
accessList = None       # spreadsheet with list of users and access rights
machineLog = None       # spreadsheet to log machine usage 
imageDrive = None       # drive on which to store machine usage images

# Main script to setup card then loop to detect cards and interperet.
while True:
    # Read NFC from Rowan ID card
    set_machine_state('disabled')
    lcd_message(lcd,'Red',(MACHINE_NAME + ': Disabled\n\nInsert Rowan ID\nto enable ' + MACHINE_NAME))
    uidhex = read_nfc_blocking()    
        
    # Gain access to drive
    if imageDrive is None:
        imageDrive = login_drive(DRIVE_CREDENTIALS)
    
    # Gain access to database and machine log then look up card to see if valid
    if accessList is None:
        accessList = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, WORKSHEET_ACCESS_NAME)
        machineLog = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME, 'Mill1 - Log')
    status = process_card(accessList, uidhex)
    
    # Choose action based on status of card in database
    if status == CARD_TYPE_USER:
        userRow = accessList.find(str(uidhex)).row
        userData = accessList.row_values(userRow)   
        #print('User: {0} {1}'.format(userData[3], userData[2]))
        tempMessage = ('User: {0} {1}\n'.format(userData[3], userData[2]))
        
        # Log user start into machine log
        #timestamp = clock.request('north-america.pool.ntp.org',version=3)
        row = machineLog.row_count
        timestamp = time.strftime('%x %X %Z')
        machineLog.resize(rows=row+1, cols=6)
        machineLog.update_acell('A'+str(row+1), str(userData[1]))
        machineLog.update_acell('B'+str(row+1), str(userData[3] + ' ' + userData[2]))
        machineLog.update_acell('C'+str(row+1), str(timestamp))
        if camera is not None:
            camera.capture(imageFilename)
            uploadId = upload_file(imageFilename, MACHINE_NAME + ' ' + timestamp, imageDrive, DRIVE_SAVE_FOLDER_ID)
            machineLog.update_acell('E'+str(row+1), str('https://drive.google.com/open?id='+uploadId))
        
        # Check users training and grant access if allowed
        if userData[MACHINE_COL] == '1':
            tempMessage = (MACHINE_NAME + ': Enabled\n' + tempMessage + '\nRemove ID when done.')
            lcd_message(lcd,'Green',tempMessage)
            set_machine_state('enabled')
            
            # Wait for user to log out then complete machine log
            wait_for_card_removal()
            #timestamp = clock.request('north-america.pool.ntp.org',version=3)
            machineLog.update_acell('D'+str(row+1), str(time.strftime('%x %X %Z')))
            if camera is not None:
                camera.capture(imageFilename)
                uploadId = upload_file(imageFilename, MACHINE_NAME + ' ' + timestamp, imageDrive, DRIVE_SAVE_FOLDER_ID)
                machineLog.update_acell('F'+str(row+1), str('https://drive.google.com/open?id='+uploadId))
        else:
            tempMessage = (MACHINE_NAME + ': Disabled\n' + tempMessage + '\nCertification not current')
            lcd_message(lcd,'Red',tempMessage)
            set_machine_state('disabled')
            
    elif status == CARD_TYPE_UNKNOWN:
        lcd_message(lcd,'Red','Card Error\nID is not registered.\nSee technician for help.')
        set_machine_state('disabled')
    else:
        lcd_message(lcd,'Red','Error: \nDatabase could not be reached.\nSee technician for help')
        continue
    wait_for_card_removal()
