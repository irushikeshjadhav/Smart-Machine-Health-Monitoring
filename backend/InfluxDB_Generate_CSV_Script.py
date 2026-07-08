import sys
import pandas as pd
from influxdb_client import InfluxDBClient

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = " YOUR INFLUX TOKEN"  # the same one now in bridge.py
INFLUX_ORG = "smart-machine"
INFLUX_BUCKET = "vibration"

def export_range(start, stop, outfile):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start}, stop: {stop})
      |> filter(fn: (r) => r._measurement == "vibration")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> keep(columns: ["_time", "ax", "ay", "az"])
    '''

    result = query_api.query_data_frame(query)
    df = pd.concat(result, ignore_index=True) if isinstance(result, list) else result

    if df is None or len(df) == 0:
        print("No data returned — check the time range and that bridge.py was writing during it.")
        client.close()
        return

    df = df.rename(columns={"_time": "timestamp"})[["timestamp", "ax", "ay", "az"]]
    df.to_csv(outfile, index=False)
    print(f"Saved {len(df)} rows to {outfile}")
    client.close()

if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "-10m"
    stop = sys.argv[2] if len(sys.argv) > 2 else "now()"
    outfile = sys.argv[3] if len(sys.argv) > 3 else "export.csv"
    export_range(start, stop, outfile)