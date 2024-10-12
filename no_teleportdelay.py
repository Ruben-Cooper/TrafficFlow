import dash
from dash import html, Output, Input
import dash_leaflet as dl
import dash_core_components as dcc  # For intervals
import requests
import osmnx as ox
import networkx as nx
import pandas as pd
import random
import time
from shapely.geometry import LineString

# Set up API key
apiKey = '7QIl8HqHstNjUcx5Ljvd5zWr0OAzAJor'  # Replace with your TomTom API key

# Define the starting latitude and longitude
startLat = -27.47041   # Latitude
startLon = 153.024754  # Longitude

# Initialize the Dash app
app = dash.Dash(__name__)

# Download the road network data for the area
G = ox.graph_from_point((startLat, startLon), dist=2000, network_type='drive')

# Get nodes and edges
nodes, edges = ox.graph_to_gdfs(G)

# Generate random routes
def generate_random_route(G):
    # Randomly select start and end nodes
    nodes_list = list(G.nodes())
    start_node = random.choice(nodes_list)
    end_node = random.choice(nodes_list)
    # Calculate the shortest path
    try:
        route = nx.shortest_path(G, start_node, end_node, weight='length')
        return route
    except nx.NetworkXNoPath:
        return None

# Generate routes for multiple vehicles
num_vehicles = 100
vehicles = []
for idx in range(num_vehicles):
    route = None
    while route is None or len(route) < 2:
        route = generate_random_route(G)
    # Initialize vehicle data
    u = route[0]
    v = route[1]
    edge_data = G.get_edge_data(u, v)
    if edge_data is None:
        continue  # Skip if no edge between u and v
    edge_data = list(edge_data.values())[0]
    edge_length = edge_data.get('length')
    edge_geometry = edge_data.get('geometry')
    if edge_geometry is None:
        x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
        x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
        edge_geometry = LineString([(x1, y1), (x2, y2)])
    vehicles.append({
        'id': idx,
        'route': route,
        'edge_index': 0,  # Start at the first edge
        'distance_traveled_on_edge': 0.0,
        'edge_length': edge_length,
        'edge_geometry': edge_geometry,
        'speed': 20,  # Speed in meters per second
        'current_position': (G.nodes[u]['y'], G.nodes[u]['x']),
        'loop_count': 0,  # Track route completion
        'hidden_until': 0  # Time when vehicle will reappear
    })

# Function to update vehicle positions
def update_vehicle_positions(vehicles, delta_time=1.0):
    current_time = time.time()
    for vehicle in vehicles:
        if current_time < vehicle['hidden_until']:
            # Skip updating vehicle if it's in the hidden state
            continue

        delta_distance = vehicle['speed'] * delta_time
        vehicle['distance_traveled_on_edge'] += delta_distance
        while vehicle['distance_traveled_on_edge'] >= vehicle['edge_length']:
            vehicle['distance_traveled_on_edge'] -= vehicle['edge_length']
            vehicle['edge_index'] += 1
            if vehicle['edge_index'] >= len(vehicle['route']) - 1:
                vehicle['edge_index'] = 0  # Loop back to start
                vehicle['loop_count'] += 1  # Increment loop_count when looping back
                vehicle['hidden_until'] = current_time + 10  # Hide for 10 seconds
                vehicle['current_position'] = (G.nodes[vehicle['route'][0]]['y'], G.nodes[vehicle['route'][0]]['x'])
                break
            u = vehicle['route'][vehicle['edge_index']]
            v = vehicle['route'][vehicle['edge_index'] + 1]
            edge_data = G.get_edge_data(u, v)
            if edge_data is None:
                continue  # Skip if no edge between u and v
            edge_data = list(edge_data.values())[0]
            vehicle['edge_length'] = edge_data.get('length')
            vehicle['edge_geometry'] = edge_data.get('geometry')
            if vehicle['edge_geometry'] is None:
                x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
                x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
                vehicle['edge_geometry'] = LineString([(x1, y1), (x2, y2)])
        # Progress along edge
        progress = vehicle['distance_traveled_on_edge'] / vehicle['edge_length']
        position = vehicle['edge_geometry'].interpolate(progress, normalized=True)
        vehicle['current_position'] = (position.y, position.x)
    return vehicles

# Define the app layout
app.layout = html.Div([
    html.H1("Interactive Zoomable Map with Traffic Flow Overlay and Simulated Traffic"),
    html.Button('Stop Animation', id='stop-button', n_clicks=0),  # Add the button here
    html.Div([
        html.Div([
            html.Pre(id='info', children='Click on the map to get traffic data.')
        ], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'top'}),
        html.Div([
            dl.Map(
                id="map",
                center=[startLat, startLon],
                zoom=15,
                style={'width': '100%', 'height': '800px'},
                children=[
                    dl.TileLayer(id='basemap', url=f"https://api.tomtom.com/map/1/tile/basic/main/{{z}}/{{x}}/{{y}}.png?tileSize=256&key={apiKey}", attribution='&copy; TomTom'),
                    dl.TileLayer(id='traffic', url=f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{{z}}/{{x}}/{{y}}.png?tileSize=256&key={apiKey}", opacity=0.7),
                    dl.LayerGroup(id="layer"),
                    dl.LayerGroup(id="vehicles")
                ],
            ),
            # Interval component for updating vehicle positions
            dcc.Interval(id='interval', interval=1000, n_intervals=0)
        ], style={'width': '75%', 'display': 'inline-block'})
    ])
])

# Callback to update vehicle positions
@app.callback(
    Output('vehicles', 'children'),
    [Input('interval', 'n_intervals')]
)
def update_vehicles(n):
    # Update vehicle positions
    updated_vehicles = update_vehicle_positions(vehicles)
    markers = []
    current_time = time.time()
    for vehicle in updated_vehicles:
        if current_time < vehicle['hidden_until']:
            # Skip rendering the vehicle if it's in the hidden state
            continue
        lat, lon = vehicle['current_position']
        marker = dl.Marker(
            position=[lat, lon],
            icon={
                'iconUrl': '/assets/car.png',
                'iconSize': [25, 25],
                'iconAnchor': [10, 10],
                'className': 'car-marker'  
            },
            id=f"vehicle_{vehicle['id']}_{vehicle['loop_count']}"  # Set a unique id
        )
        markers.append(marker)
    return markers

# Callback to toggle animation
@app.callback(
    [Output('interval', 'disabled'),
     Output('stop-button', 'children')],
    [Input('stop-button', 'n_clicks')]
)
def toggle_animation(n_clicks):
    if n_clicks is None:
        n_clicks = 0
    if n_clicks % 2 == 0:
        # Animation is running
        return False, 'Stop Animation'
    else:
        # Animation is stopped
        return True, 'Start Animation'

# Define the callback to handle click events
@app.callback(
    [Output('info', 'children'),
     Output('layer', 'children')],
    [Input('map', 'clickData')]
)
def display_click_info(clickData):
    if not clickData:
        return 'Click on the map to get traffic data.', []
    else:
        # Extract latitude and longitude from clickData
        lat = clickData['latlng']['lat']
        lon = clickData['latlng']['lng']

        # Make API call to flow segment data
        api_url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json?point={lat},{lon}&unit=KMPH&openLr=false&key={apiKey}"
        res = requests.get(api_url)

        if res.status_code == 200:
            res_json = res.json()

            trafficData = res_json.get('flowSegmentData', {})

            # Extract the desired fields
            currentSpeed = trafficData.get('currentSpeed')
            freeFlowSpeed = trafficData.get('freeFlowSpeed')
            currentTravelTime = trafficData.get('currentTravelTime')
            freeFlowTravelTime = trafficData.get('freeFlowTravelTime')
            confidence = trafficData.get('confidence')
            roadClosure = trafficData.get('roadClosure')

            # Format the response for display
            formatted_response = f"""Current Speed: {currentSpeed} km/h
Free Flow Speed: {freeFlowSpeed} km/h
Current Travel Time: {currentTravelTime} seconds
Free Flow Travel Time: {freeFlowTravelTime} seconds
Confidence: {confidence}
Road Closure: {'Yes' if roadClosure else 'No'}"""

            # Add a marker to the map at the clicked location
            marker = dl.Marker(position=[lat, lon], children=[
                dl.Tooltip(f"Lat: {lat:.6f}, Lon: {lon:.6f}"),
                dl.Popup(formatted_response)
            ])

            # Display the response
            info_text = f"""Clicked at Latitude: {round(lat, 6)} Longitude: {round(lon, 6)}
Traffic Data:
{formatted_response}"""
            return info_text, [marker]
        else:
            # Handle API errors
            info_text = f"""Clicked at Latitude: {round(lat, 6)} Longitude: {round(lon, 6)}
Error fetching traffic data."""
            return info_text, []

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
