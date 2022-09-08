import requests
from datetime import datetime 
from urllib.parse import urlencode
import time

# replace with your user info bellow
# and in command line, run `python dps_check_availability.py`
email = 'xxxx@gmail.com'
first_name = 'John'
last_name = 'Doe'
date_of_birth = 'MM/DD/YYYY'
last4ssn = '0000'
zipcode = '78750'
type_id = 71 # service type id, 71 for new driver's license
distance = 10 # How far from the zipcode. unit in miles

check_interval = 60 # in seconds, check every 60 seconds.

data = {'TypeId': type_id, 'ZipCode': zipcode, 'CityName': '', 'PreferredDay': '0'}
credential = {'FirstName': first_name, 'LastName': last_name, 'DateOfBirth': date_of_birth, 'Last4Ssn': last4ssn}
headers = {
  "Host": "publicapi.txdpsscheduler.com",
  "Connection": "keep-alive",
  "Content-Length": "62",
  "sec-ch-ua": "' Not A;Brand';v='99', 'Chromium';v='99', 'Google Chrome';v='99'",
  "Accept": "application/json, text/plain, */*",
  "Content-Type": "application/json;charset=UTF-8",
  "sec-ch-ua-mobile": "?0",
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
  "sec-ch-ua-platform": "macOS",
  "Origin": "https://public.txdpsscheduler.com",
  "Sec-Fetch-Site": "same-site",
  "Sec-Fetch-Mode": "cors",
  "Sec-Fetch-Dest": "empty",
  "Referer": "https://public.txdpsscheduler.com/",
  "Accept-Encoding": "gzip, deflate, br",
  "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"
}

# default cur appointment date
cur_date = datetime.now()
cur_appointment_date = datetime(cur_date.year + 1, cur_date.month, cur_date.day)

# login
print("loging in....")
try:
  payload = {
    'DateOfBirth': date_of_birth,
    'FirstName': first_name,
    'LastName': last_name,
    'LastFourDigitsSsn': last4ssn,
  }
  res = requests.post(url='https://publicapi.txdpsscheduler.com/api/Eligibility', data=str(payload), headers=headers)
  responseId = res.json()[0]['ResponseId']
  print("Login succeed (%s)..." % responseId)
  res = requests.post(url='https://publicapi.txdpsscheduler.com/api/Booking', data=str(payload), headers=headers)
  appointments = res.json()
  if not appointments:
    print("No existing appointment found.")
  else:
    print("Existing appointment dates: %s" % appointments[0]['BookingDateTime'])
    cur_appointment_date = datetime.strptime(appointments[0]['BookingDateTime'][:10], "%Y-%m-%d")
except requests.exceptions.HTTPError as e:
  print('login failed.', e.response.text)

rescheduled = False

def checkAvailability():
  global rescheduled
  global cur_appointment_date
  global distance
  # get available locations
  res = requests.post('https://publicapi.txdpsscheduler.com/api/AvailableLocation', data=str(data), headers=headers)
  locations = res.json()
  if not type(locations)==list:
    print("[Error] failed to request available locations.")
    return
  locations.sort(key=lambda l:datetime.strptime(l['NextAvailableDate'], '%m/%d/%Y'))
  # filter out locations that are too distant.
  locations = [location for location in locations if location['Distance'] < distance]

  # refresh current appointment
  if rescheduled:
    print("Fetching current appointment...")
    payload = {
      'DateOfBirth': date_of_birth,
      'FirstName': first_name,
      'LastName': last_name,
      'LastFourDigitsSsn': last4ssn,
    }
    res = requests.post(url='https://publicapi.txdpsscheduler.com/api/Booking', data=str(payload), headers=headers)
    appointments = res.json()
    if not appointments:
      print("No existing appointment found.")
    else:
      print("Existing appointment dates: %s" % appointments[0]['BookingDateTime'])
      cur_appointment_date = datetime.strptime(appointments[0]['BookingDateTime'][:10], "%Y-%m-%d")

  # check for available dates
  for location in locations:
    next_available_date = datetime.strptime(location['NextAvailableDate'], '%m/%d/%Y')
    if next_available_date < cur_appointment_date:
      print("Ealier available date found in %s (%s miles) at %s" % (location['Name'], location['Distance'], location['NextAvailableDate']))
      availability = location['Availability']
      if not availability:
        print("Fetching availability...")
        payload = {'TypeId': type_id, 'LocationId': location['Id']}
        res = requests.post(url='https://publicapi.txdpsscheduler.com/api/AvailableLocationDates', data=str(payload), headers=headers)
        availability = res.json()
      if availability['LocationAvailabilityDates']:
        time_slots = availability['LocationAvailabilityDates'][0]['AvailableTimeSlots']
        if len(time_slots) > 0:
          selected_slot_id = time_slots[-1]['SlotId'] # choose the last time slot
          scheduled_time = time_slots[-1]['StartDateTime']
          # hold slot
          print("Holding your slots(%s) at %s." % (selected_slot_id, scheduled_time))
          payload = {**credential, "SlotId": selected_slot_id}
          res = requests.post(url='https://publicapi.txdpsscheduler.com/api/HoldSlot', data=str(payload), headers=headers)
          print('Hold status:', res.json()['SlotHeldSuccessfully'])
          if res.json()['SlotHeldSuccessfully']:
            print("Rescheduling...")
            payload = {
              **credential,
              'Email': email,
              'ServiceTypeId': type_id,
              'BookingDateTime': scheduled_time,
              'BookingDuration': time_slots[-1]['Duration'],
              'SpanishLanguage': 'N',
              'SiteId': location['Id'],
              'ResponseId': responseId,
              'CardNumber': '',
              'CellPhone': '',
              'HomePhone': '',
            }
            try:
              res = requests.post(url='https://publicapi.txdpsscheduler.com/api/RescheduleBooking', data=str(payload), headers=headers)
              rescheduled = True
              print("Reschedule succeed, check your email for appointment details.")
              break
            except requests.exceptions.HTTPError as e:
              print('Reschedule failed.', e.response.text)
          else:
            print("Hold slots failed.")

  if not rescheduled:
    print("No ealier date found.")


def startChecking():
  lookup_cnt = 0
  while True:
    print("Start checking:", lookup_cnt)
    checkAvailability()
    lookup_cnt += 1
    time.sleep(check_interval)

startChecking()
  
