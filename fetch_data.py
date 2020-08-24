import csv
import datetime
from io import StringIO
import json
import os
import urllib.parse

import requests

# Create a dict for holding all the data for all counties and for the whole state aggregate
# {
#   "Johnson": {
#       "2020-01-22": {...}
#       "2020-01-23": {...}
#   }
#   "STATEWIDE": {
#       "2020-01-22": {...}
#       "2020-01-23": {...}   
#   }
# }
all_data = {}
all_data["STATEWIDE"] = {}

# Set the URL template used to fetch data for each date
url_template = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/[[mm]]-[[dd]]-[[yyyy]].csv"

# County-level data at https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_daily_reports
# begins on 2020-03-22.
date = datetime.date(year=2020,month=3,day=22)

# Loop through every date and fetch the CSV data until we reach a date
# that gives us a 404 error
while True:
    # Get the CSV text for this date
    yyyy = date.strftime("%Y")
    mm = date.strftime("%m")
    dd  = date.strftime("%d")
    url = url_template.replace("[[yyyy]]", yyyy).replace("[[mm]]", mm).replace("[[dd]]", dd)
    response = requests.get(url)
    if response.status_code != 200:
        break
    csv_text = response.text
    
    # Parse text into a CSV object
    reader = csv.DictReader(StringIO(csv_text))
    
    # Go through each line in the CSV, skipping any lines where "Province_State" is not "Missouri"
    for row in reader:
        if row.get("Province_State") != "Missouri":
            continue
        
        # Add an entry to our data dict for this county and this date
        county_name = row.get("Admin2")
        if county_name not in all_data:
            all_data[county_name] = {}
            
        # Look up the county's date for the previous day to calculate new cases and deaths
        yesterday = date - datetime.timedelta(days=1)
        yesterday_data = all_data[county_name].get(yesterday.isoformat())
        
        cases = int(row.get("Confirmed"))
        new_cases = 0
        if yesterday_data and yesterday_data.get("cases"):
            new_cases = cases - int(yesterday_data.get("cases"))
        active_cases = int(row.get("Active"))
        deaths = int(row.get("Deaths"))
        new_deaths = 0
        if yesterday_data and yesterday_data.get("deaths"):
            new_deaths = deaths - int(yesterday_data.get("deaths"))
        
        all_data[county_name][date.isoformat()] = {
            "cases": cases,
            "new_cases": new_cases,
            "active_cases": active_cases,
            "deaths": deaths,
            "new_deaths": new_deaths
        }
        
        # Add this county's data to the statewide totals for this date
        if date.isoformat() not in all_data["STATEWIDE"]:
            all_data["STATEWIDE"][date.isoformat()] = {
                "cases": 0,
                "new_cases": 0,
                "active_cases": 0,
                "deaths": 0,
                "new_deaths": 0
            }
        if isinstance(cases, str) or isinstance(all_data["STATEWIDE"][date.isoformat()]["cases"], str):
            breakpoint()
        all_data["STATEWIDE"][date.isoformat()]["cases"] += cases
        all_data["STATEWIDE"][date.isoformat()]["new_cases"] += new_cases
        all_data["STATEWIDE"][date.isoformat()]["active_cases"] += active_cases
        all_data["STATEWIDE"][date.isoformat()]["deaths"] += deaths
        all_data["STATEWIDE"][date.isoformat()]["new_deaths"] += new_deaths
        
    # Move on to the next date after handling all counties for this date
    date = date + datetime.timedelta(days=1)
    
# Create a JSON file for each county in the all_data dict
for county_name in all_data:
    json_string = json.dumps(all_data[county_name])
    filename = "data" + os.path.sep + urllib.parse.quote(county_name) + ".json"
    with open(filename, "w") as file:
        file.write(json_string)