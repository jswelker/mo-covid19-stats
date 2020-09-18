import csv
import datetime
from io import StringIO
import json
import os
import urllib.parse

import requests

# Read census data to a dictionary
census_data = {}
with open('data/census_data.csv', 'r') as f:
    csv_text = f.read()
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        census_data[row["CTYNAME"]] = int(row["POPESTIMATE"])
statewide_total_population = sum(census_data.values())

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
    print(date)
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

        county_name = row.get("Admin2")
    
        # Skip "Unassigned" county and "Kansas City" county (which is part of Jackson)
        if county_name == "Unassigned" or county_name == "Kansas City":
            continue
        
        # Add an entry to our data dict for this county and this date
        if county_name not in all_data:
            all_data[county_name] = {}
            
        # Get the county's population
        if county_name == "St. Louis City":
            population = census_data[f"St. Louis city"]
        else:
            population = census_data[f"{county_name} County"]
        
        # Look up the county's data for the previous day to calculate new cases and deaths
        yesterday = date - datetime.timedelta(days=1)
        yesterday_data = all_data[county_name].get(yesterday.isoformat())
                
        cases = int(row.get("Confirmed"))
        new_cases = 0
        if yesterday_data is not None and yesterday_data.get("cases") is not None:
            new_cases = cases - int(yesterday_data.get("cases"))
        deaths = int(row.get("Deaths"))
        new_deaths = 0
        if yesterday_data is not None and yesterday_data.get("deaths") is not None:
            new_deaths = deaths - int(yesterday_data.get("deaths"))
        
        # Look up the county's data for the previous 6 and 13 days
        # to calculate rolling averages and to estimate active cases
        past_6_days_data = []        
        past_13_days_data = []
        for i in range(0,13):
            past_date = date - datetime.timedelta(days=i+1)
            past_date_data = all_data[county_name].get(past_date.isoformat())
            if past_date_data:
                past_13_days_data.append(past_date_data)
                if i < 6:
                    past_6_days_data.append(past_date_data)

        # Get 7-day and 14-day totals for deaths and new cases
        past_7_new_cases = sum([past_date_data.get("new_cases") for past_date_data in past_6_days_data]) + new_cases
        past_14_new_cases = sum([past_date_data.get("new_cases") for past_date_data in past_13_days_data]) + new_cases
        past_14_new_deaths = sum([past_date_data.get("new_deaths") for past_date_data in past_13_days_data]) + new_deaths
        
        rolling_avg_new_cases = int(past_7_new_cases / 7)
        estimated_active_cases = past_14_new_cases - past_14_new_deaths
        
        all_data[county_name][date.isoformat()] = {
            "cases": cases,
            "cases_per_100k": round(100000 / population, 2) * cases,
            "new_cases": new_cases,
            "new_cases_per_100k": round(100000 / population, 2) * new_cases,
            "deaths": deaths,
            "deaths_per_100k": round(100000 / population, 2) * deaths,
            "new_deaths": new_deaths,
            "new_deaths_per_100k": round(100000 / population, 2) * new_deaths,
            "rolling_avg_new_cases": rolling_avg_new_cases,
            "rolling_avg_new_cases_per_100k": round(100000 / population, 2) * rolling_avg_new_cases,
            "estimated_active_cases": estimated_active_cases,
            "estimated_active_cases_per_100k": round(100000 / population, 2) * estimated_active_cases
        }
        
        # Add this county's data to the statewide totals for this date
        if date.isoformat() not in all_data["STATEWIDE"]:
            all_data["STATEWIDE"][date.isoformat()] = {
                "cases": 0,
                "cases_per_100k": 0,
                "new_cases": 0,
                "new_cases_per_100k": 0,
                "deaths": 0,
                "deaths_per_100k": 0,
                "new_deaths": 0,
                "new_deaths_per_100k": 0,
                "past_14_days_new_cases": 0,
                "past_14_days_new_deaths": 0,
                "past_7_days_new_cases": 0,
                "estimated_active_cases": 0,
                "estimated_active_cases_per_100k": 0,
                "rolling_avg_new_cases": 0,
                "rolling_avg_new_cases_per_100k": 0
            }
        
        all_data["STATEWIDE"][date.isoformat()]["cases"] += cases
        all_data["STATEWIDE"][date.isoformat()]["cases_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["cases"]
        all_data["STATEWIDE"][date.isoformat()]["new_cases"] += new_cases
        all_data["STATEWIDE"][date.isoformat()]["new_cases_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["new_cases"]
        all_data["STATEWIDE"][date.isoformat()]["deaths"] += deaths
        all_data["STATEWIDE"][date.isoformat()]["deaths_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["deaths"]
        all_data["STATEWIDE"][date.isoformat()]["new_deaths"] += new_deaths
        all_data["STATEWIDE"][date.isoformat()]["new_deaths_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["new_deaths"]
        all_data["STATEWIDE"][date.isoformat()]["past_14_days_new_cases"] += past_14_new_cases
        all_data["STATEWIDE"][date.isoformat()]["past_14_days_new_deaths"] += past_14_new_deaths
        all_data["STATEWIDE"][date.isoformat()]["past_7_days_new_cases"] += past_7_new_cases
        all_data["STATEWIDE"][date.isoformat()]["estimated_active_cases"] = all_data["STATEWIDE"][date.isoformat()]["past_14_days_new_cases"] - all_data["STATEWIDE"][date.isoformat()]["past_14_days_new_deaths"]
        all_data["STATEWIDE"][date.isoformat()]["estimated_active_cases_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["estimated_active_cases"]
        all_data["STATEWIDE"][date.isoformat()]["rolling_avg_new_cases"] = round(all_data["STATEWIDE"][date.isoformat()]["past_7_days_new_cases"] / 7, 2)
        all_data["STATEWIDE"][date.isoformat()]["rolling_avg_new_cases_per_100k"] = round(100000 / statewide_total_population, 2) * all_data["STATEWIDE"][date.isoformat()]["rolling_avg_new_cases"]
        
    # Move on to the next date after handling all counties for this date
    date = date + datetime.timedelta(days=1)
    
# Create a JSON file for each county in the all_data dict
for county_name in all_data:
    json_string = json.dumps(all_data[county_name])
    filename = f"data{os.path.sep}{urllib.parse.quote(county_name.replace(' ', '_'))}.json"
    with open(filename, "w") as file:
        file.write(json_string)