import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load Master stations for Incheon 1 & 2
with open('data/seoul_subway_master.json', encoding='utf-8') as f:
    master = json.load(f)

incheon1_raw = sorted([s for s in master if s.get('ROUTE') == '인천1호선'], key=lambda x: int(x.get('BLDN_ID', 0)))
incheon2_raw = sorted([s for s in master if s.get('ROUTE') == '인천2호선'], key=lambda x: int(x.get('BLDN_ID', 0)))

def clean_station_name(raw_name):
    n = re.sub(r'\(.*?\)', '', raw_name).strip()
    return n if n.endswith('역') else n + '역'

incheon1_names = [clean_station_name(s['BLDN_NM']) for s in incheon1_raw]
incheon2_names = [clean_station_name(s['BLDN_NM']) for s in incheon2_raw]

print("Incheon 1 sequence:", incheon1_names)
print("Incheon 2 sequence:", incheon2_names)

# 2. Update subwayData.ts
data_path = 'Weather-Transport Recommendation UI/src/subwayData.ts'
with open(data_path, encoding='utf-8') as f:
    data_content = f.read()

m = re.search(r'export const SUBWAY_STATIONS: SubwayStation\[\] = (\[.*?\]);\n\n// ── 지하철역 초성', data_content, re.DOTALL)
if not m:
    print("Failed to find SUBWAY_STATIONS in subwayData.ts")
    sys.exit(1)

stations = json.loads(m.group(1))
station_map = {s['name']: s for s in stations}

# Update existing transfer stations
transfer_updates = {
    '계양역': '인천1호선',
    '부평구청역': '인천1호선',
    '부평역': '인천1호선',
    '원인재역': '인천1호선',
    '검암역': '인천2호선',
    '석남역': '인천2호선',
    '주안역': '인천2호선',
}

for name, line in transfer_updates.items():
    if name in station_map:
        if line not in station_map[name]['lines']:
            station_map[name]['lines'].append(line)
            print(f"Updated {name} lines -> {station_map[name]['lines']}")

# Add new stations for Incheon 1
added_count = 0
for s in incheon1_raw:
    name = clean_station_name(s['BLDN_NM'])
    if name not in station_map:
        new_st = {
            'id': f"sub-{s['BLDN_ID']}",
            'name': name,
            'lines': ['인천1호선'],
            'coords': [round(float(s['LOT']), 6), round(float(s['LAT']), 6)],
            'zone': '수도권/인천',
            'baseCrowd': 50
        }
        stations.append(new_st)
        station_map[name] = new_st
        added_count += 1

# Add new stations for Incheon 2
for s in incheon2_raw:
    name = clean_station_name(s['BLDN_NM'])
    if name in station_map:
        if '인천2호선' not in station_map[name]['lines']:
            station_map[name]['lines'].append('인천2호선')
    else:
        new_st = {
            'id': f"sub-{s['BLDN_ID']}",
            'name': name,
            'lines': ['인천2호선'],
            'coords': [round(float(s['LOT']), 6), round(float(s['LAT']), 6)],
            'zone': '수도권/인천',
            'baseCrowd': 50
        }
        stations.append(new_st)
        station_map[name] = new_st
        added_count += 1

print(f"Added {added_count} new stations. Total stations: {len(stations)}")

# Sort stations by name or id for consistency
stations.sort(key=lambda x: x['name'])

# Rebuild subwayData.ts content
new_stations_json = json.dumps(stations, ensure_ascii=False, indent=2)
prefix = data_content[:m.start(1)]
suffix = data_content[m.end(1):]
new_data_content = prefix + new_stations_json + suffix

with open(data_path, 'w', encoding='utf-8') as f:
    f.write(new_data_content)
print("Successfully updated subwayData.ts!")

# 3. Update subwayGraph.ts
graph_path = 'Weather-Transport Recommendation UI/src/subwayGraph.ts'
with open(graph_path, encoding='utf-8') as f:
    graph_content = f.read()

gm = re.search(r'export const SUBWAY_GRAPH: Record<string, string\[\]> = ({.*?});\n\nexport interface RouteStep', graph_content, re.DOTALL)
if not gm:
    # Try with \r\n
    gm = re.search(r'export const SUBWAY_GRAPH: Record<string, string\[\]> = ({.*?});\r?\n\r?\nexport interface RouteStep', graph_content, re.DOTALL)
if not gm:
    print("Failed to find SUBWAY_GRAPH in subwayGraph.ts")
    sys.exit(1)

subway_graph = json.loads(gm.group(1))
# Convert lists to sets for easy updating
graph_sets = {k: set(v) for k, v in subway_graph.items()}

def add_edge(u, v):
    if u not in graph_sets:
        graph_sets[u] = set()
    if v not in graph_sets:
        graph_sets[v] = set()
    graph_sets[u].add(v)
    graph_sets[v].add(u)

# Add Incheon 1 edges
for i in range(len(incheon1_names) - 1):
    u = incheon1_names[i]
    v = incheon1_names[i + 1]
    add_edge(u, v)

# Add Incheon 2 edges
for i in range(len(incheon2_names) - 1):
    u = incheon2_names[i]
    v = incheon2_names[i + 1]
    add_edge(u, v)

# Convert sets back to sorted lists
updated_graph = {k: sorted(list(graph_sets[k])) for k in sorted(graph_sets.keys())}
print(f"Total graph nodes: {len(updated_graph)}")

new_graph_json = json.dumps(updated_graph, ensure_ascii=False, indent=2)
g_prefix = graph_content[:gm.start(1)]
g_suffix = graph_content[gm.end(1):]
new_graph_content = g_prefix + new_graph_json + g_suffix

with open(graph_path, 'w', encoding='utf-8') as f:
    f.write(new_graph_content)
print("Successfully updated subwayGraph.ts!")
