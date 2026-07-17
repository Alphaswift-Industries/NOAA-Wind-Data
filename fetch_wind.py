import requests
import time
import os
import json
import datetime
import xarray as xr

# 1. Calculate the latest available NOAA Cycle
# We subtract 4 hours from the current UTC time because NOAA takes ~4 hours to publish
now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
cycle_hour = (now.hour // 6) * 6
date_str = now.strftime("%Y%m%d")
cycle_str = f"{cycle_hour:02d}"

print(f"Targeting GFS Cycle: {date_str} t{cycle_str}z")

# Create output directory
output_dir = "public_data"
os.makedirs(output_dir, exist_ok=True)

# 2. Loop through the next 24 hourly predictions
for forecast_hour in range(25):
    f_str = f"{forecast_hour:03d}"
    grib_filename = f"temp_f{f_str}.grib2"
    json_filename = f"{output_dir}/wind_{f_str}.json"
    
    print(f"Fetching hour {f_str}...")

    # The exact NOMADS grib_filter URL for U/V winds at 10m above ground
    url = (
        f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?"
        f"file=gfs.t{cycle_str}z.pgrb2.0p25.f{f_str}&"
        f"lev_10_m_above_ground=on&"
        f"var_UGRD=on&"
        f"var_VGRD=on&"
        f"dir=%2Fgfs.{date_str}%2F{cycle_str}%2Fatmos"
    )

    # Download with a safety sleep to prevent NOAA IP bans
    response = requests.get(url)
    if response.status_code == 200:
        with open(grib_filename, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to fetch {f_str}. HTTP {response.status_code}")
        continue
        
    time.sleep(1) # CRITICAL: Respect NOAA's 120 hits/min limit

    # 3. Parse the GRIB file and convert to cesium-wind JSON format
    try:
        # Load GRIB via xarray + cfgrib backend
        ds = xr.open_dataset(grib_filename, engine='cfgrib')
        
        # Flatten arrays and round to 2 decimals to save file size
        u_data = ds['u10'].values.flatten().round(2).tolist()
        v_data = ds['v10'].values.flatten().round(2).tolist()
        
        # Build the exact array structure cesium-wind expects
        wind_json = [
            {
                "header": {
                    "parameterCategory": 2, "parameterNumber": 2, # U-Component
                    "dx": 0.25, "dy": 0.25, 
                    "la1": 90.0, "la2": -90.0, 
                    "lo1": 0.0, "lo2": 359.75, 
                    "nx": 1440, "ny": 721,
                    "refTime": f"{date_str} {cycle_str}:00:00",
                    "forecastTime": forecast_hour
                },
                "data": u_data
            },
            {
                "header": {
                    "parameterCategory": 2, "parameterNumber": 3, # V-Component
                    "dx": 0.25, "dy": 0.25, 
                    "la1": 90.0, "la2": -90.0, 
                    "lo1": 0.0, "lo2": 359.75, 
                    "nx": 1440, "ny": 721,
                    "refTime": f"{date_str} {cycle_str}:00:00",
                    "forecastTime": forecast_hour
                },
                "data": v_data
            }
        ]
        
        with open(json_filename, 'w') as f:
            json.dump(wind_json, f)
            
        # Clean up the temp file
        ds.close()
        os.remove(grib_filename)
        
    except Exception as e:
        print(f"Error parsing hour {f_str}: {e}")

print("Complete! Data ready for Git push.")