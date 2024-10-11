import dash
from dash import html, Output, Input
import dash_leaflet as dl
import dash_core_components as dcc  # For intervals
import requests
import osmnx as ox
import networkx as nx
import pandas as pd
import random
import math

# Set up API key
apiKey = '7QIl8HqHstNjUcx5Ljvd5zWr0OAzAJor'  # Replace with your TomTom API key

# Define the starting latitude and longitude (e.g., for San Francisco)
startLat = 37.771    # Latitude of San Francisco
startLon = -122.4240  # Longitude of San Francisco

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
num_vehicles = 10
vehicles = []
for _ in range(num_vehicles):
    route = None
    while route is None:
        route = generate_random_route(G)
    vehicles.append({
        'route': route,
        'position_index': 0,  # Start at the first node
        'speed': random.uniform(5, 15)  # Speed in meters per second
    })

# Function to update vehicle positions
def update_vehicle_positions(vehicles):
    for vehicle in vehicles:
        # Increment position index based on speed
        vehicle['position_index'] += 1
        if vehicle['position_index'] >= len(vehicle['route']):
            vehicle['position_index'] = 0  # Loop back to start
    return vehicles

# Define the app layout
app.layout = html.Div([
    html.H1("Interactive Zoomable Map with Traffic Flow Overlay and Simulated Traffic"),
    html.Div([
        html.Div([
            html.Pre(id='info', children='Click on the map to get traffic data.')
        ], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'top'}),
        html.Div([
            dl.Map(
                id="map",
                center=[startLat, startLon],
                zoom=13,
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
    for vehicle in updated_vehicles:
        # Get current position
        node = vehicle['route'][vehicle['position_index']]
        lat = G.nodes[node]['y']
        lon = G.nodes[node]['x']
        marker = dl.Marker(position=[lat, lon], icon={
            'iconUrl': '/assets/car.png',
            'iconSize': [25, 25],
            'iconAnchor': [10, 10],
        })
        markers.append(marker)
    return markers

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
