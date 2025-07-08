import influxdb_client
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class TimeSeriesManager:
    def __init__(self):
        self.client = InfluxDBClient(
            url="http://localhost:8086",
            token="JZm7xcbBi7_Lbyg4cBWdnlCuOSFblf727-m2jHZ0kPoS3bTSXsjwL3VGol1kFf2NeVj2QhpQMOVEElCPBpEI7A==",
            org="RIF"
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def log_buffer_state(self, buffer_id, fill_level, timestamp):
        point = Point("buffer_metrics") \
            .tag("buffer_id", buffer_id) \
            .field("fill_level", fill_level) \
            .time(timestamp)
        self.write_api.write(bucket="simulation", record=point)

    def get_buffer_stats(self, buffer_id, start_time):
        query = f'''
        from(bucket:"simulation")
            |> range(start: {start_time})
            |> filter(fn: (r) => r["_measurement"] == "buffer_metrics")
            |> filter(fn: (r) => r["buffer_id"] == "{buffer_id}")
            |> aggregateWindow(every: 1s, fn: mean)
        '''
        result = self.query_api.query(query)
        # Process results
        return avg, variability