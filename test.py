import requests
import csv

CSV_URL="https://docs.google.com/spreadsheets/d/1PBmdCKLuQAxGdfyrRLLD4jXIb_bjCcchcesypdbL-BA/export?format=csv&gid=0"
response = requests.get(CSV_URL)

# Check if the request was successful
if response.status_code == 200:
    # Decode the content as text
    csv_data = response.content.decode('utf-8')

    # Use csv.reader to parse the content
    csv_reader = csv.reader(csv_data.splitlines(), delimiter=',')


    # Loop through rows in the CSV
    for row in csv_reader:
        print(row)
else:
    print("Failed to retrieve the CSV file")