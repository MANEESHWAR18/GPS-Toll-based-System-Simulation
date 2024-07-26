import simpy
import geopandas as gpd
from shapely.geometry import Point, LineString
import pandas as pd
import matplotlib.pyplot as plt
import folium
import webbrowser
import random
from geopy.distance import geodesic

SIMULATION_TIME = 100
SIM_SPEED = 60
AREA_SIZE = 100

toll_gates = gpd.GeoDataFrame({
    'id': [1, 2, 3, 4],
    'geometry': [
        Point(77.5899, 12.9716),
        Point(77.5946, 12.9781),
        Point(77.5800, 12.9750),
        Point(77.5850, 12.9680)
    ],
    'rate_per_km': [5, 7, 6, 8]
})

users = {
    1: {'balance': 6000, 'vehicle_type': 'truck', 'distance': 8.0},
    2: {'balance': 7000, 'vehicle_type': 'car', 'distance': 7.0}
}

def random_point_within_area(area_size):
    x = random.uniform(77.0, 77.0 + area_size / 100.0)
    y = random.uniform(12.0, 12.0 + area_size / 100.0)
    return Point(x, y)

def create_route(start, end, toll_gates):
    points = [start] + list(toll_gates.geometry) + [end]
    return LineString(points)

class Vehicle:
    def __init__(self, env, vehicle_id, start_location, end_location, user_id, distance, non_toll=False):
        self.env = env
        self.vehicle_id = vehicle_id
        self.start_location = start_location
        self.end_location = end_location
        self.route = create_route(self.start_location, self.end_location, toll_gates)
        self.distance_traveled = 0
        self.current_location = start_location
        self.user_id = user_id
        self.distance = distance
        self.vehicle_type = users[user_id]['vehicle_type']
        self.non_toll = non_toll
        self.action = env.process(self.move())

    def move(self):
        while self.distance_traveled < self.distance:
            yield self.env.timeout(1)
            self.distance_traveled += SIM_SPEED / 60
            self.current_location = self.route.interpolate(self.distance_traveled / self.route.length, normalized=True)
            current_toll = self.calculate_toll()
            if not self.non_toll:
                users[self.user_id]['balance'] -= current_toll
                print(f"Vehicle {self.vehicle_id}: Distance Traveled = {self.distance_traveled:.2f} km, Toll = {current_toll:.2f} Rs, User Balance = {users[self.user_id]['balance']:.2f} Rs")
                check_pass(self.vehicle_id)

    def calculate_toll(self):
        total_toll = 0
        if self.non_toll:
            return total_toll
        
        for index, row in toll_gates.iterrows():
            if self.route.intersects(row['geometry'].buffer(0.001)):
                intersected = self.route.intersection(row['geometry'].buffer(0.001))
                if isinstance(intersected, LineString):
                    distance_in_zone = sum(geodesic((p[1], p[0]), (q[1], q[0])).km for p, q in zip(intersected.coords[:-1], intersected.coords[1:]))
                    toll = distance_in_zone * row['rate_per_km']
                    total_toll += toll
                    print(f"Alert: Vehicle {self.vehicle_id} has entered Toll Gate {row['id']}")

        if self.user_id == 1:
            total_toll = 60
        elif self.user_id == 2:
            total_toll = 100

        return total_toll

def check_pass(vehicle_id):
    print(f"Alert: Vehicle {vehicle_id} has passed through a toll gate.")

env = simpy.Environment()

vehicles = [
    Vehicle(env, 1, random_point_within_area(AREA_SIZE), random_point_within_area(AREA_SIZE), 1, users[1]['distance']),
    Vehicle(env, 2, random_point_within_area(AREA_SIZE), random_point_within_area(AREA_SIZE), 2, users[2]['distance'])
]

def run_simulation(env, vehicles):
    while True:
        yield env.timeout(1)
        for vehicle in vehicles:
            if vehicle.distance_traveled >= vehicle.distance:
                continue

env.process(run_simulation(env, vehicles))
env.run(until=SIMULATION_TIME)

m = folium.Map(location=[12.9716, 77.5946], zoom_start=14)

for _, row in toll_gates.iterrows():
    folium.Marker([row['geometry'].y, row['geometry'].x],
                  tooltip=f"Toll Gate {row['id']}").add_to(m)

vehicle_icons = {
    'truck': 'truck',
    'car': 'car'
}

for vehicle in vehicles:
    icon = vehicle_icons.get(vehicle.vehicle_type, 'car')
    folium.Marker([vehicle.start_location.y, vehicle.start_location.x],
                  icon=folium.Icon(color='blue', icon=icon, prefix='fa')).add_to(m)
    folium.Marker([vehicle.end_location.y, vehicle.end_location.x],
                  icon=folium.Icon(color='green', icon=icon, prefix='fa')).add_to(m)
    folium.PolyLine(locations=[(point[1], point[0]) for point in list(vehicle.route.coords)],
                    color='blue', weight=2.5, opacity=1).add_to(m)

m.save('index.html')
webbrowser.open('index.html')

data = {
    'Vehicle ID': [v.vehicle_id for v in vehicles],
    'Distance Traveled': [v.distance_traveled for v in vehicles],
    'Remaining Balance': [users[v.user_id]['balance'] for v in vehicles]
}

df = pd.DataFrame(data)
print(df)

plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.bar(df['Vehicle ID'], df['Distance Traveled'])
plt.xlabel('Vehicle ID')
plt.ylabel('Distance Traveled (km)')
plt.title('Distance Traveled by Vehicles')

plt.subplot(1, 2, 2)
plt.bar(df['Vehicle ID'], df['Remaining Balance'])
plt.xlabel('Vehicle ID')
plt.ylabel('Remaining Balance (Rupees)')
plt.title('Remaining Balance for Users')

plt.tight_layout()
plt.show()
