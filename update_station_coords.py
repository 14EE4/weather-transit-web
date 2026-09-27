import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv('SEOUL_SUBWAY_API_KEY') or 'sample'

# 1. Fetch official Seoul Station Master data
url = f'http://openapi.seoul.go.kr:8088/{key}/json/subwayStationMaster/1/1000/'
res = requests.get(url)
master_data = res.json()
rows = master_data.get('subwayStationMaster', {}).get('row', [])
print(f"Fetched {len(rows)} master records from Seoul Open API.")

# Save master data for backup/reference
os.makedirs('data', exist_ok=True)
with open('data/seoul_subway_master.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

def clean_name(name):
    # Remove parenthesized nicknames e.g., '동대문역사문화공원(DDP)' -> '동대문역사문화공원'
    n = re.sub(r'\(.*?\)', '', name).strip()
    if n.endswith('역') and len(n) > 2 and n != '서울역':
        n = n[:-1]
    return n

master_coords = {}
# Build master map: name -> (lat, lng)
for r in rows:
    raw_name = r.get('BLDN_NM', '')
    lat_str = r.get('LAT', '0')
    lng_str = r.get('LOT', '0')
    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except:
        continue
    if lat == 0 or lng == 0:
        continue
    cname = clean_name(raw_name)
    master_coords[raw_name] = (lng, lat)
    master_coords[cname] = (lng, lat)
    if not raw_name.endswith('역'):
        master_coords[raw_name + '역'] = (lng, lat)
    if not cname.endswith('역'):
        master_coords[cname + '역'] = (lng, lat)

# 2. Load user's subway stations list (from data/subway_stations.json)
with open('data/subway_stations.json', 'r', encoding='utf-8') as f:
    stations_raw = json.load(f)

# Group stations by unique station name
station_dict = {}
for item in stations_raw:
    name = item.get('STATN_NM', '').strip()
    st_id = item.get('STATN_ID', '')
    line = item.get('호선이름', '')
    
    clean_n = clean_name(name)
    display_name = clean_n if clean_n.endswith('역') else clean_n + '역'
    
    if display_name not in station_dict:
        station_dict[display_name] = {
            'id': f"sub-{st_id}",
            'name': display_name,
            'raw_name': name,
            'lines': set(),
            'zone': '수도권/서울',
            'baseCrowd': 70
        }
    station_dict[display_name]['lines'].add(line)

print(f"Total unique stations in user list: {len(station_dict)}")

# 3. Match coordinates
matched = 0
unmatched = []

for name, info in station_dict.items():
    raw_n = info['raw_name']
    c_n = clean_name(raw_n)
    
    coords = None
    for cand in [raw_n, c_n, name, c_n + '역', raw_n + '역']:
        if cand in master_coords:
            coords = master_coords[cand]
            break
            
    if coords:
        info['coords'] = [round(coords[0], 6), round(coords[1], 6)]
        matched += 1
    else:
        unmatched.append((name, raw_n, list(info['lines'])))

print(f"Matched: {matched}/{len(station_dict)}")
print(f"Unmatched count: {len(unmatched)}")
if unmatched:
    print("Sample unmatched:", unmatched[:20])
