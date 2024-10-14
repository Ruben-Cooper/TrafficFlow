import dash
from dash import html, Output, Input, State, dcc
import dash_leaflet as dl
import requests
import os
import pandas as pd
import dash_bootstrap_components as dbc
from datetime import datetime

# Set up API key
apiKey = '7QIl8HqHstNjUcx5Ljvd5zWr0OAzAJor'  # Replace with your TomTom API key

# Define the starting latitude and longitude
startLat = 37.74862   # Latitude
startLon = -122.4228  # Longitude

# Initialize the Dash app with Bootstrap CSS
external_stylesheets = [dbc.themes.BOOTSTRAP]
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

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

# Define Navbar
navbar = dbc.NavbarSimple(
    brand="San Francisco Historical Traffic Visualisation",
    brand_href="#",
    color="primary",
    dark=True,
    fluid=True,
)

# Define controls
controls = dbc.Card([
    dbc.CardHeader("Simulation Controls"),
    dbc.CardBody([
        html.Div([
            dbc.Label('Select Date:'),
            dcc.DatePickerSingle(
                id='date-picker',
                min_date_allowed=min_date_str,
                max_date_allowed=max_date_str,
                date=min_date_str,
                display_format='YYYY-MM-DD',
                style={'width': '100%'}
            ),
        ]),
        html.Br(),
        html.Div([
            dbc.Label('Simulation Speed:'),
            dbc.RadioItems(
                id='speed-multiplier',
                options=[
                    {'label': '1x', 'value': 1},
                    {'label': '2x', 'value': 2},
                    {'label': '4x', 'value': 4},
                    {'label': '8x', 'value': 8},
                ],
                value=1,
                inline=True
            ),
        ]),
        html.Br(),
        html.Div([
            dbc.Label('Simulation Time:'),
            dcc.Slider(
                id='time-slider',
                min=0,
                max=24*60*60 - 1,
                step=60,
                value=0,
                marks={i*3600: f'{i:02d}:00' for i in range(0, 25, 3)},
                tooltip={'always_visible': False, 'placement': 'bottom'}
            ),
        ]),
        html.Br(),
        dbc.Button('Stop Animation', id='stop-button', n_clicks=0, color='primary', className='mr-1'),
        html.Br(),
        html.Br(),
        html.Div(id='current-time-display'),
    ])
])

# Define the app layout
app.layout = dbc.Container([
    navbar,
    dbc.Row([
        dbc.Col([
            html.Br(),
            controls,
            html.Br(),
            dbc.Card([
                dbc.CardHeader("Map Information"),
                dbc.CardBody([
                    html.P(id='info', children='Click on the map to get traffic data.')
                ])
            ]),
            # Hidden div to store simulation data
            dcc.Store(id='simulation-data', data={
                'current_time': None,
                'last_update_timestamp': None,
                'slider_value': None,
                'selected_date': None
            })
        ], width=3, style={'padding': '20px'}),
        dbc.Col([
            dl.Map(
                id="map",
                center=[startLat, startLon],
                zoom=12,
                style={'width': '100%', 'height': 'calc(100vh - 70px)'},
                children=[
                    dl.TileLayer(id='basemap', url=f"https://api.tomtom.com/map/1/tile/basic/main/{{z}}/{{x}}/{{y}}.png?tileSize=256&key={apiKey}", attribution='&copy; TomTom, &copy; CRAWDAD'),
                    dl.TileLayer(id='traffic', url=f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{{z}}/{{x}}/{{y}}.png?tileSize=256&key={apiKey}", opacity=0.7),
                    dl.LayerGroup(id="layer"),
                    dl.LayerGroup(id="vehicles")
                ],
            ),
            # Interval component for updating vehicle positions
            dcc.Interval(id='interval', interval=1000, n_intervals=0)
        ], width=9, style={'padding': '0px'})
    ], style={'margin': '0px'})
], fluid=True)

# Callback to update vehicle positions
@app.callback(
    [Output('vehicles', 'children'),
     Output('current-time-display', 'children'),
     Output('simulation-data', 'data')],
    [Input('interval', 'n_intervals'),
     Input('speed-multiplier', 'value'),
     Input('date-picker', 'date'),
     Input('stop-button', 'n_clicks'),
     Input('time-slider', 'value')],
    [State('simulation-data', 'data')]
)
def update_vehicles(n_intervals, speed_multiplier, selected_date, n_clicks, time_slider_value, sim_data):
    from datetime import datetime

    # Handle None values for time_slider_value and selected_date
    if time_slider_value is None:
        time_slider_value = 0

    if selected_date is None:
        selected_date = min_date_str  # Default to min_date_str

    if sim_data is None:
        sim_data = {
            'current_time': None,
            'last_update_timestamp': None,
            'slider_value': None,
            'selected_date': None
        }

    # Get current real time
    current_real_time = datetime.now().timestamp()

    last_update_timestamp = sim_data.get('last_update_timestamp', None)
    current_time = sim_data.get('current_time', None)
    prev_slider_value = sim_data.get('slider_value', None)
    prev_selected_date = sim_data.get('selected_date', None)

    # Determine if animation is stopped
    if n_clicks % 2 != 0:
        # Animation is stopped
        if prev_slider_value != time_slider_value or prev_selected_date != selected_date:
            # Slider value or date changed, update current_time
            selected_date_dt = pd.to_datetime(selected_date)
            start_of_day = pd.Timestamp(selected_date_dt).tz_localize(None)
            current_time = start_of_day.timestamp() + time_slider_value
            sim_data['current_time'] = current_time
            sim_data['slider_value'] = time_slider_value
            sim_data['selected_date'] = selected_date
            sim_data['last_update_timestamp'] = current_real_time
        else:
            # Animation is stopped, do not update
            current_time_str = pd.to_datetime(sim_data['current_time'], unit='s').strftime('%Y-%m-%d %H:%M:%S')
            return dash.no_update, f"Current Time: {current_time_str}", sim_data
    else:
        # Animation is running
        if prev_slider_value != time_slider_value or prev_selected_date != selected_date:
            # Slider value or date changed, reset current_time
            selected_date_dt = pd.to_datetime(selected_date)
            start_of_day = pd.Timestamp(selected_date_dt).tz_localize(None)
            current_time = start_of_day.timestamp() + time_slider_value
            last_update_timestamp = current_real_time
        else:
            if last_update_timestamp is None or current_time is None:
                # Initialize current_time
                selected_date_dt = pd.to_datetime(selected_date)
                start_of_day = pd.Timestamp(selected_date_dt).tz_localize(None)
                current_time = start_of_day.timestamp() + time_slider_value
                last_update_timestamp = current_real_time
            else:
                # Compute delta_real_time
                delta_real_time = current_real_time - last_update_timestamp

                # Compute delta_simulation_time
                delta_simulation_time = delta_real_time * speed_multiplier

                # Update current_time
                current_time += delta_simulation_time

    # Update sim_data
    sim_data['current_time'] = current_time
    sim_data['last_update_timestamp'] = current_real_time
    sim_data['slider_value'] = time_slider_value
    sim_data['selected_date'] = selected_date

    # Check if current_time exceeds the max time for the selected day
    selected_date_dt = pd.to_datetime(selected_date)
    start_of_day = pd.Timestamp(selected_date_dt).tz_localize(None)
    end_of_day = start_of_day + pd.Timedelta(days=1)
    end_time = end_of_day.timestamp()

    if current_time > end_time:
        sim_data['current_time'] = end_time  # Ensure it doesn't go beyond
        current_time_str = pd.to_datetime(sim_data['current_time'], unit='s').strftime('%Y-%m-%d %H:%M:%S')
        return dash.no_update, f"Current Time: {current_time_str}", sim_data

    # Update the time slider position if animation is running
    if n_clicks % 2 == 0:
        elapsed_seconds = current_time - start_of_day.timestamp()
        if elapsed_seconds > 24*3600:
            elapsed_seconds = 24*3600 - 1
        # Update the slider value in sim_data
        sim_data['slider_value'] = elapsed_seconds

    # Filter data for the selected day
    selected_date_start = start_of_day.timestamp()
    selected_date_end = end_of_day.timestamp()
    df_current = taxi_data[(taxi_data['time'] >= selected_date_start) & (taxi_data['time'] <= selected_date_end)]

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
            # No next point, use last known position if within threshold
            time_diff = current_time - prev_point['time']
            max_time_diff = 600  # seconds (10 minutes)
            if time_diff > max_time_diff:
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
                'iconAnchor': [12, 12],
                'className': 'car-marker'
            },
            id=f"vehicle_{taxi_id}"
        )
        markers.append(marker)

    current_time_str = pd.to_datetime(sim_data['current_time'], unit='s').strftime('%Y-%m-%d %H:%M:%S')
    return markers, f"Current Time: {current_time_str}", sim_data

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

# Callback to update the time slider when animation is running
@app.callback(
    Output('time-slider', 'value'),
    [Input('simulation-data', 'data')]
)
def update_time_slider(sim_data):
    if sim_data is None:
        return 0
    return sim_data.get('slider_value', 0)

# Define the callback to handle click events
@app.callback(
    [Output('info', 'children'),
     Output('layer', 'children')],
    [Input('map', 'clickData')]
)
def display_click_info(clickData):
    if not clickData:
        return dcc.Markdown('Click on the map to get traffic data.'), []
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

            # Format the response for display using HTML for line breaks
            formatted_response = html.Div([
                html.B("Current Speed:"), f" {currentSpeed} km/h", html.Br(),
                html.B("Free Flow Speed:"), f" {freeFlowSpeed} km/h", html.Br(),
                html.B("Current Travel Time:"), f" {currentTravelTime} seconds", html.Br(),
                html.B("Free Flow Travel Time:"), f" {freeFlowTravelTime} seconds", html.Br(),
                html.B("Confidence:"), f" {confidence}", html.Br(),
                html.B("Road Closure:"), f" {'Yes' if roadClosure else 'No'}"
            ])

            # Add a marker to the map at the clicked location
            marker = dl.Marker(position=[lat, lon], children=[
                dl.Tooltip(f"Lat: {lat:.6f}, Lon: {lon:.6f}"),
                dl.Popup(formatted_response)
            ])

            # Display the response
            info_text = html.Div([
                html.B("Latitude:"), f" {round(lat, 6)} ",html.Br(),
                html.B("Longitude:"), f" {round(lon, 6)}", html.Br(), html.Br(),
                formatted_response
            ])
            
            return info_text, [marker]
        else:
            # Handle API errors
            info_text = html.Div([
                html.B("Latitude:"), f" {round(lat, 6)} ",html.Br(),
                html.B("Longitude:"), f" {round(lon, 6)}", html.Br(), html.Br(),
                "Error fetching traffic data."
            ])
            return info_text, []

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
