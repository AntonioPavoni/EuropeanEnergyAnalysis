import pandas as pd
import folium
from folium.plugins import MarkerCluster
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RenewablePowerPlantMap:
    def __init__(self):
        # Using country_long names instead of codes
        self.countries = {
            'Spain': 'Spain',
            'France': 'France',
            'Germany': 'Germany',
            'Italy': 'Italy'
        }
        
        self.fuel_colors = {
            'Solar': 'orange',
            'Wind': 'lightblue'
        }

    def load_and_filter_data(self, file_path: str) -> pd.DataFrame:
        """Load and filter the database for renewable plants in selected countries."""
        logger.info(f"Loading data from {file_path}")
        
        # Read the CSV file with low_memory=False to avoid dtype warnings
        df = pd.read_csv(file_path, low_memory=False)
        
        # First, let's see what we have
        logger.info(f"\nUnique countries found: {df['country_long'].unique()}")
        logger.info(f"\nUnique fuel types found: {df['primary_fuel'].unique()}")
        
        # Filter for our countries and renewable sources
        renewable_plants = df[
            (df['country_long'].isin(self.countries.keys())) & 
            (df['primary_fuel'].isin(['Solar', 'Wind'])) &
            (df['latitude'].notna()) &  # Ensure we have coordinates
            (df['longitude'].notna())
        ].copy()
        
        # Add country names (in this case, they're the same)
        renewable_plants['country_name'] = renewable_plants['country_long']
        
        logger.info(f"\nFound {len(renewable_plants)} renewable plants in selected countries")
        # Show distribution
        for country in self.countries.keys():
            country_data = renewable_plants[renewable_plants['country_long'] == country]
            logger.info(f"\n{country}:")
            for fuel_type in ['Solar', 'Wind']:
                count = len(country_data[country_data['primary_fuel'] == fuel_type])
                capacity = country_data[country_data['primary_fuel'] == fuel_type]['capacity_mw'].sum()
                logger.info(f"  {fuel_type}: {count} plants, {capacity:.1f} MW total capacity")
        
        return renewable_plants

    def create_map(self, df: pd.DataFrame, output_path: Path) -> None:
            """Create an interactive map with renewable power plants."""
            # Create base map centered on Europe
            m = folium.Map(
                location=[47, 5],  # Center of Western Europe
                zoom_start=5,
                tiles='OpenStreetMap'
            )

            # Define custom icons
            wind_icon = {
                'prefix': 'fa',
                'icon': 'fan',  # Wind turbine icon
                'color': 'lightblue'
            }
            
            solar_icon = {
                'prefix': 'fa',
                'icon': 'sun',  # Sun icon
                'color': 'orange'
            }

            # Add country-specific clusters
            for country_name in self.countries.keys():
                country_data = df[df['country_long'] == country_name]
                
                if country_data.empty:
                    continue
                    
                # Create separate clusters for solar and wind
                for fuel_type in ['Solar', 'Wind']:
                    fuel_data = country_data[country_data['primary_fuel'] == fuel_type]
                    if fuel_data.empty:
                        continue
                    
                    cluster = MarkerCluster(
                        name=f"{country_name} {fuel_type} ({len(fuel_data)} plants)",
                        overlay=True,
                        control=True
                    )

                    # Add markers for each plant
                    for _, plant in fuel_data.iterrows():
                        # Create popup content
                        popup_content = f"""
                        <b>{plant['name']}</b><br>
                        Country: {plant['country_name']}<br>
                        Type: {plant['primary_fuel']}<br>
                        Capacity: {plant['capacity_mw']:.1f} MW<br>
                        Commission Year: {int(plant['commissioning_year']) if pd.notna(plant['commissioning_year']) else 'Unknown'}<br>
                        """

                        # Choose icon based on fuel type
                        icon_dict = wind_icon if plant['primary_fuel'] == 'Wind' else solar_icon
                        
                        # Create marker with icon
                        folium.Marker(
                            location=[plant['latitude'], plant['longitude']],
                            popup=popup_content,
                            icon=folium.Icon(**icon_dict),
                        ).add_to(cluster)

                    cluster.add_to(m)

            # Add layer control
            folium.LayerControl().add_to(m)

            # Add legend
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; right: 50px; width: 150px; height: 90px; 
                        border:2px solid grey; z-index:9999; 
                        background-color:white;
                        padding: 10px;
                        font-size: 14px;
                        ">
            <p><i class="fa fa-fan fa-lg" style="color:lightblue"></i> Wind Plant</p>
            <p><i class="fa fa-sun fa-lg" style="color:orange"></i> Solar Plant</p>
            </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))

            # Save the map
            output_file = output_path / "renewable_plants_map.html"
            m.save(str(output_file))
            logger.info(f"Map saved to {output_file}")
    

def main():
    """Main execution function."""
    try:
        # Use your specific file location
        db_file = r"C:\Users\Antonio\ENTSOE\global_power_plant_database.csv"
        
        # Setup output path
        output_path = Path(r"C:\Users\Antonio\ENTSOE")
        output_path.mkdir(exist_ok=True)

        # Initialize map creator and process data
        map_creator = RenewablePowerPlantMap()
        renewable_plants = map_creator.load_and_filter_data(db_file)
        map_creator.create_map(renewable_plants, output_path)
        
        logger.info("Process completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()