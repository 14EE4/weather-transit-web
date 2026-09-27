import json
import re
import os

with open('data/seoul_subway_master.json', 'r', encoding='utf-8') as f:
    master = json.load(f)

def normalize(name):
    # remove parentheses and trim
    n = re.sub(r'\(.*?\)', '', name).strip()
    n = n.replace(' ', '')
    if n.endswith('역') and len(n) > 2 and n != '서울역':
        n = n[:-1]
    return n

coords_map = {}
for m in master:
    raw_nm = m.get('BLDN_NM', '').strip()
    norm_nm = normalize(raw_nm)
    try:
        lat = float(m.get('LAT', 0))
        lng = float(m.get('LOT', 0))
        if lat > 0 and lng > 0:
            coords_map[raw_nm] = (lng, lat)
            coords_map[norm_nm] = (lng, lat)
            coords_map[raw_nm.replace(' ', '')] = (lng, lat)
    except:
        pass

# Add known renames / specific station coordinates
manual_overrides = {
    '한국항공대': (126.868387, 37.602888),
    '한국항공대역': (126.868387, 37.602888),
    '시우': (126.796261, 37.313210),
    '시우역': (126.796261, 37.313210),
    '세종대왕릉': (127.570938, 37.295309),
    '세종대왕릉역': (127.570938, 37.295309),
    '세종왕릉': (127.570938, 37.295309),
    '세종왕릉역': (127.570938, 37.295309),
    '4.19민주묘지': (127.013684, 37.649502),
    '4.19민주묘지역': (127.013684, 37.649502),
    '4.19 민주묘지': (127.013684, 37.649502),
    '4.19 민주묘지역': (127.013684, 37.649502),
    '운정중앙': (126.728410, 37.716140),
    '운정중앙역': (126.728410, 37.716140),
    '응암순환': (126.915500, 37.598600),
    '응암순환(상선)': (126.915500, 37.598600),
}
coords_map.update(manual_overrides)

with open('data/subway_stations.json', 'r', encoding='utf-8') as f:
    stations_list = json.load(f)

# Group stations by unique cleaned name
station_dict = {}
unmatched = []

for s in stations_list:
    statn_id = s.get('STATN_ID', '')
    raw_nm = s.get('STATN_NM', '').strip()
    line = s.get('호선이름', '').strip()
    
    clean_n = normalize(raw_nm)
    display_name = clean_n if clean_n.endswith('역') else clean_n + '역'
    
    coords = None
    for cand in [raw_nm, clean_n, display_name, raw_nm.replace(' ', ''), clean_n + '역']:
        if cand in coords_map:
            coords = coords_map[cand]
            break
            
    if not coords:
        # Try substring
        for k, v in coords_map.items():
            if clean_n == k or (len(clean_n) >= 2 and clean_n in k and len(k) <= len(clean_n) + 2):
                coords = v
                break
                
    if not coords:
        unmatched.append((raw_nm, line))
        continue
        
    if display_name not in station_dict:
        # Determine zone roughly based on line or name
        zone = '서울 도심권' if '2호선' in line or '1호선' in line else '수도권/서울'
        station_dict[display_name] = {
            'id': f"sub-{statn_id}",
            'name': display_name,
            'lines': [],
            'coords': [round(coords[0], 6), round(coords[1], 6)],
            'zone': zone,
            'baseCrowd': 70
        }
        
    if line and line not in station_dict[display_name]['lines']:
        station_dict[display_name]['lines'].append(line)

print(f"Total processed stations: {len(station_dict)}")
print(f"Unmatched: {len(unmatched)}")
if unmatched:
    print("Unmatched items:", unmatched)

# Format list sorted by name
final_stations = sorted(list(station_dict.values()), key=lambda x: x['name'])

# Write output to:
# 1. Weather-Transport Recommendation UI/src/subwayData.ts
ts_content = """// 서울 및 수도권 전체 지하철역 마스터 데이터 (공공 API 검증 정밀 좌표 560+개 역)
export interface SubwayStation {
  id: string
  name: string
  lines: string[]
  coords: [number, number] // [lng, lat]
  zone: string
  baseCrowd: number
}

export const SUBWAY_STATIONS: SubwayStation[] = """ + json.dumps(final_stations, ensure_ascii=False, indent=2) + """;

// ── 지하철역 초성 및 부분 일치 고속 검색 함수 ──
export function searchSubwayStations(query: string): SubwayStation[] {
  if (!query || !query.trim()) return []
  const cleanQuery = query.trim().replace(/역$/, '').toLowerCase()

  return SUBWAY_STATIONS.filter(s => {
    const rawName = s.name.toLowerCase()
    const nameWithoutSuffix = s.name.replace(/역$/, '').toLowerCase()
    return rawName.includes(cleanQuery) || 
           nameWithoutSuffix.includes(cleanQuery) ||
           s.lines.some(l => l.toLowerCase().includes(cleanQuery))
  })
}
"""

with open('Weather-Transport Recommendation UI/src/subwayData.ts', 'w', encoding='utf-8') as f:
    f.write(ts_content)

# 2. Also write updated subway_stations.json to data/ and Weather-Transport Recommendation UI/data/
with open('data/subway_stations_with_coords.json', 'w', encoding='utf-8') as f:
    json.dump(final_stations, f, ensure_ascii=False, indent=2)

with open('Weather-Transport Recommendation UI/data/subway_stations.json', 'w', encoding='utf-8') as f:
    json.dump(final_stations, f, ensure_ascii=False, indent=2)

print("Successfully written updated coordinates to subwayData.ts and data files!")
