import dash
from dash import html, Output, Input, dcc
import dash_leaflet as dl
import requests
import os
import pandas as pd
from datetime import datetime

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

# Ensure 'time' is numeric
taxi_data['time'] = pd.to_numeric(taxi_data['time'], errors='coerce')

# Drop rows with NaN 'time' values
taxi_data = taxi_data.dropna(subset=['time'])

# Convert 'time' to integer
taxi_data['time'] = taxi_data['time'].astype(int)

# Convert 'time' to datetime
taxi_data['datetime'] = pd.to_datetime(taxi_data['time'], unit='s', errors='coerce')

# Drop rows with NaT in 'datetime'
taxi_data = taxi_data.dropna(subset=['datetime'])

# Extract unique dates
unique_dates = taxi_data['datetime'].dt.date.unique()
min_date = min(unique_dates)
max_date = max(unique_dates)

# Convert dates to strings for DatePickerSingle
min_date_str = min_date.isoformat()
max_date_str = max_date.isoformat()

# Define the app layout
app.layout = html.Div([
    html.H1("Interactive Map with Simulated Taxi Traffic"),
    html.Button('Stop Animation', id='stop-button', n_clicks=0),
    html.Div([
        html.Div([
            html.Pre(id='info', children='Click on the map to get traffic data.'),
            html.Div(id='current-time-display'),
            html.Label('Select Date:'),
            dcc.DatePickerSingle(
                id='date-picker',
                min_date_allowed=min_date_str,
                max_date_allowed=max_date_str,
                date=min_date_str,
                display_format='YYYY-MM-DD'
            ),
            html.Label('Simulation Speed:'),
            dcc.RadioItems(
                id='speed-multiplier',
                options=[
                    {'label': '1x', 'value': 1},
                    {'label': '2x', 'value': 2},
                    {'label': '4x', 'value': 4},
                    {'label': '8x', 'value': 8},
                ],
                value=1,  # default to 1x speed
                labelStyle={'display': 'inline-block'}
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
     Input('speed-multiplier', 'value'),
     Input('date-picker', 'date'),
     Input('stop-button', 'n_clicks')]
)
def update_vehicles(n_intervals, speed_multiplier, selected_date, n_clicks):
    # Determine if animation is stopped
    if n_clicks % 2 != 0:
        return dash.no_update, dash.no_update  # Do not update if stopped

    if selected_date is None:
        return dash.no_update, 'No date selected.'

    # Convert selected_date to datetime
    selected_date = pd.to_datetime(selected_date)

    # Get the start timestamp of the selected day
    start_of_day = pd.Timestamp(selected_date).tz_localize(None)
    start_time = int(start_of_day.timestamp())

    # delta_time is 1 second * speed_multiplier
    delta_time = 1 * speed_multiplier

    # current_time is start_time + n_intervals * delta_time
    current_time = start_time + n_intervals * delta_time

    # Check if current_time exceeds the max time for the selected day
    end_of_day = start_of_day + pd.Timedelta(days=1)
    end_time = int(end_of_day.timestamp())

    if current_time > end_time:
        return dash.no_update, 'End of day reached.'

    # Define a time window for active taxis (e.g., taxis that have data within the last 60 seconds)
    time_window = 60  # seconds

    # Filter data for the selected day within the time window
    min_time = current_time - time_window
    df_current = taxi_data[(taxi_data['time'] >= min_time) & (taxi_data['time'] <= current_time + time_window)]

    # Group by taxi_id
    grouped = df_current.groupby('taxi_id')

    markers = []

    for taxi_id, group in grouped:
        # Sort the group by time
        group = group.sort_values('time')

        # Find data points before and after current_time
        prev_points = group[group['time'] <= current_time]
        next_points = group[group['time'] > current_time]

        if not prev_points.empty:
            prev_point = prev_points.iloc[-1]
        else:
            continue  # No previous point, skip this taxi

        if not next_points.empty:
            next_point = next_points.iloc[0]
            # Interpolate position
            t0 = prev_point['time']
            t1 = next_point['time']
            lat0 = prev_point['lat']
            lon0 = prev_point['lon']
            lat1 = next_point['lat']
            lon1 = next_point['lon']

            # Avoid division by zero
            if t1 == t0:
                ratio = 0
            else:
                ratio = (current_time - t0) / (t1 - t0)

            lat = lat0 + (lat1 - lat0) * ratio
            lon = lon0 + (lon1 - lon0) * ratio
        else:
            # No next point, check if the previous point is within the time window
            time_diff = current_time - prev_point['time']
            if time_diff > time_window:
                continue  # Taxi is inactive
            else:
                # Use last known position
                lat = prev_point['lat']
                lon = prev_point['lon']

        # Add marker
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
