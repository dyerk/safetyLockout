# safetyLockout
Rowan College of Engineering safety lockout system to restrict access to equipment with special training requirements.

# addUser:
This program allows the operator to read the NFC hex id from Rowan 
issued student ID and correlate the hex number to the studetns Banner
ID. These values are added to the College of Engineering maintained 
database (google sheet). The database is used to allow/deny students 
access to a variety of NFC locked out equipment based on status of 
training. 

# monitorEquipment:
This program allows the operator to read the NFC hex id from Rowan 
issued student ID and lookup the hex number in the College of 
Engineering maintained database (google sheet). The program enables 
access to the machine by turning providing 3.3V logic level signals
that can be used to drive a relay or some other electronic control.
