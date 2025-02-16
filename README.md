
# 🚗 TrafficFlow: Interactive Web Traffic Visualiser

TrafficFlow is a web application developed to visualise real-time traffic congestion patterns and vehicle movements using TomTom API data. This project includes a data-driven taxi movement visualisation system that combines historical GPS datasets with live traffic data, enabling temporal analysis of urban traffic patterns.

## Features

-   **Real-Time Traffic Visualisation:** Displays live traffic congestion patterns using TomTom API data.
    
-   **Taxi Movement Visualisation:** Combines historical GPS data of taxis with real-time traffic data.
    
-   **Interactive Maps:** Allows users to explore traffic patterns and vehicle movements on a 2D map.
    
-   **Temporal Analysis:** Enables analysis of traffic patterns over time.
    

## Dependencies

Built Using Python and Dash.

Note: Due to the size of the data taxi data must be acquired separately for the San Francisco area it is recommended to import data from: https://ieee-dataport.org/open-access/crawdad-epflmobility 

### Installed using pip install
```
dash==2.1.0
dash-bootstrap-components==1.0.0
dash-core-components==2.0.0
dash-html-components==2.0.0
dash-leaflet==0.1.18
pandas==1.3.3
```

## Usage

1.  Run the application:
    ```
    python app.py
    ```
2.  Open your web browser and navigate to `http://localhost:8050` to view the interactive traffic visualisations.

Note: By default the starting coords are set to the downtown San Francisco area.
