import dash
from dash import html, Output, Input, dcc
import dash_leaflet as dl
import requests
import os
import osmnx as ox
import pandas as pd
import math
from shapely.geometry import LineString
import pandas as pd

# Set up API key
apiKey = '7QIl8HqHstNjUcx5Ljvd5zWr0OAzAJor'  # Replace with your TomTom API key

# Define the starting latitude and longitude
startLat = 37.74862   # Latitude
startLon = -122.4228  # Longitude

# Initialize the Dash app
app = dash.Dash(__name__)

# Read taxi data
data_folder = 'data'
all_taxi_data = []

for filename in os.listdir(data_folder):
    if filename.endswith('.txt'):
        taxi_id = os.path.splitext(filename)[0]
        filepath = os.path.join(data_folder, filename)
        df = pd.read_csv(filepath, sep=' ', header=None, names=['lat', 'lon', 'occupancy', 'time'])
        df['taxi_id'] = taxi_id
        all_taxi_data.append(df)

# Combine all data
taxi_data = pd.concat(all_taxi_data, ignore_index=True)
taxi_data.sort_values(by='time', inplace=True)
taxi_data['datetime'] = pd.to_datetime(taxi_data['time'], unit='s')

# Get start and end times
start_time = taxi_data['time'].min()
end_time = taxi_data['time'].max()
delta_time = 60  # seconds per interval

# Map UNIX timestamps to formatted date strings for slider marks
def generate_slider_marks(start, end, step):
    marks = {}
    for t in range(int(start), int(end)+1, step):
        readable_time = pd.to_datetime(t, unit='s').strftime('%Y-%m-%d %H:%M')
        marks[t] = readable_time
    return marks

# Define the app layout
app.layout = html.Div([
    html.H1("Interactive Zoomable Map with Traffic Flow Overlay and Simulated Traffic"),
    html.Button('Stop Animation', id='stop-button', n_clicks=0),
    html.Div([
        html.Div([
            html.Pre(id='info', children='Click on the map to get traffic data.'),
            html.Div(id='current-time-display'),
            html.Label('Select Time:'),
            dcc.Slider(
                id='time-slider',
                min=start_time,
                max=end_time,
                value=start_time,
                marks=generate_slider_marks(start_time, end_time, step=3600*6),  # Every 6 hours
                step=delta_time
            ),
            html.Label('Simulation Speed (seconds per interval):'),
            dcc.Slider(
                id='delta-time-slider',
                min=10,
                max=600,
                step=10,
                value=60,
                marks={i: str(i) for i in range(10, 601, 50)}
            )
        ], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'top'}),
        html.Div([
            dl.Map(
                id="map",
                center=[startLat, startLon],
                zoom=12,
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
    [Output('vehicles', 'children'),
     Output('current-time-display', 'children')],
    [Input('interval', 'n_intervals'),
     Input('delta-time-slider', 'value'),
     Input('time-slider', 'value'),
     Input('stop-button', 'n_clicks')]
)
def update_vehicles(n_intervals, delta_time, slider_time, n_clicks):
    # Determine if animation is stopped
    if n_clicks % 2 != 0:
        return dash.no_update, dash.no_update  # Do not update if stopped

    current_time = slider_time + n_intervals * delta_time
    if current_time > end_time:
        current_time = start_time  # Loop back to start
    # Filter data up to current time
    df_current = taxi_data[taxi_data['time'] <= current_time]
    # Get latest position for each taxi
    latest_positions = df_current.groupby('taxi_id').last().reset_index()
    markers = []
    for idx, row in latest_positions.iterrows():
        lat = row['lat']
        lon = row['lon']
        taxi_id = row['taxi_id']
        marker = dl.Marker(
            position=[lat, lon],
            icon={
                'iconUrl': '/assets/car.png',
                'iconSize': [25, 25],
                'iconAnchor': [10, 10],
                'className': 'car-marker'  
            },
            id=f"vehicle_{taxi_id}"
        )
        markers.append(marker)
    current_time_str = pd.to_datetime(current_time, unit='s').strftime('%Y-%m-%d %H:%M:%S')
    return markers, f"Current Time: {current_time_str}"

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
